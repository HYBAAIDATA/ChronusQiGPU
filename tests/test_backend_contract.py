"""Backend contract tests for the Chronus substrate runtime.

Run: pytest tests/test_backend_contract.py -q
"""
from __future__ import annotations

import importlib
import sys

import pytest

from chronus import backend as contract
from chronus.backends import cpu_reference, mla1517_mmio, opencl_igpu, remote

STRICT_OPS = {"miner", "submit", "strict_gate", "hash_pipeline_accept", "pool_commit"}
SOLVER_OPS = {"solver", "amplitude_amplification", "grover", "shor", "period_finding", "bitcoin_sha256d"}


class TestBackendContract:
    def test_probe_returns_all_four_backends(self):
        probes = contract.probe()
        assert set(probes) == {"cpu_reference", "opencl", "mla1517", "remote"}

    def test_probe_never_raises(self):
        probes = contract.probe()
        for backend, info in probes.items():
            assert isinstance(info, dict)
            assert "available" in info

    def test_cpu_reference_probe(self):
        p = cpu_reference.probe()
        assert p["available"] is True
        assert p["reason"].startswith("declared always-available")
        assert p["self_check"] == "PASS"

    def test_cpu_reference_execute_labels_cpu(self):
        result, route = contract.execute("sha256d", b"hello")
        assert route.executed == "cpu_reference"
        assert result["backend"] == "cpu_reference"
        assert len(result["digest"]) == 64
        assert all(c in "0123456789abcdef" for c in result["digest"])

    def test_cpu_as_executed_is_never_masked(self):
        result, route = contract.execute("hash", "x")
        assert route.executed == "cpu_reference"
        assert result["backend"] == "cpu_reference"

    def test_route_records_substitution(self):
        result, route = contract.execute("sha256d", b"hello", requested="mla1517")
        assert route.executed == "cpu_reference"
        assert "fell back" in route.fallback_reason


class TestFailClosedContract:
    def test_strict_op_fails_closed_when_backend_missing(self):
        with pytest.raises(contract.BackendUnavailable):
            contract.execute("miner", None, requested="mla1517")

    def test_solver_falls_back_to_cpu(self):
        result, route = contract.execute("grover", None, requested="mla1517")
        assert route.executed == "cpu_reference"
        assert "fell back" in route.fallback_reason

    def test_cpu_reference_runs_strict_op(self):
        result, route = contract.execute("miner", None, requested="cpu_reference")
        assert route.executed == "cpu_reference"
        assert result["backend"] == "cpu_reference"


class TestBackendIsolation:
    def test_contract_imports_lucas_not_opencl(self):
        import chronus.backend
        assert "opencl" not in sys.modules
        assert "pyopencl" not in sys.modules

    def test_backends_own_hw_imports(self):
        mla = importlib.import_module("chronus.backends.mla1517_mmio")
        assert "ctypes" in sys.modules
        assert "pyopencl" not in sys.modules
        o = importlib.import_module("chronus.backends.opencl_igpu")
        try:
            import pyopencl  # noqa: F401
            assert "pyopencl" in sys.modules
        except ModuleNotFoundError:
            p = o.probe()
            assert p["available"] is False
            assert "pyopencl" in p["reason"] or "import failed" in p["reason"]

    def test_backends_exposed_via_package(self):
        from chronus.backends import remote, mla1517_mmio
        assert remote is not None
        assert mla1517_mmio is not None

