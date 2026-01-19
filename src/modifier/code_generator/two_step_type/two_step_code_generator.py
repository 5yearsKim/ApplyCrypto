"""
Two-Step Code Generator

2단계 LLM 협업 전략 (Planning + Execution)을 사용하는 CodeGenerator입니다.

- Step 1 (Planning): 논리적 분석 능력이 뛰어난 모델 (예: GPT-OSS-120B)이
  Data Flow를 분석하고 구체적인 수정 지침을 생성합니다.
- Step 2 (Execution): 코드 생성 안정성이 높은 모델 (예: Codestral-2508)이
  수정 지침에 따라 실제 코드를 작성합니다.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import tiktoken
from jinja2 import Template

from config.config_manager import Configuration, TwoStepConfig
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


class TwoStepCodeGenerator(BaseCodeGenerator):
    """2단계 LLM 협업 Code 생성기"""

    def __init__(self, config: Configuration):
        """
        TwoStepCodeGenerator 초기화

        Args:
            config: 설정 객체 (two_step_config 필수)

        Raises:
            ValueError: two_step_config가 설정되지 않은 경우
        """
        self.config = config

        # TwoStepConfig 검증
        if not config.two_step_config:
            raise ValueError(
                "modification_type이 'TwoStep'일 때는 two_step_config가 필수입니다."
            )

        self.two_step_config: TwoStepConfig = config.two_step_config

        # 두 개의 LLM Provider 초기화
        logger.info(
            f"Planning LLM 초기화: {self.two_step_config.planning_provider} "
            f"(model: {self.two_step_config.planning_model})"
        )
        self.planning_provider: LLMProvider = create_llm_provider(
            provider_name=self.two_step_config.planning_provider,
            model_id=self.two_step_config.planning_model,
        )

        logger.info(
            f"Execution LLM 초기화: {self.two_step_config.execution_provider} "
            f"(model: {self.two_step_config.execution_model})"
        )
        self.execution_provider: LLMProvider = create_llm_provider(
            provider_name=self.two_step_config.execution_provider,
            model_id=self.two_step_config.execution_model,
        )

        # 템플릿 로드
        template_dir = Path(__file__).parent
        self.planning_template_path = template_dir / "planning_template.md"
        self.execution_template_path = template_dir / "execution_template.md"

        if not self.planning_template_path.exists():
            raise FileNotFoundError(
                f"Planning 템플릿을 찾을 수 없습니다: {self.planning_template_path}"
            )
        if not self.execution_template_path.exists():
            raise FileNotFoundError(
                f"Execution 템플릿을 찾을 수 없습니다: {self.execution_template_path}"
            )

        # 캐시 초기화
        self._prompt_cache: Dict[str, Any] = {}

        # BaseContextGenerator.create_batches()에서 토큰 계산을 위해 사용하는 속성
        # TwoStepCodeGenerator는 두 개의 템플릿을 사용하므로 planning 템플릿을 기본으로 사용
        self.template_path = self.planning_template_path

        # 토큰 인코더 초기화 (BaseCodeGenerator와 동일)
        try:
            self.token_encoder = tiktoken.encoding_for_model("gpt-4")
        except Exception:
            logger.warning(
                "tiktoken을 사용할 수 없습니다. 간단한 토큰 추정을 사용합니다."
            )
            self.token_encoder = None

        # Planning 결과 저장 디렉토리 설정
        self.planning_output_dir = (
            Path(config.target_project) / ".applycrypto" / "planning_instructions"
        )
        self.planning_output_dir.mkdir(parents=True, exist_ok=True)

    def _save_planning_instructions(
        self,
        modification_context: ModificationContext,
        instructions: Dict[str, Any],
        tokens_used: int,
    ) -> Path:
        """
        Planning 단계에서 생성된 수정 지침을 JSON 파일로 저장합니다.

        Args:
            modification_context: 수정 컨텍스트
            instructions: Planning LLM이 생성한 수정 지침
            tokens_used: 사용된 토큰 수

        Returns:
            Path: 저장된 파일 경로
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        table_name = modification_context.table_name
        layer = modification_context.layer

        # 수정 대상 파일명 추출
        file_names = [Path(fp).stem for fp in modification_context.file_paths]
        if len(file_names) == 1:
            files_part = file_names[0]
        elif len(file_names) > 1:
            # 여러 파일인 경우: 첫 번째 파일명 + "_외{n-1}개"
            files_part = f"{file_names[0]}_외{len(file_names) - 1}개"
        else:
            files_part = "unknown"

        # 파일명 생성: {files_part}_{table}_{timestamp}.json
        filename = f"{files_part}_{table_name}_{timestamp}.json"
        output_path = self.planning_output_dir / filename

        # 저장할 데이터 구성
        save_data = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "table_name": table_name,
                "layer": layer,
                "file_count": len(modification_context.file_paths),
                "tokens_used": tokens_used,
                "planning_provider": self.two_step_config.planning_provider,
                "planning_model": self.two_step_config.planning_model,
            },
            "input_files": modification_context.file_paths,
            "context_files": modification_context.context_files or [],
            "planning_instructions": instructions,
        }

        # JSON 파일로 저장
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(save_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Planning 지침 저장됨: {output_path}")
        return output_path

    def create_prompt(self, input_data: CodeGeneratorInput) -> str:
        """
        토큰 계산을 위한 프롬프트를 생성합니다.

        Note: 이 메서드는 BaseContextGenerator.create_batches()에서
        토큰 크기 계산 목적으로만 사용됩니다.
        실제 LLM 호출 시에는 _create_planning_prompt()와
        _create_execution_prompt()를 사용합니다.

        Args:
            input_data: Code 생성 입력

        Returns:
            str: 토큰 계산용 프롬프트
        """
        # 소스 파일 내용 읽기
        source_files_str = self._read_file_contents(input_data.file_paths)

        # 간단한 템플릿으로 토큰 계산
        variables = {
            "table_info": input_data.table_info,
            "source_files": source_files_str,
            "layer_name": input_data.layer_name,
        }

        return self._render_template(_TOKEN_CALCULATION_TEMPLATE, variables)

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

    def _create_planning_prompt(
        self,
        modification_context: ModificationContext,
        table_access_info: TableAccessInfo,
    ) -> str:
        """
        Step 1 (Planning) 프롬프트를 생성합니다.

        Args:
            modification_context: 수정 컨텍스트
            table_access_info: 테이블 접근 정보

        Returns:
            str: Planning 프롬프트
        """
        # 테이블/칼럼 정보
        table_info = {
            "table_name": modification_context.table_name,
            "columns": modification_context.columns,
        }
        table_info_str = json.dumps(table_info, indent=2, ensure_ascii=False)

        # 소스 파일 내용
        source_files_str = self._read_file_contents(modification_context.file_paths)

        # 컨텍스트 파일 (VO) 내용
        context_files_str = self._read_file_contents(
            modification_context.context_files or []
        )

        # SQL 쿼리 정보 (핵심 Data Flow 정보)
        sql_queries_str = self._get_sql_queries_for_prompt(
            table_access_info, modification_context.file_paths
        )

        # Call Stacks 정보
        call_stacks_str = self._get_callstacks_from_table_access_info(
            modification_context.file_paths, table_access_info
        )

        # 템플릿 변수 준비
        variables = {
            "table_info": table_info_str,
            "source_files": source_files_str,
            "context_files": context_files_str,
            "sql_queries": sql_queries_str,
            "call_stacks": call_stacks_str,
            "layer_name": modification_context.layer,
            "file_count": len(modification_context.file_paths),
        }

        # 템플릿 렌더링
        template_str = self._load_template(self.planning_template_path)
        return self._render_template(template_str, variables)

    def _create_execution_prompt(
        self,
        modification_context: ModificationContext,
        modification_instructions: Dict[str, Any],
    ) -> str:
        """
        Step 2 (Execution) 프롬프트를 생성합니다.

        Args:
            modification_context: 수정 컨텍스트
            modification_instructions: Step 1에서 생성된 수정 지침

        Returns:
            str: Execution 프롬프트
        """
        # 소스 파일 내용
        source_files_str = self._read_file_contents(modification_context.file_paths)

        # 컨텍스트 파일 (VO) 내용
        context_files_str = self._read_file_contents(
            modification_context.context_files or []
        )

        # 수정 지침을 JSON 문자열로 변환
        instructions_str = json.dumps(
            modification_instructions, indent=2, ensure_ascii=False
        )

        # 템플릿 변수 준비
        variables = {
            "source_files": source_files_str,
            "context_files": context_files_str,
            "modification_instructions": instructions_str,
            "layer_name": modification_context.layer,
            "file_count": len(modification_context.file_paths),
        }

        # 템플릿 렌더링
        template_str = self._load_template(self.execution_template_path)
        return self._render_template(template_str, variables)

    def _parse_planning_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Step 1 (Planning) LLM 응답을 파싱합니다.

        Args:
            response: LLM 응답

        Returns:
            Dict[str, Any]: 파싱된 수정 지침

        Raises:
            ValueError: 파싱 실패 시
        """
        content = response.get("content", "")
        if not content:
            raise ValueError("Planning LLM 응답에 content가 없습니다.")

        # JSON 블록 추출 시도
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
            instructions = json.loads(content)
            logger.info("Planning 응답 파싱 성공")
            return instructions
        except json.JSONDecodeError as e:
            logger.error(f"Planning 응답 JSON 파싱 실패: {e}")
            logger.debug(f"원본 응답:\n{content[:500]}...")
            raise ValueError(f"Planning 응답 JSON 파싱 실패: {e}")

    def _parse_execution_response(
        self, response: Dict[str, Any], file_paths: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Step 2 (Execution) LLM 응답을 파싱합니다.

        TwoStep 전용: REASON 섹션 없이 FILE → MODIFIED_CODE → END 형식을 파싱합니다.
        reason은 Planning 단계에서 생성되었으므로 Execution에서는 생성하지 않습니다.

        형식:
            ======FILE======
            EmployeeService.java
            ======MODIFIED_CODE======
            package com.example;
            ...
            ======END======

        Args:
            response: LLM 응답
            file_paths: 원본 파일 경로 리스트

        Returns:
            List[Dict[str, Any]]: 파싱된 수정 정보 리스트
        """
        content = response.get("content", "")
        if not content:
            raise ValueError("Execution LLM 응답에 content가 없습니다.")

        # 파일명 -> 절대 경로 매핑 생성
        file_mapping = {Path(fp).name: fp for fp in file_paths}

        modifications = []
        content = content.strip()

        # ======END====== 기준으로 블록 분리
        blocks = content.split("======END======")

        for block in blocks:
            block = block.strip()
            if not block or "======FILE======" not in block:
                continue

            try:
                # FILE과 MODIFIED_CODE 섹션 추출 (REASON 없음)
                file_name = self._extract_section(
                    block, "======FILE======", "======MODIFIED_CODE======"
                )
                modified_code = self._extract_section(
                    block, "======MODIFIED_CODE======", "======END======"
                )

                # 파일명 정리
                file_name = file_name.strip()

                # 파일명을 절대 경로로 변환
                if file_name in file_mapping:
                    file_path = file_mapping[file_name]
                else:
                    # 매핑에 없으면 파일명 그대로 사용 (절대 경로일 수도 있음)
                    file_path = file_name
                    logger.warning(
                        f"파일 매핑에서 찾을 수 없음: {file_name}. 원본 값 사용."
                    )

                modifications.append(
                    {
                        "file_path": file_path,
                        "modified_code": modified_code.strip(),
                    }
                )

            except Exception as e:
                logger.warning(f"Execution 블록 파싱 중 오류 (건너뜀): {e}")
                continue

        if not modifications:
            raise Exception(
                "Execution 응답 파싱 실패: 유효한 수정 블록을 찾을 수 없습니다."
            )

        logger.info(
            f"{len(modifications)}개 파일 수정 정보를 파싱했습니다 (TwoStep Execution 형식)."
        )
        return modifications

    def _extract_section(self, content: str, start_marker: str, end_marker: str) -> str:
        """
        콘텐츠에서 두 마커 사이의 섹션을 추출합니다.

        Args:
            content: 전체 콘텐츠
            start_marker: 시작 마커
            end_marker: 종료 마커

        Returns:
            str: 추출된 섹션 (마커 제외)
        """
        start_idx = content.find(start_marker)
        if start_idx == -1:
            return ""

        start_idx += len(start_marker)
        end_idx = content.find(end_marker, start_idx)

        if end_idx == -1:
            # 종료 마커가 없으면 끝까지 추출
            return content[start_idx:].strip()

        return content[start_idx:end_idx].strip()

    def generate(self, input_data: CodeGeneratorInput) -> CodeGeneratorOutput:
        """
        2-Step 방식으로 코드를 생성합니다.

        Note: 이 메서드는 BaseCodeGenerator 인터페이스 준수를 위해 구현되었으나,
        실제 사용은 generate_modification_plan()을 통해 이루어집니다.

        Args:
            input_data: Code 생성 입력

        Returns:
            CodeGeneratorOutput: 생성 결과
        """
        # generate_modification_plan() 사용을 권장
        raise NotImplementedError(
            "TwoStepCodeGenerator는 generate() 대신 "
            "generate_modification_plan()을 사용하세요."
        )

    def generate_modification_plan(
        self,
        modification_context: ModificationContext,
        table_access_info: Optional[TableAccessInfo] = None,
    ) -> List[ModificationPlan]:
        """
        2단계 LLM 협업을 통해 수정 계획을 생성합니다.

        Step 1 (Planning): GPT-OSS-120B가 Data Flow를 분석하고 수정 지침 생성
        Step 2 (Execution): Codestral-2508이 지침에 따라 코드 작성

        Args:
            modification_context: 수정 컨텍스트
            table_access_info: 테이블 접근 정보 (필수)

        Returns:
            List[ModificationPlan]: 수정 계획 리스트
        """
        if not modification_context.file_paths:
            return []

        if not table_access_info:
            raise ValueError("TwoStepCodeGenerator는 table_access_info가 필수입니다.")

        plans = []
        layer_name = modification_context.layer
        total_tokens_used = 0

        logger.info("=" * 60)
        logger.info("2-Step Code Generation 시작")
        logger.info(f"테이블: {modification_context.table_name}")
        logger.info(f"레이어: {layer_name}")
        logger.info(f"파일 수: {len(modification_context.file_paths)}")
        for fp in modification_context.file_paths:
            logger.info(f"  - {fp}")
        logger.info("=" * 60)

        try:
            # ===== Step 1: Planning (GPT-OSS-120B) =====
            logger.info("-" * 40)
            logger.info("[Step 1] Planning LLM 호출 중...")
            logger.info(f"Provider: {self.two_step_config.planning_provider}")
            logger.info(f"Model: {self.two_step_config.planning_model}")

            planning_prompt = self._create_planning_prompt(
                modification_context, table_access_info
            )
            logger.debug(f"Planning 프롬프트 길이: {len(planning_prompt)} chars")

            planning_response = self.planning_provider.call(planning_prompt)
            planning_tokens = planning_response.get("tokens_used", 0)
            total_tokens_used += planning_tokens
            logger.info(f"Planning LLM 응답 완료 (토큰: {planning_tokens})")

            # Planning 응답 파싱
            modification_instructions = self._parse_planning_response(planning_response)

            # Planning 결과 저장
            saved_path = self._save_planning_instructions(
                modification_context, modification_instructions, planning_tokens
            )

            # Planning 결과 로깅
            if "data_flow_analysis" in modification_instructions:
                analysis = modification_instructions["data_flow_analysis"]
                logger.info(f"Data Flow 분석 결과: {analysis.get('summary', 'N/A')}")

            instruction_count = len(
                modification_instructions.get("modification_instructions", [])
            )
            logger.info(f"생성된 수정 지침 수: {instruction_count}")
            logger.info(f"Planning 지침 파일: {saved_path}")

            # ===== Step 2: Execution (Codestral-2508) =====
            logger.info("-" * 40)
            logger.info("[Step 2] Execution LLM 호출 중...")
            logger.info(f"Provider: {self.two_step_config.execution_provider}")
            logger.info(f"Model: {self.two_step_config.execution_model}")

            execution_prompt = self._create_execution_prompt(
                modification_context, modification_instructions
            )
            logger.debug(f"Execution 프롬프트 길이: {len(execution_prompt)} chars")

            execution_response = self.execution_provider.call(execution_prompt)
            execution_tokens = execution_response.get("tokens_used", 0)
            total_tokens_used += execution_tokens
            logger.info(f"Execution LLM 응답 완료 (토큰: {execution_tokens})")

            # Execution 응답 파싱
            parsed_modifications = self._parse_execution_response(
                execution_response, modification_context.file_paths
            )

            # Planning 지침에서 파일명 -> reason 매핑 생성
            # (reason은 Step 1에서 생성되고, Step 2에서는 생성하지 않음)
            planning_reasons = {}
            for instr in modification_instructions.get("modification_instructions", []):
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
            logger.info(f"2-Step Code Generation 완료")
            logger.info(f"총 토큰 사용량: {total_tokens_used}")
            logger.info(f"생성된 계획 수: {len(plans)}")
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"2-Step Code Generation 실패: {e}")
            # 모든 파일에 대해 실패 계획 기록
            for file_path in modification_context.file_paths:
                plans.append(
                    ModificationPlan(
                        file_path=file_path,
                        layer_name=layer_name,
                        modification_type="encryption",
                        status="failed",
                        error=str(e),
                        tokens_used=total_tokens_used,
                    )
                )

        return plans
