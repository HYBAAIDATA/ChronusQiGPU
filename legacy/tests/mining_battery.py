"""Mining battery — subsystem-level checks for the mining/ package.

Deterministic, no randomness, no heuristics.
"""

import hashlib
import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mining.difficulty import DifficultyController
from mining.nonce_scheduler import NonceScheduler
from mining.safety_fsm import EDGES, IllegalTransition, MiningState, SafetyFSM
from mining.search import GroverStyleSearch, MerklePathVerifier, PreimageSearch
import turing_core


def test_fsm_has_exactly_four_states():
    assert [s.value for s in MiningState] == [
        "searching",
        "submitting",
        "waiting_external",
        "cooldown",
    ]
    assert set(EDGES) == set(MiningState)


def test_fsm_full_cycle_leg():
    fsm = SafetyFSM()
    assert fsm.begin_search()
    fsm.on_winner_found()
    assert fsm.state is MiningState.SUBMITTING
    fsm.on_block_accepted(1)
    assert fsm.state is MiningState.WAITING_EXTERNAL
    fsm.on_external_block(2)
    assert fsm.state is MiningState.COOLDOWN
    fsm.cooldown_complete()
    assert fsm.state is MiningState.SEARCHING


def test_fsm_rejects_undeclared_transition():
    fsm = SafetyFSM()
    with pytest.raises(IllegalTransition):
        fsm._go(MiningState.COOLDOWN)
    with pytest.raises(IllegalTransition):
        fsm._go(MiningState.WAITING_EXTERNAL)


def test_fsm_never_two_consecutive_blocks():
    fsm = SafetyFSM()
    fsm.on_winner_found()
    fsm.on_block_accepted(7)
    assert not fsm.can_mine()
    assert not fsm.begin_search()
    assert fsm.consecutive_blocks_prevented == 1
    fsm.on_external_block(8)
    fsm.cooldown_complete()
    assert fsm.can_mine()


def test_fsm_orphan_edge_returns_to_searching():
    fsm = SafetyFSM()
    fsm.on_winner_found()
    fsm.on_block_orphaned()
    assert fsm.state is MiningState.SEARCHING
    # Orphaned block was never mined — immediate re-search is legal.
    assert fsm.can_mine()


def test_nonce_scheduler_deterministic_and_bounded():
    sched = NonceScheduler(nonce_window=100_000, cap=500)
    h = hashlib.sha256(b"block-1").digest()[:80].ljust(80, b"\x00")
    a = sched.schedule(h)
    b = sched.schedule(h)
    assert a == b and len(a) > 0
    assert len(set(a)) == len(a)
    k = sched.kernel_check(len(a))
    assert k["is_lucas_bounded"]
    assert k["bound"] >= len(a)


def test_difficulty_adjusts_per_block():
    d = DifficultyController(zero_bits=0)
    easy = d.target_bytes()
    assert d.update(True)["zero_bits_after"] == 1
    assert d.target_int() < int.from_bytes(easy, "big")
    assert d.update(False)["zero_bits_after"] == 0


def test_grover_search_finds_winner_on_easy_target():
    g = GroverStyleSearch()
    header = hashlib.sha256(b"hdr").digest()[:80].ljust(80, b"\x00")
    target = b"\xff" * 32
    res = g.search(header, list(range(64)), target)
    assert res["mining_success"] and res["winner_nonce"] >= 0
    assert res["grover_k_star"] >= 1
    assert res["theorem_proven"] is False


def test_grover_search_miss_on_impossible_target():
    g = GroverStyleSearch()
    header = hashlib.sha256(b"hdr").digest()[:80].ljust(80, b"\x00")
    res = g.search(header, list(range(64)), b"\x00" * 32)
    assert not res["mining_success"] and res["winner_nonce"] == -1


def test_merkle_verifier_real_path():
    m = MerklePathVerifier()
    leaf = hashlib.sha256(b"coinbase").digest()
    b1 = hashlib.sha256(b"branch1").digest()
    b2 = hashlib.sha256(b"branch2").digest()
    root = turing_core.PythiaMiningEngine.compute_merkle_root(leaf, [b1, b2])
    ok = m.verify(leaf, [b1, b2], root)
    assert ok["included"]
    bad = m.verify(leaf, [b2, b1], root)
    assert not bad["included"]


def test_preimage_search_consensus():
    p = PreimageSearch()
    header = hashlib.sha256(b"hdr").digest()[:80].ljust(80, b"\x00")
    target = b"\xff" * 32
    res = p.scan(header, [5], target)
    assert res["mining_success"] and res["winner_nonce"] == 5
    blob = header + struct.pack("<I", 5)
    assert turing_core.PythiaMiningEngine.double_sha256(blob) < target


def test_kernel_bound_calls():
    from mining import difficulty, nonce_scheduler, safety_fsm, search

    for mod in (safety_fsm, nonce_scheduler, difficulty, search):
        r = mod.lucas_bound(15)
        assert r["bound"] == 1364
        assert r["theorem_proven"] is False


def test_live_session_smoke(tmp_path):
    """Boot the real orchestrator and run two cycles end-to-end."""
    from orchestrator import MiningOrchestrator

    orch = MiningOrchestrator(store_dir=tmp_path / "store")
    r1 = orch.run_cycle(1)
    r2 = orch.run_cycle(2)
    assert r1["theorem_proven"] is False
    assert r1["fsm"]["admitted"] is True
    assert r2["fsm"]["admitted"] is True
    # No fabricated transitions: with no winner the FSM stays in
    # SEARCHING — the cycle never self-feeds acceptance or the
    # external-block observation.
    assert "submitting" not in r1["fsm"]["states_visited"]
    assert "waiting_external" not in r1["fsm"]["states_visited"]
    assert "cooldown" not in r1["fsm"]["states_visited"]
    for c in (r1, r2):
        for subsys in (
            "fsm",
            "toe",
            "mining",
            "meta_evolution",
            "pythia_learning",
            "memory",
            "safety",
            "difficulty",
            "folded",
        ):
            assert c[subsys]["theorem_proven"] is False


def test_live_session_never_two_consecutive(tmp_path):
    """An accepted block blocks the next cycle until a real external block."""
    from orchestrator import MiningOrchestrator

    orch = MiningOrchestrator(store_dir=tmp_path / "store")
    # Simulate a found block, then inject the acceptance verdict.
    orch.fsm.on_winner_found()
    orch.note_block_accepted(1, "00" * 32)
    assert orch.fsm.state.value == "waiting_external"

    # The next cycle must be refused — no hashing while WAITING_EXTERNAL.
    blocked = orch.run_cycle(2)
    assert blocked["blocked"] is True
    assert blocked["fsm"]["admitted"] is False
    assert orch.fsm.consecutive_blocks_prevented == 1

    # A real external-block observation releases the guard.
    orch.note_external_block(2)
    assert orch.fsm.state.value == "searching"
    r3 = orch.run_cycle(3)
    assert r3["fsm"]["admitted"] is True
    assert "mining" in r3
