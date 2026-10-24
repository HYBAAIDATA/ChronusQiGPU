"""Recovery dispatch safety using real imports and recorded unit actuators.

No physical MMIO, GPU, pool share or production authority is certified here.
"""
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from chronus.mla1517.mining.recovery_authority import (
    RecoveryGovernor, RecoveryRecord, RecoveryState,
)


def proposal(governor, command="RESTART_LANE"):
    return governor.propose([command], "dispatch boundary test")


def test_completed_record_cannot_reexecute():
    governor = RecoveryGovernor()
    record = proposal(governor)
    calls = []
    steps = [("RESTART_LANE", lambda: calls.append(1) or "RESTART_LANE")]
    governor.dispatch(record, steps)
    governor.observe(True)
    with pytest.raises(ValueError, match="active owned"):
        governor.dispatch(record, steps)
    assert calls == [1]
    assert record.state is RecoveryState.VERIFIED
    assert len(governor.snapshot()["recent"]) == 1


def test_dispatched_record_cannot_reexecute_before_observation():
    governor = RecoveryGovernor()
    record = proposal(governor)
    governor.dispatch(record, [("RESTART_LANE", lambda: "RESTART_LANE")])
    with pytest.raises(ValueError, match="already been dispatched"):
        governor.dispatch(record, [("RESTART_LANE", lambda: pytest.fail("replayed"))])


def test_foreign_record_cannot_execute():
    governor = RecoveryGovernor()
    record = proposal(RecoveryGovernor())
    with pytest.raises(ValueError, match="active owned"):
        governor.dispatch(record, [("RESTART_LANE", lambda: pytest.fail("foreign"))])
    assert record.state is RecoveryState.PROPOSED


def test_copied_identity_is_not_owned_record():
    governor = RecoveryGovernor()
    record = proposal(governor)
    forged = RecoveryRecord(record.recovery_id, record.origin, record.commands, record.reason)
    with pytest.raises(ValueError, match="active owned"):
        governor.dispatch(forged, [("RESTART_LANE", lambda: pytest.fail("forged"))])
    assert record.state is RecoveryState.PROPOSED


def test_reentrant_action_cannot_execute_twice():
    governor = RecoveryGovernor()
    record = proposal(governor)
    calls = []

    def action():
        calls.append(1)
        with pytest.raises(ValueError, match="already been dispatched"):
            governor.dispatch(record, [("RESTART_LANE", lambda: pytest.fail("recursive"))])
        return "RESTART_LANE"

    governor.dispatch(record, [("RESTART_LANE", action)])
    assert calls == [1]


def test_concurrent_duplicate_has_one_side_effect():
    governor = RecoveryGovernor()
    record = proposal(governor)
    entered, release = Event(), Event()
    calls = []

    def action():
        calls.append(1)
        entered.set()
        assert release.wait(5)
        return "RESTART_LANE"

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(governor.dispatch, record, [("RESTART_LANE", action)])
        assert entered.wait(5)
        second = pool.submit(governor.dispatch, record, [("RESTART_LANE", action)])
        release.set()
        first.result(timeout=5)
        with pytest.raises(ValueError, match="already been dispatched"):
            second.result(timeout=5)
    assert calls == [1]


def test_ack_exception_cannot_become_verified():
    governor = RecoveryGovernor()
    record = proposal(governor, "FLUSH_LANE")

    def ack():
        raise OSError("transport lost")

    with pytest.raises(OSError, match="transport lost"):
        governor.dispatch(record, [("FLUSH_LANE", lambda: "FLUSH_LANE")], ack=ack)
    assert record.state is RecoveryState.FAILED
    assert "supervisor acknowledgement" in record.failure
    assert governor.observe(True) == []
    assert record.state is RecoveryState.FAILED
    with pytest.raises(ValueError):
        governor.dispatch(record, [("FLUSH_LANE", lambda: pytest.fail("replayed"))])


@pytest.mark.parametrize("ack_value, expected", [(True, RecoveryState.ACKED),
                                               (False, RecoveryState.FAILED),
                                               (None, RecoveryState.DISPATCHED)])
def test_existing_ack_contract(ack_value, expected):
    governor = RecoveryGovernor()
    record = proposal(governor, "FLUSH_LANE")
    governor.dispatch(record, [("FLUSH_LANE", lambda: "FLUSH_LANE")], ack=lambda: ack_value)
    assert record.state is expected


def test_live_supervisor_still_defers_lane_write():
    governor = RecoveryGovernor(clock=lambda: 10)
    governor.external_mode("NORMAL")
    record = proposal(governor, "FLUSH_LANE")
    governor.dispatch(record, [("FLUSH_LANE", lambda: pytest.fail("two writers"))])
    assert record.state is RecoveryState.DEFERRED
    assert record.deferred == ["FLUSH_LANE"]
    with pytest.raises(ValueError, match="already been dispatched"):
        governor.dispatch(record, [("FLUSH_LANE", lambda: pytest.fail("retry"))])


def test_entire_plan_validated_before_any_side_effect():
    governor = RecoveryGovernor()
    record = proposal(governor)
    with pytest.raises(ValueError, match="not proposed"):
        governor.dispatch(record, [("RESTART_LANE", lambda: pytest.fail("partial effect")),
                                   ("FLUSH_LANE", lambda: "FLUSH_LANE")])
    assert record.state is RecoveryState.FAILED


def test_broken_step_iterator_closes_failed():
    governor = RecoveryGovernor()
    record = proposal(governor)

    def steps():
        yield "RESTART_LANE", lambda: pytest.fail("partial effect")
        raise RuntimeError("broken step iterator")

    with pytest.raises(RuntimeError, match="broken step iterator"):
        governor.dispatch(record, steps())
    assert record.state is RecoveryState.FAILED
    assert "prepare dispatch" in record.failure


def test_authorization_denial_still_precedes_action():
    governor = RecoveryGovernor(require_authorization=True,
                                recovery_authorizer=lambda *_: {"allowed": False, "reason": "TEST"})
    record = proposal(governor)
    with pytest.raises(PermissionError, match="AL HARAS recovery authorization denied:TEST"):
        governor.dispatch(record, [("RESTART_LANE", lambda: pytest.fail("denied effect"))])
    assert record.state is RecoveryState.FAILED


def test_observation_inside_action_cannot_verify_unfinished_dispatch():
    governor = RecoveryGovernor()
    record = proposal(governor)

    def action():
        assert governor.observe(True) == []
        assert record.state is RecoveryState.DISPATCHED
        raise OSError("action failed after observation")

    with pytest.raises(OSError):
        governor.dispatch(record, [("RESTART_LANE", action)])
    assert record.state is RecoveryState.FAILED


def test_success_requires_observation_after_dispatch_returns():
    governor = RecoveryGovernor()
    record = proposal(governor)

    def action():
        assert governor.observe(True) == []
        return "RESTART_LANE"

    governor.dispatch(record, [("RESTART_LANE", action)])
    assert record.state is RecoveryState.DISPATCHED
    assert governor.observe(True) == [record]
    assert record.state is RecoveryState.VERIFIED
