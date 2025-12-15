"""
JSON 스키마 정의 모듈

각 데이터 모델에 대한 JSON 스키마를 정의합니다.
"""

# SourceFile 스키마
SOURCE_FILE_SCHEMA = {
    "type": "object",
    "required": [
        "path",
        "relative_path",
        "filename",
        "extension",
        "size",
        "modified_time",
        "tags",
    ],
    "properties": {
        "path": {"type": "string"},
        "relative_path": {"type": "string"},
        "filename": {"type": "string"},
        "extension": {"type": "string"},
        "size": {"type": "integer"},
        "modified_time": {"type": "string", "format": "date-time"},
        "tags": {"type": "array", "items": {"type": "string"}},
    },
}

# Method 스키마
METHOD_SCHEMA = {
    "type": "object",
    "required": [
        "name",
        "return_type",
        "parameters",
        "access_modifier",
        "class_name",
        "file_path",
    ],
    "properties": {
        "name": {"type": "string"},
        "return_type": {"type": "string"},
        "parameters": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "type"],
                "properties": {
                    "name": {"type": "string"},
                    "type": {"type": "string"},
                    "is_varargs": {"type": "boolean"},
                },
            },
        },
        "access_modifier": {"type": "string"},
        "class_name": {"type": "string"},
        "file_path": {"type": "string"},
        "is_static": {"type": "boolean"},
        "is_abstract": {"type": "boolean"},
        "annotations": {"type": "array", "items": {"type": "string"}},
        "exceptions": {"type": "array", "items": {"type": "string"}},
    },
}

# CallRelation 스키마
CALL_RELATION_SCHEMA = {
    "type": "object",
    "required": ["caller", "callee", "caller_file", "callee_file"],
    "properties": {
        "caller": {"type": "string"},
        "callee": {"type": "string"},
        "caller_file": {"type": "string"},
        "callee_file": {"type": "string"},
        "line_number": {"type": "integer"},
    },
}

# TableAccessInfo 스키마
TABLE_ACCESS_INFO_SCHEMA = {
    "type": "object",
    "required": ["table_name", "columns", "access_files", "query_type"],
    "properties": {
        "table_name": {"type": "string"},
        "columns": {"type": "array", "items": {"type": "string"}},
        "access_files": {"type": "array", "items": {"type": "string"}},
        "query_type": {
            "type": "string",
            "enum": ["SELECT", "INSERT", "UPDATE", "DELETE"],
        },
        "sql_query": {"type": "string"},
        "layer": {"type": "string"},
    },
}

# ModificationRecord 스키마
MODIFICATION_RECORD_SCHEMA = {
    "type": "object",
    "required": [
        "file_path",
        "table_name",
        "column_name",
        "modified_methods",
        "added_imports",
        "timestamp",
    ],
    "properties": {
        "file_path": {"type": "string"},
        "table_name": {"type": "string"},
        "column_name": {"type": "string"},
        "modified_methods": {"type": "array", "items": {"type": "string"}},
        "added_imports": {"type": "array", "items": {"type": "string"}},
        "timestamp": {"type": "string", "format": "date-time"},
        "status": {"type": "string", "enum": ["success", "failed", "skipped"]},
        "error_message": {"type": "string"},
        "diff": {"type": "string"},
    },
}

# 스키마 매핑 딕셔너리
SCHEMA_MAP = {
    "SourceFile": SOURCE_FILE_SCHEMA,
    "Method": METHOD_SCHEMA,
    "CallRelation": CALL_RELATION_SCHEMA,
    "TableAccessInfo": TABLE_ACCESS_INFO_SCHEMA,
    "ModificationRecord": MODIFICATION_RECORD_SCHEMA,
}
