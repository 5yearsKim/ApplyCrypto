import logging
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Tuple

from config.config_manager import Configuration

logger = logging.getLogger("applycrypto.code_patcher")


class BaseCodePatcher(ABC):
    """
    Abstract base class for code patchers.
    """

    def __init__(
        self,
        project_root: Optional[Path] = None,
        config: Optional[Configuration] = None,
    ):
        """
        Initialize BaseCodePatcher.

        Args:
            project_root: Root directory of the project (optional).
            config: Configuration object (optional).
        """
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.config = config

    @abstractmethod
    def apply_patch(
        self, file_path: Path, modified_code: str, dry_run: bool = False
    ) -> Tuple[bool, Optional[str]]:
        """
        Apply changes to a file.

        Args:
            file_path: Path to the file to modify.
            modified_code: The code or diff to apply.
            dry_run: If True, simulate the operation without changes.

        Returns:
            Tuple[bool, Optional[str]]: (Success, Error message)
        """
        pass

    def validate_syntax(self, file_path: Path) -> Tuple[bool, Optional[str]]:
        """
        Validate the syntax of the modified file.

        Args:
            file_path: Path to the file to validate.

        Returns:
            Tuple[bool, Optional[str]]: (Valid, Error message)
        """
        try:
            # Use absolute path from LLM response
            if not file_path.is_absolute():
                logger.warning(
                    f"Relative path passed: {file_path}. Converting to absolute."
                )
                file_path = self.project_root / file_path

            # Normalize path
            file_path = file_path.resolve()

            if not file_path.exists():
                return False, f"File does not exist: {file_path}"

            # Java syntax check
            if file_path.suffix == ".java":
                result = subprocess.run(
                    ["javac", "-Xlint:all", "-cp", ".", str(file_path)],
                    capture_output=True,
                    text=True,
                    cwd=self.project_root,
                )

                if result.returncode != 0:
                    error_msg = f"Java syntax error: {result.stderr}"
                    logger.warning(error_msg)
                    return False, error_msg

            # XML syntax check
            elif file_path.suffix == ".xml":
                result = subprocess.run(
                    ["xmllint", "--noout", str(file_path)],
                    capture_output=True,
                    text=True,
                    cwd=self.project_root,
                )

                if result.returncode != 0:
                    error_msg = f"XML syntax error: {result.stderr}"
                    logger.warning(error_msg)
                    return False, error_msg

            return True, None

        except FileNotFoundError:
            logger.debug("Syntax check tools not found, skipping.")
            return True, None
        except Exception as e:
            logger.warning(f"Error during syntax check: {e}")
            return True, None
