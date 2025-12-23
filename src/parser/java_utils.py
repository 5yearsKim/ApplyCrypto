"""
Java 유틸리티 모듈

Java 소스 코드 처리에 필요한 유틸리티 함수들을 제공합니다.
"""


class JavaUtils:
    """
    Java 소스 코드 처리 유틸리티 클래스
    """

    @staticmethod
    def remove_java_comments(source_code: str) -> str:
        """
        Java 소스 코드에서 주석을 제거합니다.

        줄 단위 주석(//)과 블록 주석(/* ... */)을 제거하며,
        문자열 리터럴 내부의 주석은 보존합니다.

        Args:
            source_code: 원본 소스 코드

        Returns:
            str: 주석이 제거된 소스 코드

        Examples:
            >>> code = '''
            ... // 한 줄 주석
            ... public class Test {
            ...     /* 블록 주석 */
            ...     public void method() {}
            ... }
            ... '''
            >>> JavaUtils.remove_java_comments(code)
            '\\npublic class Test {\\n    \\n    public void method() {}\\n}\\n'
        """
        result = []
        i = 0
        in_string = False
        string_char = None
        in_single_line_comment = False
        in_block_comment = False

        while i < len(source_code):
            char = source_code[i]

            # 문자열 리터럴 감지 (주석 처리하지 않음)
            if not in_single_line_comment and not in_block_comment:
                if char in ("'", '"') and (i == 0 or source_code[i - 1] != "\\"):
                    if not in_string:
                        in_string = True
                        string_char = char
                    elif char == string_char:
                        in_string = False
                        string_char = None

            # 문자열 내부가 아니면 주석 처리
            if not in_string:
                # 블록 주석 시작 (/*)
                if i < len(source_code) - 1 and source_code[i : i + 2] == "/*":
                    in_block_comment = True
                    i += 2
                    continue

                # 블록 주석 끝 (*/)
                if in_block_comment and i < len(source_code) - 1 and source_code[i : i + 2] == "*/":
                    in_block_comment = False
                    i += 2
                    continue

                # 한 줄 주석 시작 (//)
                if not in_block_comment and i < len(source_code) - 1 and source_code[i : i + 2] == "//":
                    in_single_line_comment = True
                    i += 2
                    continue

                # 줄바꿈 시 한 줄 주석 종료
                if in_single_line_comment and char == "\n":
                    in_single_line_comment = False
                    result.append(char)  # 줄바꿈은 유지
                    i += 1
                    continue

            # 주석이 아닌 경우에만 문자 추가
            if not in_single_line_comment and not in_block_comment:
                result.append(char)

            i += 1

        return "".join(result)

