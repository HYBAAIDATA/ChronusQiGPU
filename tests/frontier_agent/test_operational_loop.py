from dataclasses import replace
from chronus.agent.control import StoppingCondition as Stop


def test_real_write_and_no_self_promotion(wired):
    r, o, c, p, a = wired
    authority_before = r.authority_snapshot()
    out = r.run(o, c, p)
    assert out.stop == Stop.GOAL_ACHIEVED and a.path.read_text() == "after"
    assert r.authority_snapshot() == authority_before
    assert len(r.learning_queue) == 1
    assert not hasattr(r, "qualify") and not hasattr(r, "trust")


def test_failed_verification_rolls_back(wired):
    r, o, c, p, a = wired
    a.fail = True
    out = r.run(o, c, p)
    assert out.stop == Stop.CONFIDENCE_INSUFFICIENT
    assert out.iterations == 2 and out.rollback_verified
    assert a.path.read_text() == "before"


def test_rollback_failure_not_success(wired):
    r, o, c, p, a = wired
    a.fail = True
    a.bad_rollback = True
    out = r.run(o, c, p)
    assert out.stop == Stop.IRRECOVERABLE_FAILURE and not out.rollback_verified
    assert r.safety.stopped


def test_expired_snapshot_cannot_write(wired):
    r, o, c, p, a = wired
    original = r.authority_snapshot()
    r.authority_snapshot = lambda: replace(original, expires_at=99)
    assert r.run(o, c, p).stop == Stop.PERMISSION_BOUNDARY
    assert not a.executions


def test_missing_verifier_rolls_back(wired):
    r, o, c, p, a = wired
    r.verification_provider = lambda *args: ()
    out = r.run(o, c, p)
    assert out.stop == Stop.CONFIDENCE_INSUFFICIENT and out.rollback_verified


def test_pre_acting_checkpoint_cannot_be_skipped(wired):
    r, o, c, p, a = wired
    c = replace(c, strategy=replace(c.strategy, checkpoint_before_acting=True))
    actions = tuple(replace(x, cognition_digest=c.fingerprint) for x in p.actions)
    p = replace(p, cognition_digest=c.fingerprint, actions=actions)
    out = r.run(o, c, p)
    assert out.stop == Stop.HUMAN_ESCALATION and not a.executions


def test_checkpoint_failure_before_write_is_bounded(wired):
    r, o, c, p, a = wired

    def unavailable():
        raise OSError("checkpoint unavailable")

    a.checkpoint = unavailable
    out = r.run(o, c, p)
    assert out.stop == Stop.CONFIDENCE_INSUFFICIENT and not a.executions


def test_actual_cost_overrun_rolls_back(wired):

    r, o, c, p, a = wired
    execute = a.execute

    def overrun(request, **kwargs):
        receipt = execute(request, **kwargs)
        return replace(receipt, actual_costs=tuple((k, 2) for k, v in receipt.actual_costs))

    a.execute = overrun
    out = r.run(o, c, p)
    assert out.stop == Stop.BUDGET_EXHAUSTED and out.rollback_verified


def test_global_goal_verifier_required(wired):
    r, o, c, p, a = wired
    r.objective_verification_provider = lambda *_: ()
    out = r.run(o, c, p)
    assert out.stop == Stop.CONFIDENCE_INSUFFICIENT and out.rollback_verified


def test_hard_guard_wraps_actor_before_spend(wired):
    r, o, c, p, a = wired

    def deny(adapter, request, **limits):
        assert limits["hard_limits"] == dict(p.actions[0].costs)
        assert limits["permission_scope"] == request
        raise PermissionError("unit external guard denied before actor")

    r.execution_guard = deny
    out = r.run(o, c, p)
    assert not a.executions and a.path.read_text() == "before"
    assert out.stop == Stop.CONFIDENCE_INSUFFICIENT


def test_operational_module_cannot_call_qualification():
    import ast
    from pathlib import Path

    source = Path("chronus/agent/operational_loop.py").read_text()
    tree = ast.parse(source)
    forbidden = {"qualify", "qualify_strategy", "trust_transition", "elevate", "apply", "sign"}
    assert not any(
        isinstance(n, ast.Call)
        and (
            (isinstance(n.func, ast.Name) and n.func.id in forbidden)
            or (isinstance(n.func, ast.Attribute) and n.func.attr in forbidden)
        )
        for n in ast.walk(tree)
    )


def test_recovery_budget_reserved_before_any_write(wired):
    from chronus.agent.resources import BudgetSet, BudgetMeter

    r, o, c, p, a = wired
    r.budgets = BudgetMeter(BudgetSet(1, 1, 1, 1, 1))
    out = r.run(o, c, p)
    assert out.stop == Stop.BUDGET_EXHAUSTED and not a.executions


def test_rollback_receipt_verification_e2e(wired):
    """E2E test: failing iteration triggers rollback, verifying pre-action state restored with receipts compared (6.6)."""
    import hashlib
    import json

    r, o, c, p, a = wired

    # Record baseline state and cryptographic digest
    pre_text = a.path.read_text()
    pre_digest = hashlib.sha256(pre_text.encode()).hexdigest()

    # Force verification failure to trigger rollback
    a.fail = True

    out = r.run(o, c, p)

    assert out.stop == Stop.CONFIDENCE_INSUFFICIENT
    assert out.rollback_verified is True
    # Verify disk content is restored
    assert a.path.read_text() == pre_text

    # Verify audit trail contains rollback receipts that are cryptographically verified
    rollback_events = []
    for ev in r.audit._events:
        data = json.loads(ev.body)
        if data.get("event_type") == "rollback_executed":
            rollback_events.append(data.get("payload", {}))

    assert len(rollback_events) >= 1
    for ev_data in rollback_events:
        assert ev_data["verified"] is True

    # Receipts compared, not assumed: cryptographic content digest before mutation vs after rollback
    post_receipt = hashlib.sha256(a.checkpoint()).hexdigest()
    assert pre_digest == post_receipt
