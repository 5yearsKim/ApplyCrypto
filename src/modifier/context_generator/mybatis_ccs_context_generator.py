"""
MybatisCCS Context Generator

AnyframeCCS 프레임워크용 Context Generator입니다.
MybatisContextGenerator를 상속하여 CCS 레이어명(CTL, SVCImpl, DQM)을 처리합니다.
"""

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

from modifier.context_generator.mybatis_context_generator import MybatisContextGenerator
from models.modification_context import ModificationContext
from parser.java_ast_parser import JavaASTParser

logger = logging.getLogger("applycrypto.context_generator")


class MybatisCCSContextGenerator(MybatisContextGenerator):
    """
    AnyframeCCS 프레임워크용 Context Generator

    MybatisContextGenerator를 상속하여 CCS 레이어명을 표준 레이어명으로 매핑합니다.

    CCS 레이어명 매핑:
        - ctl -> controller
        - svc -> service
        - svcimpl -> service
        - biz -> service (Business Component)
        - dqm -> repository
        - dvo -> repository (Data Value Object)

    수정 대상 (file_paths):
        - CTL, SVCImpl, BIZ

    참조용 context (context_files):
        - DVO: layer_files에서 직접 수집
        - DQM: layer_files에서 직접 수집
        - svcutil: import 경로에서 추론
    """

    # CCS 레이어명 -> 표준 레이어명 매핑
    LAYER_NAME_MAPPING = {
        "ctl": "controller",
        "svc": "service",
        "svcimpl": "service",
        "biz": "service",
        "dqm": "repository",
        "dvo": "repository",
    }

    # 구현체 접미사 목록 (인터페이스 import 시 구현체 매칭용)
    IMPL_SUFFIXES = ["Impl", "IMPL", "impl"]

    # context_files에 포함할 추가 패턴 (import 경로에서 매칭)
    CONTEXT_INCLUDE_PATTERNS = ["svcutil"]

    def _match_import_to_file_path(
        self, import_statement: str, target_files: List[str]
    ) -> Optional[str]:
        """
        import 문과 일치하는 파일 경로를 찾습니다.

        CCS 특화 로직:
            - I 접두사 제거 후 Impl 접미사 파일 우선 매칭
              (예: ICRActPnstaSVC → CRActPnstaSVCImpl.java)
            - Impl 파일이 없으면 정확히 일치하는 파일 찾기

        Args:
            import_statement: import 문 (예: "com.example.svc.IUserSVC")
            target_files: 대상 파일 목록

        Returns:
            Optional[str]: 일치하는 파일 경로, 없으면 None
        """
        class_name = import_statement.split(".")[-1]

        # I 접두사 제거 (예: ICRActPnstaSVC → CRActPnstaSVC)
        class_name_without_prefix = class_name
        if (
            class_name.startswith("I")
            and len(class_name) > 1
            and class_name[1].isupper()
        ):
            class_name_without_prefix = class_name[1:]

        # 1차: I 접두사 제거 + Impl 접미사로 매칭
        for suffix in self.IMPL_SUFFIXES:
            impl_class_name = class_name_without_prefix + suffix
            for file_path in target_files:
                file_stem = os.path.splitext(os.path.basename(file_path))[0]
                if file_stem == impl_class_name:
                    logger.debug(f"CCS Impl 매칭: {class_name} -> {file_stem}")
                    return file_path

        # 2차: 원본 클래스명 + Impl 접미사로 매칭
        if class_name != class_name_without_prefix:
            for suffix in self.IMPL_SUFFIXES:
                impl_class_name = class_name + suffix
                for file_path in target_files:
                    file_stem = os.path.splitext(os.path.basename(file_path))[0]
                    if file_stem == impl_class_name:
                        return file_path

        # 3차: 정확히 일치하는 파일 찾기
        for file_path in target_files:
            file_stem = os.path.splitext(os.path.basename(file_path))[0]
            if file_stem == class_name or file_stem == class_name_without_prefix:
                return file_path

        return None

    def _collect_service_chain(
        self,
        initial_imports: set,
        service_files: List[str],
        java_parser: JavaASTParser,
    ) -> List[str]:
        """
        BFS 방식으로 Service 호출 체인을 탐색합니다.

        CTL → SVC1 → SVC2 → BIZ 같은 다단계 호출 체인을 추적합니다.

        Args:
            initial_imports: 시작점의 import 목록
            service_files: service 파일 목록 (SVCImpl + BIZ)
            java_parser: JavaASTParser 인스턴스

        Returns:
            List[str]: 수집된 service 파일 경로
        """
        collected: List[str] = []
        visited: set = set()
        queue: List[str] = []

        # 초기 import에서 service 파일 매칭
        for import_stmt in initial_imports:
            matched = self._match_import_to_file_path(import_stmt, service_files)
            if matched and matched not in visited:
                queue.append(matched)
                visited.add(matched)
                collected.append(matched)

        # BFS로 호출 체인 탐색
        while queue:
            current_file = queue.pop(0)
            try:
                current_path = Path(current_file)
                tree, error = java_parser.parse_file(current_path)
                if error:
                    continue

                classes = java_parser.extract_class_info(tree, current_path)
                if not classes:
                    continue

                target_class = next(
                    (c for c in classes if c.access_modifier == "public"),
                    classes[0],
                )

                for import_stmt in target_class.imports:
                    matched = self._match_import_to_file_path(
                        import_stmt, service_files
                    )
                    if matched and matched not in visited:
                        queue.append(matched)
                        visited.add(matched)
                        collected.append(matched)
                        logger.debug(f"Service 체인: {current_file} -> {matched}")

            except Exception as e:
                logger.warning(f"Service 체인 탐색 실패: {current_file} - {e}")

        return collected

    def _infer_source_root(self, file_paths: List[str]) -> Optional[str]:
        """
        파일 경로에서 source_root를 추론합니다.

        Args:
            file_paths: 파일 경로 목록

        Returns:
            Optional[str]: 추론된 source_root
        """
        patterns = [
            os.sep + "src" + os.sep + "main" + os.sep + "java" + os.sep,
            os.sep + "src" + os.sep + "java" + os.sep,
            os.sep + "src" + os.sep,
        ]

        for file_path in file_paths:
            for pattern in patterns:
                if pattern in file_path:
                    idx = file_path.find(pattern)
                    return file_path[: idx + len(pattern) - 1]

        # 패키지 시작점에서 추론
        if file_paths:
            for pkg in ["sli", "com", "org", "kr"]:
                pkg_pattern = os.sep + pkg + os.sep
                if pkg_pattern in file_paths[0]:
                    return file_paths[0][: file_paths[0].find(pkg_pattern)]

        return None

    def _resolve_import_to_file(
        self, import_statement: str, source_root: str
    ) -> Optional[str]:
        """import 문을 파일 경로로 변환합니다."""
        relative_path = import_statement.replace(".", os.sep) + ".java"
        full_path = os.path.join(source_root, relative_path)
        return full_path if os.path.exists(full_path) else None

    def _collect_svcutil_files(self, all_imports: set, source_root: str) -> List[str]:
        """
        import에서 svcutil 패턴을 찾아 파일 경로로 변환합니다.

        Args:
            all_imports: 모든 import 문
            source_root: 소스 루트 경로

        Returns:
            List[str]: svcutil 파일 경로 목록
        """
        svcutil_files: List[str] = []

        for import_stmt in all_imports:
            import_lower = import_stmt.lower()
            for pattern in self.CONTEXT_INCLUDE_PATTERNS:
                if f".{pattern}." in import_lower:
                    file_path = self._resolve_import_to_file(import_stmt, source_root)
                    if file_path and file_path not in svcutil_files:
                        logger.debug(f"svcutil 수집: {import_stmt} -> {file_path}")
                        svcutil_files.append(file_path)
                    break

        return svcutil_files

    def _normalize_layer_files(
        self, layer_files: Dict[str, List[str]]
    ) -> Dict[str, List[str]]:
        """CCS 레이어명을 표준 레이어명으로 변환합니다."""
        normalized: Dict[str, List[str]] = {}

        for layer_name, files in layer_files.items():
            normalized_name = self.LAYER_NAME_MAPPING.get(
                layer_name.lower(), layer_name.lower()
            )
            if normalized_name not in normalized:
                normalized[normalized_name] = []
            for f in files:
                if f not in normalized[normalized_name]:
                    normalized[normalized_name].append(f)

        logger.debug(
            f"레이어 정규화: {list(layer_files.keys())} -> {list(normalized.keys())}"
        )
        return normalized

    def generate(
        self,
        layer_files: Dict[str, List[str]],
        table_name: str,
        columns: List[Dict],
    ) -> List[ModificationContext]:
        """
        AnyframeCCS용 context 생성

        수정 대상 (file_paths): CTL, SVCImpl, BIZ
        참조용 context (context_files): DVO, DQM, svcutil

        Args:
            layer_files: CCS 레이어명으로 키가 설정된 파일 목록
            table_name: 테이블명
            columns: 컬럼 목록

        Returns:
            List[ModificationContext]: 생성된 context 목록
        """
        normalized = self._normalize_layer_files(layer_files)

        logger.info(
            f"MybatisCCSContextGenerator: 레이어 정규화 완료 "
            f"({list(layer_files.keys())} -> {list(normalized.keys())})"
        )

        all_batches: List[ModificationContext] = []

        controller_files = normalized.get("controller", [])
        service_files = normalized.get("service", [])
        repository_files = normalized.get("repository", [])

        # DVO 파일 분리 (context용)
        dvo_files = [f for f in repository_files if f.lower().endswith("vo.java")]

        if not controller_files:
            logger.info("Controller Layer 파일이 없습니다.")
            return all_batches

        java_parser = JavaASTParser()

        # Service의 모든 import 사전 수집
        all_service_imports: set = set()
        for svc_file in service_files:
            try:
                svc_path = Path(svc_file)
                tree, error = java_parser.parse_file(svc_path)
                if error:
                    continue

                classes = java_parser.extract_class_info(tree, svc_path)
                if classes:
                    target_class = next(
                        (c for c in classes if c.access_modifier == "public"),
                        classes[0],
                    )
                    all_service_imports.update(target_class.imports)
            except Exception as e:
                logger.warning(f"Service import 수집 실패: {svc_file} - {e}")

        file_groups: Dict[str, List[str]] = {}
        context_groups: Dict[str, List[str]] = {}

        # Controller별 파일 그룹 생성
        for ctl_file in controller_files:
            ctl_path = Path(ctl_file)
            ctl_key = ctl_path.stem
            file_paths: List[str] = [ctl_file]
            context_files: List[str] = []

            try:
                tree, error = java_parser.parse_file(ctl_path)
                if error:
                    file_groups[ctl_key] = file_paths
                    continue

                classes = java_parser.extract_class_info(tree, ctl_path)
                if not classes:
                    file_groups[ctl_key] = file_paths
                    continue

                ctl_class = next(
                    (c for c in classes if c.access_modifier == "public"),
                    classes[0],
                )
                ctl_imports = set(ctl_class.imports)

                # Service 체인 수집 (CTL → SVCImpl → BIZ)
                collected_services = self._collect_service_chain(
                    ctl_imports, service_files, java_parser
                )
                for svc in collected_services:
                    if svc not in file_paths:
                        file_paths.append(svc)

                # Context 파일 수집 (DVO만 포함, DQM/svcutil은 프롬프트 길이 문제로 제외)
                all_imports = ctl_imports | all_service_imports

                # DVO 파일만 포함
                MAX_DVO_FILES = 3
                for imp in all_imports:
                    if len(context_files) >= MAX_DVO_FILES:
                        break
                    matched = self._match_import_to_file_path(imp, dvo_files)
                    if matched and matched not in context_files:
                        context_files.append(matched)

            except Exception as e:
                logger.warning(f"Controller 처리 실패: {ctl_file} - {e}")
                file_groups[ctl_key] = file_paths
                continue

            file_groups[ctl_key] = file_paths
            context_groups[ctl_key] = context_files

        # Batch 생성
        for ctl_key, file_paths in file_groups.items():
            if not file_paths:
                continue

            ctx_files = context_groups.get(ctl_key, [])

            logger.info(
                f"Controller '{ctl_key}': "
                f"{len(file_paths)}개 수정 대상, "
                f"{len(ctx_files)}개 context (DVO)"
            )

            batches = self.create_batches(
                file_paths=file_paths,
                table_name=table_name,
                columns=columns,
                layer="",
                context_files=ctx_files,
            )
            all_batches.extend(batches)

        return all_batches
