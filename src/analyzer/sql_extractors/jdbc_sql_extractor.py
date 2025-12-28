"""
JDBC SQL Extractor

JDBC를 사용하는 Java 파일에서 SQL을 추출하는 구현 클래스입니다.
"""

import logging
import re
from pathlib import Path
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple, override

from config.config_manager import Configuration
from models.source_file import SourceFile
from models.sql_extraction_output import SQLExtractionOutput
from parser.xml_mapper_parser import XMLMapperParser

from ..llm_sql_extractor.llm_sql_extractor import LLMSQLExtractor
from ..sql_extractor import SQLExtractor


class JDBCSQLExtractor(SQLExtractor):
    """
    JDBC SQL Extractor 구현 클래스

    JDBC를 사용하는 Java 파일에서 SQL을 추출합니다.
    config.use_llm_parser가 True인 경우 LLMSQLExtractor를 사용합니다.
    """

    def __init__(
        self,
        config: Configuration,
        xml_parser: XMLMapperParser = None,
        java_parse_results: List[dict] = None,
        call_graph_builder = None,
    ):
        """
        JDBCSQLExtractor 초기화

        Args:
            config: 설정 객체
            xml_parser: XML Mapper 파서 (사용하지 않지만 호환성을 위해 유지)
            java_parse_results: Java 파싱 결과 리스트
            call_graph_builder: CallGraphBuilder 인스턴스 (선택적)
        """
        super().__init__(config=config, xml_parser=xml_parser, java_parse_results=java_parse_results, call_graph_builder=call_graph_builder)
        self.logger = logging.getLogger(__name__)

    @override
    def extract_from_files(
        self, source_files: List[SourceFile]
    ) -> List[SQLExtractionOutput]:
        """
        소스 파일들에서 SQL 쿼리 추출

        Args:
            source_files: 분석할 소스 파일 목록

        Returns:
            List[SQLExtractionOutput]: 추출된 SQL 쿼리 정보 목록
        """
        # 먼저 파일 필터링 수행
        filtered_files = self.filter_sql_files(source_files)
        
        if self.config.use_llm_parser:
            # LLM 기반 추출 사용
            if filtered_files:
                llm_extractor = LLMSQLExtractor(
                    llm_provider_name=self.config.llm_provider
                )
                return llm_extractor.extract_from_files(filtered_files)
            return []
        else:
            # 기존 방식 사용 (이미 필터링된 파일 목록 사용)
            return self.extract_sqls(filtered_files)

    @override
    def extract_sqls(
        self, source_files: List[SourceFile]
    ) -> List[SQLExtractionOutput]:
        """
        JDBC 전략: Java 파일에서 JDBC SQL 추출

        Args:
            source_files: 소스 파일 목록

        Returns:
            List[SQLExtractionOutput]: 추출 결과
        """
        from models.sql_extraction_output import ExtractedSQLQuery

        results = []
        
        for java_file in source_files:
            try:
                # JDBC SQL 추출
                sql_queries_data = self._extract_jdbc_sql_from_file(java_file.path)

                if sql_queries_data:
                    # strategy_specific에 JDBC 특정 정보 저장
                    sql_queries = []
                    for query in sql_queries_data:
                        sql_queries.append(
                            ExtractedSQLQuery(
                                id=query.get("id", ""),
                                query_type=query.get("query_type", "SELECT"),
                                sql=query.get("sql", ""),
                                strategy_specific=query.get("strategy_specific", {}),
                            )
                        )

                    results.append(
                        SQLExtractionOutput(file=java_file, sql_queries=sql_queries)
                    )

            except Exception as e:
                self.logger.warning(f"JDBC SQL 추출 실패: {java_file.path} - {e}")

        return results

    def _extract_jdbc_sql_from_file(self, file_path: Path) -> List[dict]:
        """
        JDBC를 사용하는 Java 파일에서 SQL 쿼리 추출

        Args:
            file_path: Java 파일 경로

        Returns:
            List[dict]: 추출된 SQL 쿼리 목록
                각 항목은 {"id": str, "query_type": str, "sql": str, "strategy_specific": dict} 형태
        """
        sql_queries = []

        # 파일 읽기
        source_code = None
        encodings = ["utf-8", "euc-kr", "cp949", "latin-1", "iso-8859-1"]

        for encoding in encodings:
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    source_code = f.read()
                break
            except UnicodeDecodeError:
                continue
            except Exception:
                continue

        if not source_code:
            return sql_queries

        # JDBC 패턴 찾기: executeQuery, executeUpdate, prepareStatement 등
        # prepareStatement("SELECT ...") 또는 executeQuery("SELECT ...") 패턴
        jdbc_patterns = [
            # prepareStatement("SQL")
            (r'prepareStatement\s*\(\s*["\']([^"\']+)["\']', "SELECT"),
            # executeQuery("SQL")
            (r'executeQuery\s*\(\s*["\']([^"\']+)["\']', "SELECT"),
            # executeUpdate("SQL")
            (r'executeUpdate\s*\(\s*["\']([^"\']+)["\']', "UPDATE"),
            # execute("SQL")
            (r'execute\s*\(\s*["\']([^"\']+)["\']', "SELECT"),
        ]

        # 메서드 내에서 SQL 문자열 찾기
        # 메서드 시그니처 추출
        method_pattern = r"(?:public|private|protected)?\s+\w+\s+(\w+)\s*\("
        methods = re.finditer(method_pattern, source_code)

        for method_match in methods:
            method_name = method_match.group(1)
            method_start = method_match.start()

            # 메서드 끝 찾기 (다음 메서드 또는 클래스 끝)
            next_method = re.search(
                r"(?:public|private|protected)?\s+\w+\s+\w+\s*\(",
                source_code[method_match.end() :],
            )
            if next_method:
                method_end = method_match.end() + next_method.start()
            else:
                method_end = len(source_code)

            method_body = source_code[method_start:method_end]

            # JDBC 패턴 매칭
            for pattern, default_query_type in jdbc_patterns:
                matches = re.finditer(pattern, method_body, re.IGNORECASE | re.DOTALL)
                for match in matches:
                    sql = match.group(1)
                    # SQL 타입 자동 감지
                    query_type = self._detect_query_type(sql)
                    if not query_type:
                        query_type = default_query_type

                    sql_queries.append(
                        {
                            "id": method_name,
                            "query_type": query_type,
                            "sql": sql.strip(),
                            "strategy_specific": {
                                "method_name": method_name,
                                "file_path": str(file_path),
                            },
                        }
                    )

        return sql_queries

    @override
    def filter_sql_files(self, source_files: List[SourceFile]) -> List[SourceFile]:
        """
        JDBC 관련 파일 필터링 (Java 파일 중 SQL 키워드 포함)

        Args:
            source_files: 소스 파일 목록

        Returns:
            List[SourceFile]: 필터링된 파일 목록
        """
        filtered = []
        for f in source_files:
            if f.extension == ".java" and self._has_sql_content(f.path):
                filtered.append(f)
        return filtered

    def _has_sql_content(self, file_path: Path) -> bool:
        """
        파일 내용에 SQL 키워드가 포함되어 있는지 확인

        Args:
            file_path: 파일 경로

        Returns:
            bool: SQL 키워드 포함 여부
        """
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                content_upper = content.upper()

                # Basic SQL keywords
                keywords = ["SELECT ", "INSERT ", "UPDATE ", "DELETE "]

                for kw in keywords:
                    if kw in content_upper:
                        return True

        except Exception as e:
            self.logger.warning(f"Failed to check SQL content for {file_path}: {e}")

        return False

    @override
    def get_class_files_from_sql_query(
        self, sql_query: Dict[str, Any]
    ) -> Tuple[Optional[str], Dict[str, Set[str]], Set[str]]:
        """
        SQL 쿼리에서 관련 클래스 파일 목록 추출

        Args:
            sql_query: SQL 쿼리 정보 딕셔너리

        Returns:
            Tuple[Optional[str], Dict[str, Set[str]], Set[str]]: (method_string, layer_files, all_files) 튜플
                - method_string: 메서드 시그니처 문자열 (예: "ClassName.methodName")
                - layer_files: 레이어별 파일 경로 집합을 담은 딕셔너리
                - all_files: 모든 관련 파일 경로 집합
        """
        layer_files: Dict[str, Set[str]] = defaultdict(set)
        all_files: Set[str] = set()

        strategy_specific = sql_query.get("strategy_specific", {})
        method_name = strategy_specific.get("method_name", "")
        file_path_str = strategy_specific.get("file_path", "")

        # method_string 생성: class_name.method_name
        method_string = None
        if file_path_str and self.call_graph_builder:
            class_info_map = self.call_graph_builder.get_class_info_map()
            # 파일 경로로 클래스 찾기
            for class_name, class_infos in class_info_map.items():
                for class_info in class_infos:
                    if class_info["file_path"] == file_path_str:
                        method_string = f"{class_info['class_name']}.{method_name}"
                        break
                if method_string:
                    break

        if not method_string:
            method_string = method_name if method_name else None

        return method_string, layer_files, all_files

