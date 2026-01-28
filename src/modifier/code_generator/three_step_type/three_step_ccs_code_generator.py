"""
Three-Step CCS Code Generator

CCS(AnyframeCCS) 프레임워크 전용 ThreeStepCodeGenerator입니다.

CCS 프로젝트의 특징:
- DQM.xml 파일의 resultMap 태그에 컬럼↔필드 매핑 정보가 명시되어 있음
- VO 파일 전체를 포함하지 않고, resultMap 매핑 정보만 추출하여 사용
- Phase 1 프롬프트 토큰 70-90% 절약

상속 구조:
    BaseMultiStepCodeGenerator
        └── ThreeStepCodeGenerator (기본 3단계 생성기)
            └── ThreeStepCCSCodeGenerator (CCS 전용)
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Tuple

from models.modification_context import ModificationContext
from models.table_access_info import TableAccessInfo

from .three_step_code_generator import ThreeStepCodeGenerator

logger = logging.getLogger("applycrypto")


class ThreeStepCCSCodeGenerator(ThreeStepCodeGenerator):
    """
    CCS(AnyframeCCS) 프레임워크 전용 3단계 LLM 협업 Code 생성기

    Phase 1에서 VO 파일 전체 대신 DQM.xml의 resultMap 필드 매핑을 사용합니다.
    Phase 2, 3는 기본 ThreeStepCodeGenerator와 동일합니다.
    """

    def __init__(self, config):
        """
        ThreeStepCCSCodeGenerator 초기화

        Args:
            config: 설정 객체 (three_step_config 필수)
        """
        super().__init__(config)

        # CCS 전용 템플릿 경로 설정
        template_dir = Path(__file__).parent
        self.data_mapping_template_ccs_path = (
            template_dir / "data_mapping_template_ccs.md"
        )

        # CCS 템플릿 존재 여부 확인
        if not self.data_mapping_template_ccs_path.exists():
            raise FileNotFoundError(
                f"CCS 템플릿을 찾을 수 없습니다: {self.data_mapping_template_ccs_path}"
            )

        logger.info("ThreeStepCCSCodeGenerator 초기화 완료 (resultMap 기반 필드 매핑 사용)")

    # ========== Phase 1 오버라이드: CCS 전용 Data Mapping ==========

    def _execute_data_mapping_phase(
        self,
        session_dir: Path,
        modification_context: ModificationContext,
        table_access_info: TableAccessInfo,
    ) -> Tuple[Dict[str, Any], int]:
        """
        Step 1 (Query Analysis): CCS용 resultMap 기반 데이터 매핑 정보를 추출합니다.

        VO 파일 전체 대신 DQM.xml에서 추출한 필드 매핑 정보를 사용하여
        토큰을 대폭 절약합니다.
        """
        logger.info("-" * 40)
        logger.info("[Step 1] Query Analysis 시작 (CCS: resultMap 기반)...")

        # CCS 전용 프롬프트 생성
        prompt = self._create_ccs_data_mapping_prompt(
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

    # ========== CCS 전용 헬퍼 메서드 ==========

    def _create_ccs_data_mapping_prompt(
        self,
        modification_context: ModificationContext,
        table_access_info: TableAccessInfo,
    ) -> str:
        """
        CCS 전용 Phase 1 프롬프트를 생성합니다.

        VO 파일 전체 대신 DQM.xml에서 추출한 필드 매핑 정보를
        각 SQL 쿼리와 함께 컴팩트하게 제공합니다.

        Args:
            modification_context: 수정 컨텍스트
            table_access_info: 테이블 접근 정보

        Returns:
            str: 렌더링된 프롬프트
        """
        # 테이블/칼럼 정보
        table_info = {
            "table_name": modification_context.table_name,
            "columns": modification_context.columns,
        }
        table_info_str = json.dumps(table_info, indent=2, ensure_ascii=False)

        # target columns 추출 (관심 대상 컬럼명 리스트)
        target_columns = [col.get("name", "") for col in modification_context.columns]

        # SQL 쿼리 + 관련 필드 매핑을 함께 포맷팅 (중복 제거, 컴팩트화)
        sql_queries_with_mappings = self._format_ccs_sql_with_relevant_mappings(
            table_access_info, modification_context.file_paths, target_columns
        )

        variables = {
            "table_info": table_info_str,
            "sql_queries_with_mappings": sql_queries_with_mappings,
        }

        template_str = self._load_template(self.data_mapping_template_ccs_path)
        return self._render_template(template_str, variables)

    def _format_ccs_sql_with_relevant_mappings(
        self,
        table_access_info: TableAccessInfo,
        file_paths: list,
        target_columns: list,
    ) -> str:
        """
        CCS용 SQL 쿼리와 관련 필드 매핑을 함께 포맷팅합니다.

        각 쿼리 밑에 target_columns에 해당하는 필드 매핑만 자연어로 설명합니다.

        Args:
            table_access_info: 테이블 접근 정보
            file_paths: 파일 경로 리스트 (필터링용)
            target_columns: 관심 대상 컬럼명 리스트

        Returns:
            str: 포맷팅된 SQL 쿼리 + 매핑 정보 문자열
        """
        # target_columns를 대문자로 정규화 (비교용)
        target_cols_upper = {col.upper() for col in target_columns}

        # 파일 경로에서 클래스명 추출 (필터링용)
        file_class_names = set()
        if file_paths:
            for file_path in file_paths:
                class_name = Path(file_path).stem
                file_class_names.add(class_name)

        output_parts = []
        query_num = 0

        for sql_query in table_access_info.sql_queries:
            # 파일 경로가 지정된 경우 관련 SQL만 필터링
            if file_paths and file_class_names:
                call_stacks = sql_query.get("call_stacks", [])
                is_relevant = False
                for call_stack in call_stacks:
                    if not isinstance(call_stack, list):
                        continue
                    for method_sig in call_stack:
                        if not isinstance(method_sig, str):
                            continue
                        method_class_name = (
                            method_sig.split(".")[0] if "." in method_sig else method_sig
                        )
                        if method_class_name in file_class_names:
                            is_relevant = True
                            break
                    if is_relevant:
                        break
                if not is_relevant:
                    continue

            query_num += 1
            query_id = sql_query.get("id", "unknown")
            query_type = sql_query.get("query_type", "SELECT")
            sql_text = sql_query.get("sql", "")
            strategy_specific = sql_query.get("strategy_specific", {})

            # 쿼리 헤더
            output_parts.append(f"### Query {query_num}: {query_id} ({query_type})")
            output_parts.append("")

            # SQL 텍스트 (strategy_specific 제외한 간결한 형태)
            output_parts.append("**SQL:**")
            output_parts.append("```sql")
            output_parts.append(sql_text.strip())
            output_parts.append("```")
            output_parts.append("")

            # 메타 정보
            param_type = strategy_specific.get("parameter_type", "")
            result_type = strategy_specific.get("result_type", "")
            if param_type:
                output_parts.append(f"- **Parameter Type:** `{param_type}`")
            if result_type:
                output_parts.append(f"- **Result Type:** `{result_type}`")
            output_parts.append("")

            # 관련 필드 매핑 (target_columns만 필터링)
            relevant_mappings = []

            if query_type == "SELECT":
                # resultMap에서 추출한 필드 매핑
                result_field_mappings = strategy_specific.get(
                    "result_field_mappings", []
                )
                for java_field, db_column in result_field_mappings:
                    if db_column.upper() in target_cols_upper:
                        relevant_mappings.append(
                            f"- Column `{db_column}` → Java field `{java_field}`"
                        )

            elif query_type in ("INSERT", "UPDATE"):
                # SQL 내 #{fieldName} 패턴
                param_fields = strategy_specific.get("parameter_field_mappings", [])
                # INSERT/UPDATE는 SQL에서 컬럼명을 직접 추출해야 함
                # 여기서는 parameter_fields만 제공하고, 컬럼 매칭은 LLM에게 위임
                if param_fields:
                    # 간단히 모든 파라미터 필드 나열 (LLM이 컬럼과 매칭)
                    for field in param_fields:
                        relevant_mappings.append(
                            f"- Parameter `#{{{field}}}` → Java field `{field}`"
                        )

            if relevant_mappings:
                output_parts.append(
                    f"**Relevant Field Mappings for Target Columns ({', '.join(target_columns)}):**"
                )
                output_parts.extend(relevant_mappings)
            else:
                output_parts.append(
                    "**Field Mappings:** No direct mapping found for target columns. "
                    "Infer from SQL parameter names or use camelCase conversion."
                )

            output_parts.append("")
            output_parts.append("---")
            output_parts.append("")

        if query_num == 0:
            return "No relevant SQL queries found for this context."

        logger.info(f"CCS SQL 쿼리 포맷팅 완료: {query_num}개 쿼리")
        return "\n".join(output_parts)
