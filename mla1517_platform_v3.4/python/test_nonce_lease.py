"""Generation-scoped nonce leases: no duplicated coverage, no resurrected work."""

from __future__ import annotations

import pytest

from agentic_fixtures import Extranonce2
from mla1517.mining.nonce_lease import (
    NONCE_SPACE,
    LeaseConflict,
    LeaseExhausted,
    NonceLeaseLedger,
    lease_span,
)
from mla1517.mining.search_plan import LeaseState, NonceLease
from mla1517.mining.solver import M32SearchSolver

KEY_A = ("session-1", 1, "fp-a")
KEY_B = ("session-1", 2, "fp-b")


def ledger(**kwargs) -> NonceLeaseLedger:
    led = NonceLeaseLedger(**kwargs)
    led.bind(KEY_A, 1)
    return led


class TestOverlapRefusal:
    def test_overlapping_reserved_ranges_refused(self):
        led = ledger()
        led.reserve_range("a", "00", 0, 128)
        with pytest.raises(LeaseConflict, match="RESERVED"):
            led.reserve_range("b", "00", 96, 64)

    def test_reserved_cannot_overlap_executing(self):
        led = ledger()
        led.reserve_range("a", "00", 0, 128)
        led.begin("a", KEY_A)
        with pytest.raises(LeaseConflict, match="EXECUTING"):
            led.reserve_range("b", "00", 64, 64)

    def test_completed_coverage_cannot_be_leased_again(self):
        led = ledger()
        led.reserve_range("a", "00", 0, 128)
        led.begin("a", KEY_A)
        led.complete("a")
        with pytest.raises(LeaseConflict, match="completed coverage"):
            led.reserve_range("b", "00", 0, 32)

    def test_same_range_on_another_header_is_distinct_work(self):
        led = ledger()
        led.reserve_range("a", "00", 0, 128)
        assert led.reserve_range("b", "01", 0, 128).extranonce2 == "01"

    def test_adjacent_ranges_are_allowed(self):
        led = ledger()
        led.reserve_range("a", "00", 0, 128)
        assert led.reserve_range("b", "00", 128, 128).start == 128

    @pytest.mark.parametrize("start,count", [(-32, 64), (NONCE_SPACE - 32, 64), (16, 32), (0, 0)])
    def test_ranges_outside_contract_refused(self, start, count):
        with pytest.raises(LeaseConflict):
            ledger().reserve_range("a", "00", start, count)

    def test_lease_ids_are_single_use(self):
        led = ledger()
        led.reserve_range("a", "00", 0, 32)
        led.invalidate("a")
        with pytest.raises(LeaseConflict, match="not fresh"):
            led.reserve_range("a", "00", 64, 32)


class TestLifecycle:
    def test_completed_lease_cannot_execute_again(self):
        led = ledger()
        led.reserve_range("a", "00", 0, 32)
        led.begin("a", KEY_A)
        assert led.complete("a")
        with pytest.raises(LeaseConflict, match="COMPLETE"):
            led.begin("a", KEY_A)

    def test_invalidated_lease_cannot_reach_executor(self):
        led = ledger()
        led.reserve_range("a", "00", 0, 32)
        led.invalidate("a")
        with pytest.raises(LeaseConflict, match="INVALIDATED"):
            led.begin("a", KEY_A)

    def test_executing_twice_refused(self):
        led = ledger()
        led.reserve_range("a", "00", 0, 32)
        led.begin("a", KEY_A)
        with pytest.raises(LeaseConflict, match="EXECUTING"):
            led.begin("a", KEY_A)

    def test_lease_belongs_to_one_identity(self):
        led = ledger()
        led.reserve_range("a", "00", 0, 32)
        with pytest.raises(LeaseConflict, match="different work identity"):
            led.begin("a", KEY_B)

    def test_generation_change_invalidates_reserved_and_executing(self):
        led = ledger()
        led.reserve_range("a", "00", 0, 32)
        led.reserve_range("b", "00", 32, 32)
        led.begin("b", KEY_A)
        assert led.bind(KEY_B, 2) == 2
        assert led.get("a").state is LeaseState.INVALIDATED
        assert led.get("b").state is LeaseState.INVALIDATED
        assert led.complete("b") is False
        with pytest.raises(LeaseConflict):
            led.begin("a", KEY_B)

    def test_unbound_ledger_refuses_everything(self):
        led = NonceLeaseLedger()
        with pytest.raises(LeaseConflict):
            led.reserve_range("a", "00", 0, 32)
        with pytest.raises(LeaseConflict):
            led.allocate("a", 32, Extranonce2())

    def test_active_leases_are_bounded(self):
        led = ledger(max_active=2)
        alloc = Extranonce2()
        led.allocate("a", 32, alloc)
        led.allocate("b", 32, alloc)
        with pytest.raises(LeaseConflict, match="bound"):
            led.allocate("c", 32, alloc)

    def test_contract_projection_matches_shared_shape(self):
        led = ledger()
        record = led.reserve_range("a", "00", 64, 32)
        contract = record.contract()
        assert isinstance(contract, NonceLease)
        assert (contract.generation, contract.start, contract.count) == (1, 64, 32)
        assert contract.state is LeaseState.RESERVED


class TestAllocation:
    def test_sequential_allocations_never_overlap(self):
        led = ledger()
        alloc = Extranonce2()
        leases = [led.allocate(f"p{i}", 100, alloc) for i in range(5)]
        spans = sorted((lease.extranonce2, lease.start, lease.end) for lease in leases)
        for (e1, _s1, end1), (e2, s2, _end2) in zip(spans, spans[1:]):
            assert e1 != e2 or end1 <= s2
        assert alloc.issued == ["00000000"]

    def test_span_covers_every_nonce_the_solver_touches(self):
        solver = M32SearchSolver()
        for window in (1, 31, 32, 33, 123, 199):
            touched = {nonce for nonce, _ in solver.candidates(0, window)}
            assert max(touched) < lease_span(window)

    def test_nonce_space_rollover_takes_fresh_extranonce2(self):
        led = ledger()
        alloc = Extranonce2()
        first = led.allocate("first", 64, alloc)
        led._cursor = NONCE_SPACE - 32
        lease = led.allocate("next", 64, alloc)
        assert (first.extranonce2, lease.extranonce2) == ("00000000", "00000001")
        assert lease.start == 0

    def test_repeated_extranonce2_is_exhaustion_not_duplication(self):
        """extranonce2_size == 0 yields '' forever; a second unit must be refused."""
        led = ledger()
        alloc = Extranonce2(width=0)
        led.allocate("first", 64, alloc)
        led._cursor = NONCE_SPACE
        with pytest.raises(LeaseExhausted):
            led.allocate("second", 64, alloc)

    def test_reconnect_to_the_same_header_space_never_rehashes(self):
        """Same Stratum fingerprint in a new session: coverage and extranonce2 carry over."""
        led = NonceLeaseLedger()
        led.bind(("session-1", 1, "fp-a"), 1, work_space="fp-a")
        first_alloc = Extranonce2()
        done = led.allocate("a", 64, first_alloc)
        led.begin("a", ("session-1", 1, "fp-a"))
        led.complete("a")
        led.bind(("session-2", 1, "fp-a"), 1, work_space="fp-a")
        reconnect_alloc = Extranonce2()  # the pool reset its extranonce2 counter
        fresh = led.allocate("b", 64, reconnect_alloc)
        assert fresh.extranonce2 != done.extranonce2
        assert reconnect_alloc.issued == ["00000000", "00000001"]
        with pytest.raises(LeaseConflict, match="completed coverage"):
            led.reserve_range("c", done.extranonce2, done.start, 32)
        assert led.snapshot()["carried_units_total"] == 1

    def test_a_different_header_space_starts_clean(self):
        led = NonceLeaseLedger()
        led.bind(("session-1", 1, "fp-a"), 1, work_space="fp-a")
        led.allocate("a", 64, Extranonce2())
        led.bind(("session-2", 1, "fp-b"), 1, work_space="fp-b")
        assert led.allocate("b", 64, Extranonce2()).extranonce2 == "00000000"

    def test_rebind_restarts_allocation_for_new_generation(self):
        led = ledger()
        alloc = Extranonce2()
        led.allocate("a", 64, alloc)
        led.bind(KEY_B, 2)
        lease = led.allocate("b", 64, alloc)
        assert lease.generation == 2 and lease.start == 0
        assert lease.extranonce2 == alloc.issued[-1] != alloc.issued[0]
