"""
OpenAI Provider 구현

OpenAI LLM API를 호출하는 프로바이더입니다.
"""

import logging
from typing import Dict, Any, Optional

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from .llm_provider import LLMProvider


logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    """
    OpenAI Provider 구현 클래스
    
    OpenAI API를 사용하여 LLM 호출을 수행합니다.
    """
    
    def __init__(
        self,
        api_key: str,
        model_id: Optional[str] = None,
        **kwargs
    ):
        """
        OpenAI Provider 초기화
        
        Args:
            api_key: OpenAI API 키
            model_id: 모델 ID (선택적, 기본값: "gpt-4")
            **kwargs: 추가 설정 파라미터
        """
        if not OPENAI_AVAILABLE:
            raise ImportError(
                "OpenAI 라이브러리가 설치되지 않았습니다. "
                "다음 명령어로 설치하세요: pip install openai"
            )
        
        self.api_key = api_key
        self.model_id = model_id or "gpt-4"
        
        # OpenAI 클라이언트 초기화
        try:
            openai.api_key = self.api_key
            self.client = openai.OpenAI(api_key=self.api_key)
            
            logger.info(f"OpenAI Provider 초기화 완료: {self.model_id}")
        except Exception as e:
            logger.error(f"OpenAI Provider 초기화 실패: {e}")
            raise
    
    def call(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        OpenAI API를 호출하여 응답을 받습니다.
        
        Args:
            prompt: LLM에 전달할 프롬프트
            max_tokens: 최대 토큰 수 (선택적)
            temperature: 온도 파라미터 (선택적)
            
        Returns:
            Dict[str, Any]: LLM 응답 딕셔너리
                - content: 응답 내용
                - tokens_used: 사용된 토큰 수
                - model: 사용된 모델명
        """
        try:
            # 파라미터 설정
            params = {
                "model": self.model_id,
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            }
            
            if max_tokens:
                params["max_tokens"] = max_tokens
            if temperature is not None:
                params["temperature"] = temperature
            
            # API 호출
            response = self.client.chat.completions.create(**params)
            
            # 응답 파싱
            content = response.choices[0].message.content
            tokens_used = response.usage.total_tokens if response.usage else 0
            
            result = {
                "content": content,
                "tokens_used": tokens_used,
                "model": self.model_id
            }
            
            logger.debug(f"OpenAI 응답 수신: {len(content)} 문자, {tokens_used} 토큰")
            return result
            
        except Exception as e:
            logger.error(f"OpenAI API 호출 실패: {e}")
            raise
    
    def validate_response(self, response: Dict[str, Any]) -> bool:
        """
        OpenAI 응답의 유효성을 검증합니다.
        
        Args:
            response: 검증할 응답 딕셔너리
            
        Returns:
            bool: 응답이 유효하면 True, 그렇지 않으면 False
        """
        required_fields = ["content", "tokens_used", "model"]
        return all(field in response for field in required_fields) and bool(response.get("content"))
    
    def get_provider_name(self) -> str:
        """
        프로바이더 이름을 반환합니다.
        
        Returns:
            str: "openai"
        """
        return "openai"

