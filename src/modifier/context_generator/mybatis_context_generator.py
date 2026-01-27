import logging
import os
from typing import List, Dict, Optional
from pathlib import Path

from modifier.context_generator.base_context_generator import BaseContextGenerator
from models.modification_context import ModificationContext
from parser.java_ast_parser import JavaASTParser

logger = logging.getLogger("applycrypto.context_generator")


class MybatisContextGenerator(BaseContextGenerator):
    """
    Mybatis Context Generator

    Groups files based on import relationships between Controller and Service layers.
    """

    # VO 파일 최대 토큰 예산 (80k = 128k 모델의 ~62%, 출력용 48k 여유)
    MAX_VO_TOKENS = 80000

    def _calculate_token_size(self, text: str) -> int:
        """
        텍스트의 토큰 크기를 계산합니다.

        tiktoken 라이브러리가 있으면 정확히 계산하고,
        없으면 문자 4개당 1토큰으로 근사합니다.

        Args:
            text: 토큰 크기를 계산할 텍스트

        Returns:
            int: 추정 토큰 수
        """
        try:
            import tiktoken

            encoder = tiktoken.encoding_for_model("gpt-4")
            return len(encoder.encode(text))
        except Exception:
            # tiktoken 없으면 근사값 사용 (4문자 = 1토큰)
            return len(text) // 4

    def _select_vo_files_by_token_budget(
        self,
        vo_files: List[str],
        all_imports: set,
        max_tokens: int,
    ) -> List[str]:
        """
        토큰 예산 내에서 VO 파일을 선택합니다.

        import 문 순서대로 VO 파일을 매칭하고, 토큰 예산을 초과하면 중단합니다.

        Args:
            vo_files: 전체 VO 파일 목록
            all_imports: Controller + Service의 모든 import 문
            max_tokens: 최대 토큰 예산 (기본 80k)

        Returns:
            List[str]: 선택된 VO 파일 경로 목록
        """
        selected_files: List[str] = []
        current_tokens = 0

        for imp in all_imports:
            matched = self._match_import_to_file_path(imp, vo_files)
            if matched and matched not in selected_files:
                try:
                    with open(matched, "r", encoding="utf-8") as f:
                        content = f.read()
                    file_tokens = self._calculate_token_size(content)

                    if current_tokens + file_tokens <= max_tokens:
                        selected_files.append(matched)
                        current_tokens += file_tokens
                        logger.debug(
                            f"VO 선택: {Path(matched).name} "
                            f"({file_tokens:,} tokens, 누적: {current_tokens:,})"
                        )
                    else:
                        logger.info(
                            f"VO 토큰 예산 초과로 제외: {Path(matched).name} "
                            f"({file_tokens:,} tokens, 현재 누적: {current_tokens:,})"
                        )
                except Exception as e:
                    logger.warning(f"VO 파일 읽기 실패: {matched} - {e}")

        logger.info(
            f"VO 파일 선택 완료: {len(selected_files)}개, "
            f"총 {current_tokens:,} tokens (예산: {max_tokens:,})"
        )
        return selected_files

    def _match_import_to_file_path(
        self, import_statement: str, target_files: List[str]
    ) -> Optional[str]:
        """
        import 문과 일치하는 파일 경로를 찾습니다.

        Args:
            import_statement: import 문 (예: "com.example.service.UserService")
            target_files: 대상 파일 목록

        Returns:
            Optional[str]: 일치하는 파일 경로, 없으면 None
        """
        # import 문에서 클래스명 추출 (마지막 부분)
        class_name = import_statement.split(".")[-1]

        # 대상 파일 중에서 클래스명과 일치하는 파일 찾기
        for file_path in target_files:
            file_name = os.path.basename(file_path)
            # 확장자 제거
            file_stem = os.path.splitext(file_name)[0]
            if file_stem == class_name:
                return file_path

        return None

    def generate(
        self,
        layer_files: Dict[str, List[str]],
        table_name: str,
        columns: List[Dict],
    ) -> List[ModificationContext]:
        """
        Generates modification contexts based on import relationships between Controller, Service, and Repository layers.

        Args:
            layer_files: Dictionary of layer names and file paths.
            table_name: Table name.
            columns: List of columns.

        Returns:
            List[ModificationContext]: The generated batches of contexts.
        """
        all_batches: List[ModificationContext] = []

        # Controller Layer와 Service Layer, Repository Layer 파일 목록 가져오기
        controller_files = layer_files.get("controller", [])
        service_files = layer_files.get("service", [])
        repository_files = layer_files.get("repository", [])
        repository_files = [
            x for x in repository_files if x.lower().endswith("vo.java")
        ]

        if not controller_files:
            logger.info("Controller Layer 파일이 없습니다.")
            return all_batches

        # JavaASTParser 인스턴스 생성
        java_parser = JavaASTParser()

        # Controller별 파일 묶음을 저장할 딕셔너리
        # key: controller 파일 이름(stem), value: 관련 파일 경로 리스트
        file_groups: Dict[str, List[str]] = {}
        # Controller별 VO 파일 (context용, 수정 대상 아님)
        context_file_groups: Dict[str, List[str]] = {}

        # 1단계: Controller 파일별로 파일 묶음 생성
        for controller_file in controller_files:
            file_path = Path(controller_file)
            controller_key = file_path.stem
            file_group_paths: List[str] = [
                controller_file
            ]  # 최소한 controller 파일은 포함
            vo_group_paths: List[str] = []  # VO 파일은 별도로 관리 (context용)

            # 2. JavaASTParser를 사용하여 class 정보를 가져오고,
            # 그 중에서 public class의 class 이름을 가져온다
            try:
                # 파일 파싱
                tree, error = java_parser.parse_file(file_path)
                if error:
                    logger.debug(
                        f"Controller 파일 파싱 실패: {controller_file} - {error}"
                    )
                    # 파싱 실패해도 controller 파일만 포함된 그룹으로 저장
                    file_groups[controller_key] = file_group_paths
                    context_file_groups[controller_key] = []
                    continue

                # 클래스 정보 추출
                classes = java_parser.extract_class_info(tree, file_path)

                if not classes:
                    logger.debug(
                        f"Controller 파일에서 클래스 정보를 찾을 수 없습니다: {controller_file}"
                    )
                    # 클래스 정보가 없어도 controller 파일만 포함된 그룹으로 저장
                    file_groups[controller_key] = file_group_paths
                    context_file_groups[controller_key] = []
                    continue

                # public class 찾기
                controller_class = None
                for cls in classes:
                    if cls.access_modifier == "public":
                        controller_class = cls
                        break

                # public class가 없으면 첫 번째 클래스 사용
                if controller_class is None:
                    controller_class = classes[0]
                    logger.debug(
                        f"Controller 파일에서 public class를 찾을 수 없어 첫 번째 클래스를 사용합니다: {controller_file}"
                    )

                # 3. class 정보에서 import 목록을 가져온다
                controller_imports = set(controller_class.imports)

                # 4. Service Layer에 수집되어 있는 파일 목록 중에서
                # Controller의 import문에 존재하는 파일만 선택해서 파일 그룹에 추가한다
                matched_service_files: List[str] = []
                for import_stmt in controller_imports:
                    matched_file = self._match_import_to_file_path(
                        import_stmt, service_files
                    )
                    if matched_file:
                        matched_service_files.append(matched_file)
                        if matched_file not in file_group_paths:
                            file_group_paths.append(matched_file)

                # 5. 실제 호출하는 Service들의 import만 수집
                # (Controller가 import한 Service 체인에서만 import 수집)
                chain_imports: set = set(controller_imports)
                for svc_file in matched_service_files:
                    try:
                        svc_path = Path(svc_file)
                        svc_tree, svc_error = java_parser.parse_file(svc_path)
                        if svc_error:
                            continue
                        svc_classes = java_parser.extract_class_info(svc_tree, svc_path)
                        if svc_classes:
                            svc_class = next(
                                (c for c in svc_classes if c.access_modifier == "public"),
                                svc_classes[0],
                            )
                            chain_imports.update(svc_class.imports)
                    except Exception as e:
                        logger.warning(f"Service import 수집 실패: {svc_file} - {e}")

                # 6. 해당 Controller-Service 체인에서 실제 사용하는 VO만 토큰 예산 내에서 선택
                vo_group_paths = self._select_vo_files_by_token_budget(
                    vo_files=repository_files,
                    all_imports=chain_imports,
                    max_tokens=self.MAX_VO_TOKENS,
                )
                logger.info(
                    f"Controller '{controller_key}': "
                    f"Service 체인 {len(matched_service_files)}개에서 "
                    f"VO {len(vo_group_paths)}개 선택"
                )

            except Exception as e:
                logger.warning(f"Controller 파일 처리 실패: {controller_file} - {e}")
                # 에러 발생해도 controller 파일만 포함된 그룹으로 저장
                file_groups[controller_key] = file_group_paths
                context_file_groups[controller_key] = []
                continue

            # 파일 그룹 저장
            file_groups[controller_key] = file_group_paths  # sorted(file_group_paths)
            context_file_groups[controller_key] = vo_group_paths

        # 2단계: 각 파일 묶음에 대해 create_batches 실행
        for controller_key, file_group_paths in file_groups.items():
            if len(file_group_paths) == 0:
                continue

            # VO 파일은 context_files로 전달
            vo_files = context_file_groups.get(controller_key, [])

            logger.info(
                f"Controller '{controller_key}'에 대한 파일 그룹 생성: {len(file_group_paths)}개 파일, {len(vo_files)}개 VO 파일 (context)"
            )

            batches = self.create_batches(
                file_paths=file_group_paths,
                table_name=table_name,
                columns=columns,
                layer="",  # 빈 문자열 기본값
                context_files=vo_files,  # VO 파일은 context로 전달
            )
            all_batches.extend(batches)

        return all_batches
