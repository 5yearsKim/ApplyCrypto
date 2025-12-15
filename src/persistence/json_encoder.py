"""
커스텀 JSON 인코더 모듈

datetime, Path 등 기본 JSON 타입이 아닌 객체들을 처리하는 커스텀 JSON 인코더입니다.
"""

import json
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class CustomJSONEncoder(json.JSONEncoder):
    """
    커스텀 JSON 인코더 클래스

    기본 JSON 타입이 아닌 객체들을 JSON으로 변환합니다:
    - datetime: ISO 8601 형식 문자열로 변환
    - Path: 문자열로 변환
    - Enum: 값으로 변환
    """

    def default(self, obj: Any) -> Any:
        """
        객체를 JSON 직렬화 가능한 형태로 변환

        Args:
            obj: 변환할 객체

        Returns:
            JSON 직렬화 가능한 객체
        """
        # datetime 객체 처리
        if isinstance(obj, datetime):
            return obj.isoformat()

        # Path 객체 처리
        if isinstance(obj, Path):
            return str(obj)

        # Enum 객체 처리
        if isinstance(obj, Enum):
            return obj.value

        # dataclass 처리 (to_dict 메서드가 있는 경우)
        if hasattr(obj, "to_dict"):
            return obj.to_dict()

        # 기본 처리 (부모 클래스의 default 메서드 호출)
        return super().default(obj)
