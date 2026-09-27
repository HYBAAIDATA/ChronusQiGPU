"""ASIC fail-closed contract: no channel → no capability → no dispatch.

These tests assert the negative path only. When a real ASIC is attached
and configured, the network channel is exercised against the live
endpoint by a separate integration run — nothing here simulates one.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from hyba.hybrid.asic_solver import ASICSolver
from hyba.hybrid.coordinator import HybridCoordinator
from hyba.hybrid.nonce_scheduler import (
    ASICNotPresent,
    AttestationRegistry,
)


def _window():
    from hyba.hybrid.nonce_scheduler import NonceWindow

    return NonceWindow(
        job_id="j",
        session_epoch=0,
        job_epoch=0,
        base_nonce=0,
        span=1024,
        target=b"\xff" * 32,
    )


def test_no_channels_configured_is_unsupported(monkeypatch):
    for var in ("HYBRID_ASIC_ENDPOINT", "HYBRID_ASIC_SERIAL", "HYBRID_ASIC_PCIE"):
        monkeypatch.delenv(var, raising=False)
    solver = ASICSolver()
    cap = solver.capability()
    assert cap.supported is False
    assert cap.measured_hashes_per_sec == 0.0
    assert "no ASIC channel configured" in cap.reason_if_unsupported


def test_dispatch_raises_asic_not_present(monkeypatch):
    for var in ("HYBRID_ASIC_ENDPOINT", "HYBRID_ASIC_SERIAL", "HYBRID_ASIC_PCIE"):
        monkeypatch.delenv(var, raising=False)
    solver = ASICSolver()
    with pytest.raises(ASICNotPresent):
        solver.dispatch(_window())


def test_configured_but_unresponsive_endpoint_is_unsupported():
    # Port 1 on localhost is not listening; probe must report unsupported.
    solver = ASICSolver(endpoint="127.0.0.1:1")
    cap = solver.capability()
    assert cap.supported is False
    assert "probe failed" in (cap.reason_if_unsupported or "").lower()


def test_pcie_node_absent_is_unsupported(tmp_path):
    solver = ASICSolver(pcie_node=str(tmp_path / "no_such_node"))
    cap = solver.capability()
    assert cap.supported is False


def test_hybrid_degrades_to_gpu_only_with_gap(monkeypatch):
    """With an absent ASIC the coordinator runs gpu_only AND logs a gap."""
    for var in ("HYBRID_ASIC_ENDPOINT", "HYBRID_ASIC_SERIAL", "HYBRID_ASIC_PCIE"):
        monkeypatch.delenv(var, raising=False)
    AttestationRegistry.reset()
    try:
        from hyba.hybrid.gpu_solver import GPUSolver

        gpu = GPUSolver()
    except Exception:
        pytest.skip("no GPU solver substrate available in this environment")
    coord = HybridCoordinator(gpu, ASICSolver())
    assert coord.mode == "gpu_only"
    kinds = {r["kind"] for r in AttestationRegistry.get().snapshot()}
    assert "gap" in kinds


def test_no_synthetic_capability_fields():
    """The capability record never fabricates device identity or H/s."""
    solver = ASICSolver()
    cap = solver.capability()
    if not cap.supported:
        assert cap.measured_hashes_per_sec == 0.0
        assert cap.device_id.startswith("asic:")
