"""
CallRelation 데이터 모델

메서드 호출 관계를 저장하는 데이터 모델입니다.
"""

from dataclasses import dataclass


@dataclass
class CallRelation:
    """
    메서드 호출 관계를 저장하는 데이터 모델

    Attributes:
        caller: 호출하는 메서드 (형식: "ClassName.methodName")
        callee: 호출되는 메서드 (형식: "ClassName.methodName")
        caller_file: 호출하는 메서드가 있는 파일 경로
        callee_file: 호출되는 메서드가 있는 파일 경로
        line_number: 호출 위치의 라인 번호 (선택적)
    """

    caller: str
    callee: str
    caller_file: str
    callee_file: str
    line_number: int = 0

    def to_dict(self) -> dict:
        """딕셔너리 형태로 변환"""
        return {
            "caller": self.caller,
            "callee": self.callee,
            "caller_file": self.caller_file,
            "callee_file": self.callee_file,
            "line_number": self.line_number,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CallRelation":
        """딕셔너리로부터 CallRelation 객체 생성"""
        return cls(
            caller=data["caller"],
            callee=data["callee"],
            caller_file=data["caller_file"],
            callee_file=data["callee_file"],
            line_number=data.get("line_number", 0),
        )
