"""
Config Migration 유틸리티

기존 config.json 파일의 필드명 변경 및 마이그레이션을 처리하는 유틸리티 모듈입니다.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

from .config_manager import ConfigurationError

logger = logging.getLogger(__name__)


class ConfigMigration:
    """
    Config 파일 마이그레이션 클래스
    
    기존 config.json 파일의 필드명 변경 및 값 변환을 처리합니다.
    """

    # diff_gen_type -> modification_type 마이그레이션 맵
    DIFF_GEN_TYPE_MIGRATION_MAP = {
        "mybatis_service": "ControllerOrService",
        "mybatis_typehandler": "TypeHandler",
        "mybatis_dao": "ServiceImplOrBiz",
        "call_chain": "ControllerOrService",
    }

    # framework_type 기본값
    DEFAULT_FRAMEWORK_TYPE = "SpringMVC"

    def __init__(self, config_file_path: str):
        """
        ConfigMigration 초기화

        Args:
            config_file_path: 마이그레이션할 config.json 파일 경로
        """
        self.config_file_path = Path(config_file_path)
        if not self.config_file_path.exists():
            raise ConfigurationError(f"설정 파일을 찾을 수 없습니다: {self.config_file_path}")

    def migrate(self, update_file: bool = False, backup: bool = True) -> Dict:
        """
        config.json 파일을 마이그레이션합니다.

        Args:
            update_file: True인 경우 파일을 실제로 업데이트 (기본값: False)
            backup: True인 경우 백업 파일 생성 (기본값: True)

        Returns:
            Dict: 마이그레이션 결과 정보
                - migrated: 마이그레이션이 필요한지 여부
                - changes: 변경된 필드 목록
                - old_values: 변경 전 값들
                - new_values: 변경 후 값들
                - backup_path: 백업 파일 경로 (생성된 경우)
        """
        # 파일 읽기
        with open(self.config_file_path, "r", encoding="utf-8") as f:
            config_data = json.load(f)

        changes = []
        old_values = {}
        new_values = {}
        migrated = False

        # 1. diff_gen_type -> modification_type 마이그레이션
        if "diff_gen_type" in config_data and "modification_type" not in config_data:
            diff_gen_type = config_data["diff_gen_type"]
            modification_type = self.DIFF_GEN_TYPE_MIGRATION_MAP.get(
                diff_gen_type, "ControllerOrService"
            )
            
            old_values["diff_gen_type"] = diff_gen_type
            new_values["modification_type"] = modification_type
            changes.append(
                f"diff_gen_type ({diff_gen_type}) -> modification_type ({modification_type})"
            )
            
            config_data["modification_type"] = modification_type
            if update_file:
                # diff_gen_type 제거
                del config_data["diff_gen_type"]
            migrated = True

        # 2. framework_type 기본값 추가
        if "framework_type" not in config_data:
            old_values["framework_type"] = None
            new_values["framework_type"] = self.DEFAULT_FRAMEWORK_TYPE
            changes.append(
                f"framework_type 추가 (기본값: {self.DEFAULT_FRAMEWORK_TYPE})"
            )
            
            config_data["framework_type"] = self.DEFAULT_FRAMEWORK_TYPE
            migrated = True

        # 3. generate_full_source -> generate_type 마이그레이션
        if "generate_full_source" in config_data:
            generate_full_source = config_data["generate_full_source"]
            # generate_full_source가 True이면 "full_source", False이면 "diff"
            # (기본값이 "diff"이므로 명시적으로 설정)
            if generate_full_source:
                generate_type = "full_source"
            else:
                generate_type = "diff"
            
            old_values["generate_full_source"] = generate_full_source
            new_values["generate_type"] = generate_type
            changes.append(
                f"generate_full_source ({generate_full_source}) -> generate_type ({generate_type})"
            )
            
            config_data["generate_type"] = generate_type
            if update_file:
                # generate_full_source 제거
                del config_data["generate_full_source"]
            migrated = True

        # 파일 업데이트
        backup_path = None
        if update_file and migrated:
            # 백업 생성
            if backup:
                backup_path = self._create_backup()
            
            # 파일 쓰기
            with open(self.config_file_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Config 파일이 업데이트되었습니다: {self.config_file_path}")

        return {
            "migrated": migrated,
            "changes": changes,
            "old_values": old_values,
            "new_values": new_values,
            "backup_path": backup_path,
        }

    def _create_backup(self) -> Path:
        """
        현재 config.json 파일의 백업을 생성합니다.

        Returns:
            Path: 백업 파일 경로
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.config_file_path.parent / f"{self.config_file_path.stem}_backup_{timestamp}.json"
        
        import shutil
        shutil.copy2(self.config_file_path, backup_path)
        
        logger.info(f"백업 파일이 생성되었습니다: {backup_path}")
        return backup_path

    def check_migration_needed(self) -> Tuple[bool, Dict]:
        """
        마이그레이션이 필요한지 확인합니다.

        Returns:
            Tuple[bool, Dict]: (마이그레이션 필요 여부, 변경 사항 정보)
        """
        result = self.migrate(update_file=False, backup=False)
        return result["migrated"], result

    def generate_migration_log(self, migration_result: Dict) -> str:
        """
        마이그레이션 로그를 생성합니다.

        Args:
            migration_result: migrate() 메서드의 반환값

        Returns:
            str: 마이그레이션 로그 문자열
        """
        log_lines = [
            "=" * 60,
            "Config Migration Log",
            "=" * 60,
            f"파일: {self.config_file_path}",
            f"마이그레이션 필요: {migration_result['migrated']}",
            "",
        ]

        if migration_result["migrated"]:
            log_lines.append("변경 사항:")
            for change in migration_result["changes"]:
                log_lines.append(f"  - {change}")
            
            log_lines.append("")
            log_lines.append("변경 전 값:")
            for key, value in migration_result["old_values"].items():
                log_lines.append(f"  - {key}: {value}")
            
            log_lines.append("")
            log_lines.append("변경 후 값:")
            for key, value in migration_result["new_values"].items():
                log_lines.append(f"  - {key}: {value}")
            
            if migration_result.get("backup_path"):
                log_lines.append("")
                log_lines.append(f"백업 파일: {migration_result['backup_path']}")
        else:
            log_lines.append("마이그레이션이 필요하지 않습니다.")

        log_lines.append("")
        log_lines.append("=" * 60)
        log_lines.append(f"생성 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        log_lines.append("=" * 60)

        return "\n".join(log_lines)


def migrate_config_file(
    config_file_path: str,
    update_file: bool = False,
    backup: bool = True,
    save_log: bool = True,
) -> Dict:
    """
    Config 파일을 마이그레이션하는 편의 함수

    Args:
        config_file_path: 마이그레이션할 config.json 파일 경로
        update_file: True인 경우 파일을 실제로 업데이트 (기본값: False)
        backup: True인 경우 백업 파일 생성 (기본값: True)
        save_log: True인 경우 마이그레이션 로그를 파일로 저장 (기본값: True)

    Returns:
        Dict: 마이그레이션 결과 정보
    """
    migrator = ConfigMigration(config_file_path)
    result = migrator.migrate(update_file=update_file, backup=backup)

    # 로그 저장
    if save_log and result["migrated"]:
        log_content = migrator.generate_migration_log(result)
        log_path = Path(config_file_path).parent / "migration_log.txt"
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(log_content)
        logger.info(f"마이그레이션 로그가 저장되었습니다: {log_path}")

    return result

