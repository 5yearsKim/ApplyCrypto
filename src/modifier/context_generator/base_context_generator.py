import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Any, Optional

from config.config_manager import Configuration
from models.code_generator import CodeGeneratorInput
from models.modification_context import ModificationContext
from models.table_access_info import TableAccessInfo

from modifier.code_generator.base_code_generator import BaseCodeGenerator

logger = logging.getLogger("applycrypto.context_generator")


class BaseContextGenerator(ABC):
    """
    Base Context Generator
    """

    def __init__(self, config: Configuration, code_generator: BaseCodeGenerator):
        self._config = config
        self._code_generator = code_generator

    @abstractmethod
    def generate(
        self,
        layer_files: Dict[str, List[str]],
        table_name: str,
        columns: List[Dict],
        table_access_info: Optional["TableAccessInfo"] = None,
    ) -> List[ModificationContext]:
        """
        Generates modification contexts.

        Args:
            layer_files: Dictionary of layer names and their corresponding file paths.
            table_name: Name of the table.
            columns: List of columns accessed.
            table_access_info: TableAccessInfo object (optional).

        Returns:
            List[ModificationContext]: The generated batches of contexts.
        """
        raise NotImplementedError

    def create_batches(
        self,
        file_paths: List[str],
        table_name: str,
        columns: List[Dict],
        layer: str = "",
        context_files: List[str] = None,
    ) -> List[ModificationContext]:
        """
        Splits file list into batches based on token size.

        Args:
            file_paths: List of file paths.
            table_name: Table name.
            columns: List of columns.
            layer: Layer name.
            context_files: List of context file paths (VO files, etc.) - not to be modified.

        Returns:
            List[ModificationContext]: List of split modification contexts.
        """
        if context_files is None:
            context_files = []
        if not file_paths:
            return []

        batches: List[ModificationContext] = []
        current_paths: List[str] = []

        # Prepare basic info
        table_info = {
            "table_name": table_name,
            "columns": columns,
        }
        formatted_table_info = json.dumps(table_info, indent=2, ensure_ascii=False)
        max_tokens = self._config.max_tokens_per_batch

        input_empty_data = CodeGeneratorInput(
            file_paths=[], table_info=formatted_table_info, layer_name=layer
        )

        # Create empty prompt and calculate tokens
        empty_prompt = self._code_generator.create_prompt(input_empty_data)
        empty_num_tokens = self._code_generator.calculate_token_size(empty_prompt)

        # Calculate separator tokens ("\n\n")
        separator_tokens = self._code_generator.calculate_token_size("\n\n")

        current_batch_tokens = empty_num_tokens

        for file_path in file_paths:
            # Read content for token calculation
            try:
                path_obj = Path(file_path)
                if not path_obj.exists():
                    logger.warning(f"File not found during batch creation: {file_path}")
                    continue

                with open(path_obj, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception as e:
                logger.error(f"Failed to read file {file_path}: {e}")
                continue

            # Format snippet and calculate tokens
            snippet_formatted = f"=== File Path (Absolute): {file_path} ===\n{content}"
            snippet_tokens = self._code_generator.calculate_token_size(
                snippet_formatted
            )

            # Add separator tokens if not the first snippet
            tokens_to_add = snippet_tokens
            if current_paths:
                tokens_to_add += separator_tokens

            if current_paths and (current_batch_tokens + tokens_to_add) > max_tokens:
                # Save current batch and start new one
                batches.append(
                    ModificationContext(
                        file_paths=current_paths,
                        table_name=table_name,
                        columns=columns,
                        file_count=len(current_paths),
                        layer=layer,
                        context_files=context_files,
                    )
                )
                current_paths = [file_path]
                current_batch_tokens = empty_num_tokens + snippet_tokens
            else:
                # Add to current batch
                current_paths.append(file_path)
                current_batch_tokens += tokens_to_add

        # Add last batch
        if current_paths:
            batches.append(
                ModificationContext(
                    file_paths=current_paths,
                    table_name=table_name,
                    columns=columns,
                    file_count=len(current_paths),
                    layer=layer,
                    context_files=context_files,
                )
            )

        logger.info(
            f"Split {len(file_paths)} files into {len(batches)} batches (ModificationContext)."
        )
        return batches
