"""
AnyframeCCS Endpoint Extraction Strategy

AnyframeCCS 프레임워크를 위한 엔드포인트 추출 전략 구현입니다.
Spring MVC와 동일한 어노테이션 패턴을 사용하지만 레이어명이 다릅니다.

레이어 구조: CTL -> SVCImpl -> DQM -> DB
"""

import logging
from typing import List

from models.method import Method
from parser.java_ast_parser import ClassInfo

from .spring_mvc_endpoint_extraction import SpringMVCEndpointExtraction

logger = logging.getLogger(__name__)


class AnyframeCCSEndpointExtraction(SpringMVCEndpointExtraction):
    """
    AnyframeCCS 프레임워크 엔드포인트 추출 전략

    Spring MVC와 동일한 어노테이션(@RestController, @RequestMapping, @GetMapping 등)을 사용하지만
    레이어명이 CCS 프레임워크에 맞게 정의되어 있습니다.

    레이어 매핑:
        - CTL: Controller (@RestController, @API)
        - SVC: Service Interface
        - SVCImpl: Service Implementation (@Service)
        - DQM: Data Query Manager (@Repository) - DAO 역할
        - DVO/SVO: Value Objects
    """

    # AnyframeCCS 레이어 분류 패턴
    LAYER_PATTERNS = {
        # CTL: Controller 레이어
        "CTL": ["CTL", "Controller", "RestController", "WebController"],
        # SVC: Service 인터페이스
        "SVC": ["SVC"],
        # SVCImpl: Service 구현 클래스
        "SVCImpl": ["SVCImpl", "ServiceImpl"],
        # BIZ: Business Component (재사용 가능한 비즈니스 로직)
        "BIZ": ["BIZ"],
        # DQM: Data Query Manager (DAO 역할)
        "DQM": ["DQM", "DEM", "Repository", "DAO", "Dao"],
        # VO: Value Objects (DVO, SVO, BVO 통합)
        "DVO": ["DVO"],
        "SVO": ["SVO"],
        "BVO": ["BVO"],
    }

    def classify_layer(self, cls: ClassInfo, method: Method) -> str:
        """
        클래스와 메서드의 레이어 분류 (AnyframeCCS 특화)

        Args:
            cls: 클래스 정보
            method: 메서드 정보

        Returns:
            str: 레이어명 (CTL, SVC, SVCImpl, DQM, DVO, SVO, Unknown)
        """
        # 어노테이션 기반 분류 (우선순위 높음)
        all_annotations = cls.annotations + method.annotations
        annotation_set = set(all_annotations)

        # CTL 레이어 (Controller)
        if "RestController" in annotation_set or "Controller" in annotation_set:
            return "CTL"
        if "API" in annotation_set:
            return "CTL"

        # SVCImpl 레이어 (Service 구현)
        if "Service" in annotation_set:
            # 클래스명으로 인터페이스/구현 구분
            if "Impl" in cls.name or cls.name.endswith("SVCImpl"):
                return "SVCImpl"
            return "SVC"

        # DQM 레이어 (Data Query Manager)
        if "Repository" in annotation_set:
            return "DQM"

        # BIZ 레이어 (Business Component) - @Component + 클래스명에 BIZ 포함
        if "Component" in annotation_set:
            if "BIZ" in cls.name or "Biz" in cls.name:
                return "BIZ"
            # 패키지명으로도 확인
            package = cls.package.lower() if cls.package else ""
            if "biz" in package:
                return "BIZ"

        # 클래스명 패턴 기반 분류
        class_name = cls.name
        for layer, patterns in self.LAYER_PATTERNS.items():
            for pattern in patterns:
                # 패턴이 클래스명에 포함되어 있는지 확인
                if pattern in class_name:
                    # SVC vs SVCImpl 구분
                    if pattern == "SVC" and "Impl" in class_name:
                        return "SVCImpl"
                    return layer

        # 패키지 기반 분류
        package = cls.package.lower() if cls.package else ""
        if "ctl" in package or "controller" in package:
            return "CTL"
        elif "impl" in package and "svc" in package:
            return "SVCImpl"
        elif "biz" in package and "bvo" not in package:
            # biz/ 경로지만 bvo/가 아닌 경우 (BIZ 컴포넌트)
            return "BIZ"
        elif "svc" in package and "svo" not in package:
            # svc/ 경로지만 svo/가 아닌 경우
            return "SVC"
        elif "dqm" in package or "dem" in package or "dao" in package:
            return "DQM"
        elif "dvo" in package:
            return "DVO"
        elif "svo" in package:
            return "SVO"
        elif "bvo" in package:
            return "BVO"

        # 필드 기반 추론 (SqlSession 사용 시 DQM)
        for class_field_info in cls.fields:
            field_type = class_field_info.get("type", "").lower()
            if "sqlsession" in field_type or "sqlsessiontemplate" in field_type:
                return "DQM"

        return "Unknown"

    def get_layer_name_mapping(self) -> dict:
        """
        Spring MVC 레이어명을 AnyframeCCS 레이어명으로 매핑하는 딕셔너리 반환

        Returns:
            dict: {Spring MVC 레이어명: CCS 레이어명}
        """
        return {
            "Controller": "CTL",
            "Service": "SVCImpl",
            "Repository": "DQM",
            "Mapper": "DQM",
            "DAO": "DQM",
            "Entity": "DVO",
        }
