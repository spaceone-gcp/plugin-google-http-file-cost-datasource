import logging
import time
from dateutil.parser import parse
from spaceone.core.manager import BaseManager
from plugin.error.cost import ERROR_EMPTY_BILLED_DATE
from spaceone.core.error import ERROR_REQUIRED_PARAMETER
from plugin.connector.http_file_connector import HTTPFileConnector
from plugin.connector.google_storage_collector import (
    GoogleStorageConnector,
)

_LOGGER = logging.getLogger("spaceone")

# 필수 필드 목록 - 비용 데이터에 반드시 포함되어야 하는 필드들
_REQUIRED_FIELDS = ["cost", "currency", "billed_date"]


class CostManager(BaseManager):
    """비용 데이터 관리 클래스
    
    HTTP 파일이나 Google Cloud Storage에서 비용 데이터를 수집하고
    SpaceONE에서 사용할 수 있는 형태로 변환하는 역할을 담당합니다.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 기본 변수 설정 (옵션에서 설정 가능)
        self.default_vars = None
        # 필드 매핑 설정 (CSV 컬럼명을 표준 필드명으로 매핑)
        self.field_mapper = None
        # 타입 변환 설정 (데이터 타입 변환 규칙)
        self.type_mapper = None

    def get_data(self, options, secret_data, schema, task_options):
        """비용 데이터를 수집하고 변환하는 메인 메서드
        
        Args:
            options (dict): 플러그인 설정 옵션 (default_vars, field_mapper, type_mapper 등)
            secret_data (dict): 인증 정보 (Google Cloud Service Account 키 등)
            schema (str): 스키마 정보
            task_options (dict): 작업별 옵션 (base_url 또는 bucket_name)
            
        Yields:
            list: 처리된 비용 데이터 리스트 (페이지 단위로 반환)
        """
        start_time = time.time()
        _LOGGER.debug(
            f"[get_data] Start Collecting Cost Data (task_options={task_options})"
        )

        # 기본 변수 설정이 있는 경우 적용
        if "default_vars" in options:
            self.default_vars = options["default_vars"]
            _LOGGER.debug(f"[get_data] apply default vars: {self.default_vars}")

        # 필드 매핑 설정이 있는 경우 적용
        if "field_mapper" in options:
            self.field_mapper = options["field_mapper"]
            _LOGGER.debug(f"[get_data] apply field mapper: {self.field_mapper}")

        # 타입 변환 설정이 있는 경우 적용
        if "type_mapper" in options:
            self.type_mapper = options["type_mapper"]

        # HTTP 파일 또는 Google Cloud Storage에서 데이터 수집
        if "base_url" in task_options:
            # HTTP 파일에서 데이터 수집
            base_url = task_options["base_url"]
            http_file_connector = self.locator.get_connector(HTTPFileConnector)
            http_file_connector.create_session(options, secret_data, schema)
            response_stream = http_file_connector.get_cost_data(base_url)
        else:
            # Google Cloud Storage에서 데이터 수집
            bucket_name = task_options["bucket_name"]
            storage_connector = self.locator.get_connector(
                GoogleStorageConnector, secret_data=secret_data
            )
            response_stream = storage_connector.get_cost_data(bucket_name)
            _LOGGER.debug(f"[get_data] get cost data from {bucket_name} bucket")

        # 수집된 데이터를 처리하여 반환
        for results in response_stream:
            yield self._make_cost_data(results)

        _LOGGER.debug(
            f"[collector_collect] Finished Collecting Cost Data"
            f"(duration: {time.time() - start_time:.2f}s)"
        )

    def _make_cost_data(self, results):
        """원시 데이터를 SpaceONE 비용 데이터 형식으로 변환
        
        Args:
            results (list): 원시 비용 데이터 리스트
            
        Returns:
            list: 변환된 비용 데이터 리스트
        """
        costs_data = []
        for result in results:
            # 딕셔너리 키와 값의 공백 제거
            result = self._apply_strip_to_dict_keys(result)
            result = self._apply_strip_to_dict_values(result)

            # 필드 매핑 적용
            if self.field_mapper:
                result = self._change_result_by_field_mapper(result)

            # 기본 변수 설정 적용
            if self.default_vars:
                self._set_default_vars(result)

            # 타입 변환 적용
            if self.type_mapper:
                self._set_type_mapper(result)

            # 청구 날짜 생성
            self._create_billed_date(result)

            # 비용과 사용량 타입 변환 검증
            if not self._convert_cost_and_usage_quantity_types(result):
                continue

            # 비용과 사용량 존재 여부 검증
            if not self._exist_cost_and_usage_quantity(result):
                continue

            # 필수 필드 검증
            self._check_required_fields(result)

            try:
                # SpaceONE 비용 데이터 형식으로 변환
                data = {
                    "cost": result["cost"],
                    "usage_quantity": result.get("usage_quantity", 0),
                    "usage_type": result.get("usage_type"),
                    "usage_unit": result.get("usage_unit"),
                    "provider": result.get("provider"),
                    "region_code": result.get("region_code"),
                    "product": result.get("product"),
                    "resource": result.get("resource", ""),
                    "billed_date": result["billed_date"],
                    "additional_info": result.get("additional_info", {}),
                    "tags": result.get("tags", {}),
                }

            except Exception as e:
                _LOGGER.error(f"[_make_cost_data] make data error: {e}", exc_info=True)
                raise e

            costs_data.append(data)
        return costs_data

    @staticmethod
    def _apply_strip_to_dict_keys(result):
        """딕셔너리 키의 앞뒤 공백을 제거
        
        Args:
            result (dict): 처리할 딕셔너리
            
        Returns:
            dict: 키가 정리된 딕셔너리
        """
        for key in list(result.keys()):
            new_key = key.strip()
            if new_key != key:
                result[new_key] = result[key]
                del result[key]
        return result

    @staticmethod
    def _apply_strip_to_dict_values(result):
        """딕셔너리 값의 앞뒤 공백을 제거 (문자열인 경우만)
        
        Args:
            result (dict): 처리할 딕셔너리
            
        Returns:
            dict: 값이 정리된 딕셔너리
        """
        for key, value in result.items():
            if isinstance(value, str):
                result[key] = value.strip()
        return result

    def _change_result_by_field_mapper(self, result):
        """필드 매핑을 통해 결과 데이터의 필드명을 변경
        
        Args:
            result (dict): 매핑할 데이터
            
        Returns:
            dict: 필드명이 변경된 데이터
        """
        for origin_field, actual_field in self.field_mapper.items():
            if isinstance(actual_field, str):
                # 단순 문자열 매핑
                if actual_field in result:
                    result[origin_field] = result[actual_field]
                    del result[actual_field]

            if origin_field == "additional_info":
                # additional_info 필드의 경우 중첩 매핑 처리
                additional_info = {}
                for (
                    origin_additional_field,
                    actual_additional_field,
                ) in actual_field.items():
                    additional_info[origin_additional_field] = result[
                        actual_additional_field
                    ]
                    del result[actual_additional_field]
                result[origin_field] = additional_info

        return result

    def _create_billed_date(self, result):
        """청구 날짜를 생성하거나 변환
        
        Args:
            result (dict): 비용 데이터
            
        Returns:
            dict: 청구 날짜가 설정된 데이터
        """
        if self._exist_billed_date(result):
            # 기존 billed_date가 있는 경우 파싱하여 표준 형식으로 변환
            billed_date = result["billed_date"]
            billed_date = self._apply_parse_date(billed_date)
            billed_date = str(billed_date.strftime("%Y-%m-%d"))

            result["billed_date"] = billed_date

        else:
            # billed_date가 없는 경우 year, month, day 또는 invoice.month에서 생성
            if result.get("invoice.month"):
                # invoice.month 형식 (YYYYMM)에서 추출
                invoice_month = str(result["invoice.month"])
                if len(invoice_month) == 6:
                    year = invoice_month[:4]
                    month = invoice_month[4:6]
                else:
                    year = result.get("year")
                    month = result.get("month")
            else:
                # 개별 year, month 필드에서 추출
                year = result.get("year")
                month = result.get("month")
            
            day = result.get("day", "01")

            # 월과 일이 한 자리인 경우 앞에 0 추가
            if len(month) == 1:
                month = f"0{month}"
            if len(day) == 1:
                day = f"0{day}"

            billed_date = f"{year}-{month}-{day}"

            result["billed_date"] = billed_date

        return result

    @staticmethod
    def _exist_billed_date(result):
        """청구 날짜 필드의 존재 여부를 확인
        
        Args:
            result (dict): 확인할 데이터
            
        Returns:
            bool: billed_date가 존재하면 True, year/month 조합이면 False
            
        Raises:
            ERROR_EMPTY_BILLED_DATE: 청구 날짜 정보가 없는 경우
        """
        if result.get("billed_date"):
            return True
        elif result.get("year") and result.get("month"):
            return False
        elif result.get("invoice.month"):
            return False
        else:
            _LOGGER.error(f"[_is_not_empty_billed_at] billed_at is empty: {result}")
            raise ERROR_EMPTY_BILLED_DATE(result=result)

    @staticmethod
    def _apply_parse_date(date):
        """날짜 문자열을 파싱하여 datetime 객체로 변환
        
        Args:
            date (str): 파싱할 날짜 문자열
            
        Returns:
            datetime: 파싱된 날짜 객체
            
        Raises:
            TypeError: 날짜 파싱에 실패한 경우
        """
        try:
            parsed_date = parse(date)
            return parsed_date
        except TypeError as e:
            _LOGGER.error(f"[_apply_parse_date] parse date error: {e}", exc_info=True)
            raise e

    def _set_default_vars(self, result):
        """기본 변수를 결과 데이터에 설정
        
        Args:
            result (dict): 설정할 데이터
        """
        for key, value in self.default_vars.items():
            result[key] = value

    @staticmethod
    def _convert_cost_and_usage_quantity_types(result):
        """비용과 사용량을 float 타입으로 변환
        
        Args:
            result (dict): 변환할 데이터
            
        Returns:
            bool: 변환 성공 여부
        """
        try:
            result["cost"] = float(result["cost"])
            result["usage_quantity"] = float(result.get("usage_quantity", 0))
        except Exception as e:
            _LOGGER.error(
                f"[_convert_cost_and_usage_quantity_types] convert cost and usage quantity types error: {e} (data={result})",
                exc_info=True,
            )
            return False
        return True

    @staticmethod
    def _exist_cost_and_usage_quantity(result):
        """비용 또는 사용량이 존재하는지 확인
        
        Args:
            result (dict): 확인할 데이터
            
        Returns:
            bool: 비용 또는 사용량이 존재하면 True
        """
        if result["cost"] or result["cost"] == float(0):
            return True
        elif result["usage_quantity"] or result["usage_quantity"] == float(0):
            return True
        else:
            _LOGGER.error(
                f"[_exist_cost_and_usage_quantity] cost or usage quantity are empty: {result}"
            )
            return False

    @staticmethod
    def _check_required_fields(result):
        """필수 필드가 존재하는지 확인
        
        Args:
            result (dict): 확인할 데이터
            
        Raises:
            ERROR_REQUIRED_PARAMETER: 필수 필드가 없는 경우
        """
        for field in _REQUIRED_FIELDS:
            if field not in result:
                raise ERROR_REQUIRED_PARAMETER(key=field)

    def _set_type_mapper(self, result):
        """타입 변환 규칙을 적용
        
        Args:
            result (dict): 변환할 데이터
            
        Returns:
            dict: 타입이 변환된 데이터
        """
        # 현재는 Account ID를 12자리 문자열로 변환하는 기능만 구현됨
        if "additional_info" in self.type_mapper:
            if (
                "Account ID" in self.type_mapper["additional_info"]
                and "additional_info" in result
                and "Account ID" in result.get("additional_info", {})
            ):
                account_id = result["additional_info"]["Account ID"]
                if isinstance(account_id, int) or isinstance(account_id, float):
                    result["additional_info"]["Account ID"] = str(account_id).zfill(12)
        return result
