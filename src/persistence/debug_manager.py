"""
Debug Manager 모듈

디버깅 관련 파일들을 관리하고 저장합니다.
"""

import logging
import difflib
import shutil
import json
from pathlib import Path
from typing import Optional

from models.modification_plan import ModificationPlan
from config.config_manager import Configuration

class DebugManager:
    """
    디버그 관련 데이터 관리자 클래스
    
    주요 기능:
    1. Diff 파일 저장
    2. 디버그 로그 관리
    """
    
    def __init__(self, config: Configuration):
        """
        DebugManager 초기화
        
        Args:
            config: 설정 객체
        """
        self.config = config
        self.target_project = Path(config.target_project)
        self.generate_type = getattr(config, "generate_type", "diff")
        self.debug_dir = self.target_project / ".applycrypto" / "debug"
        self.diff_dir = self.debug_dir / "diffs"
        self.contexts_dir = self.debug_dir / "contexts"
        self.plans_dir = self.debug_dir / "plans"
        self.patch_dir = self.debug_dir / "patch"
        self.logger = logging.getLogger(__name__)
        
    def initialize_debug_directory(self) -> None:
        """디버그 디렉터리를 초기화(삭제 후 생성)"""
        try:
            if self.debug_dir.exists():
                shutil.rmtree(self.debug_dir)
            self.diff_dir.mkdir(parents=True, exist_ok=True)
            self.contexts_dir.mkdir(parents=True, exist_ok=True)
            self.plans_dir.mkdir(parents=True, exist_ok=True)
            self.patch_dir.mkdir(parents=True, exist_ok=True)
        except (OSError, PermissionError) as e:
            self.logger.error(f"디버그 디렉터리를 생성할 수 없습니다: {self.diff_dir} - {e}")

    def log_rejected_hunk(self, filename: str, hunk_detail: str, reason: str) -> None:
        """
        거부된 Hunk 정보를 파일로 저장 (파일명별로 append)
        
        Args:
            filename: 대상 파일명
            hunk_detail: Hunk 상세 내용
            reason: 거부 사유
        """
        try:
            # 파일명 생성: filename.rejected.txt
            save_path = self.patch_dir / f"{filename}.rejected.txt"
            
            # 구분선 및 내용
            separator = "=" * 50
            content = f"\n{separator}\nReason: {reason}\n{separator}\n{hunk_detail}\n"
            
            # append 모드로 저장
            with open(save_path, "a", encoding="utf-8") as f:
                f.write(content)
                
            self.logger.debug(f"Rejected hunk appended to: {save_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to append rejected hunk: {e}")

    def log_diff(self, backup_path: Optional[str], file_path: str) -> None:
        """
        변경 내용을 Diff 파일로 저장
        
        Args:
            backup_path: 백업 파일 경로 (원본)
            file_path: 수정된 파일 경로
        """
        try:
            # 파일 읽기
            original_content = ""
            if backup_path and Path(backup_path).exists():
                with open(backup_path, "r", encoding="utf-8") as f:
                    original_content = f.read()
            
            modified_content = ""
            if file_path and Path(file_path).exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    modified_content = f.read()

            if not modified_content and not original_content:
                return

            # 파일명 추출
            path_obj = Path(file_path)
            filename = path_obj.name
            diff_filename = f"{filename}.diff"
            save_path = self.diff_dir / diff_filename
            
            # 중복 파일명 처리
            counter = 1
            while save_path.exists():
                save_path = self.diff_dir / f"{filename}_{counter}.diff"
                counter += 1
            
            # Diff 생성 (항상 파일 내용 기반으로 생성)
            diff_content = self._generate_diff(modified_content, original_content, filename)
            
            # 내용이 있을 때만 저장
            if diff_content.strip():
                with open(save_path, "w", encoding="utf-8") as f:
                    f.write(diff_content)
                self.logger.debug(f"Diff 파일 저장 완료: {save_path}")
                
        except Exception as e:
            self.logger.error(f"Diff 파일 저장 중 오류 발생: {e}")

    def _generate_diff(self, modified_content: str, original_content: str, filename: str) -> str:
        """
        Diff 내용 생성
        
        Args:
            modified_content: 수정된 파일 내용
            original_content: 원본 파일 내용
            filename: 파일명 (헤더용)
            
        Returns:
            str: Unified Diff 문자열
        """
        # difflib 사용하여 Diff 생성
        # Trailing space 및 줄바꿈 차이를 무시하기 위해 rstrip() 후 \n 추가
        original_lines = [line.rstrip() + "\n" for line in original_content.splitlines()]
        modified_lines = [line.rstrip() + "\n" for line in modified_content.splitlines()]
        
        diff = difflib.unified_diff(
            original_lines,
            modified_lines,
            fromfile=str(filename),
            tofile=str(filename),
            lineterm=""
        )
        
        diff_content = "".join(diff)
                    
        return diff_content

    def log_contexts(self, contexts: list, filename: Optional[str] = None) -> None:
        """
        컨텍스트 정보를 JSON 파일로 저장
        
        Args:
            contexts: 저장할 컨텍스트 리스트
            filename: 저장할 파일명 (None일 경우 contexts_1.json, contexts_2.json ... 순으로 생성)
        """
        try:
            if not filename:
                counter = 1
                while True:
                    candidate = f"contexts_{counter}.json"
                    save_path = self.contexts_dir / candidate
                    if not save_path.exists():
                        break
                    counter += 1
            else:
                save_path = self.contexts_dir / filename
                
            # JSON 직렬화를 위한 변환
            def json_serial(obj):
                """JSON serializer for objects not serializable by default json code"""
                if hasattr(obj, '__dict__'):
                    return obj.__dict__
                return str(obj)

            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(contexts, f, indent=2, ensure_ascii=False, default=json_serial)
                
            self.logger.debug(f"컨텍스트 저장 완료: {save_path}")
            
        except Exception as e:
            self.logger.error(f"컨텍스트 저장 중 오류 발생: {e}")

    def log_plans(self, plans: list, table_name: str) -> None:
        """
        ModificationPlan 정보를 JSON 및 TXT 파일로 저장
        
        Args:
            plans: 저장할 ModificationPlan 리스트
            table_name: 테이블명 (파일명 생성용)
        """
        try:
            # 파일명 결정 (JSON 파일 기준)
            counter = 1
            while True:
                candidate_json = f"plan_{table_name}_{counter}.json"
                save_path_json = self.plans_dir / candidate_json
                if not save_path_json.exists():
                    break
                counter += 1
            
            # JSON 저장
            def json_serial(obj):
                """JSON serializer for objects not serializable by default json code"""
                if hasattr(obj, '__dict__'):
                    return obj.__dict__
                return str(obj)

            with open(save_path_json, "w", encoding="utf-8") as f:
                json.dump(plans, f, indent=2, ensure_ascii=False, default=json_serial)

            # TXT 저장
            candidate_txt = f"plan_{table_name}_{counter}.txt"
            save_path_txt = self.plans_dir / candidate_txt
            
            with open(save_path_txt, "w", encoding="utf-8") as f:
                for plan in plans:
                    # 객체 또는 딕셔너리 처리
                    if hasattr(plan, 'file_path'):
                        file_path = plan.file_path
                        modified_code = plan.modified_code
                    else:
                        file_path = plan.get('file_path')
                        modified_code = plan.get('modified_code')

                    f.write(f"====file: \"{file_path}\" ====\n\n")
                    if modified_code:
                        f.write(str(modified_code))
                    f.write("\n\n")
                
            self.logger.debug(f"계획 저장 완료: {save_path_json}, {save_path_txt}")
            
        except Exception as e:
            self.logger.error(f"계획 저장 중 오류 발생: {e}")
