"""SALAMANDER Mining — Workload Contract & API Lock acceptance.

Source-bound verification of the pinned mining-mode contract (commit cd80d037):

* Mode set: NORMAL, DE_RATE, FREEZE_SPECULATION, RECOVERING, PAUSED, FAULTED
* Freeze-speculation classification and derived-mode precedence
* 10 s supervisor TTL
* Control surface {"op":"salamander_mode"} -> {"status":"ok","mode":...} /
  {"status":"error","reason":...}; only ValueError becomes an error response
* AL HARAS authorisation: one receipt per dispatch, hash-chain re-read,
  1024 pending-grant budget, exact PermissionError strings
* Result / idempotency / replay / timeout rules
* chronus.production-mining-evidence.v1 / chronus.production-mining-integration.v1
  schemas with the enforced authority map
"""

from __future__ import annotations

import time

import pytest

from al_haras import (
    ALHaras,
    GuardianPolicy,
    HashChainAudit,
    SubscriptionAuthority,
    SubscriptionClaims,
)

from chronus.mla1517.mining.production_integration import (
    EVIDENCE_SCHEMA,
    ProductionIntegrationError,
    ProductionMiningIntegration,
    SCHEMA as INTEGRATION_SCHEMA,
    digest as mining_digest,
)
from chronus.mla1517.mining.recovery_authority import (
    FREEZING_MODES,
    SALAMANDER_MODES,
    RecoveryGovernor,
    RecoveryRecord,
)

from salamander.authority import ALHarasActionAuthorizer
from salamander.control_plane import (
    ActionRegistry,
    ActionRequest,
    ActionKind,
    AutonomicControlPlane,
    EvidenceLedger,
    FailClosed,
)
from salamander.control_plane import RecoveryPlan, RecoveryStep
from salamander.models import ActionResult

# ---------------------------------------------------------------- fixtures


def _make_guardian(*, allowed_operations=None, issuer="unit"):
    key_material = b"acceptance-unit-key-material-32-bytes!!"
    signer = SubscriptionAuthority({issuer: key_material}, issuer=issuer)
    now = int(time.time())
    token = signer.issue(SubscriptionClaims(
        subscription_id="sub:acceptance", tenant_id="tenant-a", issuer=issuer,
        key_id=issuer, capabilities=("hyba.security",), actors=("acceptance-actor",),
        not_before=now - 1, expires_at=now + 3600,
    ))
    ops = allowed_operations or frozenset({"salamander.replan", "salamander.rollback"})
    guardian = ALHaras(
        signer,
        GuardianPolicy(version="acceptance", allowed_operations=ops),
        HashChainAudit(),
    )
    return guardian, token


def _make_request(action_id="a", kind=ActionKind.REPLAN, handler="bounded",
                  tenant_id="tenant-a", actor_id="acceptance-actor",
                  idempotency_key="idem:a", target="target", reason="test"):
    return ActionRequest(
        action_id, kind, handler, tenant_id, target, reason,
        {"max_attempts": 1}, (), idempotency_key, actor_id,
    )


def _make_plane(*, token, allowed_operations=None, max_recoveries_per_target=2):
    guardian, _ = _make_guardian(allowed_operations=allowed_operations)
    adapter = ALHarasActionAuthorizer(guardian, lambda _: token)
    registry = ActionRegistry()
    registry.register(
        "bounded",
        {ActionKind.REPLAN, ActionKind.THROTTLE, ActionKind.FAILOVER,
         ActionKind.REBUILD_PROJECTION, ActionKind.ROLLBACK},
        lambda _: {"post_observation": "healthy"},
        verifier_id="independent-test-probe",
        verifier=lambda _request, response: {
            "verified": response.get("post_observation") == "healthy",
            "evidence_ref": "probe:healthy",
            "observations": {"health": response.get("post_observation")},
        },
    )
    return AutonomicControlPlane(
        registry=registry, clock_ns=time.time_ns,
        authorizer=adapter, max_recoveries_per_target=max_recoveries_per_target,
    )


def _control_surface(governor, mode, recovery_id=None):
    """Mirror of IntelligentPoolCoordinator._handle_control_request for salamander_mode."""
    try:
        governor.external_mode(mode, recovery_id)
    except ValueError as exc:
        return {"status": "error", "reason": str(exc)}
    return {"status": "ok", "mode": governor.mode}


# ---------------------------------------------------------------- mode set & freeze speculation


def test_mode_set_is_exactly_six_pinned_modes():
    assert SALAMANDER_MODES == {
        "NORMAL", "DE_RATE", "FREEZE_SPECULATION", "RECOVERING", "PAUSED", "FAULTED",
    }


def test_freezing_modes_are_exactly_the_speculation_freezers():
    assert FREEZING_MODES == {
        "FREEZE_SPECULATION", "RECOVERING", "PAUSED", "FAULTED",
    }


def test_non_freezing_modes_do_not_freeze_speculation():
    governor = RecoveryGovernor()
    for mode in ("NORMAL", "DE_RATE"):
        governor._external_mode = mode
        governor._external_seen = governor._clock()
        assert governor.freezes_speculation is False


def test_freezing_modes_freeze_speculation():
    governor = RecoveryGovernor()
    for mode in ("FREEZE_SPECULATION", "RECOVERING", "PAUSED", "FAULTED"):
        governor._external_mode = mode
        governor._external_seen = governor._clock()
        assert governor.freezes_speculation is True


# ---------------------------------------------------------------- derived-mode precedence


def test_precedence_external_freezing_mode_wins():
    governor = RecoveryGovernor(clock=lambda: 100.0)
    governor.external_mode("FAULTED", "recovery:1")
    assert governor.mode == "FAULTED"


def test_precedence_open_recovery_reports_recovering():
    governor = RecoveryGovernor(clock=lambda: 100.0)
    governor.external_mode("NORMAL")  # supervisor alive, non-freezing
    record = RecoveryRecord("recovery:1", "self_healing_agent", ("SEVER_LANE",), "fault")
    governor._records["recovery:1"] = record
    assert governor.mode == "RECOVERING"


def test_precedence_faulted_when_no_open_recovery():
    governor = RecoveryGovernor(clock=lambda: 100.0)
    governor._faulted = True
    assert governor.mode == "FAULTED"


def test_precedence_external_non_freezing_when_alive():
    governor = RecoveryGovernor(clock=lambda: 100.0)
    governor.external_mode("DE_RATE")
    assert governor.mode == "DE_RATE"


def test_precedence_normal_when_salamander_dead():
    governor = RecoveryGovernor(clock=lambda: 100.0)
    governor._external_seen = None
    assert governor.mode == "NORMAL"


# ---------------------------------------------------------------- supervisor TTL


def test_salamander_ttl_default_is_ten_seconds():
    governor = RecoveryGovernor()
    assert governor._ttl == 10.0


def test_supervisor_expires_after_ttl():
    tick = [0.0]
    governor = RecoveryGovernor(clock=lambda: tick[0], salamander_ttl_s=10.0)
    governor.external_mode("NORMAL")
    assert governor.salamander_alive() is True
    tick[0] = 10.0  # exactly at TTL boundary -> not strictly less -> dead
    assert governor.salamander_alive() is False
    assert governor.mode == "NORMAL"


# ---------------------------------------------------------------- control surface


def test_external_mode_normal_opens_no_record():
    governor = RecoveryGovernor(clock=lambda: 100.0)
    record = governor.external_mode("NORMAL")
    assert record is None
    assert len(governor._records) == 0


def test_external_mode_freezing_opens_record():
    governor = RecoveryGovernor(clock=lambda: 100.0)
    record = governor.external_mode("RECOVERING", "recovery:1")
    assert record is not None
    assert record.recovery_id == "recovery:1"
    assert record.state.name == "DISPATCHED"
    assert governor._external_recovery_id == "recovery:1"


def test_control_surface_ok_for_valid_mode():
    governor = RecoveryGovernor(clock=lambda: 100.0)
    result = _control_surface(governor, "DE_RATE")
    assert result == {"status": "ok", "mode": "DE_RATE"}


def test_control_surface_error_only_for_value_error():
    governor = RecoveryGovernor(clock=lambda: 100.0)
    result = _control_surface(governor, "BOGUS_MODE")
    assert result["status"] == "error"
    assert "unknown Salamander mode" in result["reason"]


def test_control_surface_ok_returns_governed_mode():
    governor = RecoveryGovernor(clock=lambda: 100.0)
    governor.external_mode("PAUSED", "recovery:1")
    result = _control_surface(governor, "PAUSED", "recovery:1")
    assert result["status"] == "ok"
    assert result["mode"] == "PAUSED"


# ---------------------------------------------------------------- AL HARAS authorisation


def test_pending_grant_budget_default_is_1024():
    guardian, token = _make_guardian()
    adapter = ALHarasActionAuthorizer(guardian, lambda _: token)
    assert adapter.max_pending_grants == 1024


def test_permission_error_unavailable_when_authorizer_raises():
    def boom(record, command, target):
        raise RuntimeError("authorizer down")

    governor = RecoveryGovernor(recovery_authorizer=boom, require_authorization=True)
    record = RecoveryRecord("r1", "salamander", ("SEVER_LANE",), "test")
    with pytest.raises(PermissionError, match="AL HARAS recovery authorization unavailable"):
        governor._authorize_dispatch(record, "SEVER_LANE")


def test_permission_error_denied_carry_reason():
    def denying(record, command, target):
        return {"allowed": False, "reason": "policy denies recovery", "evidence_id": "e1"}

    governor = RecoveryGovernor(recovery_authorizer=denying, require_authorization=True)
    record = RecoveryRecord("r1", "salamander", ("SEVER_LANE",), "test")
    with pytest.raises(
        PermissionError,
        match="AL HARAS recovery authorization denied:policy denies recovery",
    ):
        governor._authorize_dispatch(record, "SEVER_LANE")


def test_permission_error_no_evidence_identity():
    def no_evidence(record, command, target):
        return {"allowed": True, "reason": "ok", "evidence_id": None}

    governor = RecoveryGovernor(recovery_authorizer=no_evidence, require_authorization=True)
    record = RecoveryRecord("r1", "salamander", ("SEVER_LANE",), "test")
    with pytest.raises(
        PermissionError, match="AL HARAS recovery authorization has no evidence identity"
    ):
        governor._authorize_dispatch(record, "SEVER_LANE")


def test_grant_receipt_is_re_read_from_hash_chain():
    """One receipt per dispatch; validate_decision re-reads the AL HARAS chain."""
    guardian, token = _make_guardian()
    adapter = ALHarasActionAuthorizer(guardian, lambda _: token)
    request = _make_request()
    decision = dict(adapter(request))
    assert decision.get("allowed") is True
    assert decision.get("authority") == "AL_HARAS"
    # Re-reading the chain for the same bound request validates.
    assert adapter.validate_decision(request, decision) is True
    # A different request bound to the same receipt fails validation.
    other = _make_request(action_id="other", idempotency_key="idem:other")
    assert adapter.validate_decision(other, decision) is False


# ---------------------------------------------------------------- result / idempotency / replay / timeout


def test_idempotency_key_reuse_for_different_request_is_rejected():
    guardian, token = _make_guardian()
    plane = _make_plane(token=token)
    request = _make_request(idempotency_key="idem:shared")
    # First dispatch executes and is cached.
    first = plane.execute(request)
    assert isinstance(first, ActionResult)
    # Same idempotency key, different request body -> fail closed.
    different = _make_request(action_id="b", idempotency_key="idem:shared")
    with pytest.raises(FailClosed, match="idempotency key reused for different request"):
        plane.execute(different)


def test_same_idempotency_key_returns_cached_result():
    guardian, token = _make_guardian()
    plane = _make_plane(token=token)
    request = _make_request(idempotency_key="idem:cached")
    first = plane.execute(request)
    second = plane.execute(request)
    assert second.action_id == first.action_id
    assert second.status == first.status


def test_recovery_deadline_elapsed_is_timeout_fail_closed():
    guardian, token = _make_guardian()
    plane = _make_plane(token=token)
    now = time.time_ns()
    plan = RecoveryPlan("timeout-recovery", "tenant-a", "target",
                        (RecoveryStep("step", _make_request()),), 1, now - 1)
    with pytest.raises(FailClosed, match="recovery deadline elapsed"):
        plane.recover(plan)


# ---------------------------------------------------------------- production-mining schemas & authority map


def test_production_integration_schema_enforced():
    manifest = {
        "schema": INTEGRATION_SCHEMA,
        "base_sha": "c0258303c4eed59f0a4fcae3e62c908f641a57a7",
        "chronus104_corpus_sha256": (
            "0b4035e138256cfed08ba5d9e1b0058dc8e7c0dbce2e0ccb50039254de4e1712"
        ),
        "truth_states": {
            "f64": "UNSUPPORTED",
            "opencl.BINET_EXACT": "UNSUPPORTED",
            "FOLDED_NATIVE": "OPEN",
            "physical_opencl": "PHYSICAL_EVIDENCE_REQUIRED",
            "acceptance": "NOT_RUN",
            "ci": "NOT_REPORTED",
        },
        "authority": {
            "work_identity": "stratum_adapter",
            "sha256d_target": "proof_adapter_and_host_recheck",
            "pool_outcome": "literal_pool_response",
            "physical_execution": "execution_router",
            "recovery": "recovery_governor",
            "custody": "existing_aethel_and_causal_ledgers",
        },
    }
    x = ProductionMiningIntegration(manifest)
    assert x.manifest_digest == mining_digest(manifest)
    assert x.manifest["base_sha"] == "c0258303c4eed59f0a4fcae3e62c908f641a57a7"


def test_production_integration_authority_map_cannot_be_replaced():
    base = {
        "schema": INTEGRATION_SCHEMA,
        "base_sha": "c0258303c4eed59f0a4fcae3e62c908f641a57a7",
        "chronus104_corpus_sha256": (
            "0b4035e138256cfed08ba5d9e1b0058dc8e7c0dbce2e0ccb50039254de4e1712"
        ),
        "truth_states": {
            "f64": "UNSUPPORTED", "opencl.BINET_EXACT": "UNSUPPORTED",
            "FOLDED_NATIVE": "OPEN", "physical_opencl": "PHYSICAL_EVIDENCE_REQUIRED",
            "acceptance": "NOT_RUN", "ci": "NOT_REPORTED",
        },
        "authority": {
            "work_identity": "stratum_adapter",
            "sha256d_target": "proof_adapter_and_host_recheck",
            "pool_outcome": "literal_pool_response",
            "physical_execution": "execution_router",
            "recovery": "recovery_governor",
            "custody": "existing_aethel_and_causal_ledgers",
        },
    }
    tampered = dict(base)
    tampered["authority"] = dict(base["authority"])
    tampered["authority"]["pool_outcome"] = "planner"
    with pytest.raises(ProductionIntegrationError, match="may not replace mining truth owners"):
        ProductionMiningIntegration(tampered)


def test_evidence_records_use_production_mining_schema():
    body = {"schema": EVIDENCE_SCHEMA, "kind": "PLAN", "manifest_sha256": "abc"}
    sealed = {**body, "evidence_sha256": mining_digest(body)}
    assert sealed["schema"] == EVIDENCE_SCHEMA
    assert EVIDENCE_SCHEMA == "chronus.production-mining-evidence.v1"
    assert INTEGRATION_SCHEMA == "chronus.production-mining-integration.v1"

