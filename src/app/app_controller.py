import logging
import sys
from datetime import datetime
from parser.call_graph_builder import CallGraphBuilder, Endpoint
from parser.java_ast_parser import JavaASTParser
from parser.xml_mapper_parser import XMLMapperParser
from pathlib import Path
from typing import Optional

from tabulate import tabulate

from analyzer.db_access_analyzer import DBAccessAnalyzer
from analyzer.sql_extractor import SQLExtractor
from analyzer.sql_parsing_strategy import create_strategy
from collector.source_file_collector import SourceFileCollector
from config.config_manager import Configuration, ConfigurationError
from config.config_manager import load_config as load_global_config
from models.modification_record import ModificationRecord
from models.source_file import SourceFile
from models.table_access_info import TableAccessInfo
from modifier.code_modifier import CodeModifier
from persistence.cache_manager import CacheManager
from persistence.data_persistence_manager import (
    DataPersistenceManager,
    PersistenceError,
)


class AppController:
    """
    애플리케이션의 핵심 로직을 담당하는 컨트롤러
    """

    def __init__(self):
        """AppController 초기화"""
        self.logger = self._setup_logging()
        self.config: Optional[Configuration] = None

    def _setup_logging(self) -> logging.Logger:
        """
        로깅 설정
        """
        # 로그 디렉터리 생성
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        # 로그 파일 경로 (타임스탬프 포함)
        log_file = (
            log_dir / f"applycrypto_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        )

        # 로거 설정
        logger = logging.getLogger("applycrypto")
        logger.setLevel(logging.DEBUG)

        # 중복 핸들러 추가 방지
        if not logger.handlers:
            # 파일 핸들러
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setLevel(logging.DEBUG)
            file_formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)

            # 콘솔 핸들러
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            console_formatter = logging.Formatter("%(levelname)s - %(message)s")
            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)

        return logger

    def load_config(self, config_path: str) -> Configuration:
        """
        설정 파일 로드
        """
        try:
            self.config = load_global_config(config_path)
            self.logger.info(f"설정 파일 로드 성공: {config_path}")
            return self.config
        except ConfigurationError as e:
            self.logger.error(f"설정 파일 로드 실패: {e}")
            raise

    def analyze(self, config_path: str) -> int:
        """
        analyze 명령어 처리
        """
        try:
            # 설정 파일 로드
            config = self.load_config(config_path)
            target_project = Path(config.target_project)

            self.logger.info("프로젝트 분석 시작...")
            print("프로젝트 분석을 시작합니다...")

            # Data Persistence Manager 초기화
            persistence_manager = DataPersistenceManager(target_project)
            cache_manager = persistence_manager.cache_manager or CacheManager()

            # 1. 소스 파일 수집
            print("  [1/5] 소스 파일 수집 중...")
            self.logger.info("소스 파일 수집 시작")
            collector = SourceFileCollector(config)
            source_files = list[SourceFile](collector.collect())
            print(f"  ✓ {len(source_files)}개의 소스 파일을 수집했습니다.")
            self.logger.info(f"소스 파일 수집 완료: {len(source_files)}개")

            # 소스 파일 저장
            persistence_manager.save_to_file(
                [f.to_dict() for f in source_files], "source_files.json"
            )

            # 2. Java AST 파싱 및 Call Graph 생성
            print("  [2/5] Java AST 파싱 및 Call Graph 생성 중...")
            self.logger.info("Java AST 파싱 및 Call Graph 생성 시작")
            java_parser = JavaASTParser(cache_manager=cache_manager)
            java_files = [f.path for f in source_files if f.extension == ".java"]

            # Call Graph 생성
            call_graph_builder = CallGraphBuilder(
                java_parser=java_parser, cache_manager=cache_manager
            )
            call_graph_builder.build_call_graph(java_files)
            endpoints = call_graph_builder.get_endpoints()

            # Java 파싱 결과 생성
            java_parse_results = []
            for java_file_path in java_files:
                classes = call_graph_builder.get_classes_for_file(java_file_path)
                if classes:
                    source_file = next(
                        (f for f in source_files if f.path == java_file_path), None
                    )
                    if source_file:
                        java_parse_results.append(
                            {
                                "file": source_file.to_dict(),
                                "classes": [cls.to_dict() for cls in classes],
                            }
                        )

            print(f"  ✓ {len(java_parse_results)}개의 Java 파일을 파싱했습니다.")
            print(f"  ✓ {len(endpoints)}개의 엔드포인트를 식별했습니다.")
            self.logger.info(
                f"Java AST 파싱 및 Call Graph 생성 완료: {len(java_parse_results)}개 파일, {len(endpoints)}개 엔드포인트"
            )

            # 3. SQL 추출
            print("  [3/5] SQL 추출 중...")
            self.logger.info("SQL 추출 시작")
            sql_wrapping_type = config.sql_wrapping_type
            sql_strategy = create_strategy(sql_wrapping_type)

            xml_parser = XMLMapperParser()
            sql_extractor = SQLExtractor(
                strategy=sql_strategy, xml_parser=xml_parser, java_parser=java_parser
            )

            sql_extraction_results = sql_extractor.extract_from_files(source_files)
            print(f"  ✓ {len(sql_extraction_results)}개의 파일에서 SQL을 추출했습니다.")

            total_sql_queries = sum(
                len(r.get("sql_queries", [])) for r in sql_extraction_results
            )
            print(f"  ✓ 총 {total_sql_queries}개의 SQL 쿼리를 추출했습니다.")
            self.logger.info(
                f"SQL 추출 완료: {len(sql_extraction_results)}개 파일, {total_sql_queries}개 쿼리"
            )

            # 결과 저장
            persistence_manager.save_to_file(
                java_parse_results, "java_parse_results.json"
            )
            persistence_manager.save_to_file(
                sql_extraction_results, "sql_extraction_results.json"
            )

            call_graph_data = {
                "endpoints": [
                    ep.to_dict() if hasattr(ep, "to_dict") else str(ep)
                    for ep in endpoints
                ],
                "node_count": call_graph_builder.call_graph.number_of_nodes()
                if call_graph_builder.call_graph
                else 0,
                "edge_count": call_graph_builder.call_graph.number_of_edges()
                if call_graph_builder.call_graph
                else 0,
                "call_trees": call_graph_builder.get_all_call_trees(max_depth=20),
            }
            persistence_manager.save_to_file(call_graph_data, "call_graph.json")

            # 5. DB 접근 정보 분석
            print("  [5/5] DB 접근 정보 분석 중...")
            self.logger.info("DB 접근 정보 분석 시작")
            db_analyzer = DBAccessAnalyzer(
                config=config,
                sql_strategy=sql_strategy,
                xml_parser=xml_parser,
                java_parser=java_parser,
                call_graph_builder=call_graph_builder,
            )
            table_access_info_list = db_analyzer.analyze(source_files)
            print(
                f"  ✓ {len(table_access_info_list)}개의 테이블 접근 정보를 분석했습니다."
            )
            self.logger.info(f"DB 접근 정보 분석 완료: {len(table_access_info_list)}개")

            persistence_manager.save_to_file(
                [info.to_dict() for info in table_access_info_list],
                "table_access_info.json",
            )

            print("\n분석이 완료되었습니다.")
            print(f"  - 수집된 파일: {len(source_files)}개")
            print(f"  - Java 파일: {len(java_parse_results)}개")
            print(f"  - SQL 추출 파일: {len(sql_extraction_results)}개")
            print(f"  - 엔드포인트: {len(endpoints)}개")
            print(f"  - 테이블 접근 정보: {len(table_access_info_list)}개")
            self.logger.info("프로젝트 분석 완료")
            return 0

        except ConfigurationError as e:
            print(f"오류: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            self.logger.exception(f"analyze 명령어 실행 중 오류: {e}")
            print(f"오류: {e}", file=sys.stderr)
            return 1

    def list_info(
        self,
        config_path: str,
        show_all: bool = False,
        show_db: bool = False,
        show_modified: bool = False,
        show_endpoint: bool = False,
        callgraph_endpoint: Optional[str] = None,
    ) -> int:
        """
        list 명령어 처리
        """
        try:
            self.logger.info("정보 조회 시작...")

            # 설정 파일 로드
            config = self.load_config(config_path)
            target_project = Path(config.target_project)

            # DataPersistenceManager 초기화
            persistence_manager = DataPersistenceManager(target_project)

            if show_all:
                self._list_all_files(persistence_manager)

            if show_db:
                self._list_db_access(persistence_manager)

            if show_modified:
                self._list_modified_files(persistence_manager)

            if show_endpoint:
                self._list_endpoints(persistence_manager)

            if callgraph_endpoint:
                self._list_callgraph(callgraph_endpoint, persistence_manager)

            self.logger.info("정보 조회 완료")
            return 0

        except Exception as e:
            self.logger.exception(f"list 명령어 실행 중 오류: {e}")
            print(f"오류: {e}", file=sys.stderr)
            return 1

    def modify(
        self, config_path: str, dry_run: bool = False, force_all: bool = False
    ) -> int:
        """
        modify 명령어 처리
        """
        try:
            # 설정 파일 로드
            config = self.load_config(config_path)
            target_project = Path(config.target_project)

            self.logger.info("코드 수정 시작...")
            print("코드 수정을 시작합니다...")
            if dry_run:
                print("미리보기(Dry-Run) 모드로 실행됩니다.")

            # DataPersistenceManager 초기화
            persistence_manager = DataPersistenceManager(target_project)

            # 테이블 접근 정보 로드
            try:
                table_access_data = persistence_manager.load_from_file(
                    "table_access_info.json", TableAccessInfo
                )
            except PersistenceError:
                print(
                    "분석 결과를 찾을 수 없습니다. 먼저 'analyze' 명령어를 실행하세요.",
                    file=sys.stderr,
                )
                return 1

            if not table_access_data:
                print("테이블 접근 정보가 없습니다.", file=sys.stderr)
                return 1

            table_access_info_list = [
                TableAccessInfo.from_dict(t) if isinstance(t, dict) else t
                for t in table_access_data
            ]

            # CodeModifier 초기화
            modifier = CodeModifier(config)

            # 수정 대상 식별
            modification_targets = modifier.identify_targets(table_access_info_list)
            print(f"{len(modification_targets)}개의 파일에서 수정 대상을 식별했습니다.")

            if not modification_targets:
                print("수정할 대상이 없습니다.")
                return 0

            # 사용자 확인
            if not force_all and not dry_run:
                print("\n수정 대상 파일 목록:")
                for target in modification_targets:
                    print(f" - {target.file_path}")

                response = input("\n수정을 진행하시겠습니까? (y/N): ")
                if response.lower() != "y":
                    print("작업이 취소되었습니다.")
                    return 0

            # 수정 적용
            results = modifier.apply_modifications(
                modification_targets, dry_run=dry_run
            )

            # 수정 기록 저장
            if not dry_run:
                persistence_manager.save_to_file(
                    [r.to_dict() for r in results], "modification_records.json"
                )
                print(
                    f"\n코드 수정이 완료되었습니다. {len(results)}개의 파일이 수정되었습니다."
                )
            else:
                print(
                    f"\n미리보기가 완료되었습니다. {len(results)}개의 파일이 수정될 예정입니다."
                )

            return 0

        except Exception as e:
            self.logger.exception(f"modify 명령어 실행 중 오류: {e}")
            print(f"오류: {e}", file=sys.stderr)
            return 1

    def _list_all_files(
        self, persistence_manager: Optional[DataPersistenceManager]
    ) -> None:
        """모든 소스 파일 목록 출력"""
        try:
            if not persistence_manager:
                return

            source_files_data = persistence_manager.load_from_file(
                "source_files.json", SourceFile
            )
            if not source_files_data:
                print("수집된 소스 파일이 없습니다.")
                return

            source_files = [
                SourceFile.from_dict(f) if isinstance(f, dict) else f
                for f in source_files_data
            ]

            # 테이블 데이터 준비
            table_data = []
            for f in source_files:
                table_data.append(
                    [
                        f.filename,
                        str(f.relative_path),
                        f"{f.size:,} bytes",
                        f.modified_time.strftime("%Y-%m-%d %H:%M:%S"),
                        f.extension,
                    ]
                )

            if tabulate:
                print("\n모든 소스 파일 목록:")
                print(
                    tabulate(
                        table_data,
                        headers=["파일명", "경로", "크기", "수정 시간", "확장자"],
                        tablefmt="grid",
                    )
                )
            else:
                print("\n모든 소스 파일 목록:")
                for row in table_data:
                    print(f"  {row[0]} ({row[1]})")

            print(f"\n총 {len(source_files)}개의 파일")

        except PersistenceError as e:
            print(f"오류: {e}", file=sys.stderr)
        except Exception as e:
            self.logger.exception(f"파일 목록 조회 중 오류: {e}")
            print(f"오류: {e}", file=sys.stderr)

    def _list_db_access(
        self, persistence_manager: Optional[DataPersistenceManager]
    ) -> None:
        """테이블별 접근 파일 목록 출력"""
        try:
            if not persistence_manager:
                return

            table_access_data = persistence_manager.load_from_file(
                "table_access_info.json", TableAccessInfo
            )
            if not table_access_data:
                print("테이블 접근 정보가 없습니다.")
                return

            table_access_list = [
                TableAccessInfo.from_dict(t) if isinstance(t, dict) else t
                for t in table_access_data
            ]

            table_data = []
            for info in table_access_list:
                table_data.append(
                    [
                        info.table_name,
                        len(info.access_files),
                        ", ".join(
                            [
                                col.get("name", col) if isinstance(col, dict) else col
                                for col in info.columns[:3]
                            ]
                        )
                        + ("..." if len(info.columns) > 3 else ""),
                        info.layer,
                        info.query_type,
                    ]
                )

            if tabulate:
                print("\n테이블별 접근 파일 목록:")
                print(
                    tabulate(
                        table_data,
                        headers=[
                            "테이블명",
                            "접근 파일 수",
                            "칼럼 (일부)",
                            "레이어",
                            "쿼리 타입",
                        ],
                        tablefmt="grid",
                    )
                )
            else:
                print("\n테이블별 접근 파일 목록:")
                for row in table_data:
                    print(f"  {row[0]}: {row[1]}개 파일")

            print("\n" + "=" * 80)
            print("테이블별 접근 파일 경로 상세:")
            print("=" * 80)
            for info in table_access_list:
                print(f"\n테이블: {info.table_name} ({len(info.access_files)}개 파일)")
                print(f"  레이어: {info.layer}")
                print(f"  쿼리 타입: {info.query_type}")
                column_names = [
                    col.get("name", col) if isinstance(col, dict) else col
                    for col in info.columns
                ]
                print(f"  칼럼: {', '.join(column_names) if column_names else 'N/A'}")
                print("  접근 파일:")
                if info.access_files:
                    for file_path in info.access_files:
                        print(f"    - {file_path}")
                else:
                    print("    (접근 파일 없음)")

            print(f"\n총 {len(table_access_list)}개의 테이블")

        except PersistenceError as e:
            print(f"오류: {e}", file=sys.stderr)
        except Exception as e:
            self.logger.exception(f"DB 접근 정보 조회 중 오류: {e}")
            print(f"오류: {e}", file=sys.stderr)

    def _list_modified_files(
        self, persistence_manager: Optional[DataPersistenceManager]
    ) -> None:
        """수정된 파일 목록 출력"""
        try:
            if not persistence_manager:
                return

            try:
                modified_data = persistence_manager.load_from_file(
                    "modification_records.json", ModificationRecord
                )
            except PersistenceError:
                print("수정된 파일이 없습니다.")
                return

            if not modified_data:
                print("수정된 파일이 없습니다.")
                return

            modified_records = [
                ModificationRecord.from_dict(m) if isinstance(m, dict) else m
                for m in modified_data
            ]

            table_data = []
            for record in modified_records:
                table_data.append(
                    [
                        Path(record.file_path).name,
                        record.table_name,
                        record.column_name,
                        len(record.modified_methods),
                        record.status,
                        record.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    ]
                )

            if tabulate:
                print("\n수정된 파일 목록:")
                print(
                    tabulate(
                        table_data,
                        headers=[
                            "파일명",
                            "테이블명",
                            "칼럼명",
                            "수정된 메서드 수",
                            "상태",
                            "수정 시간",
                        ],
                        tablefmt="grid",
                    )
                )
            else:
                print("\n수정된 파일 목록:")
                for row in table_data:
                    print(f"  {row[0]} ({row[1]}.{row[2]}) - {row[3]}개 메서드")

            print(f"\n총 {len(modified_records)}개의 수정 기록")

        except PersistenceError as e:
            print(f"오류: {e}", file=sys.stderr)
        except Exception as e:
            self.logger.exception(f"수정 파일 목록 조회 중 오류: {e}")
            print(f"오류: {e}", file=sys.stderr)

    def _list_endpoints(
        self, persistence_manager: Optional[DataPersistenceManager]
    ) -> None:
        """REST API 엔드포인트 목록 출력"""
        try:
            if not persistence_manager:
                return

            call_graph_data = persistence_manager.load_from_file("call_graph.json")
            if not call_graph_data or "endpoints" not in call_graph_data:
                print("엔드포인트 정보가 없습니다.")
                return

            endpoints = call_graph_data["endpoints"]
            if not endpoints:
                print("엔드포인트가 없습니다.")
                return

            endpoint_objects = []
            for ep in endpoints:
                if isinstance(ep, dict):
                    endpoint_objects.append(Endpoint.from_dict(ep))
                elif isinstance(ep, Endpoint):
                    endpoint_objects.append(ep)
                else:
                    continue

            if not endpoint_objects:
                print("유효한 엔드포인트가 없습니다.")
                return

            table_data = []
            for ep in endpoint_objects:
                table_data.append(
                    [ep.http_method, ep.path, ep.method_signature, ep.class_name]
                )

            if tabulate:
                print("\nREST API 엔드포인트 목록:")
                print(
                    tabulate(
                        table_data,
                        headers=["HTTP 메서드", "경로", "메서드 시그니처", "클래스명"],
                        tablefmt="grid",
                    )
                )
            else:
                print("\nREST API 엔드포인트 목록:")
                for row in table_data:
                    print(f"  {row[0]} {row[1]} -> {row[2]} ({row[3]})")

            print(f"\n총 {len(endpoint_objects)}개의 엔드포인트")
            print("\n호출 그래프를 보려면: list --callgraph <method_signature>")

        except PersistenceError as e:
            print(f"오류: {e}", file=sys.stderr)
        except Exception as e:
            self.logger.exception(f"엔드포인트 목록 조회 중 오류: {e}")
            print(f"오류: {e}", file=sys.stderr)

    def _list_callgraph(
        self, endpoint: str, persistence_manager: Optional[DataPersistenceManager]
    ) -> None:
        """특정 엔드포인트의 호출 그래프 출력"""
        try:
            if not persistence_manager:
                return

            call_graph_data = persistence_manager.load_from_file("call_graph.json")
            if not call_graph_data:
                print("Call Graph 데이터가 없습니다.")
                return

            call_trees = call_graph_data.get("call_trees", {})

            if endpoint in call_trees:
                print(f"\n{endpoint}의 Call Graph:")
                import json

                print(json.dumps(call_trees[endpoint], indent=2, ensure_ascii=False))
            else:
                print(f"엔드포인트를 찾을 수 없습니다: {endpoint}")

        except Exception as e:
            self.logger.exception(f"Call Graph 조회 중 오류: {e}")
            print(f"오류: {e}", file=sys.stderr)
