"""Regression coverage for the PR #9/#10 review defect classes, exercised
against the merged production path (solver, session, winner memory).

Each test names the defect class it closes. The fabric/queue code those
reviews flagged lives on PR #9/#10's unmerged branches; these tests pin
the same guarantees on the code that actually ships.
"""

from pathlib import Path

import pytest

from chronus.mla1517.mining.pow import compact_target
from chronus.mla1517.mining.session import MiningSession, PythiaWinnerMemory, digest
from chronus.mla1517.mining.solver import M32SearchSolver

_CORPUS = Path(__file__).parent / "fixtures/btc_headers/btc_headers_805000_805009.bin"


def headers():
    raw = _CORPUS.read_bytes()
    return [raw[i : i + 80] for i in range(0, len(raw), 80)]


def test_nonce_zero_is_searchable_not_a_sentinel():
    """nonce-zero handling: nonce 0 is a real candidate, distinguishable
    from 'no winner' (found_nonce is None only when nothing met target)."""
    solver = M32SearchSolver()
    result = solver.scan_header(
        header=headers()[0], target=2**256 - 1, budget=32)
    assert result.valid and result.found_nonce == 0


def test_scanned_window_evidence_and_out_of_window_rejection():
    """Scanned-window verification: the result's claims are bounded by the
    executed candidate set — attempts == window size on a miss, and a
    winner is always an element of the window actually searched."""
    solver = M32SearchSolver()
    header = headers()[1]
    # No candidate in this window meets target=1 — the no-hit report must
    # carry executed-window evidence, not a fabricated winner.
    executed = {nonce for nonce, _ in solver.candidates(0, 64)}
    assert len(executed) == 64
    miss = solver.scan_header(header=header, target=1, budget=64)
    assert not miss.valid and miss.found_nonce is None
    assert miss.attempts == 64
    # A hit always lands inside the executed set, never outside it.
    hit = solver.scan_header(header=header, target=2**256 - 1, budget=64)
    assert hit.valid and hit.found_nonce in executed


def test_target_byte_order_is_little_endian():
    """Target byte order: real headers satisfy their own compact bits only
    under the uint256 little-endian reading; the big-endian digest is not
    the comparison value."""
    header = headers()[2]
    target = compact_target(int.from_bytes(header[72:76], "little"))
    digest_le = int.from_bytes(digest(header), "little")
    digest_be = int.from_bytes(digest(header), "big")
    assert digest_le <= target          # the block really mined
    assert digest_be != digest_le       # readings genuinely differ


def test_nonwinner_submission_rejected_before_network():
    """Inline blocking hash: a header that does not meet its target is
    rejected before any network write; nothing reaches SUBMITTING."""
    session = MiningSession(cooldown_seconds=0)
    header = headers()[3]
    with pytest.raises(ValueError, match="not a winner"):
        session.begin_submission(
            header=header,
            target=1,  # the digest cannot meet this
            job_id="rejected",
            parent_hash=header[4:36][::-1].hex(),
            parent_height=804999,
            block_candidate=False,
        )
    assert session.state == "SEARCHING" and session.pending is None


def test_unconfirmed_and_nonwinning_records_never_enter_memory():
    """Queued-failure replay / fabricated conformance: only acknowledged,
    target-meeting winners enter germ-line memory; a losing header cannot
    be consolidated even when marked accepted."""
    memory = PythiaWinnerMemory()
    header = headers()[4]
    with pytest.raises(ValueError, match="does not meet recorded target"):
        memory.consolidate(header, 1, "fails-target")
    assert memory.records == []
    # A forged record marked accepted but unfolded is rejected on restore.
    forged = {
        "folded_header": "00" * 80,
        "nonce": 0,
        "raw_buffer_materialized": False,
        "theorem_proven": False,
        "block_hash": "00" * 32,
        "target": 2**256 - 1,
        "job_id": "forged",
        "accepted": True,
        "cell_fate": "germ_line",
    }
    with pytest.raises(ValueError):
        PythiaWinnerMemory([forged])
