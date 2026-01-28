import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, List

from .base_code_patcher import BaseCodePatcher

logger = logging.getLogger("applycrypto.code_patcher")


@dataclass
class PatchBlock:
    search_line: str
    replace_line: str


class PartCodePatcher(BaseCodePatcher):
    """
    Code patcher that applies partial search/replace blocks.
    Parses <<< SEARCH ... === ... >>> REPLACE format.
    """

    def apply_patch(
        self, file_path: Path, modified_code: str, dry_run: bool = False
    ) -> Tuple[bool, Optional[str]]:
        """
        Apply Search/Replace blocks to a file.
        """
        try:
            if not file_path.is_absolute():
                logger.warning(
                    f"Relative path passed: {file_path}. Converting to absolute."
                )
                file_path = self.project_root / file_path

            file_path = file_path.resolve()

            if not file_path.exists():
                error_msg = f"File does not exist: {file_path}"
                logger.error(error_msg)
                return False, error_msg

            # Parse patches from the modified_code string
            patches: List[PatchBlock] = self._parse_blocks(modified_code)
            
            if not patches:
                # It's possible the LLM returned no changes or empty Modified Code section
                # Should we treat this as success (no op) or failure?
                # Based on usage, if we called patcher, we expected something. 
                # But if the section was empty, maybe it's fine.
                # However, if parsing failed, that's different.
                # For now, if modified_code is not empty but no patches found, warn.
                if modified_code.strip():
                    logger.warning("No valid Search/Replace blocks found in modified_code.")
                else:
                    logger.info("Empty modified code provided.")
                # We return True because maybe no changes were needed.
                # But if syntax was wrong, might be an issue.
                return True, None

            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            new_content = content
            
            for i, patch in enumerate(patches):
                try:
                    new_content = self.apply_patch_block(new_content, patch)
                except ValueError as e:
                    error_msg = f"Search block {i+1} not found in {file_path}"
                    logger.error(error_msg)
                    return False, error_msg

            if dry_run:
                logger.info(f"[DRY RUN] Applied {len(patches)} patches to {file_path}")
                return True, None

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            logger.info(f"Part replacement complete: {file_path}, {len(patches)} blocks.")
            return True, None

        except Exception as e:
            error_msg = f"Part patch failed: {e}"
            logger.error(error_msg)
            return False, error_msg

    def apply_patch_block(self, content: str, patch: PatchBlock) -> str:
        search_block = patch.search_line
        replace_block = patch.replace_line
        
        # Find block using flexible strategy
        start_idx, end_idx = self._find_match_index(content, search_block)
        
        if start_idx == -1:
            logger.debug(f"Search Block:\n{search_block!r}")
            raise ValueError("Search block not found")

        # Check for multiple occurrences to warn (only strict matches for warning)
        count = content.count(search_block)
        if count > 1:
            logger.warning(
                f"Search block found {count} times. Using the last occurrence (rfind)."
            )

        # Perform replacement
        pre = content[:start_idx]
        post = content[end_idx:]
        return pre + replace_block + post

    def _parse_blocks(self, text: str) -> List[PatchBlock]:
        """
        Parse the text for <<< SEARCH, ===, >>> REPLACE blocks.
        Returns a list of PatchBlock objects.
        """
        lines = text.splitlines(keepends=True)
        patches = []
        
        search_lines = []
        replace_lines = []
        
        # States: 'IDLE', 'SEARCHING', 'REPLACING'
        state = 'IDLE'
        
        for line in lines:
            stripped = line.strip()
            
            if state == 'IDLE':
                if stripped == '<<< SEARCH':
                    state = 'SEARCHING'
                    search_lines = []
            
            elif state == 'SEARCHING':
                if stripped == '===':
                    state = 'REPLACING'
                    replace_lines = []
                else:
                    search_lines.append(line)
            
            elif state == 'REPLACING':
                if stripped == '>>> REPLACE':
                    state = 'IDLE'
                    # Join lines to form blocks
                    # We usually want to strip the last newline if it was added by splitlines
                    # but the content lines themselves have newlines.
                    search_block = "".join(search_lines)
                    replace_block = "".join(replace_lines)
                    
                    # Note: The markers are usually on their own lines.
                    # If the code inside ended with a newline, keeping it is correct.
                    # However, if the user put `===` right after code without newline, 
                    # strict `splitlines(keepends=True)` captures the newline on the code line.
                    
                    # One Edge Case: 
                    # If the file content is:
                    # code
                    # code
                    #
                    # And block is:
                    # <<< SEARCH
                    # code
                    # code
                    # ===
                    #
                    # `search_lines` will have ["code\n", "code\n"]. 
                    # If the file has "code\ncode" (no final newline), this might fail matching "code\ncode\n".
                    # But Python source usually has final newlines.
                    # We will try exact join first.
                    
                    patches.append(PatchBlock(search_line=search_block, replace_line=replace_block))
                else:
                    replace_lines.append(line)
                    
        return patches

    def _find_match_index(self, content: str, search_block: str) -> Tuple[int, int]:
        """
        Find the start and end indices of search_block in content.
        Tries flexible matching strategies.
        """
        # 1. Exact match
        index = content.rfind(search_block)
        if index != -1:
            return index, index + len(search_block)

        # 2. Match ignoring trailing newlines in search block
        stripped_search = search_block.rstrip('\n')
        # Only try if stripping actually changed something to avoid redundant search
        if len(stripped_search) < len(search_block):
            index = content.rfind(stripped_search)
            if index != -1:
                return index, index + len(stripped_search)
        
        # 3. Fuzzy match (line-by-line ignoring trailing whitespace)
        return self._fuzzy_find_indices(content, search_block)

    def _fuzzy_find_indices(self, content: str, search_block: str) -> Tuple[int, int]:
        """
        Scan content for lines matching search_block lines, ignoring trailing whitespace.
        Returns (start_index, end_index) in content, or (-1, -1).
        """
        search_lines = search_block.splitlines()
        if not search_lines:
             if not search_block:
                 return -1, -1
             return -1, -1

        search_norm = [line.rstrip() for line in search_lines]
        
        content_lines = content.splitlines(keepends=True)
        content_norm = [line.rstrip() for line in content_lines]
        
        n_search = len(search_norm)
        n_content = len(content_norm)
        
        if n_search > n_content:
            return -1, -1
        
        # Search backwards
        for i in range(n_content - n_search, -1, -1):
            candidate = content_norm[i : i + n_search]
            if candidate == search_norm:
                # Match found
                # Calculate start index
                start_index = sum(len(x) for x in content_lines[:i])
                # Calculate match length
                match_length = sum(len(x) for x in content_lines[i : i + n_search])
                
                return start_index, start_index + match_length
                
        return -1, -1
