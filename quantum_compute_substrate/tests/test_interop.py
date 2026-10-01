"""Tests for interop adapters."""

from quantum_compute_substrate.interop import (
    TorchAdapter,
    TensorFlowAdapter,
    MPIAdapter,
    KubernetesManifest,
    EdgeDeployment,
)


class TestML:
    def test_torch_reports_availability(self):
        a = TorchAdapter()
        s = a.status()
        assert s["framework"] == "pytorch"
        assert isinstance(s["available"], bool)

    def test_tensorflow_reports_availability(self):
        a = TensorFlowAdapter()
        assert a.status()["framework"] == "tensorflow"


class TestHPC:
    def test_mpi_status(self):
        a = MPIAdapter()
        s = a.status()
        assert s["framework"] == "mpi4py"
        assert s["rank"] >= 0
        assert s["size"] >= 1

    def test_mpi_reduce_graceful(self):
        a = MPIAdapter()
        # If MPI is unavailable, all_reduce_sum returns the value
        assert a.all_reduce_sum(5) == 5


class TestCloud:
    def test_kubernetes_manifest_emits_yaml(self):
        km = KubernetesManifest()
        y = km.emit(replicas=3)
        assert "apiVersion: apps/v1" in y
        assert "replicas: 3" in y


class TestEdge:
    def test_edge_deployment_status(self):
        ed = EdgeDeployment()
        s = ed.status()
        assert s["max_state_dim"] > 0
        assert "tensor_core" in s["features"]
