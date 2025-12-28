"""
SQL Extractor 모듈

sql_wrapping_type에 따라 서로 다른 방식으로 SQL을 추출하는 기본 클래스입니다.
"""

import logging
import re
from abc import ABC, abstractmethod
from parser.xml_mapper_parser import XMLMapperParser
from typing import Any, Dict, List, Optional, Set, Tuple

from config.config_manager import Configuration
from models.source_file import SourceFile
from models.sql_extraction_output import ExtractedSQLQuery, SQLExtractionOutput


class SQLExtractor(ABC):
    """
    SQL Extractor 기본 클래스

    추상 메서드 extract_from_files()를 가지며, SQL 파싱 메서드는 공통으로 제공합니다.
    """

    def __init__(
        self,
        config: Configuration,
        xml_parser: Optional[XMLMapperParser] = None,
        java_parse_results: Optional[List[dict]] = None,
        call_graph_builder: Optional[Any] = None,
    ):
        """
        SQLExtractor 초기화

        Args:
            config: 설정 객체
            xml_parser: XML Mapper 파서 (MyBatis 전략일 때 사용)
            java_parse_results: Java 파싱 결과 리스트 (JDBC/JPA 전략일 때 사용)
            call_graph_builder: CallGraphBuilder 인스턴스 (선택적)
        """
        self.config = config
        self.xml_parser = xml_parser or XMLMapperParser()
        self.java_parse_results = java_parse_results or []
        self.call_graph_builder = call_graph_builder
        self.logger = logging.getLogger(__name__)

    @abstractmethod
    def extract_from_files(
        self, source_files: List[SourceFile]
    ) -> List[SQLExtractionOutput]:
        """
        소스 파일들에서 SQL 쿼리 추출 (추상 메서드)

        Args:
            source_files: 분석할 소스 파일 목록

        Returns:
            List[SQLExtractionOutput]: 추출된 SQL 쿼리 정보 목록
        """
        pass

    @abstractmethod
    def filter_sql_files(
        self, source_files: List[SourceFile]
    ) -> List[SourceFile]:
        """
        SQL 관련 파일 필터링 (추상 메서드)

        각 전략에 맞는 파일만 필터링하여 반환합니다.

        Args:
            source_files: 소스 파일 목록

        Returns:
            List[SourceFile]: 필터링된 파일 목록
        """
        pass

    @abstractmethod
    def extract_sqls(
        self, source_files: List[SourceFile]
    ) -> List[SQLExtractionOutput]:
        """
        필터링된 소스 파일들에서 SQL 쿼리 추출 (추상 메서드)

        각 전략에 맞는 방식으로 SQL을 추출합니다.
        이 메서드는 이미 필터링된 파일 목록을 받아서 처리합니다.

        Args:
            source_files: 필터링된 소스 파일 목록

        Returns:
            List[SQLExtractionOutput]: 추출된 SQL 쿼리 정보 목록
        """
        pass

    @abstractmethod
    def get_class_files_from_sql_query(
        self, sql_query: Dict[str, Any]
    ) -> Tuple[Optional[str], Dict[str, Set[str]], Set[str]]:
        """
        SQL 쿼리에서 관련 클래스 파일 목록 추출 (추상 메서드)

        Args:
            sql_query: SQL 쿼리 정보 딕셔너리

        Returns:
            Tuple[Optional[str], Dict[str, Set[str]], Set[str]]: (method_string, layer_files, all_files) 튜플
                - method_string: 메서드 시그니처 문자열 (예: "UserMapper.getUserById")
                - layer_files: 레이어별 파일 경로 집합을 담은 딕셔너리
                - all_files: 모든 관련 파일 경로 집합
        """
        pass

    def extract_table_names(self, sql: str) -> Set[str]:
        """
        SQL 쿼리에서 테이블명 추출 (공통 메서드)

        Args:
            sql: SQL 쿼리 문자열

        Returns:
            Set[str]: 추출된 테이블명 집합
        """
        tables = set()

        # FROM 절에서 테이블명 추출
        from_pattern = (
            r"\bFROM\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?)\b"
        )
        from_matches = re.findall(from_pattern, sql, re.IGNORECASE)
        for match in from_matches:
            # 스키마명 제거 (예: schema.table -> table)
            table = match.split(".")[-1]
            tables.add(table.upper())

        # JOIN 절에서 테이블명 추출
        join_pattern = r"\b(?:INNER|LEFT|RIGHT|FULL|OUTER)?\s+JOIN\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?)\b"
        join_matches = re.findall(join_pattern, sql, re.IGNORECASE)
        for match in join_matches:
            table = match.split(".")[-1]
            tables.add(table.upper())

        # INSERT INTO 절에서 테이블명 추출
        insert_pattern = (
            r"\bINSERT\s+INTO\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?)\b"
        )
        insert_matches = re.findall(insert_pattern, sql, re.IGNORECASE)
        for match in insert_matches:
            table = match.split(".")[-1]
            tables.add(table.upper())

        # UPDATE 절에서 테이블명 추출
        update_pattern = (
            r"\bUPDATE\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?)\b"
        )
        update_matches = re.findall(update_pattern, sql, re.IGNORECASE)
        for match in update_matches:
            table = match.split(".")[-1]
            tables.add(table.upper())

        # DELETE FROM 절에서 테이블명 추출
        delete_pattern = (
            r"\bDELETE\s+FROM\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?)\b"
        )
        delete_matches = re.findall(delete_pattern, sql, re.IGNORECASE)
        for match in delete_matches:
            table = match.split(".")[-1]
            tables.add(table.upper())

        return tables

    def extract_column_names(self, sql: str, table_name: str) -> Set[str]:
        """
        SQL 쿼리에서 특정 테이블의 칼럼명 추출 (공통 메서드)

        Args:
            sql: SQL 쿼리 문자열
            table_name: 테이블명

        Returns:
            Set[str]: 추출된 칼럼명 집합
        """
        columns = set()
        table_alias = None

        # 테이블 별칭 찾기 (예: FROM users u -> u)
        alias_pattern = (
            rf"\bFROM\s+{re.escape(table_name)}\s+([a-zA-Z_][a-zA-Z0-9_]*)\b"
        )
        alias_match = re.search(alias_pattern, sql, re.IGNORECASE)
        if alias_match:
            table_alias = alias_match.group(1)

        # SELECT 절에서 칼럼명 추출
        select_pattern = r"\bSELECT\s+(.*?)\s+FROM\b"
        select_match = re.search(select_pattern, sql, re.IGNORECASE | re.DOTALL)
        if select_match:
            select_clause = select_match.group(1)
            # 각 칼럼 추출
            column_pattern = r"([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?)"
            column_matches = re.findall(column_pattern, select_clause)
            for match in column_matches:
                if "." in match:
                    # table.column 또는 alias.column 형식
                    parts = match.split(".")
                    if len(parts) == 2:
                        if (
                            parts[0].upper() == table_name.upper()
                            or parts[0] == table_alias
                        ):
                            columns.add(parts[1].upper())
                else:
                    # 단순 칼럼명
                    columns.add(match.upper())

        # INSERT INTO 절에서 칼럼명 추출
        insert_pattern = rf"\bINSERT\s+INTO\s+{re.escape(table_name)}\s*\(([^)]+)\)"
        insert_match = re.search(insert_pattern, sql, re.IGNORECASE)
        if insert_match:
            column_list = insert_match.group(1)
            for col in column_list.split(","):
                col = col.strip()
                if col:
                    columns.add(col.upper())

        # UPDATE SET 절에서 칼럼명 추출
        update_pattern = (
            rf"\bUPDATE\s+{re.escape(table_name)}\s+SET\s+(.*?)(?:\s+WHERE|\s*$)"
        )
        update_match = re.search(update_pattern, sql, re.IGNORECASE | re.DOTALL)
        if update_match:
            set_clause = update_match.group(1)
            # column = value 형식 추출
            set_column_pattern = r"([a-zA-Z_][a-zA-Z0-9_]*)\s*="
            set_matches = re.findall(set_column_pattern, set_clause)
            for match in set_matches:
                columns.add(match.upper())

        return columns

    def _remove_sql_comments(self, sql: str) -> str:
        """
        SQL에서 주석 제거 (공통 메서드)

        Args:
            sql: SQL 쿼리 문자열

        Returns:
            str: 주석이 제거된 SQL 문자열
        """
        # 여러 줄 주석 /* */ 제거
        sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)
        
        # 한 줄 주석 -- 제거
        lines = sql.split('\n')
        cleaned_lines = []
        for line in lines:
            # -- 주석 제거 (문자열 내부의 --는 제외)
            comment_pos = line.find('--')
            if comment_pos != -1:
                # 문자열 내부인지 확인 (간단한 체크)
                before_comment = line[:comment_pos]
                # 따옴표가 짝수 개면 문자열 밖
                if before_comment.count("'") % 2 == 0 and before_comment.count('"') % 2 == 0:
                    line = line[:comment_pos].rstrip()
            cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)

    def _detect_query_type(self, sql: str) -> Optional[str]:
        """
        SQL 쿼리 타입 자동 감지 (공통 메서드)

        Args:
            sql: SQL 쿼리 문자열

        Returns:
            Optional[str]: 쿼리 타입 (SELECT, INSERT, UPDATE, DELETE) 또는 None
        """
        # 주석 제거
        sql_no_comments = self._remove_sql_comments(sql)
        sql_upper = sql_no_comments.strip().upper()

        if sql_upper.startswith("SELECT"):
            return "SELECT"
        elif sql_upper.startswith("INSERT"):
            return "INSERT"
        elif sql_upper.startswith("UPDATE"):
            return "UPDATE"
        elif sql_upper.startswith("DELETE"):
            return "DELETE"

        return None

    def _extract_generic_inner_type(self, type_str: Optional[str]) -> Optional[str]:
        """
        제네릭 타입에서 내부 클래스 타입 추출 (공통 메서드)

        Args:
            type_str: 타입 문자열 (예: "List<AdBkgImgDVO>", "Map<String, User>")

        Returns:
            Optional[str]: 추출된 내부 클래스 타입 또는 None
        """
        if not type_str:
            return None
        
        # 제네릭 타입 처리 (예: List<AdBkgImgDVO> -> AdBkgImgDVO)
        if "<" in type_str and ">" in type_str:
            # 제네릭 내부 타입 추출 (마지막 > 전의 내용)
            # Map<String, User> 같은 경우 마지막 타입을 추출
            generic_match = re.search(r'<([^>]+)>', type_str)
            if generic_match:
                inner_types = generic_match.group(1)
                # 쉼표로 구분된 경우 마지막 타입 사용 (Map<K, V> -> V)
                if "," in inner_types:
                    inner_types = inner_types.split(",")
                    # 마지막 타입에서 공백 제거
                    return inner_types[-1].strip()
                else:
                    return inner_types.strip()
        
        return type_str

    def _find_class_file(self, full_class_name: str) -> Optional[str]:
        """
        클래스명으로 파일 경로 찾기 (공통 메서드)

        Args:
            full_class_name: 전체 클래스명 (패키지 포함)

        Returns:
            Optional[str]: 파일 경로
        """
        if not self.call_graph_builder:
            return None

        class_info_map = self.call_graph_builder.get_class_info_map()

        # 전체 클래스명으로 찾기
        if full_class_name in class_info_map:
            class_infos = class_info_map[full_class_name]
            if class_infos:
                return class_infos[0]["file_path"]

        # 단순 클래스명으로 찾기
        simple_class_name = full_class_name.split(".")[-1]
        if simple_class_name in class_info_map:
            class_infos = class_info_map[simple_class_name]
            # 패키지명이 일치하는 것 우선
            for class_info in class_infos:
                if class_info["full_class_name"] == full_class_name:
                    return class_info["file_path"]
            # 없으면 첫 번째 것
            if class_infos:
                return class_infos[0]["file_path"]

        return None
