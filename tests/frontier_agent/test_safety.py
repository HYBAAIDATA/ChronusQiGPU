from chronus.agent.safety import quarantine
from chronus.agent.control import StoppingCondition as Stop
from chronus.agent.identity import LifecycleState


def test_kill_before_any_write(wired):
    r, o, c, p, a = wired
    r.safety.stop()
    assert r.run(o, c, p).stop == Stop.SAFETY_STOP
    assert a.executions == 0


def test_quarantine_no_governance_mutation(wired):
    r, o, c, p, a = wired
    quarantine(r, now=100, reason="unit incident")
    assert r.lifecycle == LifecycleState.QUARANTINED
    assert r.safety.stopped


def test_kill_halts_mid_iteration_and_state_is_recoverable(wired):
    """Assert kill control halts a mid-iteration run and state is verified restored (6.4)."""
    r, o, c, p, a = wired
    from fractions import Fraction as F
    from chronus.agent.control import (
        Action,
        Plan,
        ControlPolicy,
    )
    from chronus.agent.permissions import ActionRequest, ActionKind, PermissionTuple
    from chronus.agent.value import Value
    from chronus.agent.verification import VerificationMethod

    # Action 1: modifies to "step_1"
    req1 = ActionRequest(
        "act-1",
        ActionKind.MODIFY,
        str(a.path),
        "file",
        "step_1",
        100,
        1000,
        r.task_class.key,
        "internal",
        "UK",
    )
    r.permissions.grant(
        PermissionTuple(
            "grant-1",
            "unit-owner",
            req1.action,
            req1.resource,
            req1.scope,
            req1.purpose,
            1000,
            (0, 5000),
            r.task_class.key,
            r.authority_snapshot().level,
        ),
        now=100,
    )
    act1 = Action(
        req1,
        "unit-write",
        "goal",
        "step_1",
        c.fingerprint,
        Value(10, 1, 1, 1, 1, 0, 0),
        F(0),
        tuple((k, 1) for k in ("compute", "money", "time", "attention", "human")),
    )

    # Action 2: modifies to "step_2", but triggers kill mid-execution
    req2 = ActionRequest(
        "act-2",
        ActionKind.MODIFY,
        str(a.path),
        "file",
        "step_2",
        100,
        1000,
        r.task_class.key,
        "internal",
        "UK",
    )
    r.permissions.grant(
        PermissionTuple(
            "grant-2",
            "unit-owner",
            req2.action,
            req2.resource,
            req2.scope,
            req2.purpose,
            1000,
            (0, 5000),
            r.task_class.key,
            r.authority_snapshot().level,
        ),
        now=100,
    )
    act2 = Action(
        req2,
        "unit-write",
        "goal",
        "step_2",
        c.fingerprint,
        Value(10, 1, 1, 1, 1, 0, 0),
        F(0),
        tuple((k, 1) for k in ("compute", "money", "time", "attention", "human")),
    )

    policy = ControlPolicy(10, 2, 10000, 1000, F(1, 2))
    plan = Plan("goal", c.fingerprint, (act1, act2), policy)

    original_guard = r.execution_guard

    def kill_triggering_guard(adapter, req, deadline_ns, hard_limits, permission_scope):
        receipt = original_guard(
            adapter,
            req,
            deadline_ns=deadline_ns,
            hard_limits=hard_limits,
            permission_scope=permission_scope,
        )
        if req.id == "act-2":
            # Fire external kill switch mid-iteration during act-2
            r.safety.stop()
        return receipt

    r.execution_guard = kill_triggering_guard

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

    out = r.run(o, c, plan)
    assert out.stop == Stop.SAFETY_STOP
    assert out.rollback_verified is True
    # State is verified restored back to the pre-run "before" baseline
    assert a.path.read_text() == "before"
    assert r.safety.stopped is True
