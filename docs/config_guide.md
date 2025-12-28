# 설정 파일 가이드

이 문서는 `config.json` 파일의 각 필드와 설정값에 대한 상세한 설명을 제공합니다.

## 기본 구조

```json
{
  "target_project": "/path/to/project",
  "source_file_types": [".java", ".xml"],
  "framework_type": "SpringMVC",
  "sql_wrapping_type": "mybatis",
  "modification_type": "ControllerOrService",
  "access_tables": [...],
  "llm_provider": "watsonx_ai",
  ...
}
```

## 필수 필드

### target_project
- **타입**: `string`
- **설명**: 분석 및 수정할 대상 프로젝트의 루트 디렉터리 경로
- **예시**: `"/home/user/myproject"` 또는 `"C:\\Users\\user\\myproject"`

### source_file_types
- **타입**: `string[]`
- **설명**: 수집할 소스 파일의 확장자 목록
- **예시**: `[".java", ".xml"]`
- **권장값**: 
  - Java 프로젝트: `[".java", ".xml"]`
  - MyBatis 사용 시: `[".java", ".xml"]`
  - JPA 사용 시: `[".java"]`

### sql_wrapping_type
- **타입**: `"mybatis" | "jdbc" | "jpa"`
- **설명**: 프로젝트에서 사용하는 SQL 래핑 기술
- **가능한 값**:
  - `"mybatis"`: MyBatis를 사용하는 경우 (XML Mapper 또는 Annotation 기반)
  - `"jdbc"`: 순수 JDBC를 사용하는 경우
  - `"jpa"`: JPA/Hibernate를 사용하는 경우
- **사용 시나리오**:
  - **MyBatis**: XML Mapper 파일(`*.xml`)에서 SQL 쿼리를 추출하여 분석
  - **JDBC**: Java 소스 코드에서 직접 작성된 SQL 문자열을 추출하여 분석
  - **JPA**: JPQL 쿼리나 Entity 클래스의 어노테이션을 분석

### modification_type
- **타입**: `"TypeHandler" | "ControllerOrService" | "ServiceImplOrBiz"`
- **설명**: 코드 수정 방식을 결정하는 타입
- **가능한 값**:
  - `"TypeHandler"`: MyBatis TypeHandler를 생성하여 암호화 처리 (비즈니스 로직 수정 없음)
  - `"ControllerOrService"`: Controller 또는 Service 레이어에서 암호화 코드 삽입
  - `"ServiceImplOrBiz"`: ServiceImpl 또는 Biz 레이어에서 암호화 코드 삽입
- **사용 시나리오**:
  - **TypeHandler**: 
    - MyBatis를 사용하는 프로젝트
    - 비즈니스 로직을 최소한으로 수정하고 싶은 경우
    - XML Mapper에 TypeHandler를 등록하여 자동으로 암호화/복호화 처리
  - **ControllerOrService**:
    - REST API 레이어에서 요청/응답 데이터를 암호화/복호화하는 경우
    - Service 레이어에서 비즈니스 로직 전후에 암호화 처리가 필요한 경우
  - **ServiceImplOrBiz**:
    - ServiceImpl 또는 Biz 레이어에서 데이터 처리 전후에 암호화 처리가 필요한 경우
    - DAO 레이어 바로 위에서 암호화 처리를 하는 경우

### access_tables
- **타입**: `AccessTable[]`
- **설명**: 암호화 대상 테이블 및 칼럼 정보
- **구조**:
  ```json
  {
    "table_name": "EMPLOYEE",
    "columns": [
      "NAME",
      {
        "name": "JUMIN_NUMBER",
        "new_column": false,
        "encryption_code": "K_SIGN_JUMIN"
      }
    ]
  }
  ```
- **칼럼 형식**:
  - **문자열**: 간단한 칼럼명만 지정
  - **객체**: 상세 정보 포함
    - `name`: 칼럼명 (필수)
    - `new_column`: 새로 추가되는 칼럼 여부 (선택, 기본값: `false`)
    - `encryption_code`: 암호화 코드 (선택)
    - `column_type`: 칼럼 타입 (선택, `"dob" | "ssn" | "name" | "sex"`)

## 선택 필드

### framework_type
- **타입**: `"SpringMVC" | "AnyframeSarangOn" | "AnyframeOld" | "AnyframeEtc" | "SpringBatQrts" | "AnyframeBatSarangOn" | "AnyframeBatEtc"`
- **기본값**: `"SpringMVC"`
- **설명**: 프로젝트에서 사용하는 프레임워크 타입
- **가능한 값**:
  - `"SpringMVC"`: Spring MVC 프레임워크 (기본값)
  - `"AnyframeSarangOn"`: Anyframe SarangOn 프레임워크
  - `"AnyframeOld"`: Anyframe 구버전
  - `"AnyframeEtc"`: Anyframe 기타 버전
  - `"SpringBatQrts"`: Spring Batch + Quartz
  - `"AnyframeBatSarangOn"`: Anyframe Batch SarangOn
  - `"AnyframeBatEtc"`: Anyframe Batch 기타
- **사용 시나리오**:
  - **SpringMVC**: 
    - `@RestController`, `@Controller` 어노테이션 사용
    - `@RequestMapping`, `@GetMapping`, `@PostMapping` 등으로 엔드포인트 정의
  - **Anyframe 계열**: 
    - Anyframe 프레임워크의 특정 어노테이션 패턴 사용
    - 엔드포인트 추출 방식이 SpringMVC와 다름

### llm_provider
- **타입**: `"watsonx_ai" | "claude_ai" | "openai" | "mock" | "watsonx_ai_on_prem"`
- **기본값**: `"watsonx_ai"`
- **설명**: 코드 수정에 사용할 LLM 프로바이더
- **사용 시나리오**:
  - `"watsonx_ai"`: IBM Watsonx AI 사용 (기본값)
  - `"claude_ai"`: Anthropic Claude AI 사용
  - `"openai"`: OpenAI GPT 사용
  - `"mock"`: 테스트용 Mock 프로바이더
  - `"watsonx_ai_on_prem"`: 온프레미스 Watsonx AI 사용

### use_llm_parser
- **타입**: `boolean`
- **기본값**: `false`
- **설명**: SQL 추출 시 LLM을 사용할지 여부
- **사용 시나리오**:
  - `false`: 정규식 기반 SQL 파싱 사용 (기본값, 빠름)
  - `true`: LLM을 사용한 SQL 추출 (정확도 높음, 느림)

### use_call_chain_mode
- **타입**: `boolean`
- **기본값**: `false`
- **설명**: Call Chain 모드 사용 여부
- **사용 시나리오**:
  - `false`: 레이어별 배치 처리 (기본값)
  - `true`: 호출 체인 단위로 LLM 호출하여 최적 레이어에 암호화 코드 삽입

### exclude_dirs
- **타입**: `string[]`
- **기본값**: `[]`
- **설명**: 분석에서 제외할 디렉터리 이름 목록
- **예시**: `["test", "generated", "target"]`

### exclude_files
- **타입**: `string[]`
- **기본값**: `[]`
- **설명**: 분석에서 제외할 파일 패턴 목록 (glob 패턴 지원)
- **예시**: `["*Test.java", "*_test.java", "*.generated.*"]`

### max_tokens_per_batch
- **타입**: `number`
- **기본값**: `8000`
- **설명**: 한 번에 처리할 최대 토큰 수
- **사용 시나리오**: LLM API의 토큰 제한에 맞춰 조정

### max_workers
- **타입**: `number`
- **기본값**: `4`
- **설명**: 병렬 처리 워커 수
- **사용 시나리오**: CPU 코어 수에 맞춰 조정

### max_retries
- **타입**: `number`
- **기본값**: `3`
- **설명**: 실패 시 최대 재시도 횟수

### generate_full_source
- **타입**: `boolean`
- **기본값**: `false`
- **설명**: LLM에 전체 소스 코드를 전달할지 여부
- **사용 시나리오**:
  - `false`: 관련 부분만 전달 (기본값, 빠름)
  - `true`: 전체 소스 코드 전달 (정확도 높음, 느림)

### type_handler
- **타입**: `object | null`
- **기본값**: `null`
- **설명**: TypeHandler 모드 사용 시 설정
- **구조**:
  ```json
  {
    "package": "com.example.typehandler",
    "output_dir": "src/main/java/com/example/typehandler"
  }
  ```

## 마이그레이션 가이드

### 기존 config.json에서 마이그레이션

기존 `diff_gen_type` 필드를 사용하던 경우, 자동으로 `modification_type`으로 변환됩니다:

| 기존 값 (diff_gen_type) | 새 값 (modification_type) |
|------------------------|---------------------------|
| `mybatis_service` | `ControllerOrService` |
| `mybatis_typehandler` | `TypeHandler` |
| `mybatis_dao` | `ServiceImplOrBiz` |
| `call_chain` | `ControllerOrService` |

### 자동 마이그레이션

`load_config()` 함수가 자동으로 마이그레이션을 수행합니다:

```python
from config import load_config

# 자동으로 diff_gen_type을 modification_type으로 변환
config = load_config("config.json")
```

### 수동 마이그레이션

수동으로 마이그레이션하려면:

```python
from config import migrate_config_file

# 파일 업데이트 및 백업 생성
result = migrate_config_file(
    "config.json",
    update_file=True,
    backup=True,
    save_log=True
)
```

## 예시 설정 파일

### SpringMVC + MyBatis + ControllerOrService

```json
{
  "target_project": "/path/to/spring-project",
  "source_file_types": [".java", ".xml"],
  "framework_type": "SpringMVC",
  "sql_wrapping_type": "mybatis",
  "modification_type": "ControllerOrService",
  "access_tables": [
    {
      "table_name": "USERS",
      "columns": ["name", "email", "phone"]
    }
  ],
  "llm_provider": "watsonx_ai"
}
```

### SpringMVC + JPA + TypeHandler

```json
{
  "target_project": "/path/to/jpa-project",
  "source_file_types": [".java"],
  "framework_type": "SpringMVC",
  "sql_wrapping_type": "jpa",
  "modification_type": "TypeHandler",
  "access_tables": [
    {
      "table_name": "EMPLOYEE",
      "columns": [
        {
          "name": "JUMIN_NUMBER",
          "encryption_code": "K_SIGN_JUMIN"
        }
      ]
    }
  ],
  "type_handler": {
    "package": "com.example.typehandler",
    "output_dir": "src/main/java/com/example/typehandler"
  }
}
```

### JDBC + ServiceImplOrBiz

```json
{
  "target_project": "/path/to/jdbc-project",
  "source_file_types": [".java"],
  "framework_type": "SpringMVC",
  "sql_wrapping_type": "jdbc",
  "modification_type": "ServiceImplOrBiz",
  "access_tables": [
    {
      "table_name": "CUSTOMER",
      "columns": ["phone", "email"]
    }
  ],
  "use_llm_parser": true
}
```

