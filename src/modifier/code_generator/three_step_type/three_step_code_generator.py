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
from pathlib import Path
from typing import Any, Dict, Tuple

from config.config_manager import Configuration, ThreeStepConfig
from models.modification_context import ModificationContext
from models.table_access_info import TableAccessInfo
from modifier.llm.llm_factory import create_llm_provider
from modifier.llm.llm_provider import LLMProvider

from ..multi_step_base import BaseMultiStepCodeGenerator

logger = logging.getLogger("applycrypto")


class ThreeStepCodeGenerator(BaseMultiStepCodeGenerator):
    """3단계 LLM 협업 Code 생성기 (VO Extraction + Planning + Execution)"""

    def __init__(self, config: Configuration):
        """
        ThreeStepCodeGenerator 초기화

        Args:
            config: 설정 객체 (three_step_config 필수)

        Raises:
            ValueError: three_step_config가 설정되지 않은 경우
        """
        # 부모 클래스 초기화 (토큰 인코더 등)
        super().__init__(config)

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
        self.data_mapping_template_path = template_dir / "data_mapping_template.md"
        self.planning_template_path = template_dir / "planning_template.md"


        if self.config.generate_type == "full_source":
            execution_template_name = "execution_template_full.md"
        elif self.config.generate_type == "diff":
            execution_template_name = "execution_template_diff.md"
        else:
            raise NotImplementedError(
                f"Unsupported generate_type for ThreeStepCodeGenerator: {self.config.generate_type}"
            )

        self.execution_template_path = template_dir / execution_template_name

        for template_path in [
            self.data_mapping_template_path,
            self.planning_template_path,
            self.execution_template_path,
        ]:
            if not template_path.exists():
                raise FileNotFoundError(
                    f"\n{'='*60}\n"
                    f" [오류] 템플릿 파일을 찾을 수 없습니다\n"
                    f"{'='*60}\n\n"
                    f"찾으려는 파일:\n"
                    f"  {template_path.name}\n\n"
                    f"예상 경로:\n"
                    f"  {template_path}\n\n"
                    f"💡 해결 방법:\n"
                    f"  모든 템플릿은 'src/templates' 디렉토리 구조 내에 정의되어야 합니다.\n"
                    f"  '{template_path.parent}' 디렉토리 아래에\n"
                    f"  '{template_path.name}' 파일을 생성하거나 복사해주세요.\n\n"
                    f"  파일을 위치시킨 후 다시 실행해 주세요.\n"
                    f"{'='*60}"
                )

        # BaseContextGenerator.create_batches()에서 토큰 계산을 위해 사용하는 속성
        self.template_path = self.planning_template_path

        # 출력 디렉토리 초기화 (부모 클래스 메서드 사용)
        self._init_output_directory()

    # ========== 추상 메서드 구현 ==========

    def _get_output_subdir_name(self) -> str:
        """출력 디렉토리 하위 폴더명 반환"""
        return "three_step_results"

    def _get_step_config(self) -> ThreeStepConfig:
        """ThreeStepConfig 반환"""
        return self.three_step_config

    def _get_execution_provider(self) -> LLMProvider:
        """Execution LLM provider 반환"""
        return self.execution_provider

    def _get_execution_template_path(self) -> Path:
        """Execution 템플릿 경로 반환"""
        return self.execution_template_path

    def _get_step_name(self) -> str:
        """Step 이름 반환 (로깅용)"""
        return "3-Step"

    def _get_execution_step_number(self) -> int:
        """Execution phase의 단계 번호 반환"""
        return 3

    def _get_last_planning_step_number(self) -> int:
        """마지막 Planning 단계의 번호 반환 (ThreeStep은 Step 2)"""
        return 2

    def _get_last_planning_phase_name(self) -> str:
        """마지막 Planning 단계의 이름 반환"""
        return "planning"

    def _get_planning_reasons(self, planning_result: Dict[str, Any]) -> Dict[str, str]:
        """Planning 결과에서 파일명 -> reason 매핑 추출"""
        planning_reasons = {}
        for instr in planning_result.get("modification_instructions", []):
            file_name = instr.get("file_name", "")
            reason = instr.get("reason", "")
            if file_name:
                planning_reasons[file_name] = reason
        return planning_reasons

    def _execute_planning_phases(
        self,
        session_dir: Path,
        modification_context: ModificationContext,
        table_access_info: TableAccessInfo,
    ) -> Tuple[Dict[str, Any], int]:
        """
        Planning phases를 실행합니다.

        ThreeStep은 Phase 1 (Data Mapping) + Phase 2 (Planning)를 실행합니다.

        Args:
            session_dir: 세션 디렉토리 경로
            modification_context: 수정 컨텍스트
            table_access_info: 테이블 접근 정보

        Returns:
            Tuple[Dict[str, Any], int]: (planning_result, total_tokens_used)
        """
        total_tokens = 0

        # ===== Phase 1: Data Mapping Extraction =====
        mapping_info, phase1_tokens = self._execute_data_mapping_phase(
            session_dir, modification_context, table_access_info
        )
        total_tokens += phase1_tokens

        # ===== Phase 2: Planning =====
        planning_result, phase2_tokens = self._execute_planning_phase(
            session_dir, modification_context, table_access_info, mapping_info
        )
        total_tokens += phase2_tokens

        return planning_result, total_tokens

    # ========== ThreeStep 고유 메서드: Phase 1 (Data Mapping Extraction) ==========

    def _create_data_mapping_prompt(
        self,
        modification_context: ModificationContext,
        table_access_info: TableAccessInfo,
    ) -> str:
        """Phase 1 (Data Mapping Extraction) 프롬프트를 생성합니다."""
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

        template_str = self._load_template(self.data_mapping_template_path)
        return self._render_template(template_str, variables)

    def _execute_data_mapping_phase(
        self,
        session_dir: Path,
        modification_context: ModificationContext,
        table_access_info: TableAccessInfo,
    ) -> Tuple[Dict[str, Any], int]:
        """Step 1 (Query Analysis): VO 파일과 SQL 쿼리에서 데이터 매핑 정보를 추출합니다."""
        logger.info("-" * 40)
        logger.info("[Step 1] Query Analysis 시작...")
        logger.info(f"VO 파일 수: {len(modification_context.context_files or [])}")

        # 프롬프트 생성
        prompt = self._create_data_mapping_prompt(
            modification_context, table_access_info
        )
        logger.debug(f"Query Analysis 프롬프트 길이: {len(prompt)} chars")

        # 프롬프트 저장 (LLM 호출 직전)
        self._save_prompt_to_file(prompt, modification_context, "data_mapping")

        # LLM 호출
        response = self.analysis_provider.call(prompt)
        tokens_used = response.get("tokens_used", 0)
        logger.info(f"Query Analysis 응답 완료 (토큰: {tokens_used})")

        # 응답 파싱 (부모 클래스의 범용 메서드 사용)
        mapping_info = self._parse_json_response(response, "Query Analysis")

        # 결과 저장
        self._save_phase_result(
            session_dir=session_dir,
            modification_context=modification_context,
            step_number=1,
            phase_name="query_analysis",
            result=mapping_info,
            tokens_used=tokens_used,
        )

        return mapping_info, tokens_used

    # ========== ThreeStep 고유 메서드: Phase 2 (Planning) ==========

    def _create_planning_prompt(
        self,
        modification_context: ModificationContext,
        table_access_info: TableAccessInfo,
        mapping_info: Dict[str, Any],
    ) -> str:
        """Phase 2 (Planning) 프롬프트를 생성합니다.

        Note: SQL 쿼리와 데이터 매핑 정보는 Phase 1의 mapping_info에 포함되어 있습니다.
        """
        # 테이블/칼럼 정보
        table_info = {
            "table_name": modification_context.table_name,
            "columns": modification_context.columns,
        }
        table_info_str = json.dumps(table_info, indent=2, ensure_ascii=False)

        # 소스 파일 내용
        add_line_num: bool = self.config and self.config.generate_type != 'full_source'
        source_files_str = self._read_file_contents(
            modification_context.file_paths,
            add_line_num=add_line_num
        )

        # mapping_info (Phase 1 결과)를 JSON 문자열로 변환
        mapping_info_str = json.dumps(mapping_info, indent=2, ensure_ascii=False)

        # Call Stacks 정보 (각 call chain 별로 data flow 분석 수행)
        call_stacks_str = self._get_callstacks_from_table_access_info(
            modification_context.file_paths, table_access_info
        )

        variables = {
            "table_info": table_info_str,
            "source_files": source_files_str,
            "mapping_info": mapping_info_str,
            "call_stacks": call_stacks_str,
        }

        template_str = self._load_template(self.planning_template_path)
        return self._render_template(template_str, variables)

    def _execute_planning_phase(
        self,
        session_dir: Path,
        modification_context: ModificationContext,
        table_access_info: TableAccessInfo,
        mapping_info: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], int]:
        """Step 2 (Planning): mapping_info를 기반으로 Data Flow를 분석하고 수정 지침을 생성합니다."""
        logger.info("-" * 40)
        logger.info("[Step 2] Planning 시작...")
        logger.info(f"소스 파일 수: {len(modification_context.file_paths)}")

        # 프롬프트 생성
        prompt = self._create_planning_prompt(
            modification_context, table_access_info, mapping_info
        )
        logger.debug(f"Planning 프롬프트 길이: {len(prompt)} chars")

        # 프롬프트 저장 (LLM 호출 직전)
        self._save_prompt_to_file(prompt, modification_context, "planning")

        # LLM 호출
        response = self.analysis_provider.call(prompt)
        tokens_used = response.get("tokens_used", 0)
        logger.info(f"Planning 응답 완료 (토큰: {tokens_used})")

        # 응답 파싱 (부모 클래스의 범용 메서드 사용)
        modification_instructions = self._parse_json_response(response, "Planning")

        # 결과 저장
        self._save_phase_result(
            session_dir=session_dir,
            modification_context=modification_context,
            step_number=2,
            phase_name="planning",
            result=modification_instructions,
            tokens_used=tokens_used,
        )

        # 요약 로깅
        instruction_count = len(
            modification_instructions.get("modification_instructions", [])
        )
        logger.info(f"생성된 수정 지침 수: {instruction_count}")

        return modification_instructions, tokens_used
