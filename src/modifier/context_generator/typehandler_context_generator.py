import logging
import os
from pathlib import Path
from typing import List, Dict, Optional, Set

from modifier.context_generator.base_context_generator import BaseContextGenerator
from models.modification_context import ModificationContext
from parser.xml_mapper_parser import XMLMapperParser

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
        try:
            import tiktoken

            encoder = tiktoken.encoding_for_model("gpt-4")
            return len(encoder.encode(text))
        except Exception:
            # Fallback if tiktoken is not available (4 chars = 1 token)
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

    def _select_relevant_vo_from_xml(
        self,
        xml_file: str,
        repository_files: List[str],
        vo_files: List[str],
        xml_parser: XMLMapperParser,
    ) -> Optional[Tuple[Optional[str], Set[str]]]:
        """
        Parses XML and identifies the Mapper Interface and referenced VO files.

        Args:
            xml_file: Path to the XML file.
            repository_files: List of repository files.
            vo_files: List of known VO files.
            xml_parser: Instance of XMLMapperParser.

        Returns:
            Optional[Tuple[Optional[str], Set[str]]]:
                - Tuple of (mapper_interface_file, relevant_vo_paths) if successful.
                - None if parsing failed or critical error occurred.
        """
        mapper_interface_file = None
        relevant_vo_paths = set()

        try:
            # 1. Parse XML file using xml_parser's low-level method to get the tree
            tree, error = xml_parser.parse_file(Path(xml_file))
            if error or not tree:
                logger.warning(f"Skipping XML due to parse error: {xml_file}")
                return None

            root = tree.getroot()
            
            # 2. Extract Namespace (Mapper Interface)
            namespace = root.get("namespace", "")
            if namespace:
                mapper_interface_file = self._match_class_to_file_path(
                    namespace, repository_files
                )
                if not mapper_interface_file:
                    logger.debug(
                        f"Could not find mapper interface for namespace: {namespace}"
                    )

            # 3. Extract types from <resultMap>
            # Fetch value from <resultMap, type=???>
            used_types = set()
            
            # Find all resultMap tags
            for result_map in root.xpath(".//resultMap"):
                result_type = result_map.get("type")
                if result_type:
                    used_types.add(result_type)

            # 4. Match VOs
            for type_name in used_types:
                matched_file = self._match_class_to_file_path(
                    type_name, repository_files
                )
                if matched_file and matched_file in vo_files:
                    relevant_vo_paths.add(matched_file)
            
            return mapper_interface_file, relevant_vo_paths

        except Exception as e:
            logger.warning(f"Error processing XML file {xml_file} in _select_relevant_vo_from_xml: {e}")
            return None



    def generate(
        self,
        layer_files: Dict[str, List[str]],
        table_name: str,
        columns: List[Dict],
    ) -> List[ModificationContext]:
        """
        Generates modification contexts for TypeHandler application (XML focus).

        Args:
            layer_files: Dictionary of layer names and file paths. 
                         Expected keys: 'xml', 'repository'.
            table_name: Table name.
            columns: List of columns.

        Returns:
            List[ModificationContext]: The generated batches of contexts.
        """
        all_batches: List[ModificationContext] = []

        # Collected files should be only "repository" and "xml"
        xml_files = layer_files.get("xml", [])
        repository_files = layer_files.get("repository", [])
        
        if not xml_files:
            logger.info("No XML files found for TypeHandler generation.")
            return all_batches

        # Separate VOs and Interfaces from repository files
        # Heuristic: VOs usually end with VO.java (or DTO.java)
        vo_files = [
            x for x in repository_files 
            if x.lower().endswith("vo.java") 
            or x.lower().endswith("dto.java")
            or x.lower().endswith("daomodel.java") 
            or x.lower() == "employee.java"  # Exception for book-ssm. production 에서는 지우세요~
        ]
        
        # Mapper Interfaces might be the rest, or we just search in all repository_files
        
        xml_parser = XMLMapperParser()

        for xml_file in xml_files:
            result = self._select_relevant_vo_from_xml(
                xml_file, repository_files, vo_files, xml_parser
            )
            
            if result is None:
                continue
                
            mapper_interface_file, relevant_vo_paths = result

            # 5. Filter VOs by token budget
            context_vo_files = self._select_vo_files_by_token_budget(
                vo_files=vo_files,  # list of all VOs for reference/validation
                required_vos=relevant_vo_paths,
                max_tokens=self.MAX_VO_TOKENS
            )

            logger.info(
                f"Generated context for XML {Path(xml_file).name}: "
                f"Mapper={Path(mapper_interface_file).name if mapper_interface_file else 'None'}, "
                f"VOs={len(context_vo_files)}"
            )

            # 6. Create Batch
            # Main files to edit: XML (and potentially Mapper Interface)
            # Context: VOs
            group_files = [xml_file]
            if mapper_interface_file:
                group_files.append(mapper_interface_file)

            batches = self.create_batches(
                file_paths=group_files,
                table_name=table_name,
                columns=columns,
                layer="repository", # Keeping 'repository' since it involves repo layer
                context_files=context_vo_files
            )
            all_batches.extend(batches)

        return all_batches
