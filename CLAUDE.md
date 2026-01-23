# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ApplyCrypto는 Java Spring Boot 레거시 시스템에서 민감한 개인정보를 암호화/복호화하도록 소스 코드를 자동으로 분석하고 수정하는 AI 기반 도구입니다. 정적 코드 분석, 콜 그래프 순회, LLM 기반 코드 생성을 사용합니다.

## Common Commands

### Running the Tool
```bash
# Analyze project (collect source files, build call graph, identify DB access patterns)
python main.py analyze --config config.json

# List analysis results
python main.py list --all          # All source files
python main.py list --db           # Table access information
python main.py list --endpoint     # REST API endpoints
python main.py list --callgraph EmpController.login  # Method call chain

# Modify code (insert encryption/decryption logic)
python main.py modify --config config.json --dry-run  # Preview only
python main.py modify --config config.json            # Apply changes

# Launch Streamlit UI
python run_ui.py
```

### Development Commands
```bash
pytest                                      # Run all tests
pytest tests/test_db_access_analyzer.py     # Run specific test
pytest --cov=src --cov-report=html          # Tests with coverage

# Linting (run before commit)
./scripts/lint.ps1                          # Windows
isort . && ruff format && ruff check --fix  # Manual
```

### Environment Variables
Create a `.env` file with LLM provider credentials:
```
WATSONX_API_URL=https://us-south.ml.cloud.ibm.com
WATSONX_API_KEY=your_api_key
WATSONX_PROJECT_ID=your_project_id
```

## Architecture Overview

### Layered Architecture Flow
```
CLI Layer → Configuration → Collection → Parsing → Analysis → Modification → Persistence
```

1. **CLI Layer** (`src/cli/`) → Entry point, orchestrates workflow
2. **Configuration Layer** (`src/config/`) → JSON config with Pydantic validation
3. **Collection Layer** (`src/collector/`) → Recursive source file collection
4. **Parsing Layer** (`src/parser/`) → Java AST (tree-sitter), XML Mappers, Call Graph (NetworkX)
5. **Analysis Layer** (`src/analyzer/`) → DB access patterns via call graph traversal
6. **Modification Layer** (`src/modifier/`) → LLM-based code generation and patching
7. **LLM Layer** (`src/modifier/llm/`) → Provider abstraction (WatsonX, OpenAI, Claude)
8. **Persistence Layer** (`src/persistence/`) → JSON serialization and caching

### Key Design Patterns

**Strategy Pattern** - 새로운 프레임워크나 SQL 타입 추가 시 확장:
- `LLMProvider`: LLM 프로바이더 추상화 (`src/modifier/llm/`)
- `EndpointExtractionStrategy`: 프레임워크별 엔드포인트 추출 (`src/parser/endpoint_strategy/`)
- `SQLExtractor`: SQL 래핑 타입별 추출 전략 (`src/analyzer/sql_extractors/`)
- `BaseCodeGenerator`: 코드 생성 전략 (`src/modifier/code_generator/`)
- `ContextGenerator`: 컨텍스트 생성 전략 (`src/modifier/context_generators/`)

**Factory Pattern** - 설정 기반 전략 생성:
- `LLMFactory`, `EndpointExtractionStrategyFactory`, `SQLExtractorFactory`
- `CodeGeneratorFactory`, `ContextGeneratorFactory`

### Configuration Schema

The `config.json` file drives the entire workflow. Key fields:

| Field | Description |
|-------|-------------|
| `framework_type` | `SpringMVC`, `AnyframeSarangOn`, `AnyframeCCS`, `anyframe_ccs_batch` 등 |
| `sql_wrapping_type` | `mybatis`, `mybatis_ccs`, `mybatis_ccs_batch`, `jdbc`, `jpa` |
| `modification_type` | `ControllerOrService`, `ServiceImplOrBiz`, `TypeHandler`, `TwoStep`, `ThreeStep` |
| `llm_provider` | `watsonx_ai`, `watsonx_ai_on_prem`, `claude_ai`, `openai`, `mock` |
| `access_tables` | 암호화 대상 테이블/칼럼 목록 |

See `config.example.json` for complete schema with all options.

### Call Graph Traversal

Call Graph (`src/parser/call_graph_builder.py`)는 NetworkX를 사용하여 메서드 호출 관계를 추적합니다:
- 노드: `class_name.method_name` 형태의 메서드
- 엣지: 인수 추적이 포함된 호출 관계
- 순회: DB 접근 지점에서 역방향 BFS로 모든 호출자 식별
- 결과: `Controller → Service → DAO → Mapper` 경로 추적

### Multi-Step Code Generation

복잡한 코드 수정의 정확성을 높이기 위해 **다단계 LLM 협업 전략**을 지원합니다:

#### TwoStep (2단계)
```
Phase 1: Planning (데이터 흐름 분석) → Phase 2: Execution (코드 생성)
```

**설정 예시:**
```json
{
  "modification_type": "TwoStep",
  "two_step_config": {
    "planning_provider": "watsonx_ai",
    "planning_model": "ibm/granite-3-8b-instruct",
    "execution_provider": "watsonx_ai",
    "execution_model": "mistralai/codestral-2505"
  }
}
```

#### ThreeStep (3단계)
```
Phase 1: Query Analysis (VO/SQL 매핑) → Phase 2: Planning (수정 지침) → Phase 3: Execution (코드 생성)
```

Phase 1에서 VO 파일과 SQL 쿼리의 필드 매핑을 먼저 분석하여 Planning의 정확성을 높입니다.

**설정 예시:**
```json
{
  "modification_type": "ThreeStep",
  "three_step_config": {
    "analysis_provider": "watsonx_ai",
    "analysis_model": "ibm/granite-3-8b-instruct",
    "execution_provider": "watsonx_ai",
    "execution_model": "mistralai/codestral-2505"
  }
}
```

#### Execution Modes
두 전략 모두 `execution_options.mode`로 실행 모드를 제어합니다:
- `full`: 전체 파이프라인 실행 (기본값)
- `plan_only`: Planning 단계만 실행, 결과를 `.applycrypto/{two,three}_step_results/`에 저장
- `execution_only`: 이전 Planning 결과를 사용하여 Execution만 실행 (`plan_timestamp` 필요)

### Data Persistence

분석 결과는 JSON으로 영속화됩니다:
- `{project_root}/build/applycrypto_source_files.json`
- `{project_root}/build/applycrypto_call_graph.json`
- `{project_root}/build/applycrypto_table_access.json`
- `{project_root}/build/applycrypto_modification_records.json`

`CacheManager`는 파싱 결과를 캐싱하여 후속 실행 속도를 높입니다.

## Important Conventions

### Naming Patterns
| Type | Pattern | Example |
|------|---------|---------|
| Analyzers | `*Analyzer` | `DBAccessAnalyzer` |
| Parsers | `*Parser` | `JavaASTParser` |
| Generators | `*Generator` | `TwoStepCodeGenerator` |
| Extractors | `*Extractor` | `MyBatisSQLExtractor` |
| Providers | `*Provider` | `WatsonXAIProvider` |

### Adding New Strategies
새로운 프레임워크나 SQL 타입을 추가할 때:
1. 해당 Strategy 베이스 클래스 상속 (예: `SQLExtractor`, `EndpointExtractionStrategy`)
2. 해당 하위 디렉토리에 구현체 추가
3. Factory 클래스에 enum/생성 로직 추가
4. `config.example.json`에 새 옵션 문서화

### Template System
각 코드 생성기는 Jinja2 템플릿을 사용합니다:
```
src/modifier/code_generator/
├── two_step_type/
│   ├── planning_template.md
│   └── execution_template.md
└── three_step_type/
    ├── data_mapping_template.md   # Phase 1: VO/SQL 매핑
    ├── planning_template.md       # Phase 2: 수정 지침
    └── execution_template.md      # Phase 3: 코드 생성
```

주요 템플릿 변수: `{{source_code}}`, `{{table_info}}`, `{{call_chain}}`, `{{mapping_info}}`

### Error Handling
- 커스텀 예외: `ConfigurationError`, `CodeGeneratorError`, `PersistenceError`
- 로거: `logging.getLogger("applycrypto")`
- 검증: 모든 설정과 데이터 모델에 Pydantic 스키마 사용

## Korean Language Support

이 프로젝트는 한국어를 사용합니다:
- README, 문서화, CLI 메시지
- 도메인 관련 코드 주석

코드 명확성을 위해 변수명과 docstring은 영어로 유지합니다.
