import unittest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
from chronus.core import ChronusAPISDK, ChronusRESTAPIGatewayV35, ChronusFrontendInterfaceEngine

class TestSDKAndAPISuite(unittest.TestCase):
    def test_sdk_submit_and_status(self):
        client = ChronusAPISDK(tenant_id="tenant_test", access_token="TOKEN_XYZ")
        sub = client.submit_workload(b"SDK_Test_Payload_Data")
        self.assertEqual(sub["status"], "SUBMITTED_AND_EXECUTED")
        self.assertTrue(sub["zero_copy_pointer"].startswith("ptr_sdk_"))
        
        status = client.get_workload_status(sub["workload_id"])
        self.assertEqual(status["status"], "COMPLETED")

    def test_rest_gateway_endpoints(self):
        res_caps = ChronusRESTAPIGatewayV35.handle_request("GET", "/v1/capabilities")
        self.assertEqual(res_caps["status_code"], 200)
        
        res_cap = ChronusRESTAPIGatewayV35.handle_request("GET", "/v1/capacity")
        self.assertEqual(res_cap["status_code"], 200)

        res_unauth = ChronusRESTAPIGatewayV35.handle_request("GET", "/v1/workloads")
        self.assertEqual(res_unauth["status_code"], 401)

    def test_frontend_console_render(self):
        state = ChronusFrontendInterfaceEngine.render_console_state("01_OVERVIEW", "tenant_test")
        self.assertEqual(state["status"], "CONSOLE_STATE_RENDERED")
        self.assertEqual(state["active_destination"], "01_OVERVIEW")

if __name__ == "__main__":
    unittest.main()
