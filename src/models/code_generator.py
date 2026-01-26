from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class CodeGeneratorOutput:
    content: str
    tokens_used: int = 0
    parsed_out: List[Dict[str, Any]] = None
    file_mapping: Optional[Dict[str, str]] = field(default_factory=dict)


@dataclass
class CodeGeneratorInput:
    """Code 생성기 입력 데이터"""

    file_paths: List[str]
    """
    소스 파일 경로 리스트
    ["/abs/path/to/file.py", ...]
    """

    table_info: str
    """테이블 스키마 정보 (JSON string or formatted string)"""

    layer_name: str
    """현재 처리 중인 레이어 이름 (Service, Controller 등)"""

    extra_variables: Dict[str, Any] = None
    """기타 템플릿 변수"""

    context_files: List[str] = None
    """참조용 파일 경로 (VO 등) - 수정 대상이 아닌 컨텍스트 파일"""

    def __post_init__(self):
        if self.extra_variables is None:
            self.extra_variables = {}
        if self.context_files is None:
            self.context_files = []
