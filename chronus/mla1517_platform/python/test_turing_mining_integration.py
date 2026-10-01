"""Behavioral tests for serving Turing through the canonical miner."""
from __future__ import annotations

from chronus.mla1517.mining import M32SearchSolver, TuringMiningSubstrate


def test_turing_lane_order_is_complete_and_aligned() -> None:
    substrate = TuringMiningSubstrate()
    order = substrate.lane_order(37)
    assert len(order) == 32
    assert set(order) == set(range(32))
    assert order[0] == 37 % 32


def test_turing_exhaustive_order_preserves_every_offset() -> None:
    substrate = TuringMiningSubstrate()
    order = substrate.exhaustive_order(257, seed=1234)
    assert len(order) == 257
    assert set(order) == set(range(257))


def test_canonical_solver_uses_turing_without_changing_coverage() -> None:
    solver = M32SearchSolver()
    candidates = list(solver.candidates(start_nonce=37, budget=64))
    nonces = [nonce for nonce, _lane in candidates]
    assert len(nonces) == 64
    assert len(set(nonces)) == 64
    assert set(nonces[:32]) == set(range(32, 64))
    assert set(nonces[32:]) == set(range(64, 96))
