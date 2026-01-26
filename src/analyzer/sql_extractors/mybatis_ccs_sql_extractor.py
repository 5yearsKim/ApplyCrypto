"""
MyBatis CCS SQL Extractor

AnyframeCCS 프레임워크의 MyBatis XML Mapper 파일에서 SQL을 추출하는 구현 클래스입니다.
기존 MyBatisSQLExtractor를 상속받아 XML 파일 필터 패턴만 변경합니다.

특징:
    - XML 파일 패턴: *DQM.xml (기존 MyBatis: *mapper.xml)
    - XML 파일 경로: resources/.../dqm/ 디렉토리
    - 레이어명: DQM (기존 MyBatis: Repository/Mapper)
"""

import logging
from typing import List, override

from models.source_file import SourceFile

from .mybatis_sql_extractor import MyBatisSQLExtractor


class MybatisCCSSQLExtractor(MyBatisSQLExtractor):
    """
    MyBatis CCS SQL Extractor 구현 클래스

    AnyframeCCS 프레임워크의 MyBatis XML Mapper 파일에서 SQL을 추출합니다.
    기존 MyBatisSQLExtractor와 동일한 파싱 로직을 사용하지만
    XML 파일 필터 패턴이 *DQM.xml로 변경됩니다.
    """

    def __init__(self, *args, **kwargs):
        """MybatisCCSSQLExtractor 초기화"""
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(__name__)

    @override
    def filter_sql_files(self, source_files: List[SourceFile]) -> List[SourceFile]:
        """
        MyBatis CCS 관련 파일 필터링 (*DQM.xml)

        AnyframeCCS에서는 *DQM.xml 형식의 XML 파일을 사용합니다.
        예: MRPesnMngDQM.xml, UserDQM.xml 등

        Args:
            source_files: 소스 파일 목록

        Returns:
            List[SourceFile]: 필터링된 파일 목록
        """
        filtered = []
        for f in source_files:
            name_upper = f.filename.upper()
            # Filter for *DQM.xml (case-insensitive)
            if f.extension == ".xml" and name_upper.endswith("DQM.XML"):
                filtered.append(f)
                self.logger.debug(f"CCS XML 파일 포함: {f.filename}")

        self.logger.info(f"MyBatis CCS XML 파일 필터링 완료: {len(filtered)}개 파일")
        return filtered

    def get_layer_name(self) -> str:
        """
        CCS 프레임워크에서의 레이어명 반환 (소문자로 통일)

        db_access_analyzer에서 .lower()를 적용하므로 일관성을 위해 소문자 사용

        Returns:
            str: 레이어명 ("dqm")
        """
        return "dqm"
