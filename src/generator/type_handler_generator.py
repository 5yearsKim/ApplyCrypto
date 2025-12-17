"""
Type Handler Generator 모듈

MyBatis Type Handler를 자동 생성하여 암복호화를 적용하는 모듈입니다.
Java 비즈니스 로직을 직접 수정하지 않고, Type Handler 클래스를 생성하고
XML 매퍼에 typeHandler 속성을 등록합니다.
"""

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.config_manager import ConfigurationManager
from models.table_access_info import TableAccessInfo
from modifier.error_handler import ErrorHandler
from modifier.llm.llm_factory import create_llm_provider
from modifier.llm.llm_provider import LLMProvider
from modifier.result_tracker import ResultTracker
from persistence.data_persistence_manager import DataPersistenceManager

logger = logging.getLogger("applycrypto.type_handler_generator")


class TypeHandlerGenerator:
    """
    Type Handler Generator 클래스

    MyBatis Type Handler를 자동 생성하여 암복호화를 적용합니다.

    주요 기능:
    1. LLM을 활용한 Type Handler Java 클래스 생성
    2. XML 매퍼 파일에 typeHandler 속성 추가
    3. 생성 결과 추적 및 저장
    """

    # Type Handler 생성을 위한 프롬프트 템플릿
    TYPE_HANDLER_PROMPT_TEMPLATE = """
## Task
You are a Java developer. Generate a MyBatis TypeHandler class for encrypting/decrypting sensitive data.

## Requirements
1. Create a TypeHandler that extends BaseTypeHandler<String>
2. Use the CryptoService class for encryption/decryption
3. Package name should be: {package_name}
4. Class name should be: {class_name}
5. The TypeHandler should handle the following columns from table '{table_name}':
{columns_info}

## CryptoService Usage
- Encryption: CryptoService.encrypt(String plainText, String cryptoCode)
- Decryption: CryptoService.decrypt(String encryptedText, String cryptoCode)
- Import: import com.ksign.crypto.CryptoService;
- Each column has its own crypto_code that must be used for encryption/decryption.
- Create separate methods or logic to handle each column with its specific crypto_code.

## Output Format
Return ONLY the complete Java source code without any explanation.
Start with package declaration and end with closing brace.

```java
package {package_name};

// Your implementation here
```
"""

    XML_MODIFICATION_PROMPT_TEMPLATE = """
## Task
You are a MyBatis expert. Modify the following XML mapper file to use TypeHandler for encryption/decryption.

## Target Columns (from table '{table_name}'):
{columns_info}

## TypeHandler Class
Full class name: {type_handler_class}

## Original XML Content
```xml
{xml_content}
```

## Requirements
1. Add typeHandler attribute to <result> tags that map to target columns
2. Add typeHandler attribute to parameter mappings (#{{columnName}}) for INSERT/UPDATE statements
3. Do NOT modify any other parts of the XML
4. Preserve all formatting and comments
5. Note: Each column has its own crypto_code which is handled internally by the TypeHandler

## Output Format
Return the complete modified XML content.
If no modifications are needed, return the original XML as-is with a comment at the top: <!-- NO_MODIFICATION_NEEDED -->

```xml
(modified XML content here)
```
"""

    def __init__(
        self,
        config_manager: ConfigurationManager,
        llm_provider: Optional[LLMProvider] = None,
    ):
        """
        TypeHandlerGenerator 초기화

        Args:
            config_manager: 설정 관리자
            llm_provider: LLM 프로바이더 (선택적)
        """
        self.config_manager = config_manager
        self.project_root = Path(config_manager.target_project)

        # LLM 프로바이더 초기화
        if llm_provider:
            self.llm_provider = llm_provider
        else:
            llm_provider_name = config_manager.get("llm_provider", "watsonx_ai")
            self.llm_provider = create_llm_provider(provider_name=llm_provider_name)

        # 컴포넌트 초기화
        self.error_handler = ErrorHandler(
            max_retries=config_manager.get("max_retries", 3)
        )
        self.result_tracker = ResultTracker()
        self.persistence_manager = DataPersistenceManager(self.project_root)

        # Type Handler 기본 설정
        self.type_handler_package = config_manager.get(
            "type_handler_package", "com.example.typehandler"
        )
        self.type_handler_output_dir = config_manager.get(
            "type_handler_output_dir", "src/main/java"
        )

        logger.info(
            f"TypeHandlerGenerator 초기화 완료: {self.llm_provider.get_provider_name()}"
        )

    def execute(self, dry_run: bool = False, apply_all: bool = False) -> int:
        """
        Type Handler 생성 및 XML 수정 실행

        Args:
            dry_run: 실제 파일 수정 없이 미리보기만 수행
            apply_all: 사용자 확인 없이 모든 변경사항 적용

        Returns:
            int: 종료 코드 (0: 성공, 1: 실패)
        """
        try:
            mode = "미리보기" if dry_run else "실제 수정"
            logger.info(f"Type Handler 생성 시작 (모드: {mode})...")
            print(f"Type Handler 방식으로 암복호화를 적용합니다 (모드: {mode})...")

            # 1. 분석 결과 로드
            print("  [1/4] 분석 결과 로드 중...")
            table_access_info_list = self._load_table_access_info()
            if not table_access_info_list:
                print(
                    "  오류: 테이블 접근 정보가 없습니다. 먼저 'analyze' 명령어를 실행하세요."
                )
                return 1
            print(
                f"  ✓ {len(table_access_info_list)}개의 테이블 접근 정보를 로드했습니다."
            )

            # SQL 추출 결과 로드 확인
            sql_results = self._load_sql_extraction_results()
            if sql_results:
                print(f"  ✓ {len(sql_results)}개의 XML 매퍼 파일 정보를 로드했습니다.")

            # 통계
            total_handlers_created = 0
            total_xml_modified = 0
            total_skipped = 0
            total_failed = 0

            # 2. 각 테이블별로 처리
            for table_info in table_access_info_list:
                print(f"\n  [2/4] 테이블 '{table_info.table_name}' 처리 중...")

                # 2.1 Type Handler 클래스 생성
                print("    - Type Handler 클래스 생성 중...")
                handler_result = self._generate_type_handler_class(
                    table_info, dry_run, apply_all
                )

                if handler_result["status"] == "success":
                    total_handlers_created += 1
                    print(
                        f"    ✓ Type Handler 생성 완료: {handler_result['class_name']}"
                    )
                elif handler_result["status"] == "skipped":
                    total_skipped += 1
                    print(
                        f"    - Type Handler 생성 건너뜀: {handler_result.get('reason', '')}"
                    )
                else:
                    total_failed += 1
                    print(
                        f"    ✗ Type Handler 생성 실패: {handler_result.get('error', '')}"
                    )
                    continue

                # 2.2 관련 XML 매퍼 파일 찾기 및 수정
                print("    - XML 매퍼 파일 수정 중...")
                xml_results = self._modify_xml_mappers(
                    table_info,
                    handler_result.get("full_class_name", ""),
                    dry_run,
                    apply_all,
                )

                for result in xml_results:
                    if result["status"] == "success":
                        total_xml_modified += 1
                        print(f"    ✓ XML 수정 완료: {Path(result['file_path']).name}")
                    elif result["status"] == "skipped":
                        print(
                            f"    - XML 수정 건너뜀: {Path(result['file_path']).name}"
                        )
                    else:
                        print(f"    ✗ XML 수정 실패: {result.get('error', '')}")

            # 3. 결과 저장
            print("\n  [4/4] 결과 저장 중...")
            self.result_tracker.save_statistics()

            # 4. 최종 통계 출력
            print("\n" + "=" * 60)
            print("Type Handler 생성 완료!")
            print("=" * 60)
            print(f"  - 생성된 Type Handler: {total_handlers_created}개")
            print(f"  - 수정된 XML 파일: {total_xml_modified}개")
            print(f"  - 건너뜀: {total_skipped}개")
            print(f"  - 실패: {total_failed}개")

            if dry_run:
                print("\n[미리보기 모드] 실제 파일은 수정되지 않았습니다.")

            return 0

        except Exception as e:
            logger.exception(f"Type Handler 생성 중 오류: {e}")
            print(f"오류: {e}")
            return 1

    def _load_table_access_info(self) -> List[TableAccessInfo]:
        """분석 결과에서 테이블 접근 정보 로드 (config의 crypto_code 병합)"""
        try:
            data = self.persistence_manager.load_from_file(
                "table_access_info.json", TableAccessInfo
            )
            if not data:
                return []

            result = []
            for info in data:
                if isinstance(info, dict):
                    table_info = TableAccessInfo.from_dict(info)
                elif isinstance(info, TableAccessInfo):
                    table_info = info
                else:
                    continue

                # config_manager에서 crypto_code 정보 병합
                table_info = self._merge_crypto_codes(table_info)
                result.append(table_info)

            return result

        except Exception as e:
            logger.error(f"테이블 접근 정보 로드 실패: {e}")
            return []

    def _merge_crypto_codes(self, table_info: TableAccessInfo) -> TableAccessInfo:
        """config_manager에서 crypto_code 정보를 가져와 TableAccessInfo에 병합"""
        # config에서 해당 테이블의 컬럼 정보 가져오기
        config_columns = {}
        for table in self.config_manager.access_tables:
            if table["table_name"] == table_info.table_name:
                for col in table.get("columns", []):
                    if isinstance(col, dict):
                        col_name = col.get("name", "")
                        crypto_code = col.get("crypto_code", "")
                        if col_name:
                            config_columns[col_name] = crypto_code
                break

        # table_info의 columns에 crypto_code 추가
        updated_columns = []
        for col in table_info.columns:
            if isinstance(col, dict):
                col_name = col.get("name", "")
                # config에서 crypto_code 가져오기
                if col_name in config_columns:
                    col["crypto_code"] = config_columns[col_name]
                updated_columns.append(col)
            elif isinstance(col, str):
                # 문자열인 경우 dict로 변환
                updated_columns.append(
                    {
                        "name": col,
                        "new_column": False,
                        "crypto_code": config_columns.get(col, ""),
                    }
                )
            else:
                updated_columns.append(col)

        table_info.columns = updated_columns
        return table_info

    def _load_sql_extraction_results(self) -> List[Dict[str, Any]]:
        """sql_extraction_results.json에서 SQL 추출 결과 로드"""
        try:
            data = self.persistence_manager.load_from_file(
                "sql_extraction_results.json"
            )
            return data if data else []
        except Exception as e:
            logger.error(f"SQL 추출 결과 로드 실패: {e}")
            return []

    def _find_xml_files_for_table(self, table_name: str) -> List[Path]:
        """
        sql_extraction_results.json을 참고하여 특정 테이블과 관련된 XML 파일 탐색

        Args:
            table_name: 테이블명

        Returns:
            List[Path]: 관련 XML 파일 경로 목록
        """
        xml_files = []
        table_name_lower = table_name.lower()

        # SQL 추출 결과에서 테이블을 사용하는 XML 파일 찾기
        sql_results = self._load_sql_extraction_results()

        for result in sql_results:
            file_info = result.get("file", {})
            file_path = file_info.get("path", "")

            # XML 파일이 아니면 스킵
            if not str(file_path).endswith(".xml"):
                continue

            sql_queries = result.get("sql_queries", [])

            # 해당 파일의 SQL 쿼리 중에 타겟 테이블을 사용하는 쿼리가 있는지 확인
            for query in sql_queries:
                sql = query.get("sql", "").lower()
                # 테이블명이 SQL에 포함되어 있는지 확인
                if table_name_lower in sql:
                    xml_path = Path(file_path)
                    if xml_path.exists() and xml_path not in xml_files:
                        xml_files.append(xml_path)
                        logger.info(
                            f"테이블 '{table_name}' 관련 XML 파일 발견: {xml_path.name}"
                        )
                    break  # 이 파일에서 이미 찾았으므로 다음 파일로

        return xml_files

    def _find_xml_mapper_files(self) -> List[Path]:
        """
        프로젝트에서 모든 XML 매퍼 파일 탐색 (sql_extraction_results.json 활용)
        """
        xml_files = []

        # SQL 추출 결과에서 XML 파일 목록 추출
        sql_results = self._load_sql_extraction_results()

        for result in sql_results:
            file_info = result.get("file", {})
            file_path = file_info.get("path", "")

            # XML 파일이면 추가
            if file_path.endswith(".xml"):
                xml_path = Path(file_path)
                if xml_path.exists():
                    xml_files.append(xml_path)

        return xml_files

    def _generate_type_handler_class(
        self,
        table_info: TableAccessInfo,
        dry_run: bool,
        apply_all: bool,
    ) -> Dict[str, Any]:
        """
        Type Handler Java 클래스 생성

        Args:
            table_info: 테이블 접근 정보
            dry_run: 미리보기 모드
            apply_all: 자동 적용 모드

        Returns:
            Dict[str, Any]: 생성 결과
        """
        # 클래스 이름 생성 (테이블명 기반)
        class_name = self._generate_class_name(table_info.table_name)
        full_class_name = f"{self.type_handler_package}.{class_name}"

        # 컬럼 정보 포맷팅
        columns_info = self._format_columns_info(table_info.columns)

        # 프롬프트 생성
        prompt = self.TYPE_HANDLER_PROMPT_TEMPLATE.format(
            package_name=self.type_handler_package,
            class_name=class_name,
            table_name=table_info.table_name,
            columns_info=columns_info,
        )

        try:
            # LLM 호출
            response, error = self.error_handler.retry_with_backoff(
                self.llm_provider.call, prompt
            )

            if error:
                return {
                    "status": "failed",
                    "error": str(error),
                    "class_name": class_name,
                }

            # 응답에서 Java 코드 추출
            java_code = self._extract_java_code(response)
            if not java_code:
                return {
                    "status": "failed",
                    "error": "LLM 응답에서 Java 코드를 추출할 수 없습니다.",
                    "class_name": class_name,
                }

            # 파일 저장 경로 결정
            output_path = self._get_type_handler_output_path(class_name)

            # 미리보기 출력
            if not apply_all and not dry_run:
                print(f"\n--- Type Handler 클래스 미리보기: {class_name} ---")
                print(f"\033[92m{java_code}\033[0m")  # Green
                print(f"--- 저장 경로: {output_path} ---\n")

                choice = self._get_user_confirmation()
                if choice == "n":
                    return {
                        "status": "skipped",
                        "reason": "사용자가 건너뛰기를 선택함",
                        "class_name": class_name,
                    }
                elif choice == "q":
                    raise KeyboardInterrupt("사용자가 중단을 선택함")

            # 파일 저장
            if not dry_run:
                self._save_type_handler_file(java_code, output_path)

            return {
                "status": "success",
                "class_name": class_name,
                "full_class_name": full_class_name,
                "output_path": str(output_path),
                "java_code": java_code,
            }

        except KeyboardInterrupt:
            raise
        except Exception as e:
            logger.error(f"Type Handler 생성 실패: {e}")
            return {
                "status": "failed",
                "error": str(e),
                "class_name": class_name,
            }

    def _modify_xml_mappers(
        self,
        table_info: TableAccessInfo,
        type_handler_class: str,
        dry_run: bool,
        apply_all: bool,
    ) -> List[Dict[str, Any]]:
        """
        관련 XML 매퍼 파일들을 수정하여 typeHandler 속성 추가

        Args:
            table_info: 테이블 접근 정보
            type_handler_class: Type Handler 전체 클래스명
            dry_run: 미리보기 모드
            apply_all: 자동 적용 모드

        Returns:
            List[Dict[str, Any]]: 수정 결과 목록
        """
        results = []

        # sql_extraction_results.json에서 테이블 관련 XML 파일 찾기
        related_xml_files = self._find_xml_files_for_table(table_info.table_name)

        if not related_xml_files:
            logger.warning(
                f"테이블 '{table_info.table_name}'과 관련된 XML 파일을 찾을 수 없습니다."
            )
            return results

        for xml_file in related_xml_files:
            result = self._modify_single_xml_mapper(
                xml_file,
                table_info,
                type_handler_class,
                dry_run,
                apply_all,
            )
            results.append(result)

        return results

    def _modify_single_xml_mapper(
        self,
        xml_file: Path,
        table_info: TableAccessInfo,
        type_handler_class: str,
        dry_run: bool,
        apply_all: bool,
    ) -> Dict[str, Any]:
        """
        단일 XML 매퍼 파일 수정

        Args:
            xml_file: XML 파일 경로
            table_info: 테이블 접근 정보
            type_handler_class: Type Handler 클래스명
            dry_run: 미리보기 모드
            apply_all: 자동 적용 모드

        Returns:
            Dict[str, Any]: 수정 결과
        """
        try:
            # 원본 XML 읽기
            with open(xml_file, "r", encoding="utf-8") as f:
                original_content = f.read()

            # 컬럼 정보 포맷팅
            columns_info = self._format_columns_info(table_info.columns)

            # XML 내용의 중괄호를 이스케이프 (MyBatis #{param} 문법 때문에 필요)
            escaped_xml_content = original_content.replace("{", "{{").replace("}", "}}")

            # 프롬프트 생성
            prompt = self.XML_MODIFICATION_PROMPT_TEMPLATE.format(
                table_name=table_info.table_name,
                columns_info=columns_info,
                type_handler_class=type_handler_class,
                xml_content=escaped_xml_content,
            )

            # LLM 호출
            response, error = self.error_handler.retry_with_backoff(
                self.llm_provider.call, prompt
            )

            if error:
                return {
                    "status": "failed",
                    "file_path": str(xml_file),
                    "error": str(error),
                }

            # 응답에서 XML 코드 추출
            modified_xml = self._extract_xml_code(response)
            if not modified_xml:
                return {
                    "status": "failed",
                    "file_path": str(xml_file),
                    "error": "LLM 응답에서 XML 코드를 추출할 수 없습니다.",
                }

            # 수정 필요 없음 체크
            if "NO_MODIFICATION_NEEDED" in modified_xml:
                return {
                    "status": "skipped",
                    "file_path": str(xml_file),
                    "reason": "수정이 필요하지 않음",
                }

            # 변경사항 확인
            if original_content.strip() == modified_xml.strip():
                return {
                    "status": "skipped",
                    "file_path": str(xml_file),
                    "reason": "변경사항 없음",
                }

            # 미리보기 및 사용자 확인
            if not apply_all and not dry_run:
                self._print_xml_diff(xml_file, original_content, modified_xml)
                choice = self._get_user_confirmation()
                if choice == "n":
                    return {
                        "status": "skipped",
                        "file_path": str(xml_file),
                        "reason": "사용자가 건너뛰기를 선택함",
                    }
                elif choice == "q":
                    raise KeyboardInterrupt("사용자가 중단을 선택함")

            # 파일 저장
            if not dry_run:
                # 백업 생성
                self.error_handler.backup_file(xml_file)

                with open(xml_file, "w", encoding="utf-8") as f:
                    f.write(modified_xml)

                logger.info(f"XML 파일 수정 완료: {xml_file}")
                print(f"XML 파일 수정 완료: {xml_file}")

            return {
                "status": "success",
                "file_path": str(xml_file),
                "original": original_content,
                "modified": modified_xml,
            }

        except KeyboardInterrupt:
            raise
        except Exception as e:
            import traceback

            logger.error(f"XML 수정 실패: {xml_file} - {e}")
            logger.error(f"스택 트레이스:\n{traceback.format_exc()}")
            return {
                "status": "failed",
                "file_path": str(xml_file),
                "error": str(e),
            }

    def _generate_class_name(self, table_name: str) -> str:
        """테이블명으로부터 클래스명 생성"""
        # snake_case -> PascalCase
        parts = table_name.lower().split("_")
        # 'tb_' 접두사 제거
        if parts[0] == "tb":
            parts = parts[1:]
        pascal_name = "".join(part.capitalize() for part in parts)
        return f"{pascal_name}EncryptTypeHandler"

    def _format_columns_info(self, columns: List[Any]) -> str:
        """컬럼 정보를 문자열로 포맷팅 (crypto_code 포함)"""
        lines = []
        for col in columns:
            if isinstance(col, dict):
                col_name = col.get("name", str(col))
                is_new = col.get("new_column", False)
                crypto_code = col.get("crypto_code", "")

                col_info = f"  - {col_name}"
                if crypto_code:
                    col_info += f' (crypto_code: "{crypto_code}")'
                if is_new:
                    col_info += " (new column)"
                lines.append(col_info)
            else:
                lines.append(f"  - {col}")
        return "\n".join(lines)

    def _get_type_handler_output_path(self, class_name: str) -> Path:
        """Type Handler 파일 저장 경로 결정"""
        # 패키지 경로로 변환
        package_path = self.type_handler_package.replace(".", "/")
        output_dir = self.project_root / self.type_handler_output_dir / package_path
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir / f"{class_name}.java"

    def _save_type_handler_file(self, java_code: str, output_path: Path) -> None:
        """Type Handler Java 파일 저장"""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(java_code)
        logger.info(f"Type Handler 파일 저장: {output_path}")

    def _extract_java_code(self, response: Dict[str, Any]) -> Optional[str]:
        """LLM 응답에서 Java 코드 추출"""
        content = response.get("content", "")
        if not content:
            return None

        # ```java ... ``` 블록 추출
        pattern = r"```java\s*(.*?)\s*```"
        match = re.search(pattern, content, re.DOTALL)
        if match:
            return match.group(1).strip()

        # 코드 블록 없이 직접 반환된 경우
        if content.strip().startswith("package"):
            return content.strip()

        return None

    def _extract_xml_code(self, response: Dict[str, Any]) -> Optional[str]:
        """LLM 응답에서 XML 코드 추출"""
        content = response.get("content", "")
        if not content:
            return None

        # ```xml ... ``` 블록 추출
        pattern = r"```xml\s*(.*?)\s*```"
        match = re.search(pattern, content, re.DOTALL)
        if match:
            return match.group(1).strip()

        # 코드 블록 없이 직접 반환된 경우
        if content.strip().startswith("<?xml") or content.strip().startswith("<"):
            return content.strip()

        return None

    def _print_xml_diff(self, file_path: Path, original: str, modified: str) -> None:
        """XML 변경사항 출력"""
        import difflib

        diff = difflib.unified_diff(
            original.splitlines(keepends=True),
            modified.splitlines(keepends=True),
            fromfile=f"a/{file_path.name}",
            tofile=f"b/{file_path.name}",
        )

        print(f"\n[Diff] {file_path}")
        print("-" * 80)
        for line in diff:
            if line.startswith("+"):
                print(f"\033[92m{line}\033[0m", end="")  # Green
            elif line.startswith("-"):
                print(f"\033[91m{line}\033[0m", end="")  # Red
            elif line.startswith("@@"):
                print(f"\033[96m{line}\033[0m", end="")  # Cyan
            else:
                print(line, end="")
        print("-" * 80)

    def _get_user_confirmation(self) -> str:
        """사용자 확인 입력"""
        while True:
            choice = input(
                "\n이 변경사항을 적용하시겠습니까? [y/n/a/q] "
                "(y:적용, n:건너뛰기, a:모두적용, q:중단): "
            ).lower()
            if choice in ["y", "n", "a", "q"]:
                return choice
            print("잘못된 입력입니다.")
