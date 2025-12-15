"""
LLM Provider 추상 기본 클래스

모든 LLM 프로바이더가 구현해야 하는 인터페이스를 정의합니다.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class LLMProvider(ABC):
    """
    LLM Provider 추상 기본 클래스

    모든 LLM 프로바이더는 이 클래스를 상속받아 구현해야 합니다.
    """

    @abstractmethod
    def call(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        LLM API를 호출하여 응답을 받습니다.

        Args:
            prompt: LLM에 전달할 프롬프트
            max_tokens: 최대 토큰 수 (선택적)
            temperature: 온도 파라미터 (선택적)

        Returns:
            Dict[str, Any]: LLM 응답 딕셔너리
                - content: 응답 내용
                - tokens_used: 사용된 토큰 수
                - model: 사용된 모델명

        Raises:
            LLMError: LLM API 호출 실패 시
        """
        pass

    @abstractmethod
    def validate_response(self, response: Dict[str, Any]) -> bool:
        """
        LLM 응답의 유효성을 검증합니다.

        Args:
            response: 검증할 응답 딕셔너리

        Returns:
            bool: 응답이 유효하면 True, 그렇지 않으면 False
        """
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """
        프로바이더 이름을 반환합니다.

        Returns:
            str: 프로바이더 이름 (예: "watsonx_ai", "openai")
        """
        pass
