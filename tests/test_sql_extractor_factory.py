"""
SQL Extractor Factory 테스트

다음 시나리오를 검증합니다:
1. MyBatis, JDBC, JPA Extractor 생성
2. 지원하지 않는 sql_wrapping_type에 대한 예외 처리
3. LLM Extractor 통합 확인
"""

import pytest
from unittest.mock import Mock, MagicMock

from analyzer.sql_extractor_factory import SQLExtractorFactory
from analyzer.mybatis_sql_extractor import MyBatisSQLExtractor
from analyzer.jdbc_sql_extractor import JDBCSQLExtractor
from analyzer.jpa_sql_extractor import JPASQLExtractor
from config.config_manager import Configuration


@pytest.fixture
def sample_config():
    """샘플 Configuration 객체"""
    return Configuration(
        target_project="/path/to/project",
        source_file_types=[".java", ".xml"],
        sql_wrapping_type="mybatis",
        modification_type="ControllerOrService",
        access_tables=[
            {"table_name": "EMPLOYEE", "columns": ["NAME"]},
        ],
    )


@pytest.fixture
def mock_xml_parser():
    """Mock XMLMapperParser"""
    return Mock()


@pytest.fixture
def mock_java_parser():
    """Mock JavaASTParser"""
    return Mock()


def test_create_mybatis_extractor(sample_config, mock_xml_parser):
    """MyBatis Extractor 생성 테스트"""
    sample_config.sql_wrapping_type = "mybatis"
    
    extractor = SQLExtractorFactory.create(
        sql_wrapping_type="mybatis",
        config=sample_config,
        xml_parser=mock_xml_parser,
    )
    
    assert isinstance(extractor, MyBatisSQLExtractor)


def test_create_jdbc_extractor(sample_config, mock_java_parser):
    """JDBC Extractor 생성 테스트"""
    sample_config.sql_wrapping_type = "jdbc"
    
    extractor = SQLExtractorFactory.create(
        sql_wrapping_type="jdbc",
        config=sample_config,
        java_parser=mock_java_parser,
    )
    
    assert isinstance(extractor, JDBCSQLExtractor)


def test_create_jpa_extractor(sample_config, mock_java_parser):
    """JPA Extractor 생성 테스트"""
    sample_config.sql_wrapping_type = "jpa"
    
    extractor = SQLExtractorFactory.create(
        sql_wrapping_type="jpa",
        config=sample_config,
        java_parser=mock_java_parser,
    )
    
    assert isinstance(extractor, JPASQLExtractor)


def test_create_extractor_case_insensitive(sample_config, mock_xml_parser):
    """대소문자 구분 없이 Extractor 생성"""
    extractor = SQLExtractorFactory.create(
        sql_wrapping_type="MYBATIS",
        config=sample_config,
        xml_parser=mock_xml_parser,
    )
    
    assert isinstance(extractor, MyBatisSQLExtractor)


def test_create_unsupported_sql_wrapping_type(sample_config):
    """지원하지 않는 sql_wrapping_type에 대한 예외 처리"""
    with pytest.raises(ValueError, match="Unsupported sql_wrapping_type"):
        SQLExtractorFactory.create(
            sql_wrapping_type="unsupported",
            config=sample_config,
        )


def test_create_extractor_with_llm(sample_config, mock_xml_parser):
    """LLM 파서가 활성화된 경우 Extractor 생성"""
    sample_config.use_llm_parser = True
    sample_config.llm_provider = "mock"
    
    extractor = SQLExtractorFactory.create(
        sql_wrapping_type="mybatis",
        config=sample_config,
        xml_parser=mock_xml_parser,
    )
    
    assert isinstance(extractor, MyBatisSQLExtractor)
    # LLM Extractor가 내부적으로 사용되는지 확인
    assert hasattr(extractor, 'llm_extractor') or extractor.llm_extractor is not None

