import os
import logging
import pandas as pd
import numpy as np
import tempfile
from typing import List
import google.oauth2.service_account
from google.cloud import storage
from plugin.error import *
from spaceone.core.connector import BaseConnector

# 페이지당 처리할 데이터 개수
_PAGE_SIZE = 1000

_LOGGER = logging.getLogger("spaceone")


class GoogleStorageConnector(BaseConnector):
    """Google Cloud Storage 연결 클래스
    
    Google Cloud Storage의 버킷에서 CSV 파일을 다운로드하고 비용 데이터를 수집하는 역할을 담당합니다.
    """
    
    google_client_service = "storage"
    version = "v1"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 시크릿 데이터에서 프로젝트 ID 추출
        self.secret_data = kwargs.get("secret_data")
        self.project_id = self.secret_data.get("project_id")
        
        # private_key 형식 정리 및 검증
        if "private_key" in self.secret_data:
            private_key = self.secret_data["private_key"]
            private_key = private_key.replace('\\n', '\n')
            private_key = private_key.replace('\\\\n', '\n')
            if not private_key.startswith('-----BEGIN PRIVATE KEY-----'):
                _LOGGER.error(f"[GoogleStorageConnector] Invalid private key format")
                raise ValueError("Invalid private key format")
            self.secret_data["private_key"] = private_key
        
        try:
            # Google Cloud Service Account 인증 정보 생성
            self.credentials = (
                google.oauth2.service_account.Credentials.from_service_account_info(
                    self.secret_data
                )
            )
            # Google Cloud Storage 클라이언트 초기화
            self.client = storage.Client(
                project=self.secret_data["project_id"], credentials=self.credentials
            )
        except Exception as e:
            _LOGGER.error(f"[GoogleStorageConnector] Failed to initialize credentials: {e}")
            raise e

    def get_cost_data(self, bucket_name: str):
        """Google Cloud Storage 버킷에서 비용 데이터를 수집
        
        Args:
            bucket_name (str): Google Cloud Storage 버킷 이름
            
        Yields:
            list: 비용 데이터 리스트 (페이지 단위로 반환)
        """
        # 버킷 객체 가져오기
        bucket = self.client.get_bucket(bucket_name)
        # 버킷 내 모든 blob(파일) 목록 가져오기
        blob_names = [blob.name for blob in bucket.list_blobs()]
        
        _LOGGER.debug(f"[get_cost_data] Found blobs: {blob_names}")

        # 각 blob(파일)을 순회하며 처리
        for blob_name in blob_names:
            blob = bucket.get_blob(blob_name)

            if blob:
                # 디렉토리이거나 빈 파일인 경우 건너뛰기
                if blob_name.endswith('/') or blob.size == 0:
                    _LOGGER.debug(f"[get_cost_data] Skipping directory or empty file: {blob_name}")
                    continue
                
                # CSV 파일이 아닌 경우 건너뛰기
                if not blob_name.lower().endswith('.csv'):
                    _LOGGER.debug(f"[get_cost_data] Skipping non-CSV file: {blob_name}")
                    continue
                
                # 임시 디렉토리에 안전한 파일명으로 저장
                tmpdir = tempfile.gettempdir()
                safe_filename = os.path.basename(blob_name) if '/' in blob_name else blob_name
                csv_file_path = os.path.join(tmpdir, safe_filename)
                
                _LOGGER.debug(f"[get_cost_data] blob_name: {blob_name}, safe_filename: {safe_filename}, csv_file_path: {csv_file_path}")
                
                try:
                    # blob을 로컬 파일로 다운로드
                    blob.download_to_filename(csv_file_path)
                except Exception as e:
                    _LOGGER.error(f"[get_cost_data] Failed to download {blob_name}: {e}")
                    continue
                    
                try:
                    # CSV 파일에서 비용 데이터 파싱
                    costs_data = self._get_csv(csv_file_path)
                    _LOGGER.debug(
                        f"[get_cost_data] costs count of {blob_name} : {len(costs_data)}"
                    )
                except Exception as e:
                    _LOGGER.error(f"[get_cost_data] Failed to process CSV {blob_name}: {e}")
                    continue

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
            ERROR_REQUIRED_PARAMETER: bucket_name이 없는 경우
        """
        if "bucket_name" not in options:
            raise ERROR_REQUIRED_PARAMETER(key="options.bucket_name")

    @staticmethod
    def _get_csv(csv_file: str) -> List[dict]:
        """로컬 CSV 파일을 파싱하여 비용 데이터 추출
        
        Args:
            csv_file (str): 파싱할 CSV 파일 경로
            
        Returns:
            List[dict]: 파싱된 CSV 데이터 리스트
            
        Raises:
            FileNotFoundError: 파일이 존재하지 않는 경우
            Exception: CSV 파싱에 실패한 경우
        """
        try:
            # 파일 존재 여부 확인
            if not os.path.exists(csv_file):
                _LOGGER.error(f"[_get_csv] File does not exist: {csv_file}")
                raise FileNotFoundError(f"File not found: {csv_file}")
            
            _LOGGER.debug(f"[_get_csv] Reading CSV file: {csv_file}")
            
            # pandas를 사용하여 CSV 파일 읽기 (UTF-8 BOM 인코딩 지원)
            df = pd.read_csv(csv_file, encoding="utf-8-sig")
            # NaN 값을 None으로 변환
            df = df.replace({np.nan: None})

            # DataFrame을 딕셔너리 리스트로 변환
            costs_data = df.to_dict("records")
            return costs_data

        except Exception as e:
            _LOGGER.error(f"[_get_csv] download error: {e}", exc_info=True)
            raise e
