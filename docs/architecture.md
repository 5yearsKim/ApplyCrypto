# 아키텍처 문서

이 문서는 ApplyCrypto의 아키텍처와 주요 설계 패턴에 대한 상세한 설명을 제공합니다.

## 개요

ApplyCrypto는 Strategy 패턴과 Factory 패턴을 중심으로 한 확장 가능한 아키텍처를 가지고 있습니다. 이를 통해 다양한 프레임워크, SQL 래핑 기술, 코드 수정 방식을 지원할 수 있습니다.

## 핵심 설계 패턴

### 1. Strategy 패턴

Strategy 패턴은 알고리즘을 캡슐화하고 런타임에 선택할 수 있도록 하는 패턴입니다. ApplyCrypto에서는 세 가지 주요 영역에서 Strategy 패턴을 적용했습니다.

#### 1.1 Endpoint Extraction Strategy

**목적**: 다양한 프레임워크 타입에 따라 엔드포인트 추출 방식을 다르게 처리

**구조**:
```
EndpointExtractionStrategy (ABC)
├── SpringMVCStrategy
├── AnyframeSarangOnStrategy
├── AnyframeOldStrategy
├── AnyframeEtcStrategy
├── SpringBatQrtsStrategy
├── AnyframeBatSarangOnStrategy
└── AnyframeBatEtcStrategy
```

**사용 위치**:
- `CallGraphBuilder`: 엔드포인트 추출 시 전략 사용
- `CLIController._handle_analyze()`: `framework_type`에 따라 전략 생성

**예시**:
```python
from parser.endpoint_strategy import EndpointExtractionStrategyFactory

# SpringMVC 전략 생성
strategy = EndpointExtractionStrategyFactory.create(
    framework_type="SpringMVC",
    java_parser=java_parser,
    cache_manager=cache_manager,
)

# 엔드포인트 추출
endpoints = strategy.extract_endpoints_from_classes(classes)
```

#### 1.2 SQL Extraction Strategy

**목적**: 다양한 SQL 래핑 기술(MyBatis, JDBC, JPA)에 따라 SQL 추출 방식을 다르게 처리

**구조**:
```
SQLExtractor (일반 클래스)
├── extract_table_names(sql) -> Set[str] (구현 메서드)
├── extract_column_names(sql, table) -> Set[str] (구현 메서드)
├── MyBatisSQLExtractor
├── JDBCSQLExtractor
└── JPASQLExtractor
```

**특징**:
- `SQLExtractor`는 일반 클래스로, 공통 SQL 파싱 메서드를 제공
- 각 하위 클래스는 `extract_from_files()` 메서드만 구현
- `LLMSQLExtractor`는 공통 유틸리티로 사용

**사용 위치**:
- `DBAccessAnalyzer`: SQL 추출 및 분석
- `CLIController._handle_analyze()`: `sql_wrapping_type`에 따라 전략 생성

**예시**:
```python
from analyzer.sql_extractor_factory import SQLExtractorFactory

# MyBatis 전략 생성
extractor = SQLExtractorFactory.create(
    sql_wrapping_type="mybatis",
    config=config,
    xml_parser=xml_parser,
)

# SQL 추출
sql_queries = extractor.extract_from_files(source_files)
```

#### 1.3 Modification Strategy

**목적**: 다양한 코드 수정 방식(TypeHandler, ControllerOrService, ServiceImplOrBiz)에 따라 수정 전략을 다르게 처리

**구조**:
```
ModificationStrategy (ABC)
├── ControllerOrServiceStrategy
├── TypeHandlerStrategy
└── ServiceImplOrBizStrategy

BaseCodeGenerator (ABC)
├── ControllerOrServiceCodeGenerator
├── TypeHandlerCodeGenerator
└── ServiceImplOrBizCodeGenerator
```

**사용 위치**:
- `CodeModifier`: 코드 수정 시 전략 사용
- `CLIController._handle_modify()`: `modification_type`에 따라 전략 생성

**예시**:
```python
from modifier.modification_strategy import ModificationStrategyFactory

# ControllerOrService 전략 생성
strategy = ModificationStrategyFactory.create(
    modification_type="ControllerOrService",
    config=config,
    llm_provider=llm_provider,
)

# 수정 계획 생성
plans = strategy.generate_modification_plans(table_access_info)
```

### 2. Factory 패턴

Factory 패턴은 객체 생성 로직을 캡슐화하여 클라이언트 코드와 구체적인 클래스 구현을 분리합니다.

#### 2.1 EndpointExtractionStrategyFactory

**목적**: `framework_type`에 따라 적절한 `EndpointExtractionStrategy` 인스턴스 생성

**사용법**:
```python
strategy = EndpointExtractionStrategyFactory.create(
    framework_type="SpringMVC",
    java_parser=java_parser,
    cache_manager=cache_manager,
)
```

#### 2.2 SQLExtractorFactory

**목적**: `sql_wrapping_type`에 따라 적절한 `SQLExtractor` 인스턴스 생성

**사용법**:
```python
extractor = SQLExtractorFactory.create(
    sql_wrapping_type="mybatis",
    config=config,
    xml_parser=xml_parser,
)
```

#### 2.3 ModificationStrategyFactory

**목적**: `modification_type`에 따라 적절한 `ModificationStrategy` 인스턴스 생성

**사용법**:
```python
strategy = ModificationStrategyFactory.create(
    modification_type="ControllerOrService",
    config=config,
    llm_provider=llm_provider,
)
```

## 의존성 주입

의존성 주입을 통해 각 컴포넌트가 느슨하게 결합되어 있습니다.

### CallGraphBuilder

```python
class CallGraphBuilder:
    def __init__(
        self,
        java_parser: Optional[JavaASTParser] = None,
        cache_manager: Optional[CacheManager] = None,
        endpoint_strategy: Optional[EndpointExtractionStrategy] = None,
    ):
        self.endpoint_strategy = endpoint_strategy
        # ...
```

### DBAccessAnalyzer

```python
class DBAccessAnalyzer:
    def __init__(
        self,
        config: Configuration,
        sql_extractor: SQLExtractor,  # 주입
        xml_parser: Optional[XMLMapperParser] = None,
        java_parser: Optional[JavaASTParser] = None,
        call_graph_builder: Optional[CallGraphBuilder] = None,
    ):
        self.sql_extractor = sql_extractor
        # ...
```

### CodeModifier

```python
class CodeModifier:
    def __init__(
        self,
        config: Configuration,
        llm_provider: Optional[LLMProvider] = None,
    ):
        # ModificationStrategy 생성 및 주입
        self.modification_strategy = ModificationStrategyFactory.create(
            modification_type=config.modification_type,
            config=self.config,
            llm_provider=self.llm_provider,
        )
```

## 설정 기반 동작

모든 전략은 `config.json` 파일의 설정값에 따라 결정됩니다:

```json
{
  "framework_type": "SpringMVC",      // EndpointExtractionStrategy 선택
  "sql_wrapping_type": "mybatis",     // SQLExtractor 선택
  "modification_type": "ControllerOrService"  // ModificationStrategy 선택
}
```

## 확장성

새로운 프레임워크나 기술을 추가하려면:

1. **새로운 Strategy 클래스 구현**
   - 예: `AnyframeSarangOnStrategy` 구현

2. **Factory에 등록**
   - 예: `EndpointExtractionStrategyFactory.create()`에 분기 추가

3. **Configuration에 타입 추가**
   - 예: `framework_type`에 `"AnyframeSarangOn"` 추가

## 마이그레이션 및 하위 호환성

기존 설정 파일(`diff_gen_type` 사용)은 자동으로 새로운 형식(`modification_type`)으로 마이그레이션됩니다:

```python
from config import load_config

# 자동 마이그레이션
config = load_config("config.json")
# diff_gen_type: "mybatis_service" → modification_type: "ControllerOrService"
```

## 테스트 전략

각 Strategy와 Factory는 독립적으로 테스트 가능합니다:

- **단위 테스트**: 각 Strategy 클래스별 테스트
- **통합 테스트**: 전체 플로우 테스트 (Analyze, Modify)
- **Factory 테스트**: 각 Factory가 올바른 인스턴스를 생성하는지 확인

## 성능 고려사항

- **캐싱**: 파싱 결과는 `CacheManager`를 통해 캐싱
- **병렬 처리**: `BatchProcessor`를 통한 대량 파일 처리
- **LLM 호출 최적화**: 배치 단위로 LLM 호출하여 토큰 사용량 최적화

