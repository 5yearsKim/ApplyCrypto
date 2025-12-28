"""
Config Migration 단위 테스트

다음 시나리오를 검증합니다:
1. diff_gen_type을 modification_type으로 변환
2. framework_type 기본값 추가
3. 마이그레이션 로그 생성
4. 백업 파일 생성
5. 파일 업데이트
"""

import json
import tempfile
from pathlib import Path

import pytest

from config.config_migration import ConfigMigration, migrate_config_file
from config.config_manager import ConfigurationError


@pytest.fixture
def temp_config_file_with_diff_gen_type():
    """diff_gen_type이 있는 임시 설정 파일 생성"""
    config_data = {
        "target_project": "/path/to/project",
        "source_file_types": [".java", ".xml"],
        "sql_wrapping_type": "mybatis",
        "diff_gen_type": "mybatis_service",
        "access_tables": [
            {"table_name": "EMPLOYEE", "columns": ["NAME", "JUMIN_NUMBER"]},
        ],
    }
    
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config_data, f, ensure_ascii=False, indent=2)
        temp_path = f.name
    
    yield temp_path
    
    # 테스트 후 파일 삭제
    Path(temp_path).unlink(missing_ok=True)


@pytest.fixture
def temp_config_file_without_framework_type():
    """framework_type이 없는 임시 설정 파일 생성"""
    config_data = {
        "target_project": "/path/to/project",
        "source_file_types": [".java", ".xml"],
        "sql_wrapping_type": "mybatis",
        "modification_type": "ControllerOrService",
        "access_tables": [
            {"table_name": "EMPLOYEE", "columns": ["NAME"]},
        ],
    }
    
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config_data, f, ensure_ascii=False, indent=2)
        temp_path = f.name
    
    yield temp_path
    
    Path(temp_path).unlink(missing_ok=True)


@pytest.fixture
def temp_config_file_already_migrated():
    """이미 마이그레이션된 설정 파일 생성"""
    config_data = {
        "target_project": "/path/to/project",
        "source_file_types": [".java", ".xml"],
        "sql_wrapping_type": "mybatis",
        "framework_type": "SpringMVC",
        "modification_type": "ControllerOrService",
        "access_tables": [
            {"table_name": "EMPLOYEE", "columns": ["NAME"]},
        ],
    }
    
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config_data, f, ensure_ascii=False, indent=2)
        temp_path = f.name
    
    yield temp_path
    
    Path(temp_path).unlink(missing_ok=True)


def test_migration_needed_with_diff_gen_type(temp_config_file_with_diff_gen_type):
    """diff_gen_type이 있는 경우 마이그레이션 필요 확인"""
    migrator = ConfigMigration(temp_config_file_with_diff_gen_type)
    needed, result = migrator.check_migration_needed()
    
    assert needed is True
    assert "diff_gen_type" in result["old_values"]
    assert "modification_type" in result["new_values"]
    assert result["new_values"]["modification_type"] == "ControllerOrService"


def test_migration_needed_without_framework_type(temp_config_file_without_framework_type):
    """framework_type이 없는 경우 마이그레이션 필요 확인"""
    migrator = ConfigMigration(temp_config_file_without_framework_type)
    needed, result = migrator.check_migration_needed()
    
    assert needed is True
    assert result["new_values"]["framework_type"] == "SpringMVC"


def test_migration_not_needed(temp_config_file_already_migrated):
    """이미 마이그레이션된 파일은 마이그레이션 불필요"""
    migrator = ConfigMigration(temp_config_file_already_migrated)
    needed, result = migrator.check_migration_needed()
    
    assert needed is False
    assert len(result["changes"]) == 0


def test_migrate_without_file_update(temp_config_file_with_diff_gen_type):
    """파일 업데이트 없이 마이그레이션 확인"""
    migrator = ConfigMigration(temp_config_file_with_diff_gen_type)
    result = migrator.migrate(update_file=False, backup=False)
    
    assert result["migrated"] is True
    assert "modification_type" in result["new_values"]
    
    # 원본 파일 확인 (변경되지 않아야 함)
    with open(temp_config_file_with_diff_gen_type, "r", encoding="utf-8") as f:
        original_data = json.load(f)
    
    assert "diff_gen_type" in original_data
    assert "modification_type" not in original_data


def test_migrate_with_file_update(temp_config_file_with_diff_gen_type):
    """파일 업데이트와 함께 마이그레이션"""
    migrator = ConfigMigration(temp_config_file_with_diff_gen_type)
    result = migrator.migrate(update_file=True, backup=False)
    
    assert result["migrated"] is True
    
    # 업데이트된 파일 확인
    with open(temp_config_file_with_diff_gen_type, "r", encoding="utf-8") as f:
        updated_data = json.load(f)
    
    assert "modification_type" in updated_data
    assert updated_data["modification_type"] == "ControllerOrService"
    assert "diff_gen_type" not in updated_data


def test_migrate_with_backup(temp_config_file_with_diff_gen_type):
    """백업과 함께 마이그레이션"""
    migrator = ConfigMigration(temp_config_file_with_diff_gen_type)
    result = migrator.migrate(update_file=True, backup=True)
    
    assert result["migrated"] is True
    assert result["backup_path"] is not None
    assert Path(result["backup_path"]).exists()
    
    # 백업 파일 삭제
    Path(result["backup_path"]).unlink(missing_ok=True)


def test_migration_map_all_values(temp_config_file_with_diff_gen_type):
    """모든 diff_gen_type 값이 올바르게 변환되는지 확인"""
    migration_map = {
        "mybatis_service": "ControllerOrService",
        "mybatis_typehandler": "TypeHandler",
        "mybatis_dao": "ServiceImplOrBiz",
        "call_chain": "ControllerOrService",
    }
    
    for diff_gen_type, expected_modification_type in migration_map.items():
        # 임시 파일 생성
        config_data = {
            "target_project": "/path/to/project",
            "source_file_types": [".java"],
            "sql_wrapping_type": "mybatis",
            "diff_gen_type": diff_gen_type,
            "access_tables": [{"table_name": "TEST", "columns": ["COL"]}],
        }
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
            temp_path = f.name
        
        try:
            migrator = ConfigMigration(temp_path)
            result = migrator.migrate(update_file=False, backup=False)
            
            assert result["new_values"]["modification_type"] == expected_modification_type
        finally:
            Path(temp_path).unlink(missing_ok=True)


def test_generate_migration_log(temp_config_file_with_diff_gen_type):
    """마이그레이션 로그 생성 테스트"""
    migrator = ConfigMigration(temp_config_file_with_diff_gen_type)
    result = migrator.migrate(update_file=False, backup=False)
    log = migrator.generate_migration_log(result)
    
    assert "Config Migration Log" in log
    assert "diff_gen_type" in log
    assert "modification_type" in log
    assert "변경 사항:" in log


def test_migrate_config_file_convenience_function(temp_config_file_with_diff_gen_type):
    """편의 함수 테스트"""
    result = migrate_config_file(
        temp_config_file_with_diff_gen_type,
        update_file=True,
        backup=False,
        save_log=False,
    )
    
    assert result["migrated"] is True
    assert "modification_type" in result["new_values"]


def test_migration_invalid_file():
    """존재하지 않는 파일에 대한 예외 처리"""
    with pytest.raises(ConfigurationError):
        ConfigMigration("/nonexistent/file.json")

