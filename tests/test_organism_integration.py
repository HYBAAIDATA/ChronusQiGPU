"""Whole-organism wiring through the canonical EUCLID composition root.

Every assertion runs the production path (``EuclidRuntime.production``) and the
owners' real implementations; unavailable substrates are asserted unavailable.
"""

from __future__ import annotations

import hashlib
import time

import pytest

from al_haras import (
    ALHaras,
    GuardianPolicy,
    HashChainAudit,
    SubscriptionAuthority,
    SubscriptionClaims,
)
from chronus.mla1517.mining.pow import sha256d
from euclid.cognition.reachability import ReachabilityMatrix, ReachabilityStage
from euclid.contracts import Health
from euclid.organ_adapters import specialists as adapters
from euclid.runtime import EuclidRuntime

KEY = b"k" * 32
BELL = {
    "n_qubits": 2,
    "operations": [{"gate": "h", "qubits": [0]}, {"gate": "cx", "qubits": [0, 1]}],
}


@pytest.fixture
def runtime(tmp_path):
    rt = EuclidRuntime.production(creator_id="creator-1", state_dir=tmp_path)
    yield rt
    rt.close()


def _dispatch(rt, organ, request, **kw):
    return rt.dispatch_specialist(organ, request, tenant_id="tenant-a", actor="user-1", **kw)


def test_production_root_composes_specialists_and_autonomic(runtime):
    organism = runtime.startup_report()["organism"]
    assert organism["specialists"] == ["chronus", "triad", "turing"]
    assert organism["unavailable"] == {}
    assert organism["autonomic"] is True
    assert organism["guardian_configured"] is False
    for component in ("turing.backends", "chronus.backend_registry", "aethel.triad"):
        assert runtime.reachability.stage(component) is ReachabilityStage.REACHABLE


def test_turing_workload_reaches_turing_with_exact_truth_class(runtime):
    out = _dispatch(runtime, "turing", {"operation": "run-program", "program": BELL})
    assert out["allowed"] and out["result"]["executed"]
    result = out["result"]
    assert result["owner"] == "TURING"
    assert result["truth_class"] == "exact"
    assert result["measured_qpu"] is False
    assert runtime.reachability.stage("turing.backends") is ReachabilityStage.OUTCOME_OBSERVED


def test_turing_hardware_preference_is_refused_not_simulated(runtime):
    out = _dispatch(
        runtime, "turing", {"operation": "run-program", "program": BELL, "prefer": "qpu"}
    )
    assert out["allowed"]
    assert out["result"]["executed"] is False
    assert out["result"]["truth_class"] == "refused"
    assert out["result"]["measured_qpu"] is False


def test_chronus_substrate_selection_preserves_sha256d_semantics(runtime):
    header = bytes(range(80))
    target = b"\xff" * 32
    out = _dispatch(
        runtime,
        "chronus",
        {
            "operation": "sha256d-scan",
            "policy": "cpu",
            "header_hex": header.hex(),
            "target_hex": target.hex(),
            "nonces": [7, 8],
        },
    )
    result = out["result"]
    assert result["executed"] and result["lane"] == "cpu" and result["nonce"] == 7
    expected = sha256d(header[:76] + (7).to_bytes(4, "little"))
    assert result["digest_hex"] == expected.hex()


def test_chronus_unprobed_lane_is_never_bound(runtime):
    census = _dispatch(runtime, "chronus", {"operation": "census"})["result"]["lanes"]
    for lane, policy in (
        ("cuda", "cuda"),
        ("metal", "metal"),
        ("remote_gpu", "remote"),
        ("asic", "asic"),
    ):
        out = _dispatch(runtime, "chronus", {"operation": "select", "policy": policy})["result"]
        assert out["bound"] is census[lane]["available"]
        if not census[lane]["available"]:
            assert "no lane available" in out["reason"]


def test_triad_custody_and_transformation_keep_owners(runtime):
    payload = "organism payload"
    put = _dispatch(runtime, "triad", {"operation": "put", "payload_utf8": payload})["result"]
    assert put["owner"] == "THESEUS"
    got = _dispatch(runtime, "triad", {"operation": "get", "uuid": put["uuid"]})["result"]
    assert got["sha256"] == hashlib.sha256(payload.encode()).hexdigest()
    fold = _dispatch(runtime, "triad", {"operation": "fold", "payload_utf8": payload})["result"]
    assert fold["owner"] == "OVID" and fold["round_trip"] is True
    assert _dispatch(runtime, "triad", {"operation": "verify"})["result"]["verified"] is True


def _guardian(allowed):
    authority = SubscriptionAuthority({"k1": KEY}, "hyba-subscriptions")
    guardian = ALHaras(
        authority,
        GuardianPolicy(
            version="organism-test",
            allowed_operations=frozenset(allowed),
            max_payload_bytes=1 << 16,
        ),
        HashChainAudit(),
    )
    now = int(time.time())
    token = authority.issue(
        SubscriptionClaims(
            subscription_id="sub-1",
            tenant_id="tenant-a",
            issuer="hyba-subscriptions",
            key_id="k1",
            capabilities=("hyba.security",),
            actors=("user-1",),
            not_before=now - 60,
            expires_at=now + 600,
            max_payload_bytes=1 << 16,
        )
    )
    return guardian, token


def test_al_haras_denies_prohibited_action_and_permits_replan(tmp_path):
    guardian, token = _guardian({"turing.capability-matrix"})
    rt = EuclidRuntime.production(creator_id="creator-1", state_dir=tmp_path, guardian=guardian)
    try:
        denied = _dispatch(
            rt, "turing", {"operation": "run-program", "program": BELL}, subscription_token=token
        )
        assert denied["allowed"] is False
        assert denied["governance"]["guardian"] == "al_haras"
        assert "result" not in denied
        assert any(r.kind == "governance-denial" for r in rt.evidence.records)
        assert rt.reachability.stage("al_haras.guardian") is ReachabilityStage.CHANGES_DECISION
        replanned = _dispatch(
            rt, "turing", {"operation": "capability-matrix"}, subscription_token=token
        )
        assert replanned["allowed"] is True and replanned["governance"]["allowed"] is True
        no_token = _dispatch(rt, "turing", {"operation": "capability-matrix"})
        assert no_token["allowed"] is False
    finally:
        rt.close()


def test_salamander_detects_repairs_and_verifies_bounded_fault(runtime):
    runtime.registry.get("chronus").health = Health.DEGRADED
    vetoed = _dispatch(runtime, "chronus", {"operation": "census"})
    assert vetoed["allowed"] is False and vetoed["health"] == "degraded"
    result = runtime.heal_organ("chronus", reason="injected degradation")
    assert result.status == "VERIFIED" and result.verified
    assert runtime.registry.get("chronus").health is Health.HEALTHY
    assert _dispatch(runtime, "chronus", {"operation": "census"})["allowed"] is True
    assert (
        runtime.reachability.stage("salamander.control_plane") is ReachabilityStage.FEEDBACK_CLOSED
    )
    assert any(r.kind == "salamander-action" for r in runtime.evidence.records)


def test_salamander_does_not_mark_unverifiable_repair_verified(runtime):
    runtime.registry.get("triad").health = Health.DEGRADED
    triad = runtime.registry.get("triad")
    original = triad.handler
    triad.handler = lambda request: (
        {"verified": False} if request.get("operation") == "verify" else original(request)
    )
    result = runtime.heal_organ("triad", reason="custody integrity failure")
    assert result.verified is False
    assert runtime.registry.get("triad").health is Health.DEGRADED


def test_reachability_evidence_survives_restart(tmp_path):
    rt = EuclidRuntime.production(creator_id="creator-1", state_dir=tmp_path)
    try:
        _dispatch(rt, "turing", {"operation": "run-program", "program": BELL})
    finally:
        rt.close()
    loaded = ReachabilityMatrix.load(tmp_path / "cognition_reachability.json")
    assert loaded.stage("turing.backends") is ReachabilityStage.OUTCOME_OBSERVED
    assert loaded.stage("chronus.backend_registry") is ReachabilityStage.REACHABLE


def test_unconstructable_owner_is_recorded_unavailable(tmp_path, monkeypatch):
    def broken():
        raise ImportError("turing backends not installed")

    monkeypatch.setattr(adapters, "TuringQuantumOrgan", broken)
    rt = EuclidRuntime.production(creator_id="creator-1", state_dir=tmp_path)
    try:
        report = rt.startup_report()["organism"]
        assert "turing" not in report["specialists"]
        assert "turing backends not installed" in report["unavailable"]["turing"]
        with pytest.raises(ValueError):
            _dispatch(rt, "turing", {"operation": "capability-matrix"})
    finally:
        rt.close()


def test_mining_truth_is_not_delegated_to_specialists(runtime):
    forbidden = runtime.startup_report()["authority_boundary"]["forbidden"]
    assert "sha256d" in forbidden
    for organ in ("turing", "chronus", "triad"):
        assert runtime.registry.get(organ).authority.value == "read-only"
