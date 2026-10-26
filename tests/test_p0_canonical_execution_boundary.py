"""P0 guard/router boundary with explicit executor-result fixtures."""

from dataclasses import replace
from types import SimpleNamespace

import pytest

from chronus.mla1517.mining.execution_router import ExecutionRouter
from chronus.mla1517.mining.resident_router import ProductionExecutionRouter
from chronus.mla1517.mining.pythia_search import SEARCH_ARCHITECTURE_ID
from chronus.mla1517.mining.search_authority_guard import (
    HENDRIX,
    canonical_nonce_order,
    require_canonical_execution,
)
from chronus.mla1517.mining.search_plan import SearchPlan


def plan(canonical=True, order=HENDRIX):
    return SearchPlan(
        job_fingerprint="f" * 64,
        pool_session_id="fixture-session",
        generation=1,
        base_step=0,
        window=64,
        extranonce2="00000000",
        lane_order=tuple(range(32)),
        preferred_face=0,
        dispatch_breadth=32,
        executor_route="cpu_reference",
        policy_id="fixture",
        evidence_refs=(
            {"search_architecture": SEARCH_ARCHITECTURE_ID}
            if canonical
            else {}
        ),
        created_at=1.0,
        nonce_order=order,
    )


def record(**updates):
    # Executor evidence fixture, not a physical-execution assertion.
    fields = dict(
        completed_work_items=64,
        planned_nonce_order=HENDRIX,
        requested_nonce_order=HENDRIX,
        executed_nonce_order=HENDRIX,
        nonce_order_fallback_reason=None,
    )
    return SimpleNamespace(**{**fields, **updates})


@pytest.mark.parametrize(
    "order", [None, "", "m32_turing_complete", "sequential"]
)
def test_canonical_identity_is_literal(order):
    with pytest.raises(ValueError):
        canonical_nonce_order(order)
    assert canonical_nonce_order(HENDRIX) == HENDRIX


@pytest.mark.parametrize(
    "field",
    ["planned_nonce_order", "requested_nonce_order", "executed_nonce_order"],
)
@pytest.mark.parametrize("value", [None, "m32_turing_complete", "sequential"])
def test_positive_work_requires_complete_identity_chain(field, value):
    with pytest.raises(ValueError):
        require_canonical_execution(plan(), record(**{field: value}))


@pytest.mark.parametrize("reason", ["substituted", "", "kernel_unavailable"])
def test_canonical_execution_refuses_algorithm_fallback(reason):
    with pytest.raises(ValueError):
        require_canonical_execution(
            plan(), record(nonce_order_fallback_reason=reason)
        )


def test_zero_work_refusal_does_not_fabricate_execution():
    require_canonical_execution(
        plan(),
        record(
            completed_work_items=0,
            executed_nonce_order=None,
        ),
    )


def test_router_classifies_canonical_path_independently_and_blocks_candidate(
    monkeypatch,
):
    router = ProductionExecutionRouter.__new__(ProductionExecutionRouter)
    router._hasher = SimpleNamespace(last_batch_evidence={"old": True})
    returned = record(executed_nonce_order="m32_turing_complete")
    candidate = {
        "nonce": 1
    }  # Deliberately not a proof; must not escape the seam.
    monkeypatch.setattr(
        ExecutionRouter, "execute_plan", lambda *a, **kw: (returned, candidate)
    )
    # Missing fallback does not establish canonical/correct execution.
    with pytest.raises(ValueError, match="executed-order"):
        router.execute_plan(plan(), b"", b"")
    assert router._hasher.last_batch_evidence is None


def test_noncanonical_compatibility_is_not_classified_by_missing_fallback(
    monkeypatch,
):
    router = ProductionExecutionRouter.__new__(ProductionExecutionRouter)
    router._hasher = SimpleNamespace()
    returned = record(
        planned_nonce_order="m32_turing_complete",
        requested_nonce_order="m32_turing_complete",
        executed_nonce_order="m32_turing_complete",
    )
    monkeypatch.setattr(
        ExecutionRouter, "execute_plan", lambda *a, **kw: (returned, None)
    )
    actual, candidate = router.execute_plan(
        plan(False, "m32_turing_complete"), b"", b""
    )
    assert actual is returned and candidate is None


def test_canonical_wrong_plan_order_refused_before_executor(monkeypatch):
    router = ProductionExecutionRouter.__new__(ProductionExecutionRouter)
    router._hasher = SimpleNamespace()
    monkeypatch.setattr(
        ExecutionRouter,
        "execute_plan",
        lambda *a, **kw: pytest.fail("dispatched"),
    )
    with pytest.raises(ValueError, match="Hendrix"):
        router.execute_plan(
            replace(plan(), nonce_order="m32_turing_complete"), b"", b""
        )


def test_canonical_exact_execution_may_keep_named_device_fallback(monkeypatch):
    router = ProductionExecutionRouter.__new__(ProductionExecutionRouter)
    router._hasher = SimpleNamespace()
    returned = record(fallback_reason="chronus_batch_unavailable")
    candidate = {"nonce": 1}
    monkeypatch.setattr(
        ExecutionRouter, "execute_plan", lambda *a, **kw: (returned, candidate)
    )
    actual, found = router.execute_plan(plan(), b"", b"")
    assert actual is returned and found is candidate
