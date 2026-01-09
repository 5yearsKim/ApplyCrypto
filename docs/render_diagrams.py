#!/usr/bin/env python3
"""
PlantUML 다이어그램을 이미지로 렌더링하는 스크립트
로컬 PlantUML JAR를 사용하여 렌더링합니다.
"""

import subprocess
import sys
from pathlib import Path


def render_diagram(puml_file: Path, output_format: str = "png"):
    """
    PlantUML 파일을 이미지로 렌더링 (로컬 JAR 사용)

    Args:
        puml_file: PlantUML 파일 경로
        output_format: 출력 형식 (png, svg 등)
    """
    try:
        # 출력 파일 경로
        output_file = puml_file.with_suffix(f".{output_format}")

        print(f"렌더링 중: {puml_file.name} -> {output_file.name}")

        # PlantUML JAR 파일 경로
        script_dir = Path(__file__).parent
        plantuml_jar = script_dir / "plantuml.jar"

        if not plantuml_jar.exists():
            print(f"[ERROR] PlantUML JAR 파일을 찾을 수 없습니다: {plantuml_jar}")
            print("       PlantUML JAR를 다운로드하거나 경로를 확인하세요.")
            return False

        # Java 명령어 실행
        import os
        env = os.environ.copy()
        env["PLANTUML_LIMIT_SIZE"] = "8192"  # 이미지 크기 제한 증가
        
        cmd = [
            "java",
            "-jar",
            str(plantuml_jar),
            f"-t{output_format}",
            "-charset",
            "UTF-8",
            str(puml_file),
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(puml_file.parent),
            env=env,
        )

        if result.returncode != 0:
            print(f"[ERROR] PlantUML 렌더링 실패:")
            print(result.stderr)
            return False

        # 출력 파일 확인
        if not output_file.exists():
            print(f"[ERROR] 출력 파일이 생성되지 않았습니다: {output_file}")
            return False

        # 파일 크기 확인
        file_size = output_file.stat().st_size
        if file_size == 0:
            print(f"[ERROR] 생성된 파일이 비어있습니다: {output_file}")
            return False

        print(f"[OK] 완료: {output_file.name} ({file_size:,} bytes)")
        return True

    except FileNotFoundError:
        print("[ERROR] Java를 찾을 수 없습니다. Java가 설치되어 있는지 확인하세요.")
        return False
    except Exception as e:
        print(f"[ERROR] 오류 발생: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """메인 함수"""
    # 스크립트가 있는 디렉터리
    script_dir = Path(__file__).parent

    # PlantUML 파일 목록
    puml_files = [
        script_dir / "component_diagram.puml",
        script_dir / "class_diagram.puml",
        script_dir / "modifier_component_diagram.puml",
    ]

    print("PlantUML 다이어그램 렌더링 시작...\n")

    success_count = 0
    for puml_file in puml_files:
        if puml_file.exists():
            if render_diagram(puml_file, "png"):
                success_count += 1
        else:
            print(f"[SKIP] 파일을 찾을 수 없습니다: {puml_file.name}")

    print(f"\n완료: {success_count}/{len(puml_files)}개 파일 렌더링 성공")


if __name__ == "__main__":
    main()
