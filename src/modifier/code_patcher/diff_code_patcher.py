import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from config.config_manager import Configuration
from persistence.debug_manager import DebugManager
from .base_code_patcher import BaseCodePatcher
from .diff_utils import FileDiff, LineType, UnifiedDiffHunk, parse_diff

logger = logging.getLogger("applycrypto.code_patcher")


class DiffCodePatcher(BaseCodePatcher):
    """
    Code patcher that applies Unified Diff patches.
    """

    def __init__(self, project_root: Optional[Path] = None, config: Optional[Configuration] = None):
        super().__init__(project_root, config)
        if config:
            self.debug_manager = DebugManager(config)
            # Do NOT call initialize_debug_directory here as it wipes the directory.
            # It is expected to be initialized by the CLI controller.
        else:
            self.debug_manager = None

    def apply_patch(
        self, file_path: Path, modified_code: str, dry_run: bool = False
    ) -> Tuple[bool, Optional[str]]:
        """
        Apply a Unified Diff to a file.
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

            if dry_run:
                logger.info(f"[DRY RUN] Simulate Patching: {file_path}")
                return True, None

            # Handle Markdown Code Blocks
            stripped_code = modified_code.strip()
            if stripped_code.startswith("```"):
                # Find first newline
                first_newline = stripped_code.find("\n")
                if first_newline != -1:
                    stripped_code = stripped_code[first_newline + 1 :]
                if stripped_code.endswith("```"):
                    stripped_code = stripped_code[:-3]
                modified_code = stripped_code.strip()

            # Parse the diff
            unified_diff = parse_diff(modified_code)

            if not unified_diff.files:
                return False, "No valid diff blocks found in the provided code."
            
            if len(unified_diff.files) > 1:
                return False, "Multiple files in diff is not supported. Please provide a diff for a single file."


            # We assume the diff corresponds to the file_path.
            file_diff = unified_diff.files[0]
            

            return self._apply_patch_using_difflib(file_path, file_diff, dry_run)

        except Exception as e:
            error_msg = f"Patch application failed: {e}"
            logger.error(error_msg)
            return False, error_msg


    def _apply_patch_using_difflib(
        self, file_path: Path, file_diff: FileDiff, dry_run: bool = False
    ) -> Tuple[bool, Optional[str]]:
        """
        Apply patch using struct approach with flexible context matching.
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Split keeping newlines to preserve unknown line endings
            original_lines = content.splitlines(keepends=True)
            new_lines = []
            current_original_idx = 0
            
            # Sort hunks
            hunks = sorted(file_diff.hunks, key=lambda h: h.old_start)
            
            for hunk in hunks:
                # Find modification point based on context
                result = self._find_modification_point(
                    original_lines, hunk, current_original_idx
                )
                if result is None:
                    if self.debug_manager:
                        hunk_str = self._format_hunk(hunk)
                        self.debug_manager.log_rejected_hunk(
                            filename=file_path.name,
                            hunk_detail=hunk_str,
                            reason=f"Context not found for hunk at old_line={hunk.old_start}"
                        )
                    continue
                match_idx, match_len, skipped_map = result
                
                # Copy lines before hunk
                new_lines.extend(original_lines[current_original_idx:match_idx])
                
                # Apply new content, injecting skipped lines
                old_text_idx = 0
                for line in hunk.lines:
                    if line.type in (LineType.CONTEXT, LineType.DELETE):
                         # If we skipped comments/lines before this matching old line, inject them now
                        if old_text_idx in skipped_map:
                            new_lines.extend(skipped_map[old_text_idx])
                        
                        old_text_idx += 1
                        
                        if line.type == LineType.CONTEXT:
                            new_lines.append(line.content + "\n")
                        # If DELETE, we skip appending the content
                    
                    elif line.type == LineType.ADD:
                        new_lines.append(line.content + "\n")
                
                # Advance current_idx
                # We skip the lines that were consumed (context + deleted + skipped comments)
                current_original_idx = match_idx + match_len
            
            # Copy remaining lines
            new_lines.extend(original_lines[current_original_idx:])
            
            # Write back
            if dry_run:
                logger.info(f"[DRY RUN] Simulating write to {file_path}")
                return True, None
                
            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
                
            logger.info(f"Patch applied successfully to {file_path}")
            return True, None

        except Exception as e:
            error_msg = f"Patch failed: {e}"
            logger.error(error_msg)
            return False, error_msg

    def _find_modification_point(
        self, original_lines: List[str], hunk: UnifiedDiffHunk, search_start_idx: int
    ) -> Optional[Tuple[int, int, Dict[int, List[str]]]]:
        """
        Find the line index in original_lines where the hunk's old_text matches.
        Returns tuple of (start_index, consumed_line_count, skipped_lines_map).
        skipped_lines_map is { old_text_index: [list of raw skipped lines] }
        """
        expected_lines = hunk.old_text()
        
        # If no expected lines (pure addition), we must rely on old_start or search_start_idx
        if not expected_lines:
            target = hunk.old_start - 1
            # Ensure we don't go backwards
            if target < search_start_idx:
                return search_start_idx, 0, {}
            return target, 0, {}

        def check_match(start_idx: int) -> Tuple[int, Dict[int, List[str]]]:
            """
            Check if expected_lines match at start_idx, allowing for skipped comments.
            Returns (number of original lines consumed, skipped_map) if match, (-1, {}) otherwise.
            """
            exp_i = 0
            orig_i = 0
            local_skipped_map: Dict[int, List[str]] = {}
            
            while exp_i < len(expected_lines):
                current_orig_idx = start_idx + orig_i
                
                if current_orig_idx >= len(original_lines):
                    return -1, {} # End of file
                
                raw_line_orig = original_lines[current_orig_idx]
                line_orig = raw_line_orig.rstrip()
                line_exp = expected_lines[exp_i].rstrip()
                
                if line_orig == line_exp:
                    exp_i += 1
                    orig_i += 1
                    continue
                
                # Mismatch: Check if original line is skippable (comment/empty)
                # But NOT if the expected line matches it (already handled by == check)
                if self._check_is_skippable(line_orig):
                    if exp_i not in local_skipped_map:
                        local_skipped_map[exp_i] = []
                    local_skipped_map[exp_i].append(raw_line_orig)
                    orig_i += 1
                    continue
                
                return -1, {} # Real mismatch
            
            return orig_i, local_skipped_map

        # 1. Try Hint (hunk.old_start - 1)
        hint_idx = hunk.old_start - 1
        if hint_idx >= search_start_idx:
            consumed, s_map = check_match(hint_idx)
            if consumed != -1:
                return hint_idx, consumed, s_map

        # 2. Search forward from search_start_idx
        for idx in range(search_start_idx, len(original_lines)):
            if idx == hint_idx:
                continue
            consumed, s_map = check_match(idx)
            if consumed != -1:
                return idx, consumed, s_map
        
        # Not found
        context_snippet = "\\n".join(expected_lines[:3])
        if len(expected_lines) > 3:
            context_snippet += "\\n..."
        
        logger.error(
            f"Context not found for hunk at old_line={hunk.old_start}:\\n{context_snippet}"
        )
        return None

    def _check_is_skippable(self, line_content: str) -> bool:
        """
        Check if a line in the original file can be skipped if it doesn't match the diff context.
        This allows for flexible matching even if LLM removed comments/empty lines in the diff.
        """
        s = line_content.strip()
        if not s:
            return True
        # Comments
        if s.startswith("//"): return True
        if s.startswith("#"): return True
        if s.startswith("/*") or s.startswith("*"): return True # Javadoc style
        return False

    def _format_hunk(self, hunk: UnifiedDiffHunk) -> str:
        """
        Reconstruct hunk string for logging.
        """
        lines = []
        # Header
        header = f"@@ -{hunk.old_start},{hunk.old_count} +{hunk.new_start},{hunk.new_count} @@"
        if hunk.section_header:
            header += f" {hunk.section_header}"
        lines.append(header)
        
        for line in hunk.lines:
            prefix = line.type.value
            lines.append(f"{prefix}{line.content}")
            
        return "\n".join(lines)
