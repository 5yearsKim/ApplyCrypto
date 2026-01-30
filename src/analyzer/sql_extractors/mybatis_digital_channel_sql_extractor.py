"""
MyBatis SQL Extractor

MyBatis XML Mapper 파일에서 SQL을 추출하는 구현 클래스입니다.
"""

import logging
import os
import json
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple, override

from config.config_manager import Configuration
from models.source_file import SourceFile
from models.sql_extraction_output import SQLExtractionOutput
from parser.xml_mapper_parser import XMLMapperParser

from ..llm_sql_extractor.llm_sql_extractor import LLMSQLExtractor
from ..sql_extractor import SQLExtractor
from .mybatis_sql_extractor import MyBatisSQLExtractor


class MyBatisDigitalChannelSQLExtractor(MyBatisSQLExtractor):
    _namespace_map_cache = None

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
                - method_string: 메서드 시그니처 문자열 (예: "UserMapper.getUserById")
                - layer_files: 레이어별 파일 경로 집합을 담은 딕셔너리
                - all_files: 모든 관련 파일 경로 집합
        """
        layer_files: Dict[str, Set[str]] = defaultdict(set)
        all_files: Set[str] = set()

        layer_name = self.get_layer_name()

        strategy_specific = sql_query.get("strategy_specific", {})
        
        # MyBatis: namespace, parameter_type, result_type, result_map 사용
        namespace = strategy_specific.get("namespace", "")
        if namespace:
            interface_file = self._find_class_file(namespace)
            if interface_file:
                layer_files[layer_name].add(interface_file)
                all_files.add(interface_file)

        parameter_type = strategy_specific.get("parameter_type")
        if parameter_type:
            parameter_file = self._find_class_file(parameter_type)
            if parameter_file:
                layer_files[layer_name].add(parameter_file)
                all_files.add(parameter_file)

        result_type = strategy_specific.get("result_type")
        if result_type:
            dao_file = self._find_class_file(result_type)
            if dao_file:
                layer_files[layer_name].add(dao_file)
                all_files.add(dao_file)

        result_map = strategy_specific.get("result_map")
        if result_map:
            result_map_file = self._find_class_file(result_map)
            if result_map_file:
                layer_files[layer_name].add(result_map_file)
                all_files.add(result_map_file)

        xml_file_path = strategy_specific.get("xml_file_path")
        if xml_file_path:
            layer_files["xml"].add(xml_file_path)
            all_files.add(xml_file_path)

        # method_string 생성: namespace의 class_name + sql query의 id
        method_string = None
        query_id = sql_query.get("id", "")
        if namespace and query_id:
            # namespace에서 마지막 클래스명 추출
            class_name = self._get_class_name(query_id, namespace) 
            method_string = f"{class_name}.{query_id}"

        return method_string, layer_files, all_files

    def _get_class_name(self, query_id: str, namespace: str) -> str:
        """
        Query ID와 Namespace를 기반으로 클래스명 추출
        map 파일(digital_chananel_specific_map.json)을 활용하여 매핑 찾기

        Args:
            query_id: SQL Query ID (메서드명)
            namespace: Mapper Namespace

        Returns:
            str: 매핑된 클래스명 또는 namespace의 마지막 부분
        """
        if self._namespace_map_cache is None:
            map_file = "digital_chananel_specific_map.json"
            if os.path.exists(map_file):
                try:
                    with open(map_file, "r", encoding="utf-8") as f:
                        self._namespace_map_cache = json.load(f)
                except Exception as e:
                    logging.warning(f"Failed to load {map_file}: {e}")
                    self._namespace_map_cache = {}
            else:
                self._namespace_map_cache = {}
        
        # namespace로 조회
        if namespace in self._namespace_map_cache:
            class_map = self._namespace_map_cache[namespace]
            # 해당 namespace 아래의 클래스들을 순회하며 query_id(메서드명)가 있는지 확인
            for class_name, methods in class_map.items():
                if query_id in methods:
                    return class_name
        
        # 매핑되지 않았거나 찾을 수 없는 경우 기본 동작 (namespace의 마지막 부분 사용)
        return namespace.split(".")[-1]

