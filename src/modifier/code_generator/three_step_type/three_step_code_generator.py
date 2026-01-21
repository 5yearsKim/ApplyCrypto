"""
Three-Step Code Generator

3단계 LLM 협업 전략 (VO Extraction + Planning + Execution)을 사용하는 CodeGenerator입니다.

- Phase 1 (VO Extraction): VO 파일과 SQL 쿼리에서 필드 매핑 정보를 추출합니다.
- Phase 2 (Planning): vo_info를 기반으로 Data Flow를 분석하고 수정 지침을 생성합니다.
- Phase 3 (Execution): 수정 지침에 따라 실제 코드를 작성합니다.

Phase 1, 2는 분석 능력이 뛰어난 모델 (예: GPT-OSS-120B)이 수행하고,
Phase 3는 코드 생성 안정성이 높은 모델 (예: Codestral-2508)이 수행합니다.
"""

import json
import logging
import re
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import tiktoken
from jinja2 import Template

from config.config_manager import Configuration, ThreeStepConfig
from models.code_generator import CodeGeneratorInput, CodeGeneratorOutput
from models.modification_context import ModificationContext
from models.modification_plan import ModificationPlan
from models.table_access_info import TableAccessInfo
from modifier.llm.llm_factory import create_llm_provider
from modifier.llm.llm_provider import LLMProvider

from ..base_code_generator import BaseCodeGenerator

logger = logging.getLogger("applycrypto")


# 토큰 계산을 위한 기본 템플릿 (BaseContextGenerator.create_batches()에서 사용)
_TOKEN_CALCULATION_TEMPLATE = """
## Table Info
{{ table_info }}

## Source Files
{{ source_files }}

## Layer: {{ layer_name }}
"""


class ThreeStepCodeGenerator(BaseCodeGenerator):
    """3단계 LLM 협업 Code 생성기"""

    def __init__(self, config: Configuration):
        """
        ThreeStepCodeGenerator 초기화

        Args:
            config: 설정 객체 (three_step_config 필수)

        Raises:
            ValueError: three_step_config가 설정되지 않은 경우
        """
        self.config = config

        # ThreeStepConfig 검증
        if not config.three_step_config:
            raise ValueError(
                "modification_type이 'ThreeStep'일 때는 three_step_config가 필수입니다."
            )

        self.three_step_config: ThreeStepConfig = config.three_step_config

        # LLM Provider 초기화
        # Phase 1, 2: 분석용 (analysis_provider)
        logger.info(
            f"Analysis LLM 초기화: {self.three_step_config.analysis_provider} "
            f"(model: {self.three_step_config.analysis_model})"
        )
        self.analysis_provider: LLMProvider = create_llm_provider(
            provider_name=self.three_step_config.analysis_provider,
            model_id=self.three_step_config.analysis_model,
        )

        # Phase 3: 코드 생성용 (execution_provider)
        logger.info(
            f"Execution LLM 초기화: {self.three_step_config.execution_provider} "
            f"(model: {self.three_step_config.execution_model})"
        )
        self.execution_provider: LLMProvider = create_llm_provider(
            provider_name=self.three_step_config.execution_provider,
            model_id=self.three_step_config.execution_model,
        )

        # 템플릿 로드
        template_dir = Path(__file__).parent
        self.vo_extraction_template_path = template_dir / "vo_extraction_template.md"
        self.planning_template_path = template_dir / "planning_template.md"
        self.execution_template_path = template_dir / "execution_template.md"

        for template_path in [
            self.vo_extraction_template_path,
            self.planning_template_path,
            self.execution_template_path,
        ]:
            if not template_path.exists():
                raise FileNotFoundError(f"템플릿을 찾을 수 없습니다: {template_path}")

        # 캐시 초기화
        self._prompt_cache: Dict[str, Any] = {}

        # BaseContextGenerator.create_batches()에서 토큰 계산을 위해 사용하는 속성
        self.template_path = self.planning_template_path

        # 토큰 인코더 초기화
        try:
            self.token_encoder = tiktoken.encoding_for_model("gpt-4")
        except Exception:
            logger.warning(
                "tiktoken을 사용할 수 없습니다. 간단한 토큰 추정을 사용합니다."
            )
            self.token_encoder = None

        # 중간 결과 저장 디렉토리 설정
        self.output_dir = (
            Path(config.target_project) / ".applycrypto" / "three_step_instructions"
        )
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ========== 유틸리티 메서드 ==========

    def _load_template(self, template_path: Path) -> str:
        """템플릿 파일을 로드합니다."""
        with open(template_path, "r", encoding="utf-8") as f:
            return f.read()

    def _render_template(self, template_str: str, variables: Dict[str, Any]) -> str:
        """Jinja2 템플릿을 렌더링합니다."""
        template = Template(template_str)
        return template.render(**variables)

    def _read_file_contents(self, file_paths: List[str]) -> str:
        """파일들의 내용을 읽어서 문자열로 반환합니다."""
        snippets = []
        for file_path in file_paths:
            try:
                path_obj = Path(file_path)
                if path_obj.exists():
                    with open(path_obj, "r", encoding="utf-8") as f:
                        content = f.read()
                    snippets.append(f"=== File: {path_obj.name} ===\n{content}")
                else:
                    logger.warning(f"File not found: {file_path}")
            except Exception as e:
                logger.error(f"Failed to read file: {file_path} - {e}")
        return "\n\n".join(snippets)

    def _read_file_contents_indexed(
        self, file_paths: List[str]
    ) -> Tuple[str, Dict[int, str], Dict[str, str]]:
        """
        파일들의 내용을 인덱스와 함께 읽어서 반환합니다.

        Returns:
            Tuple[str, Dict[int, str], Dict[str, str]]:
                - 인덱스가 포함된 파일 내용 문자열
                - 인덱스 -> 파일 경로 매핑
                - 파일 경로 -> 파일 내용 매핑
        """
        snippets = []
        index_to_path: Dict[int, str] = {}
        path_to_content: Dict[str, str] = {}

        for idx, file_path in enumerate(file_paths, start=1):
            try:
                path_obj = Path(file_path)
                if path_obj.exists():
                    with open(path_obj, "r", encoding="utf-8") as f:
                        content = f.read()
                    snippets.append(
                        f"[FILE_{idx}] {path_obj.name}\n"
                        f"=== Content ===\n{content}"
                    )
                    index_to_path[idx] = file_path
                    path_to_content[file_path] = content
                else:
                    logger.warning(f"File not found: {file_path}")
            except Exception as e:
                logger.error(f"Failed to read file: {file_path} - {e}")

        return "\n\n".join(snippets), index_to_path, path_to_content

    def _extract_code_signature(self, code: str) -> Tuple[Optional[str], Optional[str]]:
        """Java 코드에서 패키지명과 클래스명을 추출합니다."""
        package_name = None
        class_name = None

        package_match = re.search(r'package\s+([\w.]+)\s*;', code)
        if package_match:
            package_name = package_match.group(1)

        class_match = re.search(
            r'(?:public\s+)?(?:abstract\s+)?(?:class|interface|enum)\s+(\w+)',
            code
        )
        if class_match:
            class_name = class_match.group(1)

        return package_name, class_name

    def _match_by_code_signature(
        self, modified_code: str, path_to_content: Dict[str, str]
    ) -> Optional[str]:
        """수정된 코드의 시그니처로 원본 파일을 찾습니다."""
        mod_package, mod_class = self._extract_code_signature(modified_code)

        if not mod_class:
            return None

        for file_path, original_content in path_to_content.items():
            orig_package, orig_class = self._extract_code_signature(original_content)

            if orig_class == mod_class:
                if mod_package == orig_package:
                    logger.info(
                        f"코드 시그니처 매칭 성공: {mod_package}.{mod_class} -> {file_path}"
                    )
                    return file_path
                elif mod_package is None or orig_package is None:
                    logger.info(
                        f"코드 시그니처 매칭 (클래스명만): {mod_class} -> {file_path}"
                    )
                    return file_path

        return None

    def _fuzzy_match_filename(
        self, llm_filename: str, file_mapping: Dict[str, str]
    ) -> Optional[str]:
        """Fuzzy matching으로 유사한 파일명을 찾습니다."""
        best_match = None
        best_ratio = 0.0
        threshold = 0.7

        llm_filename_lower = llm_filename.lower()

        for filename, filepath in file_mapping.items():
            ratio = SequenceMatcher(
                None, llm_filename_lower, filename.lower()
            ).ratio()
            if ratio > best_ratio and ratio >= threshold:
                best_ratio = ratio
                best_match = filepath

        if best_match:
            logger.info(
                f"Fuzzy 매칭 성공: {llm_filename} -> {Path(best_match).name} "
                f"(유사도: {best_ratio:.1%})"
            )

        return best_match

    def _resolve_file_path(
        self,
        llm_file_identifier: str,
        modified_code: str,
        index_to_path: Dict[int, str],
        file_mapping: Dict[str, str],
        path_to_content: Dict[str, str],
    ) -> Tuple[Optional[str], str]:
        """여러 전략을 순차적으로 시도하여 파일 경로를 해결합니다."""
        # 1. 인덱스 매칭
        index_match = re.match(r'FILE_(\d+)', llm_file_identifier.strip(), re.IGNORECASE)
        if index_match:
            idx = int(index_match.group(1))
            if idx in index_to_path:
                return index_to_path[idx], "index"

        # 2. 정확한 파일명 매칭
        clean_name = llm_file_identifier.strip()
        if '/' in clean_name or '\\' in clean_name:
            clean_name = Path(clean_name).name

        if clean_name in file_mapping:
            return file_mapping[clean_name], "exact"

        # 3. 대소문자 무시 매칭
        lower_mapping = {k.lower(): v for k, v in file_mapping.items()}
        if clean_name.lower() in lower_mapping:
            return lower_mapping[clean_name.lower()], "case_insensitive"

        # 4. 코드 시그니처 매칭
        if modified_code and modified_code.strip():
            signature_match = self._match_by_code_signature(modified_code, path_to_content)
            if signature_match:
                return signature_match, "signature"

        # 5. Fuzzy 매칭
        fuzzy_match = self._fuzzy_match_filename(clean_name, file_mapping)
        if fuzzy_match:
            return fuzzy_match, "fuzzy"

        logger.warning(f"파일 경로 해결 실패: {llm_file_identifier}")
        return None, "failed"

    def _extract_section(self, content: str, start_marker: str, end_marker: str) -> str:
        """콘텐츠에서 두 마커 사이의 섹션을 추출합니다."""
        start_idx = content.find(start_marker)
        if start_idx == -1:
            return ""

        start_idx += len(start_marker)
        end_idx = content.find(end_marker, start_idx)

        if end_idx == -1:
            return content[start_idx:].strip()

        return content[start_idx:end_idx].strip()

    def _parse_json_response(self, response: Dict[str, Any], phase_name: str) -> Dict[str, Any]:
        """LLM 응답에서 JSON을 파싱합니다."""
        content = response.get("content", "")
        if not content:
            raise ValueError(f"{phase_name} LLM 응답에 content가 없습니다.")

        content = content.strip()

        # ```json ... ``` 형식 처리
        if "```json" in content:
            start_idx = content.find("```json") + len("```json")
            end_idx = content.find("```", start_idx)
            if end_idx != -1:
                content = content[start_idx:end_idx].strip()
        elif "```" in content:
            start_idx = content.find("```") + len("```")
            end_idx = content.find("```", start_idx)
            if end_idx != -1:
                content = content[start_idx:end_idx].strip()

        try:
            result = json.loads(content)
            logger.info(f"{phase_name} 응답 파싱 성공")
            return result
        except json.JSONDecodeError as e:
            logger.error(f"{phase_name} 응답 JSON 파싱 실패: {e}")
            logger.debug(f"원본 응답:\n{content[:500]}...")
            raise ValueError(f"{phase_name} 응답 JSON 파싱 실패: {e}")

    # NOTE: _get_sql_queries_for_prompt와 _get_callstacks_from_table_access_info는
    # BaseCodeGenerator에서 상속받아 사용합니다.

    # ========== 결과 저장 메서드 ==========

    def _save_phase_result(
        self,
        modification_context: ModificationContext,
        phase_name: str,
        result: Dict[str, Any],
        tokens_used: int,
    ) -> Path:
        """각 Phase의 결과를 JSON 파일로 저장합니다."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        table_name = modification_context.table_name

        # 테이블별 디렉토리 생성
        table_dir = self.output_dir / table_name / timestamp
        table_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{phase_name}_result.json"
        output_path = table_dir / filename

        save_data = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "phase": phase_name,
                "table_name": table_name,
                "layer": modification_context.layer,
                "tokens_used": tokens_used,
            },
            "result": result,
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(save_data, f, indent=2, ensure_ascii=False)

        logger.info(f"{phase_name} 결과 저장됨: {output_path}")
        return output_path

    # ========== Phase 1: VO Extraction ==========

    def _create_vo_extraction_prompt(
        self,
        modification_context: ModificationContext,
        table_access_info: TableAccessInfo,
    ) -> str:
        """Phase 1 (VO Extraction) 프롬프트를 생성합니다."""
        # 테이블/칼럼 정보 (★ 타겟 테이블 명시)
        table_info = {
            "table_name": modification_context.table_name,
            "columns": modification_context.columns,
        }
        table_info_str = json.dumps(table_info, indent=2, ensure_ascii=False)

        # VO 파일 내용 (context_files)
        vo_files_str = self._read_file_contents(
            modification_context.context_files or []
        )

        # SQL 쿼리 정보
        sql_queries_str = self._get_sql_queries_for_prompt(
            table_access_info, modification_context.file_paths
        )

        variables = {
            "table_info": table_info_str,
            "vo_files": vo_files_str,
            "sql_queries": sql_queries_str,
        }

        template_str = self._load_template(self.vo_extraction_template_path)
        return self._render_template(template_str, variables)

    def _execute_vo_extraction_phase(
        self,
        modification_context: ModificationContext,
        table_access_info: TableAccessInfo,
    ) -> Tuple[Dict[str, Any], int]:
        """Phase 1: VO 파일과 SQL 쿼리에서 필드 매핑 정보를 추출합니다."""
        logger.info("-" * 40)
        logger.info("[Phase 1] VO Extraction 시작...")
        logger.info(f"VO 파일 수: {len(modification_context.context_files or [])}")

        # 프롬프트 생성
        prompt = self._create_vo_extraction_prompt(modification_context, table_access_info)
        logger.debug(f"VO Extraction 프롬프트 길이: {len(prompt)} chars")

        # LLM 호출
        response = self.analysis_provider.call(prompt)
        tokens_used = response.get("tokens_used", 0)
        logger.info(f"VO Extraction 응답 완료 (토큰: {tokens_used})")

        # 응답 파싱
        vo_info = self._parse_json_response(response, "VO Extraction")

        # 결과 저장
        self._save_phase_result(modification_context, "vo_extraction", vo_info, tokens_used)

        # 요약 로깅
        vo_summary = vo_info.get("vo_summary", {})
        logger.info(
            f"VO 분석 결과: {vo_summary.get('total_vo_count', 0)}개 VO, "
            f"{vo_summary.get('encryption_target_fields_count', 0)}개 암호화 대상 필드"
        )

        return vo_info, tokens_used

    # ========== Phase 2: Planning ==========

    def _create_planning_prompt(
        self,
        modification_context: ModificationContext,
        table_access_info: TableAccessInfo,
        vo_info: Dict[str, Any],
    ) -> str:
        """Phase 2 (Planning) 프롬프트를 생성합니다.

        Note: SQL 쿼리 정보는 Phase 1의 vo_info에 이미 요약되어 있으므로
        별도로 전달하지 않습니다. vo_info의 sql_column_usage를 활용합니다.
        """
        # 테이블/칼럼 정보
        table_info = {
            "table_name": modification_context.table_name,
            "columns": modification_context.columns,
        }
        table_info_str = json.dumps(table_info, indent=2, ensure_ascii=False)

        # 소스 파일 내용
        source_files_str = self._read_file_contents(modification_context.file_paths)

        # vo_info (Phase 1 결과)를 JSON 문자열로 변환
        # ★ vo_info에는 vo_mappings와 sql_column_usage가 포함되어 있어
        #    Phase 2에서 필요한 모든 VO/SQL 관련 정보를 담고 있음
        vo_info_str = json.dumps(vo_info, indent=2, ensure_ascii=False)

        # Call Stacks 정보 (각 call chain 별로 data flow 분석 수행)
        call_stacks_str = self._get_callstacks_from_table_access_info(
            modification_context.file_paths, table_access_info
        )

        variables = {
            "table_info": table_info_str,
            "source_files": source_files_str,
            "vo_info": vo_info_str,
            "call_stacks": call_stacks_str,
            "layer_name": modification_context.layer,
            "file_count": len(modification_context.file_paths),
        }

        template_str = self._load_template(self.planning_template_path)
        return self._render_template(template_str, variables)

    def _execute_planning_phase(
        self,
        modification_context: ModificationContext,
        table_access_info: TableAccessInfo,
        vo_info: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], int]:
        """Phase 2: vo_info를 기반으로 Data Flow를 분석하고 수정 지침을 생성합니다."""
        logger.info("-" * 40)
        logger.info("[Phase 2] Planning 시작...")
        logger.info(f"소스 파일 수: {len(modification_context.file_paths)}")

        # 프롬프트 생성
        prompt = self._create_planning_prompt(
            modification_context, table_access_info, vo_info
        )
        logger.debug(f"Planning 프롬프트 길이: {len(prompt)} chars")

        # LLM 호출
        response = self.analysis_provider.call(prompt)
        tokens_used = response.get("tokens_used", 0)
        logger.info(f"Planning 응답 완료 (토큰: {tokens_used})")

        # 응답 파싱
        modification_instructions = self._parse_json_response(response, "Planning")

        # 결과 저장
        self._save_phase_result(
            modification_context, "planning", modification_instructions, tokens_used
        )

        # 요약 로깅
        instruction_count = len(
            modification_instructions.get("modification_instructions", [])
        )
        logger.info(f"생성된 수정 지침 수: {instruction_count}")

        return modification_instructions, tokens_used

    # ========== Phase 3: Execution ==========

    def _create_execution_prompt(
        self,
        modification_context: ModificationContext,
        planning_result: Dict[str, Any],
    ) -> Tuple[str, Dict[int, str], Dict[str, str], Dict[str, str]]:
        """Phase 3 (Execution) 프롬프트를 생성합니다.

        Note: planning_result에서 modification_instructions만 추출하여 전달합니다.
        data_flow_analysis는 Planning 단계의 추론 과정이며, Executor에게는 불필요합니다.
        """
        # 소스 파일 내용 (인덱스 형식)
        source_files_str, index_to_path, path_to_content = (
            self._read_file_contents_indexed(modification_context.file_paths)
        )

        # 파일명 -> 파일 경로 매핑 생성
        file_mapping = {Path(fp).name: fp for fp in modification_context.file_paths}

        # ★ modification_instructions만 추출 (data_flow_analysis 제외)
        # Phase 3는 "수행"만 하므로 구체적인 수정 지침만 필요
        modification_instructions = planning_result.get("modification_instructions", [])
        instructions_str = json.dumps(
            modification_instructions, indent=2, ensure_ascii=False
        )

        variables = {
            "source_files": source_files_str,
            "modification_instructions": instructions_str,
            "layer_name": modification_context.layer,
            "file_count": len(modification_context.file_paths),
        }

        template_str = self._load_template(self.execution_template_path)
        prompt = self._render_template(template_str, variables)

        return prompt, index_to_path, file_mapping, path_to_content

    def _parse_execution_response(
        self,
        response: Dict[str, Any],
        index_to_path: Dict[int, str],
        file_mapping: Dict[str, str],
        path_to_content: Dict[str, str],
    ) -> List[Dict[str, Any]]:
        """Phase 3 (Execution) LLM 응답을 파싱합니다."""
        content = response.get("content", "")
        if not content:
            raise ValueError("Execution LLM 응답에 content가 없습니다.")

        modifications = []
        content = content.strip()

        # ======END====== 기준으로 블록 분리
        blocks = content.split("======END======")

        # 매칭 통계
        match_stats = {
            "index": 0, "exact": 0, "case_insensitive": 0,
            "signature": 0, "fuzzy": 0, "failed": 0
        }

        for block in blocks:
            block = block.strip()
            if not block:
                continue

            # FILE 마커 찾기
            file_marker_match = re.search(r'======FILE(?:_(\d+))?======', block)
            if not file_marker_match:
                continue

            try:
                # 파일 식별자 추출
                if file_marker_match.group(1):
                    file_identifier = f"FILE_{file_marker_match.group(1)}"
                else:
                    file_identifier = self._extract_section(
                        block, "======FILE======", "======MODIFIED_CODE======"
                    ).strip()

                # MODIFIED_CODE 섹션 추출
                modified_code = self._extract_section(
                    block, "======MODIFIED_CODE======", "======END======"
                ).strip()

                # 복합 전략으로 파일 경로 해결
                resolved_path, match_method = self._resolve_file_path(
                    llm_file_identifier=file_identifier,
                    modified_code=modified_code,
                    index_to_path=index_to_path,
                    file_mapping=file_mapping,
                    path_to_content=path_to_content,
                )

                match_stats[match_method] += 1

                if resolved_path:
                    modifications.append({
                        "file_path": resolved_path,
                        "modified_code": modified_code,
                        "match_method": match_method,
                    })
                else:
                    logger.error(
                        f"파일 경로 해결 실패: {file_identifier}. "
                        f"이 파일의 수정 사항은 건너뜁니다."
                    )

            except Exception as e:
                logger.warning(f"Execution 블록 파싱 중 오류 (건너뜀): {e}")
                continue

        # 매칭 통계 로깅
        logger.info(
            f"파일 매칭 통계: 인덱스={match_stats['index']}, "
            f"정확={match_stats['exact']}, 대소문자무시={match_stats['case_insensitive']}, "
            f"시그니처={match_stats['signature']}, Fuzzy={match_stats['fuzzy']}, "
            f"실패={match_stats['failed']}"
        )

        if not modifications:
            raise Exception(
                "Execution 응답 파싱 실패: 유효한 수정 블록을 찾을 수 없습니다."
            )

        logger.info(f"{len(modifications)}개 파일 수정 정보를 파싱했습니다.")
        return modifications

    def _execute_execution_phase(
        self,
        modification_context: ModificationContext,
        planning_result: Dict[str, Any],
    ) -> Tuple[List[Dict[str, Any]], Dict[int, str], int]:
        """Phase 3: 수정 지침에 따라 실제 코드를 생성합니다.

        Args:
            planning_result: Phase 2의 전체 결과 (data_flow_analysis + modification_instructions)
                            내부에서 modification_instructions만 추출하여 사용합니다.
        """
        logger.info("-" * 40)
        logger.info("[Phase 3] Execution 시작...")
        logger.info(f"Provider: {self.three_step_config.execution_provider}")
        logger.info(f"Model: {self.three_step_config.execution_model}")

        # 프롬프트 생성 (내부에서 modification_instructions만 추출)
        prompt, index_to_path, file_mapping, path_to_content = (
            self._create_execution_prompt(modification_context, planning_result)
        )
        logger.debug(f"Execution 프롬프트 길이: {len(prompt)} chars")

        # LLM 호출
        response = self.execution_provider.call(prompt)
        tokens_used = response.get("tokens_used", 0)
        logger.info(f"Execution 응답 완료 (토큰: {tokens_used})")

        # 응답 파싱
        parsed_modifications = self._parse_execution_response(
            response=response,
            index_to_path=index_to_path,
            file_mapping=file_mapping,
            path_to_content=path_to_content,
        )

        return parsed_modifications, index_to_path, tokens_used

    # ========== 메인 인터페이스 ==========

    def create_prompt(self, input_data: CodeGeneratorInput) -> str:
        """토큰 계산을 위한 프롬프트를 생성합니다."""
        source_files_str = self._read_file_contents(input_data.file_paths)

        variables = {
            "table_info": input_data.table_info,
            "source_files": source_files_str,
            "layer_name": input_data.layer_name,
        }

        return self._render_template(_TOKEN_CALCULATION_TEMPLATE, variables)

    def calculate_token_size(self, text: str) -> int:
        """텍스트의 토큰 크기를 계산합니다."""
        if self.token_encoder:
            return len(self.token_encoder.encode(text))
        else:
            # 간단한 추정: 문자 4개당 1토큰
            return len(text) // 4

    def generate(self, input_data: CodeGeneratorInput) -> CodeGeneratorOutput:
        """BaseCodeGenerator 인터페이스 준수를 위한 메서드."""
        raise NotImplementedError(
            "ThreeStepCodeGenerator는 generate() 대신 "
            "generate_modification_plan()을 사용하세요."
        )

    def generate_modification_plan(
        self,
        modification_context: ModificationContext,
        table_access_info: Optional[TableAccessInfo] = None,
    ) -> List[ModificationPlan]:
        """
        3단계 LLM 협업을 통해 수정 계획을 생성합니다.

        Phase 1 (VO Extraction): VO 파일 + SQL 쿼리 → vo_info JSON
        Phase 2 (Planning): vo_info + 소스코드 + call chain → modification_instructions
        Phase 3 (Execution): modification_instructions + 소스코드 → 수정된 코드

        Args:
            modification_context: 수정 컨텍스트
            table_access_info: 테이블 접근 정보 (필수)

        Returns:
            List[ModificationPlan]: 수정 계획 리스트
        """
        if not modification_context.file_paths:
            return []

        if not table_access_info:
            raise ValueError("ThreeStepCodeGenerator는 table_access_info가 필수입니다.")

        plans = []
        layer_name = modification_context.layer
        total_tokens_used = 0

        logger.info("=" * 60)
        logger.info("3-Step Code Generation 시작")
        logger.info(f"테이블: {modification_context.table_name}")
        logger.info(f"레이어: {layer_name}")
        logger.info(f"소스 파일 수: {len(modification_context.file_paths)}")
        logger.info(f"VO 파일 수: {len(modification_context.context_files or [])}")
        for fp in modification_context.file_paths:
            logger.info(f"  - {fp}")
        logger.info("=" * 60)

        try:
            # ===== Phase 1: VO Extraction =====
            vo_info, phase1_tokens = self._execute_vo_extraction_phase(
                modification_context, table_access_info
            )
            total_tokens_used += phase1_tokens

            # ===== Phase 2: Planning =====
            planning_result, phase2_tokens = self._execute_planning_phase(
                modification_context, table_access_info, vo_info
            )
            total_tokens_used += phase2_tokens

            # ===== Phase 3: Execution =====
            # planning_result 전체를 전달하지만, 내부에서 modification_instructions만 추출하여 사용
            parsed_modifications, index_to_path, phase3_tokens = (
                self._execute_execution_phase(
                    modification_context, planning_result
                )
            )
            total_tokens_used += phase3_tokens

            # Planning 지침에서 파일명 -> reason 매핑 생성
            planning_reasons = {}
            for instr in planning_result.get("modification_instructions", []):
                file_name = instr.get("file_name", "")
                reason = instr.get("reason", "")
                if file_name:
                    planning_reasons[file_name] = reason

            # 각 수정 사항에 대해 계획 생성
            for mod in parsed_modifications:
                file_path_str = mod.get("file_path", "")
                modified_code = mod.get("modified_code", "")

                # reason은 Planning 지침에서 가져옴
                file_name = Path(file_path_str).name
                reason = planning_reasons.get(file_name, "")

                file_path = Path(file_path_str)
                if not file_path.is_absolute():
                    file_path = Path(self.config.target_project) / file_path

                file_path = file_path.resolve()

                plan = ModificationPlan(
                    file_path=str(file_path),
                    layer_name=layer_name,
                    modification_type="encryption",
                    modified_code=modified_code,
                    reason=reason,
                    tokens_used=total_tokens_used,
                    status="pending",
                )

                if not modified_code or modified_code.strip() == "":
                    logger.info(f"파일 수정 건너뜀: {file_path} (이유: {reason})")
                    plan.status = "skipped"

                plans.append(plan)

            logger.info("=" * 60)
            logger.info("3-Step Code Generation 완료")
            logger.info(f"총 토큰 사용량: {total_tokens_used}")
            logger.info(f"  - Phase 1 (VO Extraction): {phase1_tokens}")
            logger.info(f"  - Phase 2 (Planning): {phase2_tokens}")
            logger.info(f"  - Phase 3 (Execution): {phase3_tokens}")
            logger.info(f"생성된 계획 수: {len(plans)}")
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"3-Step Code Generation 실패: {e}")
            # 모든 파일에 대해 실패 계획 기록
            for file_path in modification_context.file_paths:
                plans.append(
                    ModificationPlan(
                        file_path=file_path,
                        layer_name=layer_name,
                        modification_type="encryption",
                        modified_code="",
                        reason=f"3-Step 생성 실패: {str(e)}",
                        tokens_used=total_tokens_used,
                        status="failed",
                    )
                )

        return plans
