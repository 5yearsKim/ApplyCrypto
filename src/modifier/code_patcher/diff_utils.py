import re
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class LineType(str, Enum):
    CONTEXT = " "
    ADD = "+"
    DELETE = "-"


class HunkLine(BaseModel):
    type: LineType
    content: str  # without prefix


class UnifiedDiffHunk(BaseModel):
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    section_header: Optional[str] = None
    lines: List[HunkLine] = Field(default_factory=list)

    def old_text(self) -> List[str]:
        return [
            l.content for l in self.lines
            if l.type in (LineType.CONTEXT, LineType.DELETE)
        ]

    def new_text(self) -> List[str]:
        return [
            l.content for l in self.lines
            if l.type in (LineType.CONTEXT, LineType.ADD)
        ]


class FileDiff(BaseModel):
    old_path: str
    new_path: str
    hunks: List[UnifiedDiffHunk] = Field(default_factory=list)

    @property
    def is_new_file(self) -> bool:
        return self.old_path == "/dev/null"

    @property
    def is_deleted_file(self) -> bool:
        return self.new_path == "/dev/null"

    @property
    def is_rename(self) -> bool:
        return (
            self.old_path != "/dev/null"
            and self.new_path != "/dev/null"
            and self.old_path != self.new_path
        )

    @property
    def target_path(self) -> str:
        """
        Where patch should be applied / created.
        """
        if self.is_new_file:
            return self.new_path
        return self.old_path


class UnifiedDiff(BaseModel):
    files: List[FileDiff] = Field(default_factory=list)


def parse_diff(diff_content: str) -> UnifiedDiff:
    """
    Parses a unified diff string into a UnifiedDiff object.
    It supports creating a file entry even if the diff lacks '---'/'+++' headers
    but contains Hunks (starts with @@).
    """
    lines = diff_content.splitlines()
    files: List[FileDiff] = []
    current_file: Optional[FileDiff] = None
    current_hunk: Optional[UnifiedDiffHunk] = None
    
    # Regex for hunk header
    # Matches: @@ -1,2 +3,4 @@ optional section header
    # Note: count is optional and defaults to 1 if omitted
    hunk_header_pattern = re.compile(
        r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*\n?)?$"
    )

    i = 0
    while i < len(lines):
        line = lines[i]
        
        # File Headers
        # --- a/file.py
        # +++ b/file.py
        if line.startswith("--- "):
            old_path = line[4:].strip()
            # Look ahead for +++
            if i + 1 < len(lines) and lines[i+1].startswith("+++ "):
                new_path = lines[i+1][4:].strip()
                current_file = FileDiff(old_path=old_path, new_path=new_path)
                files.append(current_file)
                current_hunk = None
                i += 2
                continue
        
        # Hunk Header
        if line.startswith("@@ "):
            match = hunk_header_pattern.match(line.strip())
            if match:
                # If no file header was seen, create a dummy file for these hunks
                if current_file is None:
                    if files:
                        current_file = files[-1] # use last known file?
                    else:
                        current_file = FileDiff(old_path="/dev/null", new_path="/dev/null")
                        files.append(current_file)

                old_start = int(match.group(1))
                old_count = int(match.group(2)) if match.group(2) is not None else 1
                new_start = int(match.group(3))
                new_count = int(match.group(4)) if match.group(4) is not None else 1
                section = match.group(5)

                current_hunk = UnifiedDiffHunk(
                    old_start=old_start,
                    old_count=old_count,
                    new_start=new_start,
                    new_count=new_count,
                    section_header=section.strip() if section else None
                )
                current_file.hunks.append(current_hunk)
                i += 1
                continue
        
        # Hunk Content
        if current_hunk:
            if line.startswith(" "):
                current_hunk.lines.append(HunkLine(type=LineType.CONTEXT, content=line[1:]))
            elif line.startswith("-"):
                current_hunk.lines.append(HunkLine(type=LineType.DELETE, content=line[1:]))
            elif line.startswith("+"):
                current_hunk.lines.append(HunkLine(type=LineType.ADD, content=line[1:]))
            elif line == "":
                 # Assuming empty context line
                 current_hunk.lines.append(HunkLine(type=LineType.CONTEXT, content=""))
            # Ignore standard Property changes or git comments if any
            elif line.startswith("\\ No newline"):
                pass
            else:
                 # Line doesn't look like diff content. 
                 # Could be end of diff or unrecognized.
                 pass
        
        i += 1

    return UnifiedDiff(files=files)
