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
