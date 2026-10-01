"""Owner C — contract tests for Intelligence.search_crystal.

Covers the seams left open by tests/test_search_crystal.py: the vectorized
``enumerate_nonces`` ordering equivalence with the ``_candidate_stream``
generator, ``faces_exhausted`` exact accounting, ``max_faces`` partial
coverage semantics, first-satisfying-nonce winner verification, engine/
argument validation, and ``CassiniSchedule.offset_at`` bounds.
"""

from __future__ import annotations

import hashlib
import math
import struct

import pytest
import turing_core

from Intelligence.search_crystal import (
    SEARCH_ENGINE_ID,
    PoincareCassiniSearchEngine,
    cassini_permutation,
)

HEADER = bytes(range(76))
HEADER80 = bytes(range(80))


def _sha256d(blob: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(blob).digest()).digest()


# --- enumerate_nonces <=> _candidate_stream equivalence -----------------------


def test_enumerate_nonces_matches_candidate_stream_order():
    """The vectorized enumerator must emit the identical ordering and coverage
    the generator produces — the contract that lets callers skip ~30k/s
    generator machinery."""
    engine = PoincareCassiniSearchEngine(total_nonce_space=1031)
    stream_nonces = [nonce for _fid, nonce, _ex in engine._candidate_stream(HEADER, engine.faces)]
    assert engine.enumerate_nonces(HEADER) == stream_nonces


def test_enumerate_nonces_is_coverage_complete_and_unique():
    engine = PoincareCassiniSearchEngine(total_nonce_space=1031, nonce_start=17)
    order = engine.enumerate_nonces(HEADER)
    assert len(order) == 1031
    assert len(set(order)) == 1031
    assert sorted(order) == list(range(17, 17 + 1031))


def test_enumerate_nonces_respects_selected_faces():
    engine = PoincareCassiniSearchEngine(total_nonce_space=320)
    subset = engine.faces[3:9]
    expected = [nonce for _fid, nonce, _ex in engine._candidate_stream(HEADER, subset)]
    assert engine.enumerate_nonces(HEADER, selected_faces=subset) == expected
    covered = {pid for pid in range(3, 9)}
    expected_set = {
        n
        for pid in covered
        for n in range(engine.partitions[pid].start, engine.partitions[pid].stop)
    }
    assert set(expected) == expected_set


def test_enumerate_nonces_empty_selection():
    engine = PoincareCassiniSearchEngine(total_nonce_space=64)
    assert engine.enumerate_nonces(HEADER, selected_faces=[]) == []


def test_enumerate_nonces_seed_changes_ordering():
    """The seed derives from sha256(header_prefix): a different header is a
    different permutation of the same nonce set."""
    engine = PoincareCassiniSearchEngine(total_nonce_space=320)
    a = engine.enumerate_nonces(b"a" * 76)
    b = engine.enumerate_nonces(b"b" * 76)
    assert a != b
    assert sorted(a) == sorted(b)


# --- search(): winner must be the FIRST satisfying nonce in stream order ------


def test_search_winner_is_first_satisfying_nonce_in_stream_order():
    """Independently recompute the emitted order and the predicate; the
    reported winner must be the first nonce in that order whose sha256d
    (little-endian) is below the target."""
    engine = PoincareCassiniSearchEngine(total_nonce_space=512)
    target = int.from_bytes(b"\xff" * 31 + b"\x7f", "big")  # near-max
    target_bytes = target.to_bytes(32, "big")
    header_prefix = bytes(HEADER80[:76])

    selected = engine._rank_faces(header_prefix)
    expected_nonce = None
    expected_pos = None
    for pos, (_fid, nonce, _ex) in enumerate(engine._candidate_stream(header_prefix, selected)):
        digest = turing_core.PythiaMiningEngine.double_sha256(
            header_prefix + struct.pack("<I", nonce)
        )
        if int.from_bytes(digest, "little") < target:
            expected_nonce, expected_pos = nonce, pos
            break

    result = engine.search(header=HEADER80, target=target_bytes)
    assert expected_nonce is not None
    assert result.winner_nonce == expected_nonce
    assert result.hashes_checked == expected_pos + 1
    assert result.winner_hash is not None
    # The winner hash is the real sha256d of header_prefix + LE(nonce).
    assert result.winner_hash == _sha256d(header_prefix + struct.pack("<I", expected_nonce))
    assert int.from_bytes(result.winner_hash, "little") < target


def test_search_exhaustive_miss_accounting_exact():
    """On an impossible target every selected schedule runs to completion:
    hashes_checked == total_nonce_space, faces_exhausted == 32, coverage 1.0."""
    engine = PoincareCassiniSearchEngine(total_nonce_space=320, nonce_start=4096)
    result = engine.search(header=HEADER, target=bytes(32))
    assert result.winner_nonce is None
    assert result.winner_hash is None
    assert result.hashes_checked == 320
    assert result.coverage_complete is True
    assert result.coverage_fraction == 1.0
    assert result.faces_exhausted == 32
    assert result.faces_selected == 32
    assert result.nonce_space == 320


def test_faces_exhausted_counts_only_completed_schedules():
    """With a budget that stops mid-round, only schedules that emitted their
    final position before the break may be counted."""
    engine = PoincareCassiniSearchEngine(total_nonce_space=320)
    result = engine.search(header=HEADER, target=bytes(32), max_hashes=35)
    assert result.hashes_checked == 35
    # Round-robin across 32 ten-nonce shards: after one full round plus 3
    # candidates of the second round, zero faces are exhausted.
    assert result.faces_exhausted == 0


def test_max_faces_limits_selected_coverage():
    engine = PoincareCassiniSearchEngine(total_nonce_space=320)
    result = engine.search(header=HEADER, target=bytes(32), max_faces=8)
    assert result.faces_selected == 8
    assert result.faces_exhausted == 8
    selected_space = sum(engine.partitions[f.face_id].size for f in engine._rank_faces(HEADER)[:8])
    assert result.hashes_checked == selected_space < 320
    assert result.coverage_complete is False
    assert result.coverage_fraction == pytest.approx(selected_space / 320)


def test_search_result_to_dict_honesty():
    engine = PoincareCassiniSearchEngine(total_nonce_space=64)
    result = engine.search(header=HEADER80, target=bytes(32))
    d = result.to_dict()
    assert d["search_engine"] == SEARCH_ENGINE_ID == "poincare_cassini_32_face"
    assert d["truth_class"] == "computational"
    # The claim boundary explicitly disclaims any nonce-probability advantage.
    assert (
        "no measured" in d["claim_boundary"]
        or "never" in d["claim_boundary"].lower()
        or "advantage" in d["claim_boundary"]
    )
    assert len(d["schedule_digest"]) == 64
    assert d["winner_nonce"] is None and d["winner_hash"] is None
    assert d["coverage_fraction"] == 1.0 and d["nonce_space"] == 64


# --- validation ----------------------------------------------------------------


def test_engine_constructor_validation():
    with pytest.raises(ValueError, match="positive"):
        PoincareCassiniSearchEngine(total_nonce_space=0)
    with pytest.raises(ValueError, match="uint32"):
        PoincareCassiniSearchEngine(total_nonce_space=8, nonce_start=-1)
    with pytest.raises(ValueError, match="uint32"):
        PoincareCassiniSearchEngine(total_nonce_space=8, nonce_start=(1 << 32) - 4)


def test_search_input_validation():
    engine = PoincareCassiniSearchEngine(total_nonce_space=8)
    with pytest.raises(ValueError, match="76 or 80"):
        engine.search(header=bytes(75), target=bytes(32))
    with pytest.raises(ValueError, match="76 or 80"):
        engine.search(header=bytes(81), target=bytes(32))
    with pytest.raises(ValueError, match="32 bytes"):
        engine.search(header=HEADER, target=bytes(31))
    with pytest.raises(ValueError, match="non-negative"):
        engine.search(header=HEADER, target=bytes(32), max_hashes=-1)


def test_cassini_schedule_offset_at_bounds_and_formula():
    schedule = cassini_permutation(width=97, face_id=5, seed=13)
    for position in range(97):
        assert schedule.offset_at(position) == ((schedule.origin + position * schedule.stride) % 97)
    with pytest.raises(IndexError):
        schedule.offset_at(97)
    with pytest.raises(IndexError):
        schedule.offset_at(-1)


def test_cassini_permutation_stride_coprime_and_bijective():
    for width in (1, 2, 9, 32, 33, 256):
        schedule = cassini_permutation(width=width, face_id=7, seed=3)
        assert math.gcd(schedule.stride, width) == 1
        assert len(list(schedule)) == width
        assert sorted(schedule) == list(range(width))
