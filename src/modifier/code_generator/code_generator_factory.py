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

        elif modification_type == "TwoStep":
            from .two_step_type.two_step_code_generator import (
                TwoStepCodeGenerator,
            )

            # TwoStep은 내부에서 자체적으로 LLM Provider를 생성하므로
            # llm_provider 파라미터는 사용하지 않음
            return TwoStepCodeGenerator(config=config)

        elif modification_type == "ThreeStep":
            # CCS 프로젝트 여부에 따라 적절한 ThreeStep 생성기 선택
            sql_wrapping_type = config.sql_wrapping_type
            if sql_wrapping_type in ("mybatis_ccs", "mybatis_ccs_batch"):
                from .three_step_type.three_step_ccs_code_generator import (
                    ThreeStepCCSCodeGenerator,
                )

                # CCS 전용: resultMap 기반 필드 매핑 사용
                return ThreeStepCCSCodeGenerator(config=config)
            else:
                from .three_step_type.three_step_code_generator import (
                    ThreeStepCodeGenerator,
                )

                # 일반: VO 파일 전체 포함
                return ThreeStepCodeGenerator(config=config)

        else:
            raise ValueError(
                f"지원하지 않는 modification_type: {modification_type}. "
                f"가능한 값: TypeHandler, ControllerOrService, ServiceImplOrBiz, TwoStep, ThreeStep"
            )

