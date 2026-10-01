"""Tests for OpenMP and serverless adapters."""

from quantum_compute_substrate.interop.openmp_adapter import OpenMPAdapter
from quantum_compute_substrate.interop.serverless_adapter import ServerlessAdapter


class TestOpenMPAdapter:
    def test_parallel_map_returns_results(self):
        a = OpenMPAdapter(n_threads=2)
        out = a.parallel_map(lambda x: x * x, [1, 2, 3, 4])
        assert out == [1, 4, 9, 16]

    def test_status_shape(self):
        a = OpenMPAdapter(n_threads=2)
        st = a.status()
        assert st["n_threads"] == 2
        assert st["backend"] in ("joblib", "threadpool")


class TestServerlessAdapter:
    def test_aws_lambda_json(self):
        import json

        s = ServerlessAdapter()
        cfg = json.loads(s.aws_lambda())
        assert cfg["runtime"] == "python3.11"
        assert cfg["claim_lane"] == "MATHEMATICAL_QUANTUM (SUBSTRATE-AGNOSTIC)"

    def test_cloud_run_json(self):
        import json

        cfg = json.loads(ServerlessAdapter().google_cloud_run())
        assert "cpu" in cfg and "memory" in cfg

    def test_azure_functions_json(self):
        import json

        cfg = json.loads(ServerlessAdapter().azure_functions())
        assert cfg["runtime"] == "python"

    def test_status(self):
        st = ServerlessAdapter().status()
        assert set(st["providers"]) == {"aws", "gcp", "azure"}
        assert st["available"] is True
