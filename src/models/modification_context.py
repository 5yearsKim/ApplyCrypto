from dataclasses import dataclass
from typing import List, Literal


@dataclass
class ModificationContext:
    file_paths: List[str]
    table_name: str
    columns: List[dict]
    file_count: int
    layer: Literal["service", "mapper"]
