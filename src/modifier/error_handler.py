"""
Error Handler 모듈

에러 처리, 롤백, 재시도 로직을 구현하는 모듈입니다.
"""

import logging
import shutil
import time
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class ErrorHandler:
    """
    에러 처리 클래스

    LLM API 오류, 프롬프트 생성 오류, 코드 수정 적용 오류를 처리하고,
    재시도 및 롤백 기능을 제공합니다.
    """

    def __init__(
        self,
        max_retries: int = 3,
        initial_backoff: float = 1.0,
        max_backoff: float = 60.0,
        backoff_multiplier: float = 2.0,
    ):
        """
        ErrorHandler 초기화

        Args:
            max_retries: 최대 재시도 횟수 (기본값: 3)
            initial_backoff: 초기 백오프 시간 (초, 기본값: 1.0)
            max_backoff: 최대 백오프 시간 (초, 기본값: 60.0)
            backoff_multiplier: 백오프 배수 (기본값: 2.0)
        """
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        self.max_backoff = max_backoff
        self.backoff_multiplier = backoff_multiplier

        # 롤백을 위한 파일 백업 저장소
        self._backup_files: Dict[str, Path] = {}

    def retry_with_backoff(
        self, func: Callable, *args, **kwargs
    ) -> Tuple[Any, Optional[Exception]]:
        """
        지수 백오프 전략으로 함수를 재시도합니다.

        Args:
            func: 재시도할 함수
            *args: 함수 인자
            **kwargs: 함수 키워드 인자

        Returns:
            Tuple[Any, Optional[Exception]]: (함수 결과, 마지막 에러)
        """
        last_error = None
        backoff = self.initial_backoff

        for attempt in range(self.max_retries + 1):
            try:
                result = func(*args, **kwargs)
                if attempt > 0:
                    logger.info(
                        f"재시도 성공 (시도 {attempt + 1}/{self.max_retries + 1})"
                    )
                return result, None

            except Exception as e:
                last_error = e
                logger.warning(
                    f"함수 실행 실패 (시도 {attempt + 1}/{self.max_retries + 1}): {e}"
                )

                if attempt < self.max_retries:
                    # 백오프 시간 계산
                    wait_time = min(backoff, self.max_backoff)
                    logger.info(f"{wait_time:.2f}초 후 재시도...")
                    time.sleep(wait_time)

                    # 다음 백오프 시간 계산
                    backoff *= self.backoff_multiplier
                else:
                    logger.error(f"최대 재시도 횟수 초과: {e}")

        return None, last_error

    def backup_file(self, file_path: Path) -> bool:
        """
        파일을 백업합니다.

        Args:
            file_path: 백업할 파일 경로

        Returns:
            bool: 백업 성공 여부
        """
        try:
            if not file_path.exists():
                logger.warning(f"백업할 파일이 존재하지 않습니다: {file_path}")
                return False

            # 백업 파일 경로 생성
            backup_path = file_path.with_suffix(file_path.suffix + ".backup")

            # 백업
            shutil.copy2(file_path, backup_path)

            # 백업 정보 저장
            self._backup_files[str(file_path)] = backup_path

            logger.debug(f"파일 백업 완료: {file_path} -> {backup_path}")
            return True

        except Exception as e:
            logger.error(f"파일 백업 실패: {file_path} - {e}")
            return False

    def restore_file(self, file_path: Path) -> bool:
        """
        백업된 파일을 복원합니다.

        Args:
            file_path: 복원할 파일 경로

        Returns:
            bool: 복원 성공 여부
        """
        try:
            backup_path = self._backup_files.get(str(file_path))
            if not backup_path or not backup_path.exists():
                logger.warning(f"복원할 백업 파일이 없습니다: {file_path}")
                return False

            # 복원
            shutil.copy2(backup_path, file_path)

            logger.info(f"파일 복원 완료: {backup_path} -> {file_path}")
            return True

        except Exception as e:
            logger.error(f"파일 복원 실패: {file_path} - {e}")
            return False

    def cleanup_backups(self, keep_backups: bool = False):
        """
        백업 파일을 정리합니다.

        Args:
            keep_backups: 백업 파일을 유지할지 여부 (기본값: False)
        """
        if keep_backups:
            logger.debug("백업 파일을 유지합니다.")
            return

        for file_path_str, backup_path in self._backup_files.items():
            try:
                if backup_path.exists():
                    backup_path.unlink()
                    logger.debug(f"백업 파일 삭제: {backup_path}")
            except Exception as e:
                logger.warning(f"백업 파일 삭제 실패: {backup_path} - {e}")

        self._backup_files.clear()
        logger.debug("백업 파일 정리 완료")

    def handle_llm_error(
        self, error: Exception, retry_func: Optional[Callable] = None
    ) -> Tuple[bool, Optional[Any]]:
        """
        LLM API 오류를 처리합니다.

        Args:
            error: 발생한 오류
            retry_func: 재시도할 함수 (선택적)

        Returns:
            Tuple[bool, Optional[Any]]: (처리 성공 여부, 재시도 결과)
        """
        error_type = type(error).__name__
        error_msg = str(error)

        logger.error(f"LLM API 오류 발생: {error_type} - {error_msg}")

        # 재시도 가능한 오류인지 확인
        retryable_errors = [
            "ConnectionError",
            "TimeoutError",
            "RateLimitError",
            "ServiceUnavailableError",
        ]

        if any(retryable in error_type for retryable in retryable_errors):
            logger.info("재시도 가능한 오류입니다. 재시도합니다...")

            if retry_func:
                result, last_error = self.retry_with_backoff(retry_func)
                if last_error is None:
                    return True, result
                else:
                    return False, None
            else:
                return False, None
        else:
            logger.error("재시도 불가능한 오류입니다.")
            return False, None

    def handle_prompt_error(self, error: Exception) -> bool:
        """
        프롬프트 생성 오류를 처리합니다.

        Args:
            error: 발생한 오류

        Returns:
            bool: 처리 성공 여부
        """
        error_type = type(error).__name__
        error_msg = str(error)

        logger.error(f"프롬프트 생성 오류: {error_type} - {error_msg}")

        # 프롬프트 생성 오류는 일반적으로 재시도 불가능
        return False

    def handle_patch_error(self, error: Exception, file_path: Path) -> bool:
        """
        코드 수정 적용 오류를 처리하고 롤백합니다.

        Args:
            error: 발생한 오류
            file_path: 수정 실패한 파일 경로

        Returns:
            bool: 롤백 성공 여부
        """
        error_type = type(error).__name__
        error_msg = str(error)

        logger.error(f"코드 수정 적용 오류: {error_type} - {error_msg}")
        logger.info(f"파일 롤백 시도: {file_path}")

        # 롤백
        success = self.restore_file(file_path)

        if success:
            logger.info(f"파일 롤백 성공: {file_path}")
        else:
            logger.error(f"파일 롤백 실패: {file_path}")

        return success


def retry_on_error(max_retries: int = 3):
    """
    함수에 재시도 로직을 추가하는 데코레이터

    Args:
        max_retries: 최대 재시도 횟수
    """

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            error_handler = ErrorHandler(max_retries=max_retries)
            result, error = error_handler.retry_with_backoff(func, *args, **kwargs)

            if error:
                raise error

            return result

        return wrapper

    return decorator
