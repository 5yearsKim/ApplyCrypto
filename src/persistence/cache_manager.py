"""
Cache Manager 모듈

분석 결과를 캐싱하여 재분석 시 성능을 향상시키는 캐시 관리자입니다.
"""

import hashlib
import logging
import pickle
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

# tree_sitter.Tree 타입 확인을 위한 임포트 (선택적)
try:
    from tree_sitter import Tree as TreeSitterTree

    HAS_TREE_SITTER = True
except ImportError:
    HAS_TREE_SITTER = False
    TreeSitterTree = None


class CacheManager:
    """
    캐시 관리자 클래스

    메모리 캐시와 디스크 캐시를 지원하며, 캐시 만료 정책을 구현합니다.
    """

    def __init__(
        self,
        cache_dir: Path,
        memory_cache_size: int = 100,
        cache_expiry_hours: int = 24,
    ):
        """
        CacheManager 초기화

        Args:
            cache_dir: 캐시 디렉터리 경로
            memory_cache_size: 메모리 캐시 최대 크기 (항목 수)
            cache_expiry_hours: 캐시 만료 시간 (시간)
        """
        self.cache_dir = Path(cache_dir)
        self.memory_cache: Dict[str, Dict[str, Any]] = {}
        self.memory_cache_size = memory_cache_size
        self.cache_expiry = timedelta(hours=cache_expiry_hours)
        self.logger = logging.getLogger(__name__)

        # 캐시 디렉터리 생성
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_key(self, file_path: Path) -> str:
        """
        파일 경로와 수정 시간을 기반으로 캐시 키 생성

        Args:
            file_path: 파일 경로 (Path 객체 또는 문자열)

        Returns:
            str: 캐시 키
        """
        # Path 객체로 변환 (SourceFile 객체가 전달될 수 있으므로 path 속성 확인)
        if hasattr(file_path, "path"):
            # SourceFile 객체인 경우 path 속성 사용
            file_path = Path(file_path.path)
        else:
            file_path = Path(file_path)

        try:
            stat = file_path.stat()
            # 파일 경로와 수정 시간을 조합하여 해시 생성
            key_data = f"{file_path}:{stat.st_mtime}"
            return hashlib.md5(key_data.encode()).hexdigest()
        except OSError:
            # 파일이 없거나 접근 불가능한 경우 경로만 사용
            return hashlib.md5(str(file_path).encode()).hexdigest()

    def _get_cache_file_path(self, cache_key: str) -> Path:
        """캐시 파일 경로 생성"""
        return self.cache_dir / f"{cache_key}.cache"

    def get_cached_result(self, file_path: Path) -> Optional[Any]:
        """
        캐시된 결과 조회

        Args:
            file_path: 원본 파일 경로 (Path 객체 또는 문자열)

        Returns:
            캐시된 결과 (없으면 None)
        """
        # Path 객체로 변환 (SourceFile 객체가 전달될 수 있으므로 path 속성 확인)
        if hasattr(file_path, "path"):
            # SourceFile 객체인 경우 path 속성 사용
            file_path = Path(file_path.path)
        else:
            file_path = Path(file_path)

        cache_key = self._get_cache_key(file_path)

        # 메모리 캐시 확인
        if cache_key in self.memory_cache:
            cache_entry = self.memory_cache[cache_key]
            if self._is_cache_valid(cache_entry, file_path):
                self.logger.debug(f"메모리 캐시에서 조회: {file_path}")
                return cache_entry["data"]
            else:
                # 만료된 캐시 제거
                del self.memory_cache[cache_key]

        # 디스크 캐시 확인 (tree_sitter.Tree 객체는 디스크에 저장되지 않으므로 메모리 캐시만 확인)
        # Tree 객체는 메모리 캐시에만 저장되므로 디스크 캐시 확인은 선택적
        cache_file = self._get_cache_file_path(cache_key)
        if cache_file.exists():
            try:
                with open(cache_file, "rb") as f:
                    cache_entry = pickle.load(f)

                if self._is_cache_valid(cache_entry, file_path):
                    # 메모리 캐시에도 저장
                    self._add_to_memory_cache(cache_key, cache_entry)
                    self.logger.debug(f"디스크 캐시에서 조회: {file_path}")
                    return cache_entry["data"]
                else:
                    # 만료된 캐시 파일 삭제
                    cache_file.unlink()
            except (pickle.UnpicklingError, EOFError) as e:
                # 손상된 캐시 파일은 삭제하고 계속 진행
                self.logger.warning(f"손상된 캐시 파일 삭제: {cache_file} - {e}")
                try:
                    cache_file.unlink()
                except Exception:
                    pass
            except Exception as e:
                self.logger.warning(f"캐시 파일 로드 실패: {e}")

        return None

    def set_cached_result(self, file_path: Path, data: Any) -> None:
        """
        결과를 캐시에 저장

        Args:
            file_path: 원본 파일 경로 (Path 객체 또는 문자열)
            data: 캐시할 데이터
        """
        # Path 객체로 변환 (SourceFile 객체가 전달될 수 있으므로 path 속성 확인)
        if hasattr(file_path, "path"):
            # SourceFile 객체인 경우 path 속성 사용
            file_path = Path(file_path.path)
        else:
            file_path = Path(file_path)

        cache_key = self._get_cache_key(file_path)
        cache_entry = {
            "data": data,
            "file_path": str(file_path),
            "cached_time": datetime.now(),
            "file_mtime": file_path.stat().st_mtime if file_path.exists() else 0,
        }

        # 메모리 캐시에 저장
        self._add_to_memory_cache(cache_key, cache_entry)

        # 디스크 캐시에 저장 (tree_sitter.Tree 객체는 pickle 불가능하므로 건너뜀)
        # Tree 객체인지 확인 (tree_sitter.Tree는 pickle로 직렬화할 수 없음)
        is_tree_object = False
        if HAS_TREE_SITTER and TreeSitterTree is not None:
            is_tree_object = isinstance(data, TreeSitterTree)
        else:
            # tree_sitter가 없거나 타입 확인이 불가능한 경우 문자열로 확인
            try:
                if hasattr(data, "__class__") and "tree_sitter" in str(type(data)):
                    is_tree_object = True
            except Exception:
                pass

        if is_tree_object:
            # Tree 객체는 메모리 캐시에만 저장
            self.logger.debug(f"Tree 객체는 메모리 캐시에만 저장: {file_path}")
            return

        # 일반 데이터는 디스크 캐시에도 저장
        cache_file = self._get_cache_file_path(cache_key)
        try:
            with open(cache_file, "wb") as f:
                pickle.dump(cache_entry, f)
            self.logger.debug(f"캐시 저장 완료: {file_path}")
        except (pickle.PickleError, TypeError) as e:
            # pickle 불가능한 객체는 메모리 캐시에만 저장
            self.logger.debug(
                f"pickle 불가능한 객체는 메모리 캐시에만 저장: {file_path} - {e}"
            )
        except Exception as e:
            self.logger.warning(f"캐시 파일 저장 실패: {e}")

    def _add_to_memory_cache(self, cache_key: str, cache_entry: Dict[str, Any]) -> None:
        """메모리 캐시에 추가 (크기 제한 고려)"""
        # 캐시 크기 제한 확인
        if len(self.memory_cache) >= self.memory_cache_size:
            # 가장 오래된 항목 제거 (간단한 FIFO 방식)
            oldest_key = next(iter(self.memory_cache))
            del self.memory_cache[oldest_key]

        self.memory_cache[cache_key] = cache_entry

    def _is_cache_valid(self, cache_entry: Dict[str, Any], file_path: Path) -> bool:
        """
        캐시가 유효한지 확인

        Args:
            cache_entry: 캐시 항목
            file_path: 원본 파일 경로 (Path 객체 또는 문자열)

        Returns:
            bool: 캐시가 유효하면 True
        """
        # Path 객체로 변환 (SourceFile 객체가 전달될 수 있으므로 path 속성 확인)
        if hasattr(file_path, "path"):
            # SourceFile 객체인 경우 path 속성 사용
            file_path = Path(file_path.path)
        else:
            file_path = Path(file_path)

        # 파일이 존재하지 않으면 캐시 무효
        if not file_path.exists():
            return False

        # 파일 수정 시간 확인
        current_mtime = file_path.stat().st_mtime
        cached_mtime = cache_entry.get("file_mtime", 0)
        if current_mtime != cached_mtime:
            return False

        # 캐시 만료 시간 확인
        cached_time = cache_entry.get("cached_time")
        if cached_time:
            if isinstance(cached_time, str):
                cached_time = datetime.fromisoformat(cached_time)
            if datetime.now() - cached_time > self.cache_expiry:
                return False

        return True

    def invalidate_cache(self, file_path: Path) -> None:
        """
        특정 파일의 캐시 무효화

        Args:
            file_path: 캐시를 무효화할 파일 경로 (Path 객체 또는 문자열)
        """
        # Path 객체로 변환 (SourceFile 객체가 전달될 수 있으므로 path 속성 확인)
        if hasattr(file_path, "path"):
            # SourceFile 객체인 경우 path 속성 사용
            file_path = Path(file_path.path)
        else:
            file_path = Path(file_path)

        cache_key = self._get_cache_key(file_path)

        # 메모리 캐시에서 제거
        if cache_key in self.memory_cache:
            del self.memory_cache[cache_key]

        # 디스크 캐시 파일 삭제
        cache_file = self._get_cache_file_path(cache_key)
        if cache_file.exists():
            try:
                cache_file.unlink()
                self.logger.debug(f"캐시 무효화: {file_path}")
            except Exception as e:
                self.logger.warning(f"캐시 파일 삭제 실패: {e}")

    def clear_cache(self) -> None:
        """모든 캐시 삭제"""
        # 메모리 캐시 비우기
        self.memory_cache.clear()

        # 디스크 캐시 파일 삭제
        try:
            for cache_file in self.cache_dir.glob("*.cache"):
                cache_file.unlink()
            self.logger.info("모든 캐시 삭제 완료")
        except Exception as e:
            self.logger.warning(f"캐시 파일 삭제 중 오류: {e}")
