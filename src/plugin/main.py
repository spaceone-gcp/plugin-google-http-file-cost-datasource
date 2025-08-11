from typing import Generator
from spaceone.cost_analysis.plugin.data_source.lib.server import DataSourcePluginServer
from .manager.data_source_manager import DataSourceManager
from .manager.job_manager import JobManager
from .manager.cost_manager import CostManager

app = DataSourcePluginServer()


@app.route("DataSource.init")
def data_source_init(params: dict) -> dict:
    """init plugin by options

    Args:
        params (DataSourceInitRequest): {
            'options': 'dict',    # Required
            'domain_id': 'str'    # Required
        }

    Returns:
        PluginResponse: {
            'metadata': 'dict'
        }
    """
    options = params["options"]

    data_source_mgr = DataSourceManager()
    return data_source_mgr.init_response(options)


@app.route("DataSource.verify")
def data_source_verify(params: dict) -> None:
    """Verifying data source plugin

    Args:
        params (CollectorVerifyRequest): {
            'options': 'dict',      # Required
            'secret_data': 'dict',  # Required
            'schema': 'str',
            'domain_id': 'str'      # Required
        }

    Returns:
        None
    """

    options = params["options"]
    secret_data = params["secret_data"]
    secret_data['private_key'] = _clean_pem(secret_data['private_key'])
    domain_id = params.get("domain_id")
    schema = params.get("schema")

    data_source_mgr = DataSourceManager()
    data_source_mgr.verify_plugin(options, secret_data, domain_id, schema)


@app.route("Job.get_tasks")
def job_get_tasks(params: dict) -> dict:
    """Get job tasks

    Args:
        params (JobGetTaskRequest): {
            'options': 'dict',      # Required
            'secret_data': 'dict',  # Required
            'schema': 'str',
            'start': 'str',
            'last_synchronized_at': 'datetime',
            'domain_id': 'str'      # Required
        }

    Returns:
        TasksResponse: {
            'tasks': 'list',
            'changed': 'list'
        }

    """

    domain_id = params["domain_id"]
    options = params["options"]
    secret_data = params["secret_data"]
    secret_data['private_key'] = _clean_pem(secret_data['private_key'])

    schema = params.get("schema")
    start = params.get("start")
    last_synchronized_at = params.get("last_synchronized_at")

    job_mgr = JobManager()
    return job_mgr.get_tasks(
        domain_id, options, secret_data, schema, start, last_synchronized_at
    )


@app.route("Cost.get_data")
def cost_get_data(params: dict) -> Generator[dict, None, None]:
    """외부 비용 데이터를 가져오는 함수
    
    이 함수는 HTTP 파일이나 Google Cloud Storage에서 비용 데이터를 수집하여
    SpaceONE 비용 분석 플러그인에서 사용할 수 있는 형태로 변환합니다.
    
    Args:
        params (CostGetDataRequest): {
            'options': 'dict',      # 필수 - 플러그인 설정 옵션
            'secret_data': 'dict',  # 필수 - 인증 정보 (private_key 포함)
            'schema': 'str',        # 선택 - 스키마 정보
            'task_options': 'dict', # 선택 - 작업별 옵션 (base_url 또는 bucket_name)
            'domain_id': 'str'      # 필수 - 도메인 ID
        }

    Returns:
        Generator[ResourceResponse, None, None]: 비용 데이터 스트림
        {
            'cost': 'float',           # 비용 금액
            'usage_quantity': 'float', # 사용량
            'usage_unit': 'str',       # 사용량 단위
            'provider': 'str',         # 클라우드 제공자
            'region_code': 'str',      # 리전 코드
            'product': 'str',          # 제품명
            'usage_type': 'str',       # 사용 유형
            'resource': 'str',         # 리소스명
            'tags': 'dict',            # 태그 정보
            'additional_info': 'dict', # 추가 정보
            'data': 'dict',            # 원본 데이터
            'billed_date': 'str'       # 청구 날짜
        }
    """

    # 옵션과 시크릿 데이터 추출
    options = params["options"]
    secret_data = params["secret_data"]
    # PEM 키의 개행 문자 정리
    secret_data['private_key'] = _clean_pem(secret_data['private_key'])

    # 작업 옵션과 스키마 추출 (기본값 설정)
    task_options = params.get("task_options", {})
    schema = params.get("schema")

    # 비용 매니저를 통해 데이터 수집
    cost_mgr = CostManager()
    return cost_mgr.get_data(options, secret_data, schema, task_options)


@app.route("Cost.get_linked_accounts")
def cost_get_linked_accounts(params: dict) -> dict:
    """ get linked accounts

    Args:
        params: (CostGetLinkedAccountsRequest): {
            'options': 'dict'
            'schema': 'str'
            'secret_data': 'dict'
            'domain_id': 'str'
        }

    Returns:
        {
            'account_id': 'str'
            'name': 'str'
        }
    """
    options = params["options"]
    secret_data = params["secret_data"]
    secret_data['private_key'] = _clean_pem(secret_data['private_key'])

    schema = params.get("schema")

    cost_mgr = CostManager()
    return cost_mgr.get_linked_accounts(options, secret_data, schema)


def _clean_pem(pem_key: str) -> str:
    return pem_key.replace('\\n', '\n')
