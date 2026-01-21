# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ApplyCrypto is an AI-powered tool that automatically analyzes and modifies Java Spring Boot legacy systems to encrypt/decrypt sensitive personal information in database operations. It uses static code analysis, call graph traversal, and LLM-based code generation to insert encryption logic into identified files.

## Common Commands

### Setup and Installation
```bash
# Windows PowerShell setup
./scripts/setup.ps1

# Activate virtual environment
source .venv/bin/activate  # Linux/Mac
.\.venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt
```

### Running the Tool
```bash
# Analyze project (collect source files, build call graph, identify DB access patterns)
python main.py analyze --config config.json

# List analysis results
python main.py list --all          # All source files
python main.py list --db           # Table access information
python main.py list --endpoint     # REST API endpoints
python main.py list --callgraph EmpController.login  # Method call chain
python main.py list --modified     # Modified files history

# Modify code (insert encryption/decryption logic)
python main.py modify --config config.json --dry-run  # Preview only
python main.py modify --config config.json            # Apply changes
python main.py modify --config config.json --debug    # Show diff with line numbers

# Clear backup files
python main.py clear

# Launch Streamlit UI
python run_ui.py
```

### Development Commands
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_db_access_analyzer.py

# Run tests with coverage
pytest --cov=src --cov-report=html

# Linting (Windows)
./scripts/lint.ps1

# Linting (manual)
isort .
ruff format
ruff check --fix

# Clear backup files (generated during modification)
python main.py clear
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
The system follows a strict layered architecture with clear separation of concerns:

1. **CLI Layer** (`src/cli/`) → Entry point that orchestrates all other layers
2. **Configuration Layer** (`src/config/`) → Loads and validates JSON config with Pydantic schemas
3. **Collection Layer** (`src/collector/`) → Recursively collects source files with filtering
4. **Parsing Layer** (`src/parser/`) → Parses Java AST and XML Mappers, builds call graphs
5. **Analysis Layer** (`src/analyzer/`) → Identifies DB access patterns via call graph traversal
6. **Modification Layer** (`src/modifier/`) → LLM-based code generation and patching
7. **LLM Layer** (`src/modifier/llm/`) → Abstract provider interface with multiple implementations
8. **Persistence Layer** (`src/persistence/`) → JSON serialization and caching

### Key Design Patterns

**Strategy Pattern** is used extensively:
- `LLMProvider`: WatsonX, WatsonX On-Prem, OpenAI, Claude implementations
- `EndpointExtractionStrategy`: Framework-specific endpoint extraction
  - `SpringMVCEndpointExtraction`, `AnyframeSarangOnEndpointExtraction`
  - `AnyframeCCSEndpointExtraction`, `AnyframeCCSBatchEndpointExtraction`
  - `AnyframeBatEtcEndpointExtraction`
- `SQLExtractor`: SQL wrapping type strategies
  - `MyBatisSQLExtractor`, `MyBatisCCSSQLExtractor`, `MyBatisCCSBatchSQLExtractor`
  - `JDBCSQLExtractor`, `JPASQLExtractor`
  - `AnyframeJDBCSQLExtractor`, `AnyframeJDBCBatSQLExtractor`
- `BaseCodeGenerator`: Modification type strategies
  - `TypeHandlerCodeGenerator`, `ControllerServiceCodeGenerator`
  - `ServiceImplBizCodeGenerator`, `TwoStepCodeGenerator`
- `ContextGenerator`: Context generation strategies
  - `MybatisContextGenerator`, `MybatisCCSContextGenerator`, `MybatisCCSBatchContextGenerator`
  - `JdbcContextGenerator`, `PerLayerContextGenerator`

**Factory Pattern**:
- `LLMFactory`: Creates appropriate LLM provider based on config
- `EndpointExtractionStrategyFactory`: Creates framework-specific endpoint extractors
- `SQLExtractorFactory`: Creates SQL extractor based on wrapping type
- `CodeGeneratorFactory`: Creates code generator based on modification type
- `ContextGeneratorFactory`: Creates context generator based on SQL wrapping type

### Configuration Schema

The `config.json` file drives the entire workflow. Critical fields:

- `framework_type`: Framework detection strategy
  - `SpringMVC`, `AnyframeSarangOn`, `AnyframeOld`, `AnyframeEtc`
  - `AnyframeCCS`, `anyframe_ccs_batch`: CCS framework variants
  - `SpringBatQrts`, `AnyframeBatSarangOn`, `AnyframeBatEtc`: Batch variants
- `sql_wrapping_type`: How SQL is accessed
  - `mybatis`: Standard MyBatis XML mappers
  - `mybatis_ccs`: CCS-specific MyBatis (ctl/svcimpl/dqm layers)
  - `mybatis_ccs_batch`: CCS Batch MyBatis (*BAT_SQL.xml files)
  - `jdbc`, `jpa`: Other SQL wrapping methods
- `modification_type`: Where to insert encryption logic
  - `TypeHandler`: MyBatis TypeHandler approach
  - `ControllerOrService`: Controller/Service layer modification
  - `ServiceImplOrBiz`: ServiceImpl/Biz layer modification
  - `TwoStep`: Two-phase LLM collaboration (Planning + Execution)
- `two_step_config`: Required when `modification_type` is `TwoStep`
  - `planning_provider`, `planning_model`: LLM for data flow analysis
  - `execution_provider`, `execution_model`: LLM for code generation
- `llm_provider`: AI model to use (`watsonx_ai`, `watsonx_ai_on_prem`, `claude_ai`, `openai`, `mock`)
- `access_tables`: Tables/columns requiring encryption
- `generate_full_source`: Whether to include full source in prompts (uses `template_full.md` instead of `template.md`)
- `use_call_chain_mode`: Enable call chain traversal mode
- `use_llm_parser`: Use LLM for SQL extraction when static analysis fails
- `max_tokens_per_batch`: Maximum tokens per batch (default: 8000)

See `config.example.json` for complete schema.

### Call Graph Traversal

The call graph (`src/parser/call_graph_builder.py`) uses NetworkX to build a directed graph of method calls:
- Nodes: Methods (identified by `class_name.method_name`)
- Edges: Call relationships with argument tracking
- Entry points: REST endpoints extracted via framework-specific strategies
- Traversal: Reverse BFS from DB access points to find all callers

This enables tracing: `Controller → Service → DAO → Mapper` to identify which files need encryption logic.

### LLM-Based Code Modification

The modification workflow (`src/modifier/code_modifier.py`):

1. **Context Generation**: `ContextGenerator` creates `ModificationContext` objects with:
   - Source file content (full or partial based on `generate_full_source`)
   - Table/column metadata
   - Framework-specific hints

2. **Prompt Template Rendering**: Jinja2 templates (`template.md` or `template_full.md`) in each code generator directory are rendered with context variables

3. **LLM Code Generation**: `BaseCodeGenerator` subclasses call LLM provider and parse response

4. **Code Patching**: `CodePatcher` applies unified diff format patches to source files

5. **Error Handling**: `ErrorHandler` provides automatic retry with exponential backoff

6. **Result Tracking**: `ResultTracker` records all modifications with metadata

### Two-Step Code Generation (TwoStep)

The `TwoStepCodeGenerator` implements a two-phase LLM collaboration strategy for improved code generation quality:

**Phase 1: Planning (Data Flow Analysis)**
- Uses a model optimized for logical reasoning (e.g., GPT-OSS-120B, Claude Sonnet)
- Analyzes data flow through the call chain
- Identifies where encryption/decryption should be inserted
- Generates detailed modification instructions as structured JSON
- Template: `planning_template.md`

**Phase 2: Execution (Code Generation)**
- Uses a model optimized for code generation (e.g., Codestral-2508, GPT-4)
- Receives planning instructions from Phase 1
- Generates actual code patches following the plan
- Template: `execution_template.md`

**Configuration Example:**
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

**Key Benefits:**
- Separation of concerns: logical analysis vs code generation
- Better data flow understanding before code modification
- Reduced hallucination in code generation
- Model specialization: use best model for each task

### Parsing Infrastructure

**Java AST Parsing** (`src/parser/java_ast_parser.py`):
- Uses `tree-sitter` with `tree-sitter-java` grammar
- Extracts: classes, methods, annotations, method calls
- Captures method signatures with parameters and return types

**MyBatis XML Parsing** (`src/parser/xml_mapper_parser.py`):
- Uses `lxml` to parse SQL mapper XMLs
- Extracts SQL queries from `<select>`, `<insert>`, `<update>`, `<delete>` tags
- Identifies table/column references from SQL text

**Call Graph Building** (`src/parser/call_graph_builder.py`):
- Combines parsed Java and XML data
- Builds directed graph with method calls as edges
- Stores method metadata (class, package, file path, line numbers)
- Supports argument tracking for method invocations

### SQL Extraction Strategies

Different projects wrap SQL in different ways. `SQLExtractor` implementations handle:

- **MyBatis**: Extract from XML mapper files, match to Java DAO methods
- **MyBatis CCS**: CCS-specific MyBatis with ctl/svcimpl/dqm layer structure
- **MyBatis CCS Batch**: CCS Batch programs with `*BAT_SQL.xml` files
  - XML structure: `<sql>/<query id="...">SQL</query></sql>`
  - File mapping: `xxxBAT_SQL.xml → xxxBAT.java`
  - Collects related VO files from `batvo/` directory
- **JDBC**: Find `PreparedStatement` and SQL strings in Java code
- **JPA**: Parse entity annotations and JPQL queries
- **Anyframe JDBC**: Handle StringBuilder-based dynamic SQL construction
- **Anyframe JDBC Batch**: Batch-specific JDBC SQL extraction
- **LLM Fallback**: When static analysis fails, use LLM to extract SQL from code

### Data Persistence

All intermediate results are persisted as JSON:
- Source files metadata: `{project_root}/build/applycrypto_source_files.json`
- Call graph: `{project_root}/build/applycrypto_call_graph.json`
- Table access info: `{project_root}/build/applycrypto_table_access.json`
- Modification records: `{project_root}/build/applycrypto_modification_records.json`

Custom JSON encoder/decoder (`src/persistence/`) handle dataclass serialization.

Caching (`src/persistence/cache_manager.py`) stores parsed results to speed up subsequent runs.

## Important Conventions

### Module Organization
- Each layer is a top-level package under `src/`
- Strategy implementations go in subdirectories (e.g., `sql_extractors/`, `endpoint_strategy/`, `code_generator/`)
- Factory classes create strategies based on config enums
- Base classes are abstract with clear interfaces

### Naming Patterns
- Analyzers: `*Analyzer` (e.g., `DBAccessAnalyzer`)
- Parsers: `*Parser` (e.g., `JavaASTParser`, `XMLMapperParser`)
- Builders: `*Builder` (e.g., `CallGraphBuilder`)
- Generators: `*Generator` (e.g., `TypeHandlerCodeGenerator`)
- Extractors: `*Extractor` (e.g., `MyBatisSQLExtractor`)
- Providers: `*Provider` (e.g., `WatsonXAIProvider`)
- Strategies: `*Strategy` (e.g., `EndpointExtractionStrategy`)

### Error Handling
- Custom exception classes: `ConfigurationError`, `CodeGeneratorError`, `PersistenceError`
- Logger naming: Use module path (e.g., `logging.getLogger(__name__)`)
- Validation: Pydantic schemas for all config and data models

### Template System
- Each code generator type has its own directory with templates
- `template.md`: Partial source context (default)
- `template_full.md`: Full source context (when `generate_full_source: true`)
- TwoStep generator uses separate templates:
  - `planning_template.md`: For data flow analysis phase
  - `execution_template.md`: For code generation phase
- Templates use Jinja2 syntax with variables like:
  - `{{source_code}}`: Source file content
  - `{{table_info}}`: Table and column metadata
  - `{{call_chain}}`: Method call chain from endpoint to DB access
  - `{{vo_files}}`: Related Value Object files (for CCS Batch)
  - `{{planning_result}}`: Planning phase output (for TwoStep execution)

## Testing Guidelines

- Test files mirror source structure: `test_{module_name}.py`
- Integration tests: `test_integration_*.py`
- Use pytest fixtures for common setup
- Mock LLM providers with `MockLLMProvider` for testing modification logic
- Test data in `tests/` directory or inline as strings

## Recent Feature Additions

The following features have been added in recent commits (as of January 2026):

### CCS Batch Support (`bc57d0a`, `b4998d0`)
- Added `MyBatisCCSBatchSQLExtractor` for `*BAT_SQL.xml` files
- Added `MybatisCCSBatchContextGenerator` for batch-specific context generation
- Added `AnyframeCCSBatchEndpointExtraction` strategy
- New SQL wrapping type: `mybatis_ccs_batch`
- Collects related VO files from `batvo/` directory

### MyBatis CCS Context Generation (`4e7ebe4`)
- Added `MybatisCCSContextGenerator` for CCS layer structure (ctl/svcimpl/dqm)
- Added `MyBatisCCSSQLExtractor` for CCS-specific SQL extraction
- New SQL wrapping type: `mybatis_ccs`

### Hybrid Parsing Strategy (`b4998d0`)
- Added hybrid parsing for file names generated from Execution phase
- Improved file path resolution in TwoStep code generation

### Two-Step Code Generation (`6a3f28b`)
- Added `TwoStepCodeGenerator` with Planning + Execution phases
- Separate LLM providers/models for each phase
- New modification type: `TwoStep`
- Templates: `planning_template.md`, `execution_template.md`

### Call Graph Enhancements (`21a4ca0`, `a63990d`)
- Added line number tracking in call graph
- Enhanced argument tracking for method invocations
- Improved call chain visualization with `--debug` option

### VO File Handling (`4ad704f`, `354a47d`)
- VO files now passed to LLM in separate prompt section
- Logging of VO files included in prompts
- Fixed to include all VO files from service layer

### Clear Command (`9905a27`)
- Added `python main.py clear` command to remove backup files
- Added `--debug` option for diff with line numbers

## Korean Language Support

This project uses Korean (한글) for:
- README and documentation
- CLI help messages and logging
- Comments in Korean for domain-specific context
- Variable names and docstrings in English for code clarity

When modifying Korean text, ensure UTF-8 encoding is preserved.
