from config.config_manager import Configuration
from modifier.code_generator.base_code_generator import BaseCodeGenerator
from modifier.context_generator.base_context_generator import ContextGenerator


class ContextGeneratorFactory:
    """
    Factory for creating ContextGenerator instances.
    """

    @staticmethod
    def create(config: Configuration, code_generator: BaseCodeGenerator) -> ContextGenerator:
        """
        Creates a ContextGenerator instance.

        Args:
            config: Configuration object.
            code_generator: CodeGenerator instance.

        Returns:
            ContextGenerator: An instance of ContextGenerator.
        """
        # In the future, logic can be added here to select different
        # ContextGenerator implementations based on config or other parameters.
        return ContextGenerator(config, code_generator)
