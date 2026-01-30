import logging
import os
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple
from models.table_access_info import TableAccessInfo

import re
from modifier.context_generator.base_context_generator import BaseContextGenerator
from models.modification_context import ModificationContext

logger = logging.getLogger("applycrypto.context_generator")


class TypehandlerContextGenerator(BaseContextGenerator):
    """
    TypeHandler Context Generator

    Groups XML Mapper files and their corresponding Repository interfaces for TypeHandler application.
    Collecting 'repository' and 'xml' files, and adding relevant VO files as context.
    """

    # VO files max token budget (80k)
    MAX_VO_TOKENS = 80000

    def _calculate_token_size(self, text: str) -> int:
        """
        Calculates token size of text.
        
        Args:
            text: Text to calculate tokens for.

        Returns:
            int: Estimated token count.
        """
        return len(text) // 4

    def _select_vo_files_by_token_budget(
        self,
        vo_files: List[str],
        required_vos: Set[str],
        max_tokens: int,
    ) -> List[str]:
        """
        Selects VO files within the token budget.

        Args:
            vo_files: List of all available VO files (for validation).
            required_vos: Set of VO files matched from XML types.
            max_tokens: Max token budget.

        Returns:
            List[str]: Selected VO file paths.
        """
        selected_files: List[str] = []
        current_tokens = 0

        # Sort for deterministic order
        sorted_files = sorted(list(required_vos))

        for file_path in sorted_files:
            # Check if file is in the safe list of VO files (optional, but good for sanity)
            # If required_vos comes from _match_class_to_file_path using repository_files, 
            # and we filtered by VO extension, it should be fine.
            # We can skip strict existence check in 'vo_files' list if we trust the matching, 
            # but let's just use os.path.exists via open.
            
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                file_tokens = self._calculate_token_size(content)

                if current_tokens + file_tokens <= max_tokens:
                    selected_files.append(file_path)
                    current_tokens += file_tokens
                    logger.debug(
                        f"VO Selected: {Path(file_path).name} "
                        f"({file_tokens:,} tokens, accumulated: {current_tokens:,})"
                    )
                else:
                    logger.info(
                        f"VO excluded due to budget: {Path(file_path).name} "
                        f"({file_tokens:,} tokens, accumulated: {current_tokens:,})"
                    )
            except Exception as e:
                logger.warning(f"Failed to read VO file: {file_path} - {e}")

        logger.info(
            f"VO selection complete: {len(selected_files)} files, "
            f"Total {current_tokens:,} tokens (Budget: {max_tokens:,})"
        )
        return selected_files

    def _match_class_to_file_path(
        self, class_name: str, target_files: List[str]
    ) -> Optional[str]:
        """
        Matches a class name to a file path.

        Args:
            class_name: Class name (e.g., com.example.UserVO or UserVO).
            target_files: List of available file paths.

        Returns:
            Optional[str]: Matched file path or None.

        Examples:
            Success case:
                class_name = "com.example.UserVO"
                target_files = ["/path/to/UserVO.java", "/path/to/Other.java"]
                Returns: "/path/to/UserVO.java"

            Failed case:
                class_name = "com.example.UserVO"
                target_files = ["/path/to/Other.java"]
                Returns: None
        """
        # Extract simple class name
        simple_name = class_name.split(".")[-1]

        for file_path in target_files:
            file_name = os.path.basename(file_path)
            file_stem = os.path.splitext(file_name)[0]
            if file_stem == simple_name:
                return file_path

        return None

    def generate(
        self,
        layer_files: Dict[str, List[str]],
        table_name: str,
        columns: List[Dict],
        table_access_info: Optional[TableAccessInfo] = None,
    ) -> List[ModificationContext]:
        """
        Generates modification contexts for TypeHandler application (XML focus).

        Args:
            layer_files: Dictionary of layer names and file paths. 
                         Expected keys: 'xml', 'repository'.
            table_name: Table name.
            columns: List of columns.
            table_access_info: TableAccessInfo object containing SQL queries.

        Returns:
            List[ModificationContext]: The generated batches of contexts.
        """
        all_batches: List[ModificationContext] = []

        if not table_access_info:
            logger.warning("TableAccessInfo is required for TypeHandler generation but not provided.")
            return all_batches

        xml_files = layer_files.get("xml", [])
        repository_files = layer_files.get("repository", [])
        
        if not xml_files:
            logger.info("No XML files found for TypeHandler generation.")
            return all_batches

        # Collect VOs from SQL queries
        namespace_to_vos: Dict[str, Set[str]] = {}
        
        for query in table_access_info.sql_queries:
            strategy_specific = query.get("strategy_specific", {})
            namespace = strategy_specific.get("namespace")
            result_type = strategy_specific.get("result_type")
            
            if not namespace:
                continue
                
            if namespace not in namespace_to_vos:
                namespace_to_vos[namespace] = set()
                
            if result_type:
                vo_file = self._match_class_to_file_path(result_type, repository_files)
                if vo_file:
                    namespace_to_vos[namespace].add(vo_file)

        # Process each XML file
        for xml_file in xml_files:
            try:
                with open(xml_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    
                # Extract namespace using regex to avoid XML parser dependency
                match = re.search(r'namespace=["\']([^"\']+)["\']', content)
                if not match:
                    continue
                    
                namespace = match.group(1)
                
                relevant_vo_paths = namespace_to_vos.get(namespace, set())
                
                # Find Mapper Interface
                mapper_interface_file = self._match_class_to_file_path(namespace, repository_files)
                
                # Select VOs by token budget
                context_vo_files = self._select_vo_files_by_token_budget(
                    vo_files=list(relevant_vo_paths),
                    required_vos=relevant_vo_paths,
                    max_tokens=self.MAX_VO_TOKENS
                )

                logger.info(
                    f"Generated context for XML {Path(xml_file).name}: "
                    f"Mapper={Path(mapper_interface_file).name if mapper_interface_file else 'None'}, "
                    f"VOs={len(context_vo_files)}"
                )

                group_files = [xml_file]
                if mapper_interface_file:
                    group_files.append(mapper_interface_file)

                batches = self.create_batches(
                    file_paths=group_files,
                    table_name=table_name,
                    columns=columns,
                    layer="repository",
                    context_files=context_vo_files
                )
                all_batches.extend(batches)
                
            except Exception as e:
                logger.warning(f"Error processing XML file {xml_file}: {e}")
                continue

        return all_batches
