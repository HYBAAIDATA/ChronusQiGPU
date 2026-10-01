"""Durable lifecycle tests using recorded Bitcoin headers, never live-win claims."""

import hashlib
from pathlib import Path

import pytest

from chronus.mla1517.mining.pow import compact_target
from chronus.mla1517.mining.session import MiningSession, PythiaWinnerMemory, digest
from chronus.mla1517.mining.solver import M32SearchSolver

_CORPUS = Path(__file__).parent / "fixtures/btc_headers/btc_headers_805000_805009.bin"


def headers():
    raw = _CORPUS.read_bytes()
    assert (
        hashlib.sha256(raw).hexdigest()
        == "f353f5bcbd5ba170780958269a2b3ea3f057e863e6c766fd2071d0c8fb3dddc2"
    )
    return [raw[i : i + 80] for i in range(0, len(raw), 80)]


def begin(session, header):
    session.begin_submission(
        header=header,
        target=compact_target(int.from_bytes(header[72:76], "little")),
        job_id="historical-replay",
        parent_hash=header[4:36][::-1].hex(),
        parent_height=804999,
        block_candidate=True,
    )


def test_exact_cycle_requires_later_external_block(tmp_path):
    first, second = headers()[:2]
    path = tmp_path / "session.json"
    with_session = MiningSession(path, cooldown_seconds=0)
    begin(with_session, first)
    with pytest.raises(RuntimeError):
        begin(with_session, first)
    with_session.submission_finished(True)
    assert not with_session.observe_external(block_hash=digest(first)[::-1].hex(), height=805000)
    assert not with_session.observe_external(block_hash=digest(second)[::-1].hex(), height=805001)
    assert not with_session.observe_external(
        block_hash=digest(second)[::-1].hex(), height=805000, own_block_height=805000
    )
    assert with_session.observe_external(
        block_hash=digest(second)[::-1].hex(), height=805001, own_block_height=805000
    )
    assert with_session.finish_cooldown()
    assert with_session.history == [
        "SEARCHING",
        "SUBMITTING",
        "WAITING_EXTERNAL",
        "COOLDOWN",
        "SEARCHING",
    ]
    assert with_session.rung == 12
    with_session.close()
    restored = MiningSession(path)
    assert restored.cycles == 1
    assert len(restored.memory.records) == 1
    assert sorted(restored.memory.lane_order()) == list(range(32))
    assert "folded_header" in restored.memory.records[0]
    assert "header" not in restored.memory.records[0]
    restored.close()


def test_crash_and_unknown_outcome_cannot_restart_search(tmp_path):
    first, second = headers()[:2]
    path = tmp_path / "session.json"
    session = MiningSession(path)
    begin(session, first)
    with pytest.raises(BlockingIOError):
        MiningSession(path)
    session.close()
    restored = MiningSession(path)
    assert restored.state == "SUBMITTING"
    restored.submission_finished(None)
    assert restored.state == "WAITING_EXTERNAL"
    assert not restored.observe_external(block_hash=digest(second)[::-1].hex(), height=805001)
    assert restored.memory.records == []
    restored.close()


def test_rejection_still_observes_external_and_cooldown():
    first, second = headers()[:2]
    session = MiningSession(cooldown_seconds=3600)
    begin(session, first)
    session.submission_finished(False)
    assert session.observe_external(block_hash=digest(second)[::-1].hex(), height=805001)
    assert not session.finish_cooldown()
    assert session.state == "COOLDOWN"
    assert session.memory.records == []


def test_folded_memory_rejects_tampering_and_deduplicates():
    header = headers()[0]
    memory = PythiaWinnerMemory()
    target = compact_target(int.from_bytes(header[72:76], "little"))
    memory.consolidate(header, target, "historical")
    memory.consolidate(header, target, "historical")
    assert len(memory.records) == 1
    assert memory.records[0]["raw_buffer_materialized"] is False
    bad = dict(memory.records[0], folded_header="00" * 80)
    with pytest.raises(ValueError):
        PythiaWinnerMemory([bad])
    assert set(memory.lane_order()) == set(range(32))


def test_search_respects_negotiated_target_and_lucas_budget():
    solver = M32SearchSolver()
    header = headers()[0]
    # A maximum share target is an explicit test input, not a network block win.
    result = solver.scan_header(header=header, target=2**256 - 1, budget=123)
    assert result.valid and result.attempts == 1
    candidate = header[:76] + result.found_nonce.to_bytes(4, "little")
    assert int.from_bytes(digest(candidate), "little") <= 2**256 - 1
    assert not result.execution.hardware_execution
    with pytest.raises(ValueError):
        solver.scan_header(header=header, target=2**256 - 1, budget=124)


def test_reorg_to_our_block_cannot_enable_a_consecutive_submission(tmp_path):
    first, second = headers()[:2]
    path = tmp_path / "session.json"
    session = MiningSession(path, cooldown_seconds=0)
    begin(session, first)
    session.submission_finished(True)
    session.observe_external(
        block_hash=digest(second)[::-1].hex(), height=805001, own_block_height=805000
    )
    assert session.finish_cooldown()
    session.close()
    restored = MiningSession(path)
    with pytest.raises(RuntimeError, match="previous block"):
        restored.begin_submission(
            header=second,
            target=compact_target(int.from_bytes(second[72:76], "little")),
            job_id="reorg-replay",
            parent_hash=digest(first)[::-1].hex(),
            parent_height=805000,
            block_candidate=True,
        )
    assert restored.state == "SEARCHING"
    restored.close()
