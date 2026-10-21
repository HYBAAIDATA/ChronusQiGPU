"""Real governor/optimizer/lease objects; fixture coordinator, no hardware claim."""
from types import SimpleNamespace

import pytest

from chronus.mla1517.mining.agentic_controller import AgenticMiningController
from chronus.mla1517.mining.closed_loop import ClosedLoopOptimizer
from chronus.mla1517.mining.recovery_authority import RecoveryGovernor, RecoveryState
from salamander.mining_healer import SalamanderMiningHealer, HealerState


def fixture(authorizer=None):
    canonical = SimpleNamespace(job_id='new', target=100, generation_id=2)
    c = SimpleNamespace(
        optimization=ClosedLoopOptimizer(), agentic=AgenticMiningController(),
        recovery=RecoveryGovernor(recovery_authorizer=authorizer),
        client=SimpleNamespace(runtime_state=SimpleNamespace(current_job=canonical),
                               proof_adapter=SimpleNamespace(current_job=SimpleNamespace(job_id='old', target=100))),
    )
    c._resolve_work_identity = lambda: (SimpleNamespace(generation=2, job_fingerprint='fixture-fingerprint'), None)
    return c


def diagnosis(h, c):
    return h.classify(h.observe(c, trigger_reason='IDENTITY_MISMATCH'))


def test_governor_authorizes_real_mutations_and_ack_matches_dispatch():
    seen = []
    c = fixture(lambda record, command, target: seen.append(command) or {'allowed': True})
    h = SalamanderMiningHealer()
    d = diagnosis(h, c)
    rid, ack = h.bounded_action(c, d)
    assert seen == list(d.proposed_actions)
    assert ack.executed_commands == d.proposed_actions
    assert c.client.proof_adapter.current_job is c.client.runtime_state.current_job
    assert c.optimization.is_locked
    assert c.recovery.snapshot()['open'][0]['recovery_id'] == rid
    assert c.recovery.snapshot()['open'][0]['dispatched'] == list(d.proposed_actions)


def test_denied_governor_cannot_mutate_adapter_and_keeps_safety_lock():
    c = fixture(lambda *args: {'allowed': False, 'reason': 'fixture-denial'})
    original = c.client.proof_adapter.current_job
    h = SalamanderMiningHealer()
    with pytest.raises(PermissionError):
        h.bounded_action(c, diagnosis(h, c))
    assert c.client.proof_adapter.current_job is original
    assert c.optimization.is_locked
    assert h.state is HealerState.FAILED
    assert c.recovery.snapshot()['recent'][-1]['state'] == 'FAILED'


def test_missing_governor_cannot_mutate_adapter():
    c = fixture()
    c.recovery = None
    h = SalamanderMiningHealer()
    with pytest.raises(RuntimeError, match='governor unavailable'):
        h.bounded_action(c, diagnosis(h, c))
    assert c.client.proof_adapter.current_job.job_id == 'old'
    assert c.optimization.is_locked


def test_missing_generation_does_not_emit_success_ack():
    c = fixture()
    h = SalamanderMiningHealer()
    d = diagnosis(h, c)
    c.client.runtime_state.current_job = None
    with pytest.raises(RuntimeError, match='generation'):
        h.bounded_action(c, d)
    assert c.optimization.is_locked
    assert c.recovery.snapshot()['recent'][-1]['state'] == 'FAILED'


def test_post_observation_does_not_invent_cleared_leases():
    c = fixture()
    c.client.proof_adapter.current_job = c.client.runtime_state.current_job
    c.agentic._leases = None
    post = SalamanderMiningHealer().post_observe(c)
    assert post.stale_leases_cleared is False
    assert post.healthy is False


def test_targeted_post_observation_does_not_verify_other_recovery():
    g = RecoveryGovernor()
    first = g.propose(['CLEAR'], 'first')
    second = g.propose(['CLEAR'], 'second')
    g.dispatch(first, [('CLEAR', lambda: 'CLEAR')])
    g.dispatch(second, [('CLEAR', lambda: 'CLEAR')])
    closed = g.observe(True, recovery_id=first.recovery_id)
    assert closed == [first]
    assert first.state is RecoveryState.VERIFIED
    assert second.state is RecoveryState.DISPATCHED
    assert g.freezes_speculation


def test_successful_seven_stage_fixture_unlocks_only_after_rebind():
    c = fixture()
    h = SalamanderMiningHealer()
    d = diagnosis(h, c)
    rid, ack = h.bounded_action(c, d)
    h.actuator_ack(ack)
    post = h.post_observe(c)
    assert post.healthy
    audit = h.verified_recovery(c, d, post, rid)
    assert c.optimization.is_locked  # independent verification is not resume
    assert audit.execution_record.elapsed_seconds >= 0
    # Fixture identity is sufficient for lease binding, not a hardware certificate.
    c._resolve_work_identity = lambda: (SimpleNamespace(generation=2, job_fingerprint='fixture-fingerprint'), None)
    c.agentic.bind_work = lambda identity: True
    assert h.resume(c, audit).generation == 2
    assert not c.optimization.is_locked
    assert h.state is HealerState.IDLE


def test_generation_changes_between_verify_and_resume_remain_locked():
    c = fixture()
    h = SalamanderMiningHealer()
    d = diagnosis(h, c)
    rid, ack = h.bounded_action(c, d)
    h.actuator_ack(ack)
    audit = h.verified_recovery(c, d, h.post_observe(c), rid)
    c._resolve_work_identity = lambda: (SimpleNamespace(generation=3), None)
    with pytest.raises(RuntimeError, match='rebind'):
        h.resume(c, audit)
    assert c.optimization.is_locked


def test_partial_authorization_failure_stops_before_adapter_write():
    c = fixture(lambda record, command, target: {'allowed': command != 'RESYNC_PROOF_ADAPTER'})
    original = c.client.proof_adapter.current_job
    h = SalamanderMiningHealer()
    with pytest.raises(PermissionError):
        h.bounded_action(c, diagnosis(h, c))
    assert c.client.proof_adapter.current_job is original
    assert c.optimization.is_locked
    assert h.last_audit is None
