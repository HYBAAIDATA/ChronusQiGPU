"""Validation of exact schedule positions and terminal nonce leases."""
import pytest

from chronus.pythia.cassini import cassini_permutation
from chronus.pythia.search_plan import LeaseState, NonceLease

pytestmark = pytest.mark.real


@pytest.mark.parametrize("position", [True, False, 0.0, 1.5, "0", None])
def test_cassini_rejects_noninteger_positions(position):
    with pytest.raises(ValueError, match="integer"):
        cassini_permutation(7, 0, 0).offset_at(position)


def test_cassini_iteration_and_range_validation():
    schedule = cassini_permutation(7, 0, 0)
    assert sorted(schedule) == list(range(7))
    for position in (-1, 7):
        with pytest.raises(IndexError):
            schedule.offset_at(position)


@pytest.mark.parametrize("terminal", [LeaseState.COMPLETE, LeaseState.INVALIDATED])
def test_terminal_leases_cannot_reopen(terminal):
    lease = NonceLease("lease", 1, "plan", 0, 7)
    executing = lease.transition(LeaseState.EXECUTING)
    finished = executing.transition(terminal)
    for state in LeaseState:
        with pytest.raises(ValueError, match="invalid lease transition"):
            finished.transition(state)
    assert lease.state is LeaseState.RESERVED  # upstream must still reject stale copies


def test_reserved_lease_can_invalidate_but_cannot_skip_execution():
    lease = NonceLease("lease", 1, "plan", 0, 7)
    assert lease.transition(LeaseState.INVALIDATED).state is LeaseState.INVALIDATED
    with pytest.raises(ValueError):
        lease.transition(LeaseState.COMPLETE)
