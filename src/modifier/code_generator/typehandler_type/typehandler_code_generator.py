import logging
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union

from config.config_manager import Configuration
from models.modification_context import ModificationContext
from models.table_access_info import TableAccessInfo
from ..three_step_type.three_step_code_generator import ThreeStepCodeGenerator

logger = logging.getLogger("applycrypto")


class TypeHandlerCodeGenerator(ThreeStepCodeGenerator):
    """TypeHandler Code 생성기
    
    ThreeStepCodeGenerator를 상속받되, 
    Planning 단계(Step 2)의 결과를 JSON으로 파싱하지 않고 
    Raw Text 그대로 Execution 단계(Step 3)로 전달합니다.
    """
    
    def __init__(self, config: Configuration):
        super().__init__(config)

        # 템플릿 경로를 현재 클래스 파일 위치 기준으로 재설정
        template_dir = Path(__file__).parent
        self.data_mapping_template_path = template_dir / "data_mapping_template.md"
        self.planning_template_path = template_dir / "planning_template.md"

        # Execution 템플릿은 설정에 따라 결정
        if self.config.generate_type == "full_source":
            execution_template_name = "execution_template_full.md"
        elif self.config.generate_type == "diff":
            execution_template_name = "execution_template_diff.md"
        else:
            execution_template_name = "execution_template_full.md"
            
        self.execution_template_path = template_dir / execution_template_name
        
        # 토큰 계산용 템플릿 경로 업데이트
        self.template_path = self.planning_template_path

        # 템플릿 파일 존재 여부 확인
        for template_path in [
            self.data_mapping_template_path,
            self.planning_template_path,
            self.execution_template_path,
        ]:
            if not template_path.exists():
                logger.warning(f"Template file not found at local path: {template_path}, falling back to parent default might be safer or raise error.")

    def _execute_planning_phase(
        self,
        session_dir: Path,
        modification_context: ModificationContext,
        table_access_info: TableAccessInfo,
        mapping_info: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], int]:
        """Step 2 (Planning): JSON 파싱 없이 LLM 응답 텍스트를 그대로 반환합니다."""
        logger.info("-" * 40)
        logger.info("[Step 2] Planning (Text Mode) 시작...")
        logger.info(f"소스 파일 수: {len(modification_context.file_paths)}")

        # 프롬프트 생성 (부모 로직 재사용)
        prompt = self._create_planning_prompt(
            modification_context, table_access_info, mapping_info
        )
        logger.debug(f"Planning 프롬프트 길이: {len(prompt)} chars")

        # 프롬프트 저장
        self._save_prompt_to_file(prompt, modification_context, "planning")

        # LLM 호출
        response = self.analysis_provider.call(prompt)
        tokens_used = response.get("tokens_used", 0)
        content = response.get("content", "")
        
        logger.info(f"Planning 응답 완료 (토큰: {tokens_used})")

        # 텍스트 결과를 modification_instructions 키에 담음
        # (generate_modification_plan 메서드와의 호환성을 위해)
        result = {
            "modification_instructions": content
        }

        # 결과 저장
        self._save_phase_result(
            session_dir=session_dir,
            modification_context=modification_context,
            step_number=2,
            phase_name="planning",
            result=result,
            tokens_used=tokens_used,
        )

        # 요약 로깅
        logger.info(f"생성된 수정 지침(Raw Text) 길이: {len(content)}")

        return result, tokens_used

    def _get_planning_reasons(self, planning_result: Dict[str, Any]) -> Dict[str, str]:
        """Planning 결과가 텍스트이므로 파일별 reason은 생성하지 않습니다."""
        return {}

    def _create_execution_prompt(
        self,
        modification_context: ModificationContext,
        modification_instructions: Union[List[Dict[str, Any]], str],
    ) -> Tuple[str, Dict[int, str], Dict[str, str], Dict[str, str]]:
        """Execution 프롬프트를 생성합니다. (modification_instructions가 텍스트임)"""
        
        add_line_num = self.config and self.config.generate_type != 'full_source'

        # 소스 파일 내용 (인덱스 형식)
        source_files_str, index_to_path, path_to_content = (
            self._read_file_contents_indexed(
                modification_context.file_paths,
                add_line_num=add_line_num
            )
        )

        file_mapping = {Path(fp).name: fp for fp in modification_context.file_paths}

        # modification_instructions 처리
        # Step 2에서 문자열로 넘어왔으므로 그대로 사용
        instructions_str = modification_instructions
        
        # 만약 (혹시라도) 리스트/딕셔너리가 넘어오면 JSON 변환 (안전장치)
        if not isinstance(instructions_str, str):
            instructions_str = json.dumps(
                instructions_str, indent=2, ensure_ascii=False
            )

        variables = {
            "source_files": source_files_str,
            "modification_instructions": instructions_str,
        }

        template_str = self._load_template(self._get_execution_template_path())
        prompt = self._render_template(template_str, variables)

        return prompt, index_to_path, file_mapping, path_to_content