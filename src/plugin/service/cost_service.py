import logging

from spaceone.core.service import *
from plugin.manager.cost_manager import CostManager

_LOGGER = logging.getLogger(__name__)


@authentication_handler
@authorization_handler
@event_handler
class CostService(BaseService):
    """비용 서비스 클래스
    
    SpaceONE의 비용 분석 플러그인에서 비용 데이터를 처리하는 서비스 레이어입니다.
    인증, 권한, 이벤트 처리를 담당하며 CostManager를 통해 실제 비용 데이터를 수집합니다.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 비용 매니저 인스턴스 가져오기
        self.cost_mgr: CostManager = self.locator.get_manager(CostManager)

    @transaction
    @check_required(["options", "secret_data", "task_options"])
    def get_data(self, params):
        """비용 데이터를 수집하는 서비스 메서드
        
        이 메서드는 SpaceONE 플러그인 API를 통해 호출되며,
        HTTP 파일이나 Google Cloud Storage에서 비용 데이터를 수집합니다.
        
        Args:
            params (dict): {
                'options': 'dict',      # 필수 - 플러그인 설정 옵션
                'secret_data': 'dict',  # 필수 - 인증 정보
                'schema': 'str',        # 선택 - 스키마 정보
                'task_options': 'dict', # 필수 - 작업별 옵션
                'domain_id': 'str'      # 선택 - 도메인 ID
            }

        Returns:
            Generator: 비용 데이터 스트림 (페이지 단위로 반환)
        """

        # 파라미터에서 필요한 정보 추출
        options = params["options"]
        secret_data = params["secret_data"]
        schema = params.get("schema")
        task_options = params["task_options"]

        # 비용 매니저를 통해 데이터 수집 및 반환
        return self.cost_mgr.get_data(options, secret_data, schema, task_options)
