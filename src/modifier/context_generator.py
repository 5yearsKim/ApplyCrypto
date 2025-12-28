import json
import logging
from pathlib import Path
from typing import List

from config.config_manager import Configuration
from models.diff_generator import DiffGeneratorInput
from models.modification_context import CodeSnippet, ModificationContext
from models.table_access_info import TableAccessInfo
from modifier.code_generator.base_code_generator import BaseCodeGenerator

# Don't remove the following comment.. this is for example format of TableAccessInfo
# "layer_files": {
#   "Repository": [
#     "C:\\Users\\hypot\\Works\\book-ssm\\src\\com\\mybatis\\beans\\Employee.java",
#     "C:\\Users\\hypot\\Works\\book-ssm\\src\\com\\mybatis\\dao\\EmployeeMapper.java"
#   ],
#   "service": [
#     "C:\\Users\\hypot\\Works\\book-ssm\\src\\com\\mybatis\\service\\EmployeeService.java"
#   ],
#   "controller": [
#     "C:\\Users\\hypot\\Works\\book-ssm\\src\\com\\mybatis\\controller\\EmpController.java",
#     "C:\\Users\\hypot\\Works\\book-ssm\\src\\com\\mybatis\\controller\\EmployeeController.java"
#   ]
# },

logger = logging.getLogger("applycrypto.context_generator")


class ContextGenerator:
    """
    Context Generator

    Generates batches of ModificationContext from TableAccessInfo,
    handling file reading and token limits.
    """

    @staticmethod
    def generate(
        config: Configuration,
        code_generator: BaseCodeGenerator,
        table_access_info: TableAccessInfo,
    ) -> List[ModificationContext]:
        """
        Generates modification contexts. Failed files are logged.

        Args:
            config: Configuration object.
            code_generator: CodeGenerator instance.
            table_access_info: Table access information containing file paths.

        Returns:
            List[ModificationContext]: The generated batches of contexts.
        """
        all_batches: List[ModificationContext] = []
        project_root = Path(config.target_project)

        # Layer-wise file grouping
        layer_files = table_access_info.layer_files

        for layer_name, file_paths in layer_files.items():
            if not file_paths:
                continue

            logger.info(
                f"Preparing plan generation for layer '{layer_name}': {len(file_paths)} files"
            )

            code_snippets: List[CodeSnippet] = []
            for file_path in file_paths:
                try:
                    # Convert file path to absolute
                    file_path_obj = Path(file_path)
                    if not file_path_obj.is_absolute():
                        full_path = project_root / file_path_obj
                    else:
                        full_path = file_path_obj

                    # Resolve absolute path
                    full_path = full_path.resolve()

                    if full_path.exists():
                        with open(full_path, "r", encoding="utf-8") as f:
                            content = f.read()
                        code_snippets.append(
                            CodeSnippet(
                                path=str(full_path),
                                content=content,
                            )
                        )
                    else:
                        logger.warning(
                            f"File not found: {full_path} (Original path: {file_path})"
                        )

                except Exception as e:
                    logger.error(f"Failed to read file: {file_path} - {e}")

            # Create batches considering token limits
            modification_context_batches = ContextGenerator.create_batches(
                config=config,
                code_generator=code_generator,
                code_snippets=code_snippets,
                table_access_info=table_access_info,
                layer=layer_name,
            )

            all_batches.extend(modification_context_batches)

        return all_batches

    @staticmethod
    def create_batches(
        config: Configuration,
        code_generator: BaseCodeGenerator,
        code_snippets: List[CodeSnippet],
        table_access_info: TableAccessInfo,
        layer: str,
    ) -> List[ModificationContext]:
        """
        Splits file list into batches based on token size.

        Args:
            config: Configuration object.
            code_generator: CodeGenerator instance.
            code_snippets: List of code snippets.
            table_access_info: Table access information.
            layer: Layer name.

        Returns:
            List[ModificationContext]: List of split modification contexts.
        """
        if not code_snippets:
            return []

        batches: List[ModificationContext] = []
        current_snippets: List[CodeSnippet] = []

        # Prepare basic info
        table_info = {
            "table_name": table_access_info.table_name,
            "columns": table_access_info.columns,
        }
        formatted_table_info = json.dumps(table_info, indent=2, ensure_ascii=False)
        max_tokens = config.max_tokens_per_batch

        input_empty_data = DiffGeneratorInput(
            code_snippets=[], table_info=formatted_table_info, layer_name=layer
        )

        # Create empty prompt and calculate tokens
        empty_prompt = code_generator.create_prompt(input_empty_data)
        empty_num_tokens = code_generator.calculate_token_size(empty_prompt)

        # Calculate separator tokens ("\n\n")
        separator_tokens = code_generator.calculate_token_size("\n\n")

        current_batch_tokens = empty_num_tokens

        for snippet in code_snippets:
            # Format snippet and calculate tokens
            snippet_formatted = (
                f"=== File Path (Absolute): {snippet.path} ===\n{snippet.content}"
            )
            snippet_tokens = code_generator.calculate_token_size(snippet_formatted)

            # Add separator tokens if not the first snippet
            tokens_to_add = snippet_tokens
            if current_snippets:
                tokens_to_add += separator_tokens

            if current_snippets and (current_batch_tokens + tokens_to_add) > max_tokens:
                # Save current batch and start new one
                batches.append(
                    ModificationContext(
                        code_snippets=current_snippets,
                        table_access_info=table_access_info,
                        file_count=len(current_snippets),
                        layer=layer,
                    )
                )
                current_snippets = [snippet]
                current_batch_tokens = empty_num_tokens + snippet_tokens
            else:
                # Add to current batch
                current_snippets.append(snippet)
                current_batch_tokens += tokens_to_add

        # Add last batch
        if current_snippets:
            batches.append(
                ModificationContext(
                    code_snippets=current_snippets,
                    table_access_info=table_access_info,
                    file_count=len(current_snippets),
                    layer=layer,
                )
            )

        logger.info(
            f"Split {len(code_snippets)} files into {len(batches)} batches (ModificationContext)."
        )
        return batches

