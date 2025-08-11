import logging
import pandas as pd
import numpy as np
import chardet
import requests
from spaceone.core.connector import BaseConnector
from typing import List

from plugin.error import *

__all__ = ["HTTPFileConnector"]

_LOGGER = logging.getLogger(__name__)

# 페이지당 처리할 데이터 개수
_PAGE_SIZE = 1000


class HTTPFileConnector(BaseConnector):
    """HTTP 파일 연결 클래스
    
    HTTP URL을 통해 CSV 파일을 다운로드하고 비용 데이터를 수집하는 역할을 담당합니다.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 기본 URL 설정
        self.base_url = None
        # 필드 매핑 설정
        self.field_mapper = None
        # 기본 변수 설정
        self.default_vars = None

    def create_session(
        self, options: dict, secret_data: dict, schema: str = None
    ) -> None:
        """HTTP 파일 연결 세션을 생성
        
        Args:
            options (dict): 연결 옵션 (base_url, field_mapper, default_vars 등)
            secret_data (dict): 인증 정보
            schema (str): 스키마 정보
        """
        self._check_options(options)
        self.base_url = options["base_url"]

        # 필드 매핑 설정이 있는 경우 저장
        if "field_mapper" in options:
            self.field_mapper = options["field_mapper"]

        # 기본 변수 설정이 있는 경우 저장
        if "default_vars" in options:
            self.default_vars = options["default_vars"]

    def get_cost_data(self, base_url):
        """HTTP URL에서 비용 데이터를 수집
        
        Args:
            base_url (str): CSV 파일의 HTTP URL
            
        Yields:
            list: 비용 데이터 리스트 (페이지 단위로 반환)
        """
        _LOGGER.debug(f"[get_cost_data] base url: {base_url}")

        # CSV 파일에서 데이터 수집
        costs_data = self._get_csv(base_url)

        _LOGGER.debug(f"[get_cost_data] costs count: {len(costs_data)}")

        # 페이지 단위로 데이터 분할하여 반환
        page_count = int(len(costs_data) / _PAGE_SIZE) + 1

        for page_num in range(page_count):
            offset = _PAGE_SIZE * page_num
            yield costs_data[offset : offset + _PAGE_SIZE]

    @staticmethod
    def _check_options(options: dict) -> None:
        """옵션의 필수 필드를 확인
        
        Args:
            options (dict): 확인할 옵션
            
        Raises:
            ERROR_REQUIRED_PARAMETER: base_url이 없는 경우
        """
        if "base_url" not in options:
            raise ERROR_REQUIRED_PARAMETER(key="options.base_url")

    def _get_csv(self, base_url: str) -> List[dict]:
        """HTTP URL에서 CSV 파일을 다운로드하고 파싱
        
        Args:
            base_url (str): CSV 파일의 HTTP URL
            
        Returns:
            List[dict]: 파싱된 CSV 데이터 리스트
            
        Raises:
            Exception: CSV 다운로드 또는 파싱에 실패한 경우
        """
        try:
            # CSV 파일의 인코딩 형식 탐지
            csv_format = self._search_csv_format(base_url)
            
            # pandas를 사용하여 CSV 파일 읽기
            df = pd.read_csv(
                base_url,
                header=0,
                sep=",",
                engine="python",
                encoding=csv_format,
                dtype=str,
            )
            # NaN 값을 None으로 변환
            df = df.replace({np.nan: None})

            # DataFrame을 딕셔너리 리스트로 변환
            costs_data = df.to_dict("records")
            return costs_data

        except Exception as e:
            _LOGGER.error(f"[_get_csv] download error: {e}", exc_info=True)
            raise e

    @staticmethod
    def _search_csv_format(base_url: str) -> str:
        """CSV 파일의 인코딩 형식을 탐지
        
        Args:
            base_url (str): CSV 파일의 HTTP URL
            
        Returns:
            str: 탐지된 인코딩 형식
            
        Raises:
            Exception: 파일 다운로드에 실패한 경우
        """
        try:
            # HTTP 요청을 통해 파일 내용 가져오기
            response = requests.get(base_url)
            # chardet를 사용하여 인코딩 형식 탐지
            response.encoding = chardet.detect(response.content)["encoding"]
            _LOGGER.debug(f"[_search_csv_format] encoding: {response.encoding}")
            return response.encoding

        except Exception as e:
            _LOGGER.error(f"[_search_csv_format] download error: {e}", exc_info=True)
            raise e
