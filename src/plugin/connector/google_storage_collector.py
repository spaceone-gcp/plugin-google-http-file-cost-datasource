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

_PAGE_SIZE = 1000

_LOGGER = logging.getLogger("spaceone")


class GoogleStorageConnector(BaseConnector):
    google_client_service = "storage"
    version = "v1"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.secret_data = kwargs.get("secret_data")
        self.project_id = self.secret_data.get("project_id")
        
        # private key 정리
        if "private_key" in self.secret_data:
            private_key = self.secret_data["private_key"]
            # 여러 가지 형식 처리
            private_key = private_key.replace('\\n', '\n')
            private_key = private_key.replace('\\\\n', '\n')
            # PEM 형식 확인
            if not private_key.startswith('-----BEGIN PRIVATE KEY-----'):
                _LOGGER.error(f"[GoogleStorageConnector] Invalid private key format")
                raise ValueError("Invalid private key format")
            self.secret_data["private_key"] = private_key
        
        try:
            self.credentials = (
                google.oauth2.service_account.Credentials.from_service_account_info(
                    self.secret_data
                )
            )
            self.client = storage.Client(
                project=self.secret_data["project_id"], credentials=self.credentials
            )
        except Exception as e:
            _LOGGER.error(f"[GoogleStorageConnector] Failed to initialize credentials: {e}")
            raise e

    def get_cost_data(self, bucket_name: str):

        bucket = self.client.get_bucket(bucket_name)
        blob_names = [blob.name for blob in bucket.list_blobs()]
        
        _LOGGER.debug(f"[get_cost_data] Found blobs: {blob_names}")

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
                
                tmpdir = tempfile.gettempdir()
                # blob_name에 슬래시가 포함된 경우 파일명만 추출
                safe_filename = os.path.basename(blob_name) if '/' in blob_name else blob_name
                csv_file_path = os.path.join(tmpdir, safe_filename)
                
                _LOGGER.debug(f"[get_cost_data] blob_name: {blob_name}, safe_filename: {safe_filename}, csv_file_path: {csv_file_path}")
                
                try:
                    blob.download_to_filename(csv_file_path)
                except Exception as e:
                    _LOGGER.error(f"[get_cost_data] Failed to download {blob_name}: {e}")
                    continue
                try:
                    costs_data = self._get_csv(csv_file_path)
                    _LOGGER.debug(
                        f"[get_cost_data] costs count of {blob_name} : {len(costs_data)}"
                    )
                except Exception as e:
                    _LOGGER.error(f"[get_cost_data] Failed to process CSV {blob_name}: {e}")
                    continue

                # Paginate
                page_count = int(len(costs_data) / _PAGE_SIZE) + 1

                for page_num in range(page_count):
                    offset = _PAGE_SIZE * page_num
                    yield costs_data[offset : offset + _PAGE_SIZE]

    @staticmethod
    def _check_options(options: dict) -> None:
        if "bucket_name" not in options:
            raise ERROR_REQUIRED_PARAMETER(key="options.bucket_name")

    @staticmethod
    def _get_csv(csv_file: str) -> List[dict]:
        try:
            # 파일 존재 여부 확인
            if not os.path.exists(csv_file):
                _LOGGER.error(f"[_get_csv] File does not exist: {csv_file}")
                raise FileNotFoundError(f"File not found: {csv_file}")
            
            _LOGGER.debug(f"[_get_csv] Reading CSV file: {csv_file}")
            df = pd.read_csv(csv_file, encoding="utf-8-sig")
            df = df.replace({np.nan: None})

            costs_data = df.to_dict("records")
            return costs_data

        except Exception as e:
            _LOGGER.error(f"[_get_csv] download error: {e}", exc_info=True)
            raise e
