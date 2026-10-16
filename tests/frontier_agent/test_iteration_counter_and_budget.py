"""Regression tests for iteration counter on success and shared retry/recovery run budget."""

from dataclasses import replace
from fractions import Fraction as F
from chronus.agent.control import (
    Action,
    Plan,
    ControlPolicy,
    ExecutionReceipt,
    StoppingCondition as Stop,
)
from chronus.agent.permissions import ActionRequest, ActionKind, PermissionTuple
from chronus.agent.resources import BudgetSet, BudgetMeter
from chronus.agent.value import Value
from chronus.agent.verification import VerificationMethod


def test_iteration_counter_advances_on_success_with_interleaved_retries(wired):
    """Test: N successful iterations (and M interleaved retries) => counter == N.

    Successful control iterations advance the counter.
    Failed/retried attempts consume iteration attempts but do not increment counter.
    """
    r, o, c, p, a = wired

    # We will build N = 3 distinct actions.
    # Action 0 will fail once, then succeed on retry (M1 = 1 retry).
    # Action 1 will fail once, then succeed on retry (M2 = 1 retry).
    # Action 2 will succeed on first attempt (M3 = 0 retries).
    # Total successful control iterations N = 3.
    # Total interleaved retries M = M1 + M2 + M3 = 2.
    # Total attempted executions = N + M = 5.

    attempts_by_action = {}

    def custom_execution_guard(adapter, req, deadline_ns, hard_limits, permission_scope):
        count = attempts_by_action.get(req.id, 0)
        attempts_by_action[req.id] = count + 1
        # Action 0 and Action 1 fail on their first attempt (attempt == 0)
        if req.id in ("act-0", "act-1") and count == 0:
            adapter.path.write_text("corrupted_interleaved_failure")
        else:
            adapter.path.write_text(req.purpose)
        return ExecutionReceipt(
            tuple((k, 1) for k in ("compute", "money", "time", "attention", "human")),
            "d" * 64,
        )

    r.execution_guard = custom_execution_guard

    actions = []
    for i in range(3):
        req = ActionRequest(
            f"act-{i}",
            ActionKind.MODIFY,
            str(a.path),
            "file",
            f"target_state_{i}",
            100,
            1000,
            r.task_class.key,
            "internal",
            "UK",
        )
        r.permissions.grant(
            PermissionTuple(
                f"grant-{i}",
                "unit-owner",
                req.action,
                req.resource,
                req.scope,
                req.purpose,
                10000,
                (0, 5000),
                r.task_class.key,
                r.authority_snapshot().level,
            ),
            now=100,
        )
        act = Action(
            req,
            "unit-write",
            "goal",
            f"target_state_{i}",
            c.fingerprint,
            Value(10, 1, 1, 1, 1, 0, 0),
            F(0),
            tuple((k, 1) for k in ("compute", "money", "time", "attention", "human")),
        )
        actions.append(act)

    # Allow up to 10 iterations total, up to 3 attempts per action
    policy = ControlPolicy(10, 3, 10000, 1000, F(1, 2))
    plan = Plan("goal", c.fingerprint, tuple(actions), policy)

    # Custom verification matching each action's expected state
    r.verification_provider = lambda act, pre, post: (
        VerificationMethod(
            f"v-{act.request.id}",
            "file-read",
            "unit-reviewer",
            "other-unit-operator",
            "other-unit-training",
            "unit-independent-group",
            F(1),
            F(1),
            F(1),
            False,
            post.state == act.expected_state,
            post.raw_evidence,
        ),
    )
    # Objective expects the final action's state: "target_state_2"
    final_obj = replace(o, expected_state="target_state_2")
    r.objective_verification_provider = lambda obj, post: (
        VerificationMethod(
            "v-goal",
            "file-acceptance",
            "unit-reviewer",
            "other-unit-operator",
            "other-unit-training",
            "unit-independent-group",
            F(1),
            F(1),
            F(1),
            False,
            post.state == obj.expected_state,
            post.raw_evidence,
        ),
    )

    out = r.run(final_obj, c, plan)

    assert out.stop == Stop.GOAL_ACHIEVED
    # Exactly N = 3 successful control iterations
    assert out.counter == 3
    assert r.counter == 3
    assert r.iteration_counter == 3
    # Exactly N + M = 3 + 2 = 5 total attempts executed
    assert out.iterations == 5
    # Verification of attempts breakdown
    assert attempts_by_action["act-0"] == 2  # 1 retry + 1 success
    assert attempts_by_action["act-1"] == 2  # 1 retry + 1 success
    assert attempts_by_action["act-2"] == 1  # 0 retries + 1 success


def test_shared_budget_boundary_with_recovery_reservation(wired):
    """Primary attempts + retries never exceed shared run budget, enforcing 2x recovery reservation."""
    r, o, c, p, a = wired

    # Each attempt reserves 2x costs: 1 for action + 1 for recovery = 2 per attempt.
    # Set compute limit = 4.
    # Attempt 0 reserves 2 (leaves 2). It fails and triggers rollback.
    # Attempt 1 (retry) reserves 2 (leaves 0). It succeeds.
    # Total reserved across run = 4 == limit. This is the exact boundary.
    r.budgets = BudgetMeter(BudgetSet(compute=4, money=100, time=10000, attention=100, human=100))

    attempt_count = 0

    def guard_fail_then_pass(adapter, req, deadline_ns, hard_limits, permission_scope):
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count == 1:
            adapter.path.write_text("failure_attempt")
        else:
            adapter.path.write_text(req.purpose)
        return ExecutionReceipt(
            tuple((k, 1) for k in ("compute", "money", "time", "attention", "human")),
            "d" * 64,
        )

    r.execution_guard = guard_fail_then_pass

    out = r.run(o, c, p)
    assert out.stop == Stop.GOAL_ACHIEVED
    assert out.counter == 1
    assert out.iterations == 2
    assert r.budgets.used["compute"] == 4


def test_recovery_budget_boundary_refusal(wired):
    """When remaining budget is insufficient for recovery reservation (2x), retry is refused."""
    r, o, c, p, a = wired

    # Set compute limit = 3.
    # Attempt 0 reserves 2 (leaving 1). Fails.
    # Attempt 1 needs 2 (for action + recovery). But only 1 is left!
    # Even though 1 unit would cover the action alone, safety requires recovery reservation.
    # Loop must stop with BUDGET_EXHAUSTED and roll back safely.
    r.budgets = BudgetMeter(BudgetSet(compute=3, money=100, time=10000, attention=100, human=100))
    a.fail = True

    out = r.run(o, c, p)
    assert out.stop == Stop.BUDGET_EXHAUSTED
    assert "budget exhausted" in out.reason
    assert a.path.read_text() == "before"
    assert r.budgets.used["compute"] == 2  # exactly attempt 0's reservation, attempt 1 refused
    assert out.counter == 0  # no successful control iterations
    assert out.iterations == 1  # only primary attempt ran before budget stop


def test_shared_iteration_budget_boundary_with_retries(wired):
    """Shared max_iterations caps total primary + retry attempts."""
    r, o, c, p, a = wired

    # Set policy: max_iterations=2, max_attempts=3.
    # If the action fails on attempt 0 and attempt 1, iterations reach 2.
    # Attempt 2 cannot run because iterations >= max_iterations (2 >= 2).
    p = replace(p, policy=replace(p.policy, max_iterations=2, max_attempts=3))
    a.fail = True

    out = r.run(o, c, p)
    assert out.stop == Stop.BUDGET_EXHAUSTED
    assert out.reason == "shared iteration limit"
    assert out.iterations == 2
    assert out.counter == 0
    assert a.path.read_text() == "before"
