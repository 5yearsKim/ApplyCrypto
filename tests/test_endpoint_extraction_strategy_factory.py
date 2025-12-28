"""
Endpoint Extraction Strategy Factory 테스트

다음 시나리오를 검증합니다:
1. SpringMVC 전략 생성
2. 지원하지 않는 framework_type에 대한 예외 처리
3. Factory가 올바른 전략 인스턴스를 생성하는지 확인
"""

import pytest
from unittest.mock import Mock

from parser.endpoint_strategy.endpoint_extraction_strategy_factory import (
    EndpointExtractionStrategyFactory,
)
from parser.endpoint_strategy.spring_mvc_strategy import SpringMVCStrategy


@pytest.fixture
def mock_java_parser():
    """Mock JavaASTParser"""
    return Mock()


@pytest.fixture
def mock_cache_manager():
    """Mock CacheManager"""
    return Mock()


def test_create_spring_mvc_strategy(mock_java_parser, mock_cache_manager):
    """SpringMVC 전략 생성 테스트"""
    strategy = EndpointExtractionStrategyFactory.create(
        framework_type="SpringMVC",
        java_parser=mock_java_parser,
        cache_manager=mock_cache_manager,
    )
    
    assert isinstance(strategy, SpringMVCStrategy)


def test_create_spring_mvc_strategy_case_insensitive(mock_java_parser, mock_cache_manager):
    """대소문자 구분 없이 SpringMVC 전략 생성"""
    strategy = EndpointExtractionStrategyFactory.create(
        framework_type="springmvc",
        java_parser=mock_java_parser,
        cache_manager=mock_cache_manager,
    )
    
    assert isinstance(strategy, SpringMVCStrategy)


def test_create_unsupported_framework_type(mock_java_parser, mock_cache_manager):
    """지원하지 않는 framework_type에 대한 예외 처리"""
    with pytest.raises(ValueError, match="Unsupported framework_type"):
        EndpointExtractionStrategyFactory.create(
            framework_type="UnsupportedFramework",
            java_parser=mock_java_parser,
            cache_manager=mock_cache_manager,
        )


def test_create_not_implemented_framework_types(mock_java_parser, mock_cache_manager):
    """아직 구현되지 않은 framework_type에 대한 예외 처리"""
    not_implemented_types = [
        "AnyframeSarangOn",
        "AnyframeOld",
        "AnyframeEtc",
        "SpringBatQrts",
        "AnyframeBatSarangOn",
        "AnyframeBatEtc",
    ]
    
    for framework_type in not_implemented_types:
        with pytest.raises(NotImplementedError):
            EndpointExtractionStrategyFactory.create(
                framework_type=framework_type,
                java_parser=mock_java_parser,
                cache_manager=mock_cache_manager,
            )

