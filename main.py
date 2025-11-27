"""
ApplyCrypto CLI 진입점

프로젝트 루트에서 실행:
  python main.py [command] [options]

또는 설치 후:
  applycrypto [command] [options]
"""

import sys
from pathlib import Path
from dotenv import load_dotenv

from src.cli.cli_controller import CLIController


# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def main():
    load_dotenv(".env")

    """CLI 메인 함수"""
    controller = CLIController()
    exit_code = controller.execute()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

