from config.config_manager import Configuration
from modifier.code_generator.base_code_generator import BaseCodeGenerator
from modifier.context_generator.base_context_generator import ContextGenerator



from modifier.context_generator.jdbc_context_generator import (
    JdbcContextGenerator,
)


from modifier.context_generator.mybatis_context_generator import (
    MybatisContextGenerator,
)

class ContextGeneratorFactory:
    """
    Factory for creating ContextGenerator instances.
    """

    @staticmethod
    def create(
        config: Configuration, code_generator: BaseCodeGenerator
    ) -> ContextGenerator:
        """
        Creates a ContextGenerator instance.

        Args:
            config: Configuration object.
            code_generator: CodeGenerator instance.

        Returns:
            ContextGenerator: An instance of ContextGenerator.
        """
        if config.sql_wrapping_type == "jdbc":
            return JdbcContextGenerator(config, code_generator)
        elif config.sql_wrapping_type == "mybatis":
            return MybatisContextGenerator(config, code_generator)

        return ContextGenerator(config, code_generator)
