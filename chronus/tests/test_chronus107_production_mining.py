import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from chronus.mla1517.mining.production_integration import (
    EXPECTED_BASE_SHA,
    ProductionIntegrationError,
    ProductionMiningIntegration,
)

ROOT = Path(__file__).resolve().parents[2]


def integration():
    return ProductionMiningIntegration.from_repository(ROOT)


def test_manifest_locks_base_authorities_and_negative_states():
    x = integration()
    assert x.manifest["base_sha"] == EXPECTED_BASE_SHA
    assert x.manifest["truth_states"]["f64"] == "UNSUPPORTED"
    assert x.manifest["truth_states"]["opencl.BINET_EXACT"] == "UNSUPPORTED"
    assert x.manifest["truth_states"]["FOLDED_NATIVE"] == "OPEN"
    bad = json.loads((ROOT / "manifests/chronus107/production-mining.json").read_text())
    bad["authority"]["pool_outcome"] = "planner"
    with pytest.raises(ProductionIntegrationError):
        ProductionMiningIntegration(bad)


def test_pisot_intrinsic_is_real_deterministic_advice_with_conventional_candidates():
    x = integration()
    a = x.plan_evidence(1024, 256)
    b = x.plan_evidence(1024, 256)
    assert a == b and a["intrinsic_backend"] == "REFERENCE_HOST"
    assert a["authority"] == "ADVISORY_ONLY_MEASUREMENT_SELECTS"
    assert any(v["provenance"] == "CONVENTIONAL" for v in a["candidates"])
    assert any(v["provenance"] == "LUCAS_PISOT" for v in a["candidates"])


def test_device_available_is_not_hardware_executed():
    route = integration().route_evidence(
        SimpleNamespace(backend="opencl", device="test", vendor="test")
    )
    assert route["state"] == "DEVICE_AVAILABLE"
    assert route["hardware_executed"] is False
    assert route["physical_evidence_gate"] == "PHYSICAL_EVIDENCE_REQUIRED"


def test_execution_and_recovery_are_content_addressed_without_new_authority():
    x = integration()
    record = {
        "job_fingerprint": "job",
        "search_plan_id": "plan",
        "requested_route": "cpu_reference",
        "executed_route": "cpu_reference",
        "completion_state": "COMPLETE",
        "hash_count": 32,
        "completed_work_items": 32,
        "kernel_launch_count": 0,
        "evidence_class": "SOFTWARE_VERIFIED",
        "pool_outcome": "NOT_SUBMITTED",
    }
    assert x.execution_evidence(record) == x.execution_evidence(record)
    governor = SimpleNamespace(
        snapshot=lambda: {"authority": "salamander", "mode": "NORMAL", "open": [], "recent": []}
    )
    recovery = x.recovery_evidence(governor)
    assert recovery["authority"] == "recovery_governor"
    assert recovery["scope"] == "PRODUCTION_MINING_ONLY"
