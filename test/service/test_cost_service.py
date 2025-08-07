import unittest
from unittest.mock import patch

from spaceone.core.unittest.result import print_data
from spaceone.core.unittest.runner import RichTestRunner
from spaceone.core import config
from spaceone.core.transaction import Transaction

from plugin.connector.http_file_connector import HTTPFileConnector
from plugin.service.cost_service import CostService
from test.factory.common_config import OPTIONS


class TestCostService(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config.init_conf(package="plugin")
        cls.transaction = Transaction({"service": "cost_analysis", "api_class": "Cost"})
        super().setUpClass()

    @classmethod
    def tearDownClass(cls) -> None:
        super().tearDownClass()

    @patch.object(HTTPFileConnector, "__init__", return_value=None)
    def test_get_cost_data(self, *args):
        params = {"options": OPTIONS, "secret_data": {}, "task_options": {OPTIONS}}

        self.transaction.method = "get_data"
        cost_svc = CostService(transaction=self.transaction)
        responses = cost_svc.get_data(params.copy())

        for response in responses:
            print_data(response, "test_get_cost_data")


if __name__ == "__main__":
    unittest.main(testRunner=RichTestRunner)
