"""
AnyframeSarangOn Endpoint Extraction Strategy

AnyframeSarangOn 프레임워크를 위한 엔드포인트 추출 전략 구현입니다.
SpringMVC 어노테이션 패턴을 사용하여 엔드포인트를 추출합니다.
"""

import logging
import re
from typing import Dict, List, Optional

from models.method import Method
from parser.java_ast_parser import ClassInfo
from models.endpoint import Endpoint
from parser.java_utils import JavaUtils

from .endpoint_extraction_strategy import EndpointExtractionStrategy

logger = logging.getLogger(__name__)


class AnyframeSarangOnEndpointExtraction(EndpointExtractionStrategy):
    """
    AnyframeSarangOn 프레임워크 엔드포인트 추출 전략

    AnyframeSarangOn 프레임워크에서 SpringMVC 어노테이션 패턴을 사용하여 엔드포인트를 추출합니다.
    """

    # AnyframeSarangOn 어노테이션 패턴 (레이어별 분류)
    ANYFRAME_SARANGON_ANNOTATIONS = {
        # Service (인터페이스 레이어)
        "SVC": {
            "LocalName",
            "ServiceIdMapping",
        },
        # ServiceImpl (서비스 구현 레이어)
        "SVCImpl": {
            "Service",
            "Override",
            "Autowired",
            "Qualifier",
            "Transactional",
        },
        # Biz (비즈니스 로직 레이어)
        "Biz": {
            # Biz 클래스는 일반적으로 어노테이션이 없지만, 필요시 추가 가능
            "Component",
            "Autowired",
        },
        # DEM/DAQ (데이터 액세스 레이어)
        "DEM_DAQ": {
            "Repository",
            "LocalName",
        },
    }

    # 레이어 분류 패턴 (AnyframeSarangOn 특화)
    LAYER_PATTERNS = {
        # Service: 인터페이스 (I로 시작하고 SVC로 끝남)
        "SVC": [
            "SVC",  # IAPActSVC, IADActSVC 등
        ],
        # ServiceImpl: 서비스 구현 클래스 (SVCImpl로 끝남)
        "SVCImpl": [
            "SVCImpl",  # APActSVCImpl, ADActSVCImpl 등
        ],
        # Biz: 비즈니스 로직 클래스 (BIZ로 끝남)
        "BIZ": [
            "BIZ",  # APActBIZ, ADActBIZ 등
        ],
        # DEM/DAQ: 데이터 액세스 클래스 (DEM 또는 DQM으로 끝남)
        "DEM_DAQ": [
            "DEM",  # TTSA00001DEM, TSSD00001DEM 등
            "DQM",  # AdBkgImgDQM, AfBkgImgDQM 등
        ],
    }

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
        endpoints = []

        for cls in classes:
            # 클래스 레벨 경로 추출
            class_path = self.get_class_level_path(cls)

            # 메서드 레벨 엔드포인트 식별
            for method in cls.methods:
                endpoint = self.extract_endpoint(cls, method, class_path)
                if endpoint:
                    endpoints.append(endpoint)

        return endpoints

    def extract_endpoint(
        self, cls: ClassInfo, method: Method, class_path: str
    ) -> Optional[Endpoint]:
        """
        메서드에서 엔드포인트 정보 추출 (AnyframeSarangOn 패턴)

        Args:
            cls: 클래스 정보
            method: 메서드 정보
            class_path: 클래스 레벨 경로 (LocalName 값)

        Returns:
            Optional[Endpoint]: 엔드포인트 정보
        """
        http_method = None
        method_path = ""

        # 파일에서 메서드 어노테이션 전체 텍스트 가져오기
        method_annotations = self.get_annotation_text_from_file(
            cls.file_path, method.name, is_class=False
        )

        # ServiceIdMapping 어노테이션 찾기
        for annotation_name in method.annotations:
            if annotation_name == "ServiceIdMapping":
                # 파일에서 실제 어노테이션 텍스트 가져오기
                full_annotation = method_annotations.get(annotation_name, annotation_name)
                
                # HTTP 메서드는 "ServiceIdMapping"으로 설정
                http_method = "ServiceIdMapping"
                
                # ServiceIdMapping의 값 추출 (예: "txTSSAP04S1")
                method_path = self.extract_path_from_annotation(full_annotation)
                break  # ServiceIdMapping을 찾으면 종료

        if http_method and method_path:
            # class_path와 method_path 결합
            if class_path and method_path:
                # 둘 다 슬래시로 시작하면 하나 제거
                if class_path.endswith("/") and method_path.startswith("/"):
                    full_path = class_path + method_path[1:]
                elif not class_path.endswith("/") and not method_path.startswith("/"):
                    full_path = class_path + "/" + method_path
                else:
                    full_path = class_path + method_path
            elif class_path:
                full_path = class_path
            elif method_path:
                full_path = method_path
            else:
                full_path = ""

            method_signature = f"{cls.name}.{method.name}"

            return Endpoint(
                path=full_path,
                http_method=http_method,
                method_signature=method_signature,
                class_name=cls.name,
                method_name=method.name,
                file_path=cls.file_path,
            )

        return None

    def extract_path_from_annotation(self, annotation: str) -> Optional[str]:
        """
        어노테이션 문자열에서 path(value 또는 path 속성) 추출

        Args:
            annotation: 어노테이션 문자열 (예: "@ServiceIdMapping(\"txTSSAP04U1\")")

        Returns:
            Optional[str]: 추출된 path 또는 None
        """
        if not annotation:
            return None

        # value="/path" 또는 path="/path" 또는 "/path" 형식 추출
        patterns = [
            r'value\s*=\s*["\']([^"\']+)["\']',  # value="/path"
            r'path\s*=\s*["\']([^"\']+)["\']',  # path="/path"
            r'\(\s*["\']([^"\']+)["\']\s*\)',  # ("/path")
            r'\(\s*["\']([^"\']+)["\']',  # ("/path" (닫는 괄호 없을 수도)
        ]

        for pattern in patterns:
            match = re.search(pattern, annotation)
            if match:
                path = match.group(1)
                if path:
                    return path

        return None

    def extract_http_method_from_annotation(self, annotation: str) -> Optional[str]:
        """
        어노테이션에서 HTTP 메서드 추출

        Args:
            annotation: 어노테이션 문자열

        Returns:
            Optional[str]: HTTP 메서드 (GET, POST, PUT, DELETE, PATCH) 또는 None
        """
        if "ServiceIdMapping" in annotation:
            return "ServiceIdMapping"
        return None

    def classify_layer(self, cls: ClassInfo, method: Method) -> str:
        """
        클래스와 메서드의 레이어 분류 (MyBatis, JDBC, JPA 모두 지원)

        Args:
            cls: 클래스 정보
            method: 메서드 정보

        Returns:
            str: 레이어명 (Controller, Service, DAO, Repository, Mapper, Entity, Unknown)
        """
        # 어노테이션 기반 분류 (우선순위 높음)
        all_annotations = cls.annotations + method.annotations
        annotation_lower = [ann.lower() for ann in all_annotations]

        # Controller 레이어
        if any(
            "ServiceIdMapping" in ann for ann in annotation_lower
        ):
            return "SVC"

        # Service 레이어
        if any("Service" in ann for ann in annotation_lower):
            return "SVCImpl"

        if any("Repository" in ann for ann in annotation_lower):
            return "DEM_DAQ"

        # 클래스명 패턴 기반 분류
        class_name = cls.name
        for layer, patterns in self.LAYER_PATTERNS.items():
            for pattern in patterns:
                if pattern in class_name:
                    return layer

        # 패키지 기반 분류
        # TODO: 실제 코드를 보고 수정해야 함.
        package = cls.package.lower()
        if "controller" in package or "web" in package or "api" in package:
            return "Controller"
        elif "service" in package or "business" in package:
            return "Service"
        elif "mapper" in package or "mybatis" in package:
            return "Mapper"
        elif "repository" in package or "jpa" in package:
            return "Repository"
        elif "dao" in package or "data" in package:
            return "DAO"
        elif (
            "entity" in package
            or "domain" in package
            or "model" in package
            or "beans" in package
        ):
            return "Entity"

        # 필드 기반 추론 (JPA EntityManager, MyBatis SqlSession 등)
        # TODO: 실제 코드를 보고 수정해야 함.
        for class_field_info in cls.fields:
            field_type = class_field_info.get("type", "").lower()
            if "entitymanager" in field_type or "entitymanagerfactory" in field_type:
                return "Repository"  # JPA Repository로 추론
            elif "sqlsession" in field_type or "sqlsessiontemplate" in field_type:
                return "Mapper"  # MyBatis Mapper로 추론
            elif "jdbctemplate" in field_type or "datasource" in field_type:
                return "DAO"  # JDBC DAO로 추론

        return "Unknown"

    def get_class_level_path(self, cls: ClassInfo) -> str:
        """
        클래스 레벨 경로 추출

        Args:
            cls: 클래스 정보

        Returns:
            str: 클래스 레벨 경로 (빈 문자열일 수 있음)
        """
        class_path = ""

        # 파일에서 클래스 어노테이션 전체 텍스트 가져오기
        class_annotations = self.get_annotation_text_from_file(
            cls.file_path, cls.name, is_class=True
        )

        for annotation_name in cls.annotations:
            if annotation_name == "LocalName":
                # 파일에서 실제 어노테이션 텍스트 가져오기
                full_annotation = class_annotations.get(
                    annotation_name, annotation_name
                )
                # LocalName의 값 추출 (예: "활동 SVC")
                extracted_path = self.extract_path_from_annotation(full_annotation)
                if extracted_path:
                    class_path = extracted_path
                break

        return class_path

    def get_annotation_text_from_file(
        self, file_path: str, target_name: str, is_class: bool = True
    ) -> Dict[str, str]:
        """
        파일에서 어노테이션 전체 텍스트 추출 (주석 제외)

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
            try:
                with open(file_path, "r", encoding="euc-kr") as f:
                    source_code = f.read()
            except Exception:
                return annotation_map

        # 주석 제거
        source_code_no_comments = JavaUtils.remove_java_comments(source_code)

        if is_class:
            # 클래스 어노테이션 추출
            # class ClassName 또는 public class ClassName 앞의 어노테이션들 찾기
            pattern = rf"(?:@\w+(?:\([^)]*\))?\s*)+class\s+{re.escape(target_name)}\b"
            match = re.search(
                pattern, source_code_no_comments, re.MULTILINE | re.DOTALL
            )
            if match:
                # 매칭된 부분에서 어노테이션 추출
                matched_text = source_code_no_comments[: match.end()]
                # class 키워드 이전 부분
                before_class = matched_text[: matched_text.rfind("class")]
                # 어노테이션 패턴 찾기
                annotation_pattern = r"@(\w+)(\([^)]*\))?"
                for ann_match in re.finditer(annotation_pattern, before_class):
                    ann_name = ann_match.group(1)
                    ann_full = ann_match.group(0)
                    annotation_map[ann_name] = ann_full
        else:
            # 메서드 어노테이션 추출
            # 메서드 시그니처 앞의 어노테이션들 찾기
            pattern = rf"(?:@\w+(?:\([^()]*\))?\s*)+(?:public\s+|private\s+|protected\s+)?(?:static\s+)?(?:final\s+)?(?:[\w<>\[\],\s\.]+)?\s+{re.escape(target_name)}\s*\("
            match = re.search(
                pattern, source_code_no_comments, re.MULTILINE | re.DOTALL
            )
            if match:
                # 매칭된 부분에서 어노테이션 추출
                matched_text = source_code_no_comments[: match.end()]
                # 메서드명 이전 부분
                method_name_pos = matched_text.rfind(target_name)
                before_method = matched_text[:method_name_pos]
                # 어노테이션 패턴 찾기 (중첩 괄호 처리 개선)
                annotation_pattern = r"@(\w+)(\((?:[^()]|\([^()]*\))*\))?"
                for ann_match in re.finditer(
                    annotation_pattern, before_method, re.DOTALL
                ):
                    ann_name = ann_match.group(1)
                    ann_full = ann_match.group(0)
                    annotation_map[ann_name] = ann_full

        return annotation_map

