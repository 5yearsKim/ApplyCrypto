"""
CLI Controller 모듈

argparse를 사용하여 CLI 기본 구조를 구축하고, analyze, list, modify 명령어와 각 옵션을 파싱합니다.
"""

import argparse
import logging
import sys
from typing import List, Optional

from app.app_controller import AppController


class CLIController:
    """
    CLI 명령어를 파싱하고 실행하는 컨트롤러 클래스

    주요 기능:
    1. 명령어 정의: analyze, list, modify 명령어 구현
    2. 옵션 파싱: argparse를 사용하여 각 명령의 옵션 정의
    3. AppController 호출: 파싱된 인자를 AppController에 전달
    """

    def __init__(self):
        """CLIController 초기화"""
        self.parser = self._create_parser()
        # 로깅은 AppController에서도 설정하지만, CLI 레벨의 로깅 필요시 여기서도 설정 가능
        # 현재 구조에서는 AppController가 로직을 수행하므로, 단순 인자 파싱 에러 등은 stderr로 출력됨.
        self.logger = logging.getLogger("applycrypto.cli")
        self.app_controller = AppController()

    def _create_parser(self) -> argparse.ArgumentParser:
        """
        argparse 파서 생성 및 서브파서 설정

        Returns:
            argparse.ArgumentParser: 설정된 메인 파서
        """
        # 메인 파서 생성
        parser = argparse.ArgumentParser(
            prog="applycrypto",
            description="Java Spring Boot 프로젝트 암호화 자동 적용 도구",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
예제:
  %(prog)s analyze --config config.json
  %(prog)s list --all
  %(prog)s list --db
  %(prog)s modify --config config.json --dry-run
            """,
        )

        # 서브파서 생성
        subparsers = parser.add_subparsers(
            dest="command", help="사용 가능한 명령어", metavar="COMMAND"
        )

        # analyze 명령어 서브파서
        analyze_parser = subparsers.add_parser(
            "analyze",
            help="프로젝트를 분석하여 소스 파일, Call Graph, DB 접근 정보를 수집합니다",
            description="프로젝트를 분석하여 소스 파일, Call Graph, DB 접근 정보를 수집합니다.",
        )
        analyze_parser.add_argument(
            "--config",
            type=str,
            default="config.json",
            help="설정 파일 경로 (기본값: config.json)",
        )

        # list 명령어 서브파서
        list_parser = subparsers.add_parser(
            "list",
            help="수집된 정보를 조회합니다",
            description="수집된 정보를 조회합니다. 하나 이상의 옵션을 지정할 수 있습니다.",
        )
        list_parser.add_argument(
            "--config",
            type=str,
            default="config.json",
            help="설정 파일 경로 (기본값: config.json)",
        )
        list_group = list_parser.add_mutually_exclusive_group()
        list_group.add_argument(
            "--all", action="store_true", help="수집된 모든 소스 파일 목록을 출력합니다"
        )
        list_group.add_argument(
            "--db", action="store_true", help="테이블별 접근 파일 목록을 출력합니다"
        )
        list_group.add_argument(
            "--modified", action="store_true", help="수정된 파일 목록을 출력합니다"
        )
        list_group.add_argument(
            "--endpoint",
            action="store_true",
            help="REST API 엔드포인트 목록을 출력합니다",
        )
        list_parser.add_argument(
            "--callgraph",
            type=str,
            metavar="ENDPOINT",
            help="특정 엔드포인트의 호출 그래프를 출력합니다",
        )

        # modify 명령어 서브파서
        modify_parser = subparsers.add_parser(
            "modify",
            help="식별된 파일에 암복호화 코드를 삽입합니다",
            description="식별된 파일에 암복호화 코드를 삽입합니다.",
        )
        modify_parser.add_argument(
            "--config",
            type=str,
            default="config.json",
            help="설정 파일 경로 (기본값: config.json)",
        )
        modify_parser.add_argument(
            "--dry-run",
            action="store_true",
            help="실제 파일 수정 없이 미리보기만 수행합니다",
        )
        modify_parser.add_argument(
            "--all",
            action="store_true",
            help="사용자 확인 없이 모든 변경사항을 자동으로 적용합니다",
        )

        return parser

    def parse_args(self, args: Optional[List[str]] = None) -> argparse.Namespace:
        """
        명령줄 인자 파싱

        Args:
            args: 파싱할 인자 리스트 (None이면 sys.argv 사용)

        Returns:
            argparse.Namespace: 파싱된 인자

        Raises:
            SystemExit: 잘못된 인자 또는 명령어가 없을 때
        """
        parsed_args = self.parser.parse_args(args)

        # 명령어가 지정되지 않은 경우 도움말 출력
        if not parsed_args.command:
            self.parser.print_help()
            sys.exit(1)

        return parsed_args

    def execute(self, args: Optional[List[str]] = None) -> int:
        """
        CLI 명령어 실행

        Args:
            args: 명령줄 인자 리스트 (None이면 sys.argv 사용)

        Returns:
            int: 종료 코드 (0: 성공, 1: 실패, 2: 인자 오류)
        """
        try:
            parsed_args = self.parse_args(args)
            # 명령어별 핸들러 호출
            if parsed_args.command == "analyze":
                return self._handle_analyze(parsed_args)
            elif parsed_args.command == "list":
                return self._handle_list(parsed_args)
            elif parsed_args.command == "modify":
                return self._handle_modify(parsed_args)
            else:
                print(f"알 수 없는 명령어: {parsed_args.command}", file=sys.stderr)
                return 1

        except SystemExit as e:
            # argparse가 발생시킨 SystemExit
            return e.code if e.code is not None else 2
        except KeyboardInterrupt:
            print("사용자에 의해 중단되었습니다", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"명령어 실행 중 오류 발생: {e}", file=sys.stderr)
            return 1

    def _handle_analyze(self, args: argparse.Namespace) -> int:
        """analyze 명령어 핸들러"""
        return self.app_controller.analyze(config_path=args.config)

    def _handle_list(self, args: argparse.Namespace) -> int:
        """list 명령어 핸들러"""
        # 옵션 검증
        has_option = (
            args.all or args.db or args.modified or args.endpoint or args.callgraph
        )
        if not has_option:
            print(
                "오류: list 명령어에는 하나 이상의 옵션(--all, --db, --modified, --endpoint, --callgraph)이 필요합니다.",
                file=sys.stderr,
            )
            print("도움말을 보려면: applycrypto list --help", file=sys.stderr)
            return 1

        return self.app_controller.list_info(
            config_path=args.config,
            show_all=args.all,
            show_db=args.db,
            show_modified=args.modified,
            show_endpoint=args.endpoint,
            callgraph_endpoint=args.callgraph,
        )

    def _handle_modify(self, args: argparse.Namespace) -> int:
        """modify 명령어 핸들러"""
        return self.app_controller.modify(
            config_path=args.config, dry_run=args.dry_run, force_all=args.all
        )
