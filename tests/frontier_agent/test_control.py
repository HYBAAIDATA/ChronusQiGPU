from dataclasses import replace
from chronus.agent.control import StoppingCondition as Stop


def test_all_stops_defined():
    assert len(Stop) == 9


def test_successful_steps_count_toward_shared_budget(wired):
    r, o, c, p, a = wired
    plan = replace(
        p, actions=(p.actions[0], p.actions[0]), policy=replace(p.policy, max_iterations=1)
    )
    out = r.run(o, c, plan)
    assert out.stop == Stop.BUDGET_EXHAUSTED and out.iterations == 1
    assert out.rollback_verified and a.path.read_text() == "before"


def test_deadline_before_action(wired):
    r, o, c, p, a = wired
    out = r.run(o, c, replace(p, policy=replace(p.policy, deadline_ns=99)))
    assert out.stop == Stop.TIME_EXHAUSTED and not a.executions
