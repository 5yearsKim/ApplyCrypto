"""
ModificationPlan 데이터 모델

코드 수정 계획을 저장하는 데이터 모델입니다.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ModificationPlan:
    """
    코드 수정 계획을 저장하는 데이터 모델

    Attributes:
        file_path: 수정할 파일 경로
        layer_name: 레이어 이름
        modification_type: 수정 유형 (예: "encryption")
        status: 계획 상태 (pending, skipped, failed, success)
        modified_code: 수정된 코드 (전체 소스 코드 또는 diff)
        error: 에러 메시지
        tokens_used: 사용된 토큰 수
        reason: 수정/스킵 이유
    """

    file_path: str
    layer_name: str
    modification_type: str
    status: str = "pending"
    modified_code: Optional[str] = None
    error: Optional[str] = None
    tokens_used: int = 0
    reason: Optional[str] = None

    def to_dict(self) -> dict:
        """딕셔너리 형태로 변환"""
        return {
            "file_path": self.file_path,
            "layer_name": self.layer_name,
            "modification_type": self.modification_type,
            "status": self.status,
            "modified_code": self.modified_code,
            "error": self.error,
            "tokens_used": self.tokens_used,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ModificationPlan":
        """딕셔너리로부터 ModificationPlan 객체 생성"""
        return cls(
            file_path=data["file_path"],
            layer_name=data["layer_name"],
            modification_type=data["modification_type"],
            status=data.get("status", "pending"),
            modified_code=data.get("modified_code"),
            error=data.get("error"),
            tokens_used=data.get("tokens_used", 0),
            reason=data.get("reason"),
        )
