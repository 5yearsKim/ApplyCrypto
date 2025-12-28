# ApplyCrypto 리팩토링 계획 (최종)

## 개요

ApplyCrypto 프로그램을 3가지 TYPE 값(`framework_type`, `sql_wrapping_type`, `modification_type`)에 따라 다르게 동작하도록 리팩토링합니다. 각 타입별로 Strategy 패턴을 적용하여 확장 가능하고 유지보수하기 쉬운 구조로 개선합니다.

---

## 1단계: Configuration 구조 변경

### 1.1 config.json 스키마 업데이트
- **파일**: `src/config/config_manager.py`
- **변경 사항**:
  - `framework_type` 필드 추가 (Literal 타입으로 제한)
    - 가능한 값: `SpringMVC`, `AnyframeSarangOn`, `AnyframeOld`, `AnyframeEtc`, `SpringBatQrts`, `AnyframeBatSarangOn`, `AnyframeBatEtc`
  - `sql_wrapping_type` 필드 확인 및 검증
    - 현재: `Literal["mybatis", "jdbc", "jpa"]` (이미 JDBC, JPA 포함)
  - `diff_gen_type` → `modification_type`으로 필드명 변경
    - 가능한 값: `TypeHandler`, `ControllerOrService`, `ServiceImplOrBiz`
    - 기존 `mybatis_service`는 `ControllerOrService`로 매핑 (마이그레이션 로직 필요)

### 1.2 Configuration 클래스 수정
- `Configuration` 클래스에 `framework_type` 필드 추가
- `diff_gen_type` → `modification_type`으로 변경
- 하위 호환성을 위한 마이그레이션 메서드 추가

---

## 2단계: Framework Type 전략 패턴 구현

### 클래스 구조

| 클래스명 | 타입 | 역할/책임 | 주요 메서드 | 기존 코드 이전 |
|---------|------|----------|------------|--------------|
| `EndpointExtractionStrategy` | 추상 클래스 (ABC) | 엔드포인트 추출 전략 인터페이스 | `extract_endpoints_from_classes(classes) -> List[Endpoint]`<br>`extract_endpoint(cls, method, class_path) -> Optional[Endpoint]`<br>`extract_path_from_annotation(annotation) -> Optional[str]`<br>`extract_http_method_from_annotation(annotation) -> Optional[str]`<br>`classify_layer(cls, method) -> str`<br>`get_class_level_path(cls) -> str` | - |
| `SpringMVCStrategy` | 구현 클래스 | SpringMVC 프레임워크 엔드포인트 추출 | 위 메서드들 구현<br>(SpringMVC 어노테이션 패턴) | `CallGraphBuilder._identify_endpoints()`<br>`CallGraphBuilder._extract_endpoint()`<br>`CallGraphBuilder._extract_path_from_annotation()`<br>`CallGraphBuilder._extract_http_method_from_annotation()`<br>`CallGraphBuilder._classify_layer()` |
| `AnyframeSarangOnStrategy` | 구현 클래스 | Anyframe SarangOn 프레임워크 엔드포인트 추출 | 위 메서드들 구현<br>(Anyframe SarangOn 어노테이션 패턴) | - (추후 구현) |
| `AnyframeOldStrategy` | 구현 클래스 | Anyframe Old 프레임워크 엔드포인트 추출 | 위 메서드들 구현<br>(Anyframe Old 어노테이션 패턴) | - (추후 구현) |
| `AnyframeEtcStrategy` | 구현 클래스 | Anyframe 기타 프레임워크 엔드포인트 추출 | 위 메서드들 구현<br>(Anyframe 기타 어노테이션 패턴) | - (추후 구현) |
| `SpringBatQrtsStrategy` | 구현 클래스 | Spring Batch Quartz 프레임워크 엔드포인트 추출 | 위 메서드들 구현<br>(Spring Batch 어노테이션 패턴) | - (추후 구현) |
| `AnyframeBatSarangOnStrategy` | 구현 클래스 | Anyframe Batch SarangOn 프레임워크 엔드포인트 추출 | 위 메서드들 구현<br>(Anyframe Batch SarangOn 패턴) | - (추후 구현) |
| `AnyframeBatEtcStrategy` | 구현 클래스 | Anyframe Batch 기타 프레임워크 엔드포인트 추출 | 위 메서드들 구현<br>(Anyframe Batch 기타 패턴) | - (추후 구현) |
| `EndpointExtractionStrategyFactory` | Factory 클래스 | framework_type에 따라 적절한 Strategy 인스턴스 생성 | `create(framework_type, java_parser, cache_manager) -> EndpointExtractionStrategy` | - |

### 2.1 작업 내용
- `src/parser/endpoint_strategy/endpoint_extraction_strategy.py` 생성 (인터페이스)
- `src/parser/endpoint_strategy/spring_mvc_strategy.py` 생성 (기존 코드 이동)
- `src/parser/endpoint_strategy/endpoint_extraction_strategy_factory.py` 생성
- `src/parser/call_graph_builder.py` 리팩토링
  - `_identify_endpoints()` 제거
  - `_extract_endpoint()`, `_extract_path_from_annotation()`, `_extract_http_method_from_annotation()`, `_classify_layer()` 제거
  - Strategy 패턴 사용으로 변경

---

## 3단계: SQL Wrapping Type 전략 개선 (추상 메서드를 가진 일반 클래스 구조)

### 클래스 구조

| 클래스명 | 타입 | 역할/책임 | 주요 메서드 | 기존 코드 이전 |
|---------|------|----------|------------|--------------|
| `SQLExtractor` | 일반 클래스 (추상 메서드 포함) | SQL 추출 기본 클래스 | `extract_from_files(source_files) -> List[SQLExtractionOutput]` (추상)<br>`extract_table_names(sql) -> Set[str]` (구현)<br>`extract_column_names(sql, table) -> Set[str]` (구현)<br>`_extract_mybatis()` (보호 메서드)<br>`_extract_jdbc()` (보호 메서드)<br>`_extract_jpa()` (보호 메서드) | 현재 `SQLExtractor` 클래스<br>`SQLParsingStrategy`의 메서드들 | 추상 클래스 → 일반 클래스, SQL 파싱 메서드 추가 |
| `MyBatisSQLExtractor` | 하위 클래스 | MyBatis SQL 추출 구현 | `extract_from_files()` 구현:<br>- `use_llm_parser=True`: `_filter_mybatis_files()` + `LLMSQLExtractor` 사용<br>- `use_llm_parser=False`: `_extract_mybatis()` 호출<br>`_filter_mybatis_files()` | `SQLExtractor._extract_mybatis()`<br>`LLMSQLExtractor._filter_target_files()` (MyBatis 분기) | 신규 생성 |
| `JDBCSQLExtractor` | 하위 클래스 | JDBC SQL 추출 구현 | `extract_from_files()` 구현:<br>- `use_llm_parser=True`: `_filter_jdbc_files()` + `LLMSQLExtractor` 사용<br>- `use_llm_parser=False`: `_extract_jdbc()` 호출<br>`_filter_jdbc_files()` | `SQLExtractor._extract_jdbc()` | 신규 생성 |
| `JPASQLExtractor` | 하위 클래스 | JPA SQL 추출 구현 | `extract_from_files()` 구현:<br>- `use_llm_parser=True`: `_filter_jpa_files()` + `LLMSQLExtractor` 사용<br>- `use_llm_parser=False`: `_extract_jpa()` 호출<br>`_filter_jpa_files()` | `SQLExtractor._extract_jpa()` | 신규 생성 |
| `LLMSQLExtractor` | 유틸리티 클래스 | LLM 기반 SQL 추출 공통 유틸리티 | `extract_from_files(source_files)` (이미 필터링된 파일만 받음)<br>`_process_single_file(file)`<br>`_parse_llm_response(response)` | 기존 유지 | `sql_wrapping_type` 파라미터 제거, `_filter_target_files()` 제거 |
| `SQLExtractorFactory` | Factory 클래스 | sql_wrapping_type에 따라 적절한 SQLExtractor 인스턴스 생성 | `create(sql_wrapping_type, config, xml_parser, java_parser) -> SQLExtractor` | - | 신규 생성 |

### 3.1 작업 내용
- `src/analyzer/sql_extractor.py` 리팩토링 (일반 클래스로 변경, SQL 파싱 메서드 추가)
- `src/analyzer/sql_parsing_strategy.py` 삭제 (SQLParsingStrategy 제거)
- `src/analyzer/mybatis_sql_extractor.py` 생성
- `src/analyzer/jdbc_sql_extractor.py` 생성
- `src/analyzer/jpa_sql_extractor.py` 생성
- `src/analyzer/sql_extractor_factory.py` 생성
- `src/analyzer/llm_sql_extractor/llm_sql_extractor.py` 수정 (필터링 로직 제거)
- `src/analyzer/db_access_analyzer.py` 리팩토링 (Factory 사용, SQLParsingStrategy 제거)
- `src/cli/cli_controller.py` 수정 (Factory 사용, use_llm_parser 분기 제거)

---

## 4단계: Modification Type 전략 패턴 구현

### 디렉토리 구조 변경

#### 기존 디렉토리 구조
```
src/modifier/
├── diff_generator/
│   ├── base_diff_generator.py
│   ├── diff_generator_factory.py
│   ├── mybatis_service/
│   │   └── mybatis_service_diff_generator.py
│   ├── mybatis_typehandler/
│   │   └── mybatis_typehandler_diff_generator.py
│   └── mybatis_dao/
│       └── mybatis_dao_diff_generator.py
```

#### 변경 후 디렉토리 구조
```
src/modifier/
├── code_generator/
│   ├── base_code_generator.py
│   ├── code_generator_factory.py
│   ├── controller_service_type/
│   │   └── controller_service_code_generator.py
│   ├── typehandler_type/
│   │   └── typehandler_code_generator.py
│   └── serviceimpl_biz_type/
│       └── serviceimpl_biz_code_generator.py
```

### 클래스 구조

| 클래스명 | 타입 | 역할/책임 | 주요 메서드 | 기존 코드 이전 |
|---------|------|----------|------------|--------------|
| `ModificationStrategy` | 추상 클래스 (ABC) | 코드 수정 전략 인터페이스 | `generate_modification_plans(table_access_info) -> List[ModificationPlan]`<br>`create_code_generator(config, llm_provider) -> BaseCodeGenerator` | - |
| `ControllerOrServiceStrategy` | 구현 클래스 | Controller/Service 레이어 수정 전략 | 위 메서드들 구현<br>- ControllerOrServiceCodeGenerator 사용<br>- Controller/Service 레이어 타겟팅 | `CodeGeneratorFactory.create()` (mybatis_service 분기)<br>`CodeModifier.generate_modification_plans()` (ControllerOrService 로직)<br>`MyBatisServiceDiffGenerator` 참조 |
| `TypeHandlerStrategy` | 구현 클래스 | TypeHandler 수정 전략 | 위 메서드들 구현<br>- TypeHandlerCodeGenerator 사용<br>- TypeHandler 레이어 타겟팅 | `CodeGeneratorFactory.create()` (mybatis_typehandler 분기)<br>`MyBatisTypeHandlerDiffGenerator` 참조 |
| `ServiceImplOrBizStrategy` | 구현 클래스 | ServiceImpl/Biz 레이어 수정 전략 | 위 메서드들 구현<br>- ServiceImplOrBizCodeGenerator 사용<br>- ServiceImpl/Biz 레이어 타겟팅 | `CodeGeneratorFactory.create()` (mybatis_dao 분기) (추후 구현) |
| `ModificationStrategyFactory` | Factory 클래스 | modification_type에 따라 적절한 Strategy 인스턴스 생성 | `create(modification_type, config, llm_provider) -> ModificationStrategy` | - |
| `BaseCodeGenerator` | 추상 클래스 | Code 생성 추상 클래스 | `generate(input_data) -> CodeOutput` | `BaseDiffGenerator` (이름 변경) |
| `ControllerOrServiceCodeGenerator` | 구현 클래스 | Controller/Service Code 생성 | `generate()` 구현 | `MyBatisServiceDiffGenerator` (이름 변경) |
| `TypeHandlerCodeGenerator` | 구현 클래스 | TypeHandler Code 생성 | `generate()` 구현 | `MyBatisTypeHandlerDiffGenerator` (이름 변경) |
| `ServiceImplOrBizCodeGenerator` | 구현 클래스 | ServiceImpl/Biz Code 생성 | `generate()` 구현 | `MyBatisDaoDiffGenerator` (이름 변경) |
| `CodeGeneratorFactory` | Factory 클래스 | modification_type에 따라 CodeGenerator 생성 (또는 Strategy로 통합) | `create(config, llm_provider) -> BaseCodeGenerator` | `DiffGeneratorFactory` (이름 변경) |

### 4.1 작업 내용
- `src/modifier/modification_strategy/modification_strategy.py` 생성 (인터페이스)
- `src/modifier/modification_strategy/controller_or_service_strategy.py` 생성 (기존 코드 이동)
- `src/modifier/modification_strategy/type_handler_strategy.py` 생성
- `src/modifier/modification_strategy/service_impl_or_biz_strategy.py` 생성 (추후 구현)
- `src/modifier/modification_strategy/modification_strategy_factory.py` 생성
- 디렉토리 및 파일 이름 변경:
  - `diff_generator/` → `code_generator/`
  - `mybatis_service/` → `controller_service_type/`
  - `mybatis_typehandler/` → `typehandler_type/`
  - `mybatis_dao/` → `serviceimpl_biz_type/`
  - `base_diff_generator.py` → `base_code_generator.py`
  - `diff_generator_factory.py` → `code_generator_factory.py`
  - `mybatis_service_diff_generator.py` → `controller_service_code_generator.py`
  - `mybatis_typehandler_diff_generator.py` → `typehandler_code_generator.py`
  - `mybatis_dao_diff_generator.py` → `serviceimpl_biz_code_generator.py`
- 클래스 이름 변경:
  - `BaseDiffGenerator` → `BaseCodeGenerator`
  - `DiffGeneratorFactory` → `CodeGeneratorFactory`
  - `MyBatisServiceDiffGenerator` → `ControllerOrServiceCodeGenerator`
  - `MyBatisTypeHandlerDiffGenerator` → `TypeHandlerCodeGenerator`
  - `MyBatisDaoDiffGenerator` → `ServiceImplOrBizCodeGenerator`
- `src/modifier/code_generator/code_generator_factory.py` 리팩토링 (Strategy 사용)
- `src/modifier/code_modifier.py` 리팩토링 (Strategy 패턴 사용, 변수명 변경)
- `src/modifier/modification_context_generator/` 관련 파일 수정 (파라미터명 변경)
- `src/cli/cli_controller.py` 수정 (modification_type 사용)

---

## 5단계: 통합 및 의존성 주입

### 5.1 Factory 패턴 통합
- 각 Factory 클래스가 Configuration 객체를 받아 적절한 전략 인스턴스 생성
- 의존성 주입 구조로 변경하여 테스트 용이성 향상

### 5.2 CLI Controller 통합
- `_handle_analyze()` 메서드:
  - `framework_type`을 `EndpointExtractionStrategyFactory`에 전달
  - `sql_wrapping_type`을 `SQLExtractorFactory`에 전달
- `_handle_modify()` 메서드:
  - `modification_type`을 `ModificationStrategyFactory`에 전달

---

## 6단계: 마이그레이션 및 하위 호환성

### 6.1 Config 마이그레이션 유틸리티
- **파일**: `src/config/config_migration.py` (신규)
- **기능**:
  - 기존 `diff_gen_type` 값을 `modification_type`으로 변환
  - 기존 config.json 파일 자동 업데이트 (선택적)
  - 마이그레이션 로그 생성

### 6.2 하위 호환성 유지
- 기존 `diff_gen_type` 값이 있으면 자동으로 `modification_type`으로 변환
- 경고 메시지 출력하여 사용자에게 알림

---

## 7단계: 테스트 및 검증

### 7.1 단위 테스트 작성
- 각 Strategy 클래스별 테스트
- Factory 클래스 테스트
- Configuration 마이그레이션 테스트

### 7.2 통합 테스트
- Analyze 명령어 테스트 (각 framework_type별)
- Modify 명령어 테스트 (각 modification_type별)
- SQL 추출 테스트 (각 sql_wrapping_type별)

---

## 8단계: 문서화

### 8.1 설정 파일 문서화
- `config.example.json` 업데이트
- 각 type의 의미와 사용 시나리오 문서화

### 8.2 아키텍처 문서 업데이트
- Strategy 패턴 적용 내용 문서화
- 클래스 다이어그램 업데이트

---

## 전체 클래스 계층 구조 요약

### Endpoint Extraction 계층
```
EndpointExtractionStrategy (ABC)
├── SpringMVCStrategy
├── AnyframeSarangOnStrategy
├── AnyframeOldStrategy
├── AnyframeEtcStrategy
├── SpringBatQrtsStrategy
├── AnyframeBatSarangOnStrategy
└── AnyframeBatEtcStrategy

EndpointExtractionStrategyFactory
```

### SQL Extraction 계층
```
SQLExtractor (일반 클래스, extract_from_files()만 추상)
├── extract_table_names(sql) -> Set[str] (구현 메서드)
├── extract_column_names(sql, table) -> Set[str] (구현 메서드)
├── MyBatisSQLExtractor
├── JDBCSQLExtractor
└── JPASQLExtractor

LLMSQLExtractor (공통 유틸리티)

SQLExtractorFactory
```

### Modification 계층
```
ModificationStrategy (ABC)
├── ControllerOrServiceStrategy
├── TypeHandlerStrategy
└── ServiceImplOrBizStrategy

BaseCodeGenerator (ABC) (이전: BaseDiffGenerator)
├── ControllerOrServiceCodeGenerator (이전: MyBatisServiceDiffGenerator)
├── TypeHandlerCodeGenerator (이전: MyBatisTypeHandlerDiffGenerator)
└── ServiceImplOrBizCodeGenerator (이전: MyBatisDaoDiffGenerator)

CodeGeneratorFactory (이전: DiffGeneratorFactory)
ModificationStrategyFactory
```

---

## 작업 우선순위 및 순서

### 우선순위 1 (핵심 기능 - 기존 코드 이전)
1. **1단계**: Configuration 구조 변경
2. **4단계**: Modification Type 전략 구현 (기존 `mybatis_service` 코드 이전)
3. **2단계**: Framework Type 전략 구현 (기존 SpringMVC 코드 이전)
4. **3단계**: SQL Wrapping Type 개선 (기존 MyBatis 코드 이전)

### 우선순위 2 (통합 및 안정화)
5. **5단계**: 통합 및 의존성 주입
6. **6단계**: 마이그레이션 및 하위 호환성
7. **7단계**: 테스트 및 검증
8. **8단계**: 문서화

---

## 주요 변경사항 요약

### 이름 변경
- `EndpointIdentificationStrategy` → `EndpointExtractionStrategy`
- `EndpointStrategyFactory` → `EndpointExtractionStrategyFactory`
- `BaseDiffGenerator` → `BaseCodeGenerator`
- `DiffGeneratorFactory` → `CodeGeneratorFactory`
- `MyBatisServiceDiffGenerator` → `ControllerOrServiceCodeGenerator`
- `MyBatisTypeHandlerDiffGenerator` → `TypeHandlerCodeGenerator`
- `MyBatisDaoDiffGenerator` → `ServiceImplOrBizCodeGenerator`

### 제거된 클래스
- `SQLParsingStrategy` (ABC)
- `MyBatisStrategy`
- `JDBCStrategy`
- `JPAStrategy`

### 디렉토리 구조 변경
- `diff_generator/` → `code_generator/`
- `mybatis_service/` → `controller_service_type/`
- `mybatis_typehandler/` → `typehandler_type/`
- `mybatis_dao/` → `serviceimpl_biz_type/`

### 파일 이름 변경
- `base_diff_generator.py` → `base_code_generator.py`
- `diff_generator_factory.py` → `code_generator_factory.py`
- `mybatis_service_diff_generator.py` → `controller_service_code_generator.py`
- `mybatis_typehandler_diff_generator.py` → `typehandler_code_generator.py`
- `mybatis_dao_diff_generator.py` → `serviceimpl_biz_code_generator.py`

---

## 코드 이전 매핑표

### Framework Type 관련
| 현재 위치 | 현재 구현 내용 | 이전 대상 | 비고 |
|---------|-------------|---------|------|
| `CallGraphBuilder._identify_endpoints()` | SpringMVC 방식 엔드포인트 추출 | `SpringMVCStrategy.extract_endpoints_from_classes()` | 완전 이동 |
| `CallGraphBuilder._extract_endpoint()` | SpringMVC 방식 엔드포인트 추출 | `SpringMVCStrategy.extract_endpoint()` | 완전 이동 |
| `CallGraphBuilder._extract_path_from_annotation()` | SpringMVC 어노테이션 파싱 | `SpringMVCStrategy.extract_path_from_annotation()` | 완전 이동 |
| `CallGraphBuilder._extract_http_method_from_annotation()` | SpringMVC 어노테이션 파싱 | `SpringMVCStrategy.extract_http_method_from_annotation()` | 완전 이동 |
| `CallGraphBuilder._classify_layer()` | SpringMVC 레이어 분류 | `SpringMVCStrategy.classify_layer()` | 완전 이동 |

### SQL Extraction 관련
| 현재 위치 | 현재 구현 내용 | 이전 대상 | 비고 |
|---------|-------------|---------|------|
| `SQLParsingStrategy.extract_table_names()` | SQL에서 테이블명 추출 | `SQLExtractor.extract_table_names()` | 완전 이동 |
| `SQLParsingStrategy.extract_column_names()` | SQL에서 칼럼명 추출 | `SQLExtractor.extract_column_names()` | 완전 이동 |
| `SQLExtractor._extract_mybatis()` | MyBatis SQL 추출 | `MyBatisSQLExtractor._extract_mybatis()` (보호 메서드로 유지) | 부모 클래스에서 상속 |
| `SQLExtractor._extract_jdbc()` | JDBC SQL 추출 | `JDBCSQLExtractor._extract_jdbc()` (보호 메서드로 유지) | 부모 클래스에서 상속 |
| `SQLExtractor._extract_jpa()` | JPA SQL 추출 | `JPASQLExtractor._extract_jpa()` (보호 메서드로 유지) | 부모 클래스에서 상속 |
| `LLMSQLExtractor._filter_target_files()` | MyBatis 파일 필터링 | `MyBatisSQLExtractor._filter_mybatis_files()` | 완전 이동 |
| `LLMSQLExtractor._filter_target_files()` | JDBC/JPA 파일 필터링 | `JDBCSQLExtractor._filter_jdbc_files()`, `JPASQLExtractor._filter_jpa_files()` | 분리하여 이동 |
| `DBAccessAnalyzer.__init__()` | `sql_strategy: SQLParsingStrategy` 파라미터 | `sql_wrapping_type`과 `config` 파라미터로 변경 | 변경 |
| `DBAccessAnalyzer._analyze_table_access()` | `self.sql_strategy.extract_table_names()` | `self.sql_extractor.extract_table_names()` | 변경 |
| `DBAccessAnalyzer._analyze_table_access()` | `self.sql_strategy.extract_column_names()` | `self.sql_extractor.extract_column_names()` | 변경 |

### Modification 관련
| 현재 위치 | 현재 구현 내용 | 이전 대상 | 비고 |
|---------|-------------|---------|------|
| `CodeGeneratorFactory.create()` (mybatis_service 분기) | ControllerOrService CodeGenerator 생성 | `ControllerOrServiceStrategy.create_code_generator()` | 완전 이동 + 이름 변경 |
| `MyBatisServiceDiffGenerator` | ControllerOrService 방식 Code 생성 | `ControllerOrServiceCodeGenerator` | 이름 변경 + 참조 유지 |
| `CodeGeneratorFactory.create()` (mybatis_typehandler 분기) | TypeHandler CodeGenerator 생성 | `TypeHandlerStrategy.create_code_generator()` | 완전 이동 + 이름 변경 |
| `MyBatisTypeHandlerDiffGenerator` | TypeHandler Code 생성 | `TypeHandlerCodeGenerator` | 이름 변경 + 참조 유지 |
| `CodeGeneratorFactory.create()` (mybatis_dao 분기) | ServiceImpl/Biz CodeGenerator 생성 | `ServiceImplOrBizStrategy.create_code_generator()` | 완전 이동 + 이름 변경 |
| `MyBatisDaoDiffGenerator` | ServiceImpl/Biz Code 생성 | `ServiceImplOrBizCodeGenerator` | 이름 변경 + 참조 유지 |
| `BaseDiffGenerator` | Code 생성 추상 클래스 | `BaseCodeGenerator` | 이름 변경 |
| `DiffGeneratorFactory` | CodeGenerator Factory | `CodeGeneratorFactory` | 이름 변경 |
| `CodeModifier.generate_modification_plans()` | ControllerOrService 방식 계획 생성 | `ControllerOrServiceStrategy.generate_modification_plans()` | 완전 이동 |
| `CodeModifier.__init__()` | `self.diff_generator` | `self.code_generator` | 변수명 변경 |

---

## 참고사항

### 현재 구현 상태
- **Endpoint 추출**: SpringMVC 방식으로 구현됨
- **SQL 추출**: MyBatis 방식으로 구현됨
- **Modify 기능**: ControllerOrService 방식 (기존 `mybatis_service`)으로 구현됨

### 설계 원칙
- **Strategy 패턴**: 각 type별로 다른 동작을 Strategy 패턴으로 구현
- **Factory 패턴**: Configuration 기반 인스턴스 생성
- **하위 호환성**: 기존 설정 파일 자동 마이그레이션 지원
- **확장성**: 새로운 type 추가 시 Strategy 구현만 추가하면 됨

---

## 완료 체크리스트

### 1단계: Configuration 구조 변경
- [ ] `framework_type` 필드 추가
- [ ] `diff_gen_type` → `modification_type` 변경
- [ ] 마이그레이션 로직 구현

### 2단계: Framework Type 전략 구현
- [ ] `EndpointExtractionStrategy` 인터페이스 생성
- [ ] `SpringMVCStrategy` 구현 (기존 코드 이동)
- [ ] `EndpointExtractionStrategyFactory` 생성
- [ ] `CallGraphBuilder` 리팩토링

### 3단계: SQL Wrapping Type 개선
- [ ] `SQLExtractor` 일반 클래스로 변경
- [ ] SQL 파싱 메서드 추가
- [ ] `SQLParsingStrategy` 제거
- [ ] `MyBatisSQLExtractor`, `JDBCSQLExtractor`, `JPASQLExtractor` 생성
- [ ] `SQLExtractorFactory` 생성
- [ ] `LLMSQLExtractor` 리팩토링
- [ ] `DBAccessAnalyzer` 리팩토링

### 4단계: Modification Type 전략 구현
- [ ] 디렉토리 및 파일 이름 변경
- [ ] 클래스 이름 변경
- [ ] `ModificationStrategy` 인터페이스 생성
- [ ] `ControllerOrServiceStrategy`, `TypeHandlerStrategy`, `ServiceImplOrBizStrategy` 구현
- [ ] `ModificationStrategyFactory` 생성
- [ ] `CodeModifier` 리팩토링

### 5단계: 통합 및 의존성 주입
- [ ] Factory 패턴 통합
- [ ] CLI Controller 통합

### 6단계: 마이그레이션 및 하위 호환성
- [ ] Config 마이그레이션 유틸리티 생성
- [ ] 하위 호환성 로직 구현

### 7단계: 테스트 및 검증
- [ ] 단위 테스트 작성
- [ ] 통합 테스트 작성

### 8단계: 문서화
- [ ] 설정 파일 문서화
- [ ] 아키텍처 문서 업데이트

