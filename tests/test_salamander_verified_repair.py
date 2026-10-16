"""Real AL HARAS/control-plane execution with a bounded in-memory unit actuator.

No production credentials, mining, source mutation, AGI/ASI or custody claims.
"""

from dataclasses import replace
import time

import pytest

from Intelligence.salamander import SelfRepairEngine, RepairProposal
from al_haras.audit import HashChainAudit
from al_haras.entitlements import SubscriptionAuthority, SubscriptionClaims
from al_haras.guardian import ALHaras, GuardianPolicy
from salamander.authority import ALHarasActionAuthorizer
from salamander.control_plane import ActionRegistry, AutonomicControlPlane
from salamander.models import ActionKind, ActionRequest


def test_safe_diagnosis_without_executor_is_not_healing():
    engine = SelfRepairEngine()
    proposal = engine.diagnose("timeout", {"component": "batch-worker"})
    assert engine.apply_repair(proposal) is False
    assert proposal.applied is False
    assert engine.status()["successful_repairs"] == 0
    assert engine.status()["pending_proposals"] == 1


def test_unissued_safe_proposal_is_not_applied():
    engine = SelfRepairEngine()
    forged = RepairProposal("forged", "worker", "timeout", "claim", "reduce_batch_size")
    assert engine.apply_repair(forged) is False
    assert forged.applied is False
    assert engine.status()["successful_repairs"] == 0


def test_mutable_applied_flag_is_not_verified_status():
    engine = SelfRepairEngine()
    proposal = engine.diagnose("timeout", {"component": "batch-worker"})
    proposal.applied = True
    status = engine.status()
    assert status["pending_proposals"] == 1
    assert status["proposals"][0]["applied"] is False


@pytest.fixture
def composition():
    state = {"batch_size": 16, "calls": 0, "probe_calls": 0, "probe_ok": True, "fail": False}
    registry = ActionRegistry()

    def reduce_batch(request):
        state["calls"] += 1
        if state["fail"]:
            raise RuntimeError("unit actuator failed")
        # This actual unit action respects the admitted integer bound.
        state["batch_size"] = request.bounds["batch_size"]
        return {"claimed_success": True}

    def independent_probe(_request, _response):
        state["probe_calls"] += 1
        return {
            "verified": state["probe_ok"] and state["batch_size"] == 8,
            "evidence_ref": "unit:separate-batch-probe",
            "observations": {"batch_size": state["batch_size"]},
        }

    registry.register(
        "bounded-batch",
        {ActionKind.THROTTLE},
        reduce_batch,
        verifier_id="unit-independent-reader",
        verifier=independent_probe,
    )
    authority = SubscriptionAuthority(
        {"unit": b"unit-test-only-not-production-key-12345"}, issuer="unit"
    )
    now = int(time.time())
    token = authority.issue(
        SubscriptionClaims(
            "unit", "tenant", "unit", "unit", ("hyba.security",), ("actor",), now - 1, now + 3600
        )
    )
    tokens = {"current": token}
    guardian = ALHaras(
        authority,
        GuardianPolicy("unit", allowed_operations=frozenset({"salamander.throttle"})),
        HashChainAudit(),
    )
    plane = AutonomicControlPlane(
        registry=registry, authorizer=ALHarasActionAuthorizer(guardian, lambda _: tokens["current"])
    )

    def builder(proposal):
        return ActionRequest(
            proposal.proposal_id,
            ActionKind.THROTTLE,
            "bounded-batch",
            "tenant",
            proposal.target,
            proposal.description,
            {"batch_size": 8, "max_attempts": 1},
            (),
            "unit:" + proposal.proposal_id,
            "actor",
        )

    return state, plane, builder, tokens


def engine_proposal(composition, builder=None):
    state, plane, default_builder, tokens = composition
    engine = SelfRepairEngine(control_plane=plane, request_builder=builder or default_builder)
    proposal = engine.diagnose("timeout", {"component": "batch-worker"})
    return engine, proposal, state, plane, tokens


def test_authorized_real_action_and_separate_probe_are_required(composition):
    engine, proposal, state, plane, _ = engine_proposal(composition)
    assert engine.apply_repair(proposal) is True
    assert state["batch_size"] == 8
    assert state["calls"] == 1 and state["probe_calls"] == 1
    assert proposal.applied is True
    status = engine.status()
    assert status["successful_repairs"] == 1
    assert status["proposals"][0]["verification_ref"]
    assert plane.ledger.verify() is True


def test_repeated_apply_does_not_repeat_actuation_or_success(composition):
    engine, proposal, state, _, _ = engine_proposal(composition)
    assert engine.apply_repair(proposal) is True
    assert engine.apply_repair(proposal) is False
    assert state["calls"] == 1
    assert engine.status()["successful_repairs"] == 1


def test_handler_claim_is_not_postcondition_evidence(composition):
    engine, proposal, state, _, _ = engine_proposal(composition)
    state["probe_ok"] = False
    assert engine.apply_repair(proposal) is False
    assert state["calls"] == 1 and state["probe_calls"] == 1
    assert proposal.applied is False
    assert engine.status()["successful_repairs"] == 0


def test_missing_entitlement_prevents_actuator(composition):
    engine, proposal, state, _, tokens = engine_proposal(composition)
    tokens["current"] = ""
    assert engine.apply_repair(proposal) is False
    assert state["calls"] == 0 and state["probe_calls"] == 0
    assert engine.status()["successful_repairs"] == 0


def test_actuator_exception_is_not_success(composition):
    engine, proposal, state, _, _ = engine_proposal(composition)
    state["fail"] = True
    assert engine.apply_repair(proposal) is False
    assert state["calls"] == 1 and state["probe_calls"] == 0
    assert proposal.applied is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("target", "other-worker"),
        ("action_id", "other-action"),
        ("kind", ActionKind.REPLAN),
        ("handler", "unregistered"),
    ],
)
def test_wrong_request_cannot_actuate(composition, field, value):
    default = composition[2]
    engine, proposal, state, _, _ = engine_proposal(
        composition, lambda p: replace(default(p), **{field: value})
    )
    assert engine.apply_repair(proposal) is False
    assert state["calls"] == 0
    assert engine.status()["successful_repairs"] == 0


def test_diagnosed_proposal_cannot_be_retargeted(composition):
    engine, proposal, state, _, _ = engine_proposal(composition)
    proposal.target = "other-worker"
    assert engine.apply_repair(proposal) is False
    assert state["calls"] == 0


def test_unsupported_failure_is_review_only(composition):
    state, plane, builder, _ = composition
    engine = SelfRepairEngine(control_plane=plane, request_builder=builder)
    proposal = engine.diagnose("unknown_failure", {"component": "worker"})
    assert engine.apply_repair(proposal) is False
    assert state["calls"] == 0


def test_fake_control_plane_is_not_authority():
    class Fake:
        def execute(self, _):
            return {"verified": True}

    engine = SelfRepairEngine(control_plane=Fake(), request_builder=lambda _: None)
    proposal = engine.diagnose("timeout", {"component": "worker"})
    assert engine.apply_repair(proposal) is False
    assert engine.status()["successful_repairs"] == 0


def test_builder_cannot_retarget_the_proposal(composition):
    default = composition[2]

    def retarget(proposal):
        proposal.target = "other-worker"
        return default(proposal)

    engine, proposal, state, _, _ = engine_proposal(composition, retarget)
    assert engine.apply_repair(proposal) is False
    assert state["calls"] == 0


def test_shared_policy_denies_internal_recovery(composition):
    state, plane, builder, _ = composition
    # A concrete entitlement boundary, not an AGI/ASI classifier.
    plane.authorizer.guardian.policy = GuardianPolicy(
        "unit-shared-restricted", allowed_operations=frozenset({"analytics.predict"})
    )
    engine = SelfRepairEngine(control_plane=plane, request_builder=builder)
    proposal = engine.diagnose("timeout", {"component": "batch-worker"})
    assert engine.apply_repair(proposal) is False
    assert state["calls"] == 0 and state["probe_calls"] == 0
    assert engine.status()["successful_repairs"] == 0


def test_capacity_accessor_is_not_duplicated():
    import ast
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "Intelligence/salamander.py"
    tree = ast.parse(path.read_text())
    manager = next(
        n
        for n in tree.body
        if isinstance(n, ast.ClassDef) and n.name == "SalamanderPoincareAllocationManager"
    )
    accessors = [
        n
        for n in manager.body
        if isinstance(n, ast.FunctionDef) and n.name == "allocated_slots_count"
    ]
    assert len(accessors) == 1
    assert ast.unparse(accessors[0].body[0]) == "return len(self._slots)"
