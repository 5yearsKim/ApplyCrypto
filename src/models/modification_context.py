from dataclasses import dataclass, field
from typing import List, Literal


@dataclass
class ModificationContext:
    file_paths: List[str]
    table_name: str
    columns: List[dict]
    file_count: int
    layer: Literal["service", "mapper"]
    context_files: List[str] = field(default_factory=list)
    """참조용 파일 (VO 등) - 수정 대상이 아닌 컨텍스트 파일"""
