from spaceone.api.cost_analysis.plugin import cost_pb2, cost_pb2_grpc
from spaceone.core.pygrpc import BaseAPI
from plugin.service.cost_service import CostService
from plugin.info.cost_info import CostsInfo


class Cost(BaseAPI, cost_pb2_grpc.CostServicer):
    """비용 gRPC 인터페이스 클래스
    
    SpaceONE의 비용 분석 플러그인에서 gRPC 통신을 담당하는 인터페이스입니다.
    클라이언트의 요청을 받아 CostService로 전달하고 응답을 반환합니다.
    """
    
    pb2 = cost_pb2
    pb2_grpc = cost_pb2_grpc

    def get_data(self, request, context):
        """gRPC를 통해 비용 데이터를 수집하는 메서드
        
        클라이언트로부터 gRPC 요청을 받아 CostService를 통해 비용 데이터를 수집하고,
        protobuf 형식으로 변환하여 스트림으로 반환합니다.
        
        Args:
            request: gRPC 요청 객체
            context: gRPC 컨텍스트
            
        Yields:
            cost_pb2.CostsInfo: protobuf 형식의 비용 데이터
        """
        # gRPC 요청을 파라미터와 메타데이터로 파싱
        params, metadata = self.parse_request(request, context)

        # CostService를 통해 비용 데이터 수집
        with self.locator.get_service(CostService, metadata) as cost_service:
            response_stream = cost_service.get_data(params)
            # 수집된 데이터를 protobuf 형식으로 변환하여 반환
            for costs_data in response_stream:
                yield self.locator.get_info(CostsInfo, costs_data)
