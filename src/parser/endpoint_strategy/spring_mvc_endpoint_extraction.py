"""
SpringMVC Endpoint Extraction Strategy

SpringMVC 프레임워크를 위한 엔드포인트 추출 전략 구현입니다.
기존 CallGraphBuilder의 SpringMVC 관련 코드를 이 클래스로 이동했습니다.
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


class SpringMVCEndpointExtraction(EndpointExtractionStrategy):
    """
    SpringMVC 프레임워크 엔드포인트 추출 전략

    SpringMVC 어노테이션 패턴을 사용하여 엔드포인트를 추출합니다.
    """

    # Spring MVC 어노테이션 패턴
    SPRING_ANNOTATIONS = {
        # Spring MVC
        "RequestMapping",
        "GetMapping",
        "PostMapping",
        "PutMapping",
        "DeleteMapping",
        "PatchMapping",
        "Controller",
        "RestController",
        # Spring Core
        "Service",
        "Repository",
        "Component",
        "Autowired",
        "Qualifier",
        # MyBatis
        "Mapper",
        "Select",
        "Insert",
        "Update",
        "Delete",
        "Param",
        # JPA
        "Entity",
        "Table",
        "Id",
        "GeneratedValue",
        "Column",
        "OneToMany",
        "ManyToOne",
        "OneToOne",
        "ManyToMany",
        "JoinColumn",
        "Query",
        "NamedQuery",
        "NamedQueries",
        "EntityManager",
        "PersistenceContext",
        # JDBC 관련 (직접 사용하는 경우는 어노테이션이 없을 수 있음)
        "Transactional",
    }

    # 레이어 분류 패턴
    LAYER_PATTERNS = {
        "Controller": ["Controller", "RestController", "WebController"],
        "Service": ["Service", "BusinessService", "ApplicationService"],
        "Repository": [
            "Repository",
            "JpaRepository",
            "CrudRepository",
            "DAO",
            "Dao",
            "JdbcDao",
            "JdbcTemplateDao",
        ],
        "Mapper": ["Mapper", "MyBatisMapper", "SqlMapper"],
        "Entity": ["Entity", "Domain", "Model", "POJO"],
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
        메서드에서 엔드포인트 정보 추출

        Args:
            cls: 클래스 정보
            method: 메서드 정보
            class_path: 클래스 레벨 경로

        Returns:
            Optional[Endpoint]: 엔드포인트 정보
        """
        http_method = None
        method_path = ""

        # 파일에서 메서드 어노테이션 전체 텍스트 가져오기
        method_annotations = self.get_annotation_text_from_file(
            cls.file_path, method.name, is_class=False
        )

        # 메서드 어노테이션 확인
        for annotation_name in method.annotations:
            # 파일에서 실제 어노테이션 텍스트 가져오기
            full_annotation = method_annotations.get(annotation_name, annotation_name)

            # HTTP 메서드 추출
            extracted_method = self.extract_http_method_from_annotation(
                full_annotation
            )
            if extracted_method:
                http_method = extracted_method
                # path 추출
                extracted_path = self.extract_path_from_annotation(full_annotation)
                if extracted_path:
                    method_path = extracted_path
                break  # 첫 번째 매칭되는 어노테이션 사용

        if http_method:
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
            annotation: 어노테이션 문자열 (예: "@GetMapping(\"/users\")" 또는 "@RequestMapping(value=\"/api\")")

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
        if "GetMapping" in annotation:
            return "GET"
        elif "PostMapping" in annotation:
            return "POST"
        elif "PutMapping" in annotation:
            return "PUT"
        elif "DeleteMapping" in annotation:
            return "DELETE"
        elif "PatchMapping" in annotation:
            return "PATCH"
        elif "RequestMapping" in annotation:
            # RequestMapping의 method 속성 확인
            method_match = re.search(
                r'method\s*=\s*RequestMethod\.(\w+)', annotation
            )
            if method_match:
                return method_match.group(1).upper()
            # method 속성이 없으면 기본값은 GET (실제로는 모든 메서드 허용이지만 여기서는 GET으로 처리)
            return "GET"
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
            "controller" in ann or "restcontroller" in ann for ann in annotation_lower
        ):
            return "Controller"

        # Service 레이어
        if any("service" in ann for ann in annotation_lower):
            return "Service"

        # MyBatis Mapper 레이어
        if any("mapper" in ann for ann in annotation_lower):
            return "Mapper"

        # JPA Repository 레이어
        if any("repository" in ann for ann in annotation_lower):
            return "Repository"

        # JPA Entity 레이어
        if any("entity" in ann or "table" in ann for ann in annotation_lower):
            return "Entity"

        # 클래스명 패턴 기반 분류
        class_name = cls.name
        for layer, patterns in self.LAYER_PATTERNS.items():
            for pattern in patterns:
                if pattern in class_name:
                    return layer

        # 인터페이스 기반 분류 (MyBatis Mapper 인터페이스 감지)
        if cls.interfaces:
            for interface in cls.interfaces:
                interface_lower = interface.lower()
                # MyBatis Mapper 인터페이스 패턴
                if "mapper" in interface_lower or "sqlmapper" in interface_lower:
                    return "Mapper"
                # JPA Repository 인터페이스 패턴
                if (
                    "repository" in interface_lower
                    or "jparepository" in interface_lower
                ):
                    return "Repository"
                # Spring Repository 인터페이스 패턴
                if (
                    "crudrepository" in interface_lower
                    or "pagerepository" in interface_lower
                ):
                    return "Repository"

        # 패키지 기반 분류
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
            if "RequestMapping" in annotation_name:
                # 파일에서 실제 어노테이션 텍스트 가져오기
                full_annotation = class_annotations.get(
                    annotation_name, annotation_name
                )
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

