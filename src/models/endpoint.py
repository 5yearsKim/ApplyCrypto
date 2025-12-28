"""
Endpoint 모델

REST API 엔드포인트 정보를 나타내는 데이터 모델입니다.
"""

from dataclasses import dataclass


@dataclass
class Endpoint:
    """
    REST API 엔드포인트 정보

    Attributes:
        path: 엔드포인트 경로
        http_method: HTTP 메서드 (GET, POST, PUT, DELETE 등)
        method_signature: 메서드 시그니처 (ClassName.methodName)
        class_name: 클래스명
        method_name: 메서드명
        file_path: 파일 경로
    """

    path: str
    http_method: str
    method_signature: str
    class_name: str
    method_name: str
    file_path: str

    def to_dict(self) -> dict:
        """딕셔너리 형태로 변환"""
        return {
            "path": self.path,
            "http_method": self.http_method,
            "method_signature": self.method_signature,
            "class_name": self.class_name,
            "method_name": self.method_name,
            "file_path": self.file_path,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Endpoint":
        """딕셔너리로부터 Endpoint 객체 생성"""
        return cls(
            path=data["path"],
            http_method=data["http_method"],
            method_signature=data["method_signature"],
            class_name=data["class_name"],
            method_name=data["method_name"],
            file_path=data["file_path"],
        )

