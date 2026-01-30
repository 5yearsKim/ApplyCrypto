import logging
from pathlib import Path
from typing import List, Dict, Optional
from models.table_access_info import TableAccessInfo
from modifier.context_generator.base_context_generator import BaseContextGenerator
from models.modification_context import ModificationContext

logger = logging.getLogger("applycrypto.per_layer_context_generator")


class PerLayerContextGenerator(BaseContextGenerator):
    """
    Per Layer Context Generator

    Generates batches of ModificationContext from TableAccessInfo,
    grouping files by their layer definition.
    """

    def generate(
        self,
        layer_files: Dict[str, List[str]],
        table_name: str,
        columns: List[Dict],
        table_access_info: Optional[TableAccessInfo] = None,
    ) -> List[ModificationContext]:
        """
        Generates modification contexts. Failed files are logged.

        Args:
            layer_files: Dictionary of layer names and file paths.
            table_name: Table name.
            columns: List of columns.

        Returns:
            List[ModificationContext]: The generated batches of contexts.
        """
        all_batches: List[ModificationContext] = []
        project_root = Path(self._config.target_project)

        # Layer-wise file grouping
        # layer_files is passed as argument

        for layer_name, file_paths in layer_files.items():
            if not file_paths:
                continue

            logger.info(
                f"Preparing plan generation for layer '{layer_name}': {len(file_paths)} files"
            )

            # Create batches considering token limits
            modification_context_batches = self.create_batches(
                file_paths=file_paths,
                table_name=table_name,
                columns=columns,
                layer=layer_name,
            )

            all_batches.extend(modification_context_batches)

        return all_batches
