"""
Endpoint Extraction Strategy 모듈

framework_type에 따라 다른 엔드포인트 추출 방식을 제공하는 Strategy 패턴 인터페이스입니다.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from models.endpoint import Endpoint
from models.method import Method
from parser.java_ast_parser import ClassInfo


class EndpointExtractionStrategy(ABC):
    """
    엔드포인트 추출 전략 인터페이스

    framework_type에 따라 다른 엔드포인트 추출 방식을 구현합니다.
    """

    def __init__(self, java_parser=None, cache_manager=None):
        """
        EndpointExtractionStrategy 초기화

        Args:
            java_parser: Java AST 파서 (선택적)
            cache_manager: 캐시 매니저 (선택적)
        """
        self.java_parser = java_parser
        self.cache_manager = cache_manager

    @abstractmethod
    def extract_endpoints_from_classes(
        self, classes: List[ClassInfo]
    ) -> List[Endpoint]:
        """
        클래스 목록에서 모든 엔드포인트를 추출합니다.

        Args:
            classes: 클래스 정보 목록

        Returns:
            List[Endpoint]: 추출된 엔드포인트 목록
        """
        pass

    @abstractmethod
    def extract_endpoint(
        self, cls: ClassInfo, method: Method, class_path: str
    ) -> Optional[Endpoint]:
        """
        특정 클래스와 메서드에서 엔드포인트 정보를 추출합니다.

        Args:
            cls: 클래스 정보
            method: 메서드 정보
            class_path: 클래스 레벨 경로

        Returns:
            Optional[Endpoint]: 추출된 엔드포인트 정보 또는 None
        """
        pass

    @abstractmethod
    def extract_path_from_annotation(self, annotation: str) -> Optional[str]:
        """
        어노테이션 문자열에서 path(value 또는 path 속성)를 추출합니다.

        Args:
            annotation: 어노테이션 문자열

        Returns:
            Optional[str]: 추출된 path 또는 None
        """
        pass

    @abstractmethod
    def extract_http_method_from_annotation(
        self, annotation: str
    ) -> Optional[str]:
        """
        어노테이션에서 HTTP 메서드를 추출합니다.

        Args:
            annotation: 어노테이션 문자열

        Returns:
            Optional[str]: HTTP 메서드 (GET, POST, PUT, DELETE, PATCH) 또는 None
        """
        pass

    @abstractmethod
    def classify_layer(self, cls: ClassInfo, method: Method) -> str:
        """
        클래스와 메서드의 레이어를 분류합니다.

        Args:
            cls: 클래스 정보
            method: 메서드 정보

        Returns:
            str: 레이어명 (Controller, Service, DAO, Repository, Mapper, Entity, Unknown)
        """
        pass

    @abstractmethod
    def get_class_level_path(self, cls: ClassInfo) -> str:
        """
        클래스 레벨 경로를 추출합니다.

        Args:
            cls: 클래스 정보

        Returns:
            str: 클래스 레벨 경로 (빈 문자열일 수 있음)
        """
        pass

    def get_annotation_text_from_file(
        self, file_path: str, target_name: str, is_class: bool = True
    ) -> Dict[str, str]:
        """
        파일에서 어노테이션 전체 텍스트 추출 (주석 제외)

        이 메서드는 공통 유틸리티로 제공되며, 필요시 하위 클래스에서 오버라이드할 수 있습니다.

        Args:
            file_path: 파일 경로
            target_name: 클래스명 또는 메서드명
            is_class: True면 클래스, False면 메서드

        Returns:
            Dict[str, str]: 어노테이션 이름 -> 전체 텍스트 매핑
        """
        annotation_map = {}

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                source_code = f.read()
        except Exception:
            return annotation_map

        # 주석 제거 (간단한 처리)
        import re

        # 블록 주석 제거
        source_code = re.sub(r"/\*.*?\*/", "", source_code, flags=re.DOTALL)
        # 라인 주석 제거
        source_code = re.sub(r"//.*?$", "", source_code, flags=re.MULTILINE)

        if is_class:
            # 클래스 정의 찾기
            pattern = rf"class\s+{re.escape(target_name)}\s*[{{]"
        else:
            # 메서드 정의 찾기 (간단한 패턴)
            pattern = rf"(?:public|private|protected)?\s*(?:static)?\s*(?:final)?\s*\w+\s+{re.escape(target_name)}\s*\("

        match = re.search(pattern, source_code)
        if not match:
            return annotation_map

        # 클래스/메서드 정의 이전 부분에서 어노테이션 찾기
        start_pos = match.start()
        class_start = match.start()

        # 역방향으로 어노테이션 찾기
        annotation_pattern = r"@(\w+)\s*(?:\([^)]*\))?"
        annotations = re.finditer(annotation_pattern, source_code[:start_pos])

        for ann_match in annotations:
            ann_name = ann_match.group(1)
            ann_full_text = ann_match.group(0)
            annotation_map[ann_name] = ann_full_text

        return annotation_map

