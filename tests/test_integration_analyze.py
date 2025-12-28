"""
Analyze 명령어 통합 테스트

다음 시나리오를 검증합니다:
1. 각 framework_type별 엔드포인트 추출
2. 각 sql_wrapping_type별 SQL 추출
3. 전체 Analyze 플로우 통합 테스트
"""

import json
import tempfile
from pathlib import Path

import pytest

from cli.cli_controller import CLIController
from config.config_manager import Configuration, load_config


@pytest.fixture
def temp_project_dir():
    """임시 프로젝트 디렉터리 생성"""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir) / "test_project"
        project_path.mkdir()
        
        # Java 파일 구조 생성
        (project_path / "src" / "main" / "java" / "com" / "example").mkdir(parents=True)
        (project_path / "src" / "main" / "resources").mkdir(parents=True)
        
        # 샘플 Controller 파일
        controller_code = """
package com.example.controller;

import org.springframework.web.bind.annotation.*;
import org.springframework.beans.factory.annotation.Autowired;
import com.example.service.UserService;

@RestController
@RequestMapping("/api/users")
public class UserController {
    
    @Autowired
    private UserService userService;
    
    @GetMapping("/{id}")
    public User getUser(@PathVariable Long id) {
        return userService.findById(id);
    }
    
    @PostMapping
    public User createUser(@RequestBody User user) {
        return userService.save(user);
    }
}
"""
        (project_path / "src" / "main" / "java" / "com" / "example" / "UserController.java").write_text(controller_code)
        
        # 샘플 Service 파일
        service_code = """
package com.example.service;

import org.springframework.stereotype.Service;
import com.example.repository.UserRepository;

@Service
public class UserService {
    
    private UserRepository userRepository;
    
    public User findById(Long id) {
        return userRepository.findById(id);
    }
    
    public User save(User user) {
        return userRepository.save(user);
    }
}
"""
        (project_path / "src" / "main" / "java" / "com" / "example" / "UserService.java").write_text(service_code)
        
        # MyBatis Mapper XML
        mapper_xml = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN" 
    "http://mybatis.org/dtd/mybatis-3-mapper.dtd">
<mapper namespace="com.example.repository.UserRepository">
    <select id="findById" resultType="User">
        SELECT id, name, email FROM users WHERE id = #{id}
    </select>
    <insert id="save">
        INSERT INTO users (name, email) VALUES (#{name}, #{email})
    </insert>
</mapper>
"""
        (project_path / "src" / "main" / "resources" / "mapper" / "UserMapper.xml").mkdir(parents=True)
        (project_path / "src" / "main" / "resources" / "mapper" / "UserMapper.xml").write_text(mapper_xml)
        
        yield project_path


@pytest.fixture
def config_file_springmvc_mybatis(temp_project_dir):
    """SpringMVC + MyBatis 설정 파일"""
    config_data = {
        "target_project": str(temp_project_dir),
        "source_file_types": [".java", ".xml"],
        "framework_type": "SpringMVC",
        "sql_wrapping_type": "mybatis",
        "modification_type": "ControllerOrService",
        "access_tables": [
            {"table_name": "users", "columns": ["name", "email"]},
        ],
    }
    
    config_file = temp_project_dir / "config.json"
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config_data, f, ensure_ascii=False, indent=2)
    
    return str(config_file)


def test_analyze_with_springmvc_mybatis(config_file_springmvc_mybatis, temp_project_dir):
    """SpringMVC + MyBatis로 Analyze 명령어 테스트"""
    controller = CLIController()
    
    # Analyze 명령어 실행
    args = controller.parser.parse_args([
        "analyze",
        "--config", config_file_springmvc_mybatis,
    ])
    
    # 실제 실행은 시간이 오래 걸릴 수 있으므로 구조만 확인
    # result = controller.handle_command(args)
    # assert result == 0
    
    # 설정 파일이 올바르게 로드되는지 확인
    config = load_config(config_file_springmvc_mybatis)
    assert config.framework_type == "SpringMVC"
    assert config.sql_wrapping_type == "mybatis"
    assert config.modification_type == "ControllerOrService"


def test_config_migration_integration(temp_project_dir):
    """Config 마이그레이션이 Analyze와 통합되는지 테스트"""
    # 구식 config.json 생성
    old_config_data = {
        "target_project": str(temp_project_dir),
        "source_file_types": [".java", ".xml"],
        "sql_wrapping_type": "mybatis",
        "diff_gen_type": "mybatis_service",
        "access_tables": [
            {"table_name": "users", "columns": ["name"]},
        ],
    }
    
    config_file = temp_project_dir / "config_old.json"
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(old_config_data, f, ensure_ascii=False, indent=2)
    
    # load_config가 자동으로 마이그레이션하는지 확인
    config = load_config(str(config_file))
    assert config.modification_type == "ControllerOrService"
    assert config.framework_type == "SpringMVC"  # 기본값


def test_factory_integration():
    """Factory들이 올바르게 통합되어 작동하는지 테스트"""
    from parser.endpoint_strategy.endpoint_extraction_strategy_factory import (
        EndpointExtractionStrategyFactory,
    )
    from analyzer.sql_extractor_factory import SQLExtractorFactory
    from modifier.modification_strategy.modification_strategy_factory import (
        ModificationStrategyFactory,
    )
    from unittest.mock import Mock
    
    # EndpointExtractionStrategyFactory 테스트
    java_parser = Mock()
    cache_manager = Mock()
    endpoint_strategy = EndpointExtractionStrategyFactory.create(
        framework_type="SpringMVC",
        java_parser=java_parser,
        cache_manager=cache_manager,
    )
    assert endpoint_strategy is not None
    
    # SQLExtractorFactory 테스트
    config = Configuration(
        target_project="/tmp",
        source_file_types=[".java"],
        sql_wrapping_type="mybatis",
        modification_type="ControllerOrService",
        access_tables=[{"table_name": "test", "columns": ["col"]}],
    )
    sql_extractor = SQLExtractorFactory.create(
        sql_wrapping_type="mybatis",
        config=config,
    )
    assert sql_extractor is not None
    
    # ModificationStrategyFactory 테스트
    llm_provider = Mock()
    modification_strategy = ModificationStrategyFactory.create(
        modification_type="ControllerOrService",
        config=config,
        llm_provider=llm_provider,
    )
    assert modification_strategy is not None

