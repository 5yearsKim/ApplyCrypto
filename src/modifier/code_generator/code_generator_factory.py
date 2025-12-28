"""
Code Generator Factory

modification_type에 따라 적절한 CodeGenerator 인스턴스를 생성하는 Factory 클래스입니다.
CodeModifier에서 직접 사용하여 modification_type에 맞는 CodeGenerator를 생성합니다.
"""

from typing import Optional

from config.config_manager import Configuration
from modifier.llm.llm_provider import LLMProvider

from .base_code_generator import BaseCodeGenerator


class CodeGeneratorFactory:
    """CodeGenerator 생성을 위한 팩토리 클래스"""

    @staticmethod
    def create(
        config: Configuration, llm_provider: Optional[LLMProvider] = None
    ) -> BaseCodeGenerator:
        """
        modification_type에 따라 적절한 CodeGenerator 인스턴스를 생성합니다.

        Args:
            config: 설정 객체
            llm_provider: LLM 프로바이더

        Returns:
            BaseCodeGenerator: 생성된 CodeGenerator 인스턴스

        Raises:
            ValueError: 지원하지 않는 modification_type인 경우
        """
        modification_type = config.modification_type

        if modification_type == "ControllerOrService":
            from .controller_service_type.controller_service_code_generator import (
                ControllerOrServiceCodeGenerator,
            )

            return ControllerOrServiceCodeGenerator(
                llm_provider=llm_provider, config=config
            )

        elif modification_type == "ServiceImplOrBiz":
            from .serviceimpl_biz_type.serviceimpl_biz_code_generator import (
                ServiceImplOrBizCodeGenerator,
            )

            return ServiceImplOrBizCodeGenerator(
                llm_provider=llm_provider, config=config
            )

        elif modification_type == "TypeHandler":
            from .typehandler_type.typehandler_code_generator import (
                TypeHandlerCodeGenerator,
            )

            return TypeHandlerCodeGenerator(llm_provider=llm_provider, config=config)

        else:
            raise ValueError(
                f"지원하지 않는 modification_type: {modification_type}. "
                f"가능한 값: TypeHandler, ControllerOrService, ServiceImplOrBiz"
            )

