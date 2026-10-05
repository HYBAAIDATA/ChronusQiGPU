"""Whole-organism wiring through the canonical EUCLID composition root.

Every assertion runs the production path (``EuclidRuntime.production``) and the
owners' real implementations; unavailable substrates are asserted unavailable.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

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


def test_restart_restores_the_whole_organism_not_just_state(tmp_path):
    """A restored runtime must be able to reach the same organs as a fresh one.

    Regression: ``EuclidRuntime.restore`` re-created the organ registry after
    ``production()`` had already composed TURING/CHRONUS/Triad, silently
    dropping every specialist. State survived the restart while the compute,
    quantum and custody planes did not — a restored organism that could no
    longer do anything the original could.
    """
    checkpoint = tmp_path / "runtime.json"
    first = EuclidRuntime.production(creator_id="creator-1", state_dir=tmp_path)
    try:
        expected = sorted(item["organ_id"] for item in first.registry.report())
        assert expected, "the production root must compose specialists"
        first.save(checkpoint)
    finally:
        first.close()

    restored = EuclidRuntime.restore(checkpoint, state_dir=tmp_path)
    try:
        assert sorted(item["organ_id"] for item in restored.registry.report()) == expected
        # Reachability must be restored too: a restarted organism that reports
        # its organs as unreachable would misreport its own capability.
        for component in ("turing.backends", "chronus.backend_registry", "aethel.triad"):
            assert restored.reachability.stage(component) is ReachabilityStage.REACHABLE
        # And a specialist must actually execute after the restart.
        out = _dispatch(restored, "turing", {"operation": "run-program", "program": BELL})
        assert out["allowed"] and out["result"]["executed"]
    finally:
        restored.close()


def test_restored_checkpoint_rejects_tampering(tmp_path):
    """A mutated checkpoint must fail closed rather than restore partially."""
    checkpoint = tmp_path / "runtime.json"
    first = EuclidRuntime.production(creator_id="creator-1", state_dir=tmp_path)
    try:
        first.save(checkpoint)
    finally:
        first.close()
    payload = json.loads(checkpoint.read_text(encoding="utf-8"))
    payload["creator_id"] = "attacker"
    checkpoint.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        EuclidRuntime.restore(checkpoint, state_dir=tmp_path)


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


def _route(rt, request, **kw):
    return rt.route_specialist(request, tenant_id="tenant-a", actor="user-1", **kw)


def test_route_specialist_selects_organ_without_caller_naming_it(runtime):
    """Self-directed dispatch: the organism picks the organ."""
    out = _route(runtime, {"operation": "run-program", "program": BELL})
    assert out["allowed"] and out["routed"] is True
    assert out["organ"] == "turing"
    assert out["result"]["executed"] and out["result"]["owner"] == "TURING"
    assert out["routing"]["candidates"] == ["turing"]
    assert (
        runtime.reachability.stage("euclid.organism_routing") is ReachabilityStage.CHANGES_DECISION
    )


def test_route_specialist_refuses_unroutable_requests(runtime):
    missing = _route(runtime, {})
    assert missing["allowed"] is False and missing["routed"] is False
    assert "no operation" in missing["reason"]

    unknown = _route(runtime, {"operation": "not-a-real-operation"})
    assert unknown["allowed"] is False and unknown["routed"] is False
    assert unknown["candidates"] == []
    assert "no specialist declares" in unknown["reason"]
    # A refused route must not have dispatched anything.
    assert "result" not in unknown


def test_route_specialist_refuses_when_every_candidate_degraded(runtime):
    runtime.registry.get("chronus").health = Health.DEGRADED
    out = _route(runtime, {"operation": "census"})
    assert out["allowed"] is False and out["routed"] is False
    assert out["candidates"] == ["chronus"]
    assert out["excluded_unhealthy"] == ["chronus"]


def test_route_specialist_history_steers_pick_and_verifies_transfer(runtime):
    """Recorded outcomes, not caller preference, steer selection.

    Two organs declare the same operation; cold order would pick the
    lexicographically first. A durable delegation-result record for the
    second observably changes the pick — the first TRANSFER_VERIFIED
    specialist-selection result."""
    runtime.register_specialist(
        "aux-a", lambda req: {"ok": True, "organ": "aux-a"}, operations={"probe"}
    )
    runtime.register_specialist(
        "aux-b", lambda req: {"ok": True, "organ": "aux-b"}, operations={"probe"}
    )
    for organ_id in ("aux-a", "aux-b"):
        runtime.rights.grant(runtime.creator_id, organ_id, f"{organ_id}.request", "dispatch")
    # No history yet: selection falls back to deterministic default order.
    cold = runtime.select_specialist("probe")
    assert cold["organ_id"] == "aux-a" and cold["memory_influenced"] is False

    # One recorded successful outcome for aux-b steers the next pick.
    seeded = _dispatch(runtime, "aux-b", {"operation": "probe"})
    assert seeded["allowed"]
    warm = _route(runtime, {"operation": "probe"})
    assert warm["allowed"] and warm["organ"] == "aux-b"
    assert warm["routing"]["memory_influenced"] is True
    assert warm["routing"]["default_pick"] == "aux-a"
    assert (
        runtime.reachability.stage("euclid.organism_routing") is ReachabilityStage.TRANSFER_VERIFIED
    )
    readiness = runtime.startup_report()["intelligence_readiness"]
    assert readiness["transfer_verified"] is True
    assert readiness["production_certified"] is False  # never self-declared


CUSTODY_CHILD = Path(__file__).resolve().parent / "euclid_custody_restart_child.py"
CUSTODY_KEY = b"organism-custody-test-key-32b!"


def test_restart_through_theseus_custody_verified_cross_process(tmp_path):
    """Restart custody evidence must come from a fresh interpreter reading
    durable THESEUS storage — an in-process restore would prove nothing
    about survival across a process boundary."""
    from aethel.enterprise.custody import EnterpriseCustody

    custody_root = tmp_path / "custody"
    state_dir = tmp_path / "state"
    first = EuclidRuntime.production(creator_id="creator-1", state_dir=state_dir)
    custody = EnterpriseCustody(custody_root, hmac_key=CUSTODY_KEY)
    try:
        # The checkpoint embeds the chain head at snapshot time; the
        # custody-checkpoint record itself extends the live chain after.
        expected_head = first.evidence.head
        checkpoint = first.save_to_custody(custody)
    finally:
        first.close()
        custody.close()

    child = subprocess.run(
        [
            sys.executable,
            str(CUSTODY_CHILD),
            str(custody_root),
            checkpoint["record_id"],
            CUSTODY_KEY.hex(),
            str(state_dir),
        ],
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert child.returncode == 0, child.stderr[-3000:]
    report = json.loads(child.stdout.strip().splitlines()[-1])
    # The restored chain head equals the checkpointed head; the child's own
    # custody-restart record then extends it.
    assert report["restored_evidence_head"] == expected_head
    assert report["evidence_head"] != expected_head
    assert report["specialists"] == ["chronus", "triad", "turing"]
    assert report["restart_stage"] == "RESTART_VERIFIED"
    assert report["post_restart_dispatch"]["allowed"] is True
    assert report["readiness"]["restart_verified"] is True

    # The ledger the child wrote is durable for later sessions in the dir.
    resumed = EuclidRuntime.production(creator_id="creator-1", state_dir=state_dir)
    try:
        readiness = resumed.startup_report()["intelligence_readiness"]
        assert readiness["restart_verified"] is True
        assert "restart requires independent cross-process verification" not in (
            readiness["reasons"]
        )
    finally:
        resumed.close()


def test_custody_restart_refuses_unknown_record(tmp_path):
    from aethel.enterprise.custody import EnterpriseCustody

    custody = EnterpriseCustody(tmp_path / "custody", hmac_key=CUSTODY_KEY)
    try:
        with pytest.raises(KeyError):
            EuclidRuntime.restore_from_custody(
                custody, "euclid-runtime:nobody:never", state_dir=tmp_path / "state"
            )
    finally:
        custody.close()


def test_intelligence_readiness_is_computed_not_asserted(runtime):
    readiness = runtime.startup_report()["intelligence_readiness"]
    assert readiness["status"] == "NOT_CERTIFIED"
    assert readiness["production_certified"] is False
    assert readiness["restart_verified"] is False
    assert readiness["transfer_verified"] is False
    assert readiness["external_validation"] is False
    assert set(readiness["reasons"]) == {
        "restart requires independent cross-process verification",
        "transfer requires deterministic ablation-backed decision effect",
        "external validation is not present",
    }
