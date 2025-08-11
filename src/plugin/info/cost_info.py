import functools
import logging
from spaceone.api.cost_analysis.plugin import cost_pb2
from spaceone.core.pygrpc.message_type import *
from spaceone.core import utils

__all__ = ["CostInfo", "CostsInfo"]

_LOGGER = logging.getLogger(__name__)


def CostInfo(cost_data):
    """단일 비용 데이터를 protobuf 형식으로 변환
    
    딕셔너리 형태의 비용 데이터를 SpaceONE의 protobuf CostInfo 형식으로 변환합니다.
    
    Args:
        cost_data (dict): 변환할 비용 데이터 {
            'cost': 'float',           # 비용 금액
            'usage_quantity': 'float', # 사용량
            'usage_type': 'str',       # 사용 유형
            'usage_unit': 'str',       # 사용량 단위
            'provider': 'str',         # 클라우드 제공자
            'region_code': 'str',      # 리전 코드
            'product': 'str',          # 제품명
            'resource': 'str',         # 리소스명
            'tags': 'dict',            # 태그 정보
            'additional_info': 'dict', # 추가 정보
            'billed_date': 'str'       # 청구 날짜
        }

    Returns:
        cost_pb2.CostInfo: protobuf 형식의 비용 정보
        
    Raises:
        Exception: 데이터 변환에 실패한 경우
    """
    try:
        # 딕셔너리 데이터를 protobuf 형식으로 변환
        info = {
            "cost": cost_data["cost"],
            "usage_quantity": cost_data.get("usage_quantity"),
            "usage_type": cost_data.get("usage_type"),
            "usage_unit": cost_data.get("usage_unit"),
            "provider": cost_data["provider"],
            "region_code": cost_data["region_code"],
            "product": cost_data["product"],
            "resource": cost_data.get("resource"),
            # 태그와 추가 정보를 protobuf 구조체 형식으로 변환
            "tags": change_struct_type(cost_data["tags"])
            if "tags" in cost_data
            else None,
            "additional_info": change_struct_type(cost_data["additional_info"])
            if "additional_info" in cost_data
            else None,
            "billed_date": cost_data["billed_date"],
        }

        return cost_pb2.CostInfo(**info)

    except Exception as e:
        _LOGGER.debug(f"[CostInfo] cost data: {cost_data}")
        _LOGGER.debug(f"[CostInfo] error reason: {e}", exc_info=True)
        raise e


def CostsInfo(costs_data, **kwargs):
    """비용 데이터 리스트를 protobuf 형식으로 변환
    
    비용 데이터 리스트의 각 항목을 CostInfo로 변환하여 CostsInfo protobuf 객체를 생성합니다.
    
    Args:
        costs_data (list): 변환할 비용 데이터 리스트
        **kwargs: 추가 키워드 인자
        
    Returns:
        cost_pb2.CostsInfo: protobuf 형식의 비용 정보 리스트
    """
    # 각 비용 데이터를 CostInfo로 변환하여 리스트 생성
    return cost_pb2.CostsInfo(
        results=list(map(functools.partial(CostInfo, **kwargs), costs_data))
    )
