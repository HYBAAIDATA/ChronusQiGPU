"""The batched numpy Reed-Solomon decoder against the pure-Python reference.

``decode_block`` (Berlekamp-Welch, one block at a time) is the reference.
``decode_blocks`` / ``heal`` (syndromes, Berlekamp-Massey, Chien, Forney,
vectorised) must return exactly the same result on every input, including
inputs with more errors than the code can correct.
"""

from __future__ import annotations

import hashlib
import random

import numpy as np
import pytest

from chronus.security.al_haras import reed_solomon as rs

pytestmark = pytest.mark.real

N, K = rs.DEFAULT_N, rs.DEFAULT_K
T = (N - K) // 2


def _reference(word):
    res = rs.decode_block(word, N, K)
    if res["status"] == "uncorrectable":
        return None
    return res["data"]


def _random_codeword(rng):
    data = [rng.randrange(256) for _ in range(K)]
    return data + rs.encode_block(data, N, K)


def test_encode_blocks_matches_reference_encoder():
    rng = random.Random(1)
    trace = bytes(rng.randrange(256) for _ in range(32 * 37 + 5))
    fast = rs.encode_blocks(trace)
    for b, start in enumerate(range(0, len(trace), K)):
        block = list(trace[start:start + K])
        block += [0] * (K - len(block))
        assert fast[b].tolist() == rs.encode_block(block, N, K)


@pytest.mark.parametrize("errors", list(range(0, T + 4)) + [16, 24])
def test_batched_decoder_agrees_with_reference(errors):
    rng = random.Random(1000 + errors)
    words = []
    for _ in range(60):
        word = _random_codeword(rng)
        for pos in rng.sample(range(N), errors):
            word[pos] = (word[pos] + rng.randrange(1, rs.P)) % rs.P
        words.append(word)
    corrected, ok, damaged = rs.decode_blocks(np.array(words), N, K)
    for i, word in enumerate(words):
        ref = _reference(word)
        assert bool(damaged[i]) == (errors > 0)
        if ref is None:
            assert not ok[i], (errors, i)
        else:
            assert ok[i], (errors, i)
            assert corrected[i, :K].tolist() == ref
    if errors <= T:
        assert ok.all()


def test_heal_repairs_every_block_at_the_bound_byte_exact():
    rng = random.Random(7)
    trace = bytes(rng.randrange(256) for _ in range(4096 + 17))
    env = rs.protect(trace)
    bad = bytearray(trace)
    for start in range(0, len(bad), K):
        span = min(K, len(bad) - start)
        for pos in rng.sample(range(span), min(T, span)):
            bad[start + pos] ^= rng.randrange(1, 256)
    out = rs.heal(bytes(bad), env)
    assert out["repaired"] == trace
    assert out["integrity_verified"]
    assert out["uncorrectable_blocks"] == []
    assert hashlib.sha256(out["repaired"]).hexdigest() == env["sha256"]


def test_heal_beyond_bound_reports_block_and_keeps_bytes():
    trace = bytes(range(256)) * 2
    env = rs.protect(trace)
    bad = bytearray(trace)
    for pos in range(T + 1):
        bad[64 + pos] ^= 0xFF
    out = rs.heal(bytes(bad), env)
    assert 2 in out["uncorrectable_blocks"]
    assert not out["integrity_verified"]
    assert out["repaired"][64:96] == bytes(bad[64:96])


def test_symbols_outside_field_rejected():
    with pytest.raises(rs.ReedSolomonError):
        rs.decode_blocks(np.full((1, N), rs.P), N, K)


def test_legacy_dsw_healer_reports_success_only_after_a_real_repair():
    """chronus_gpiu-v36's I27 path used to return success unconditionally."""
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "src" / "chronus" / "chronus_gpiu-v36.py"
    spec = importlib.util.spec_from_file_location("chronus_gpiu_v36_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    healer = module.DSWInstantonSelfHealer
    trace = b"execution_trace_data"
    repaired, corrected, verified = healer.heal_execution_trace(trace, injected_fault=True)
    assert (repaired, corrected, verified) == (trace, 1, True)
    # The injected fault really changes the bytes the decoder sees.
    positions = rs.deterministic_fault_positions(trace, 1)
    assert rs.inject_faults(trace, positions) != trace
    assert healer.heal_execution_trace(trace) == (trace, 0, True)
    big = bytes(rs.MAX_TRACE_BYTES + 1)
    assert healer.heal_execution_trace(big, injected_fault=True) == (big, 0, None)  # not run, not a pass


def test_heal_reduces_out_of_range_parity_like_the_reference():
    trace = bytes(range(64))
    env = rs.protect(trace)
    env["parity"] = [[v + rs.P * (2 ** 70) for v in row] for row in env["parity"]]  # huge ints, same residues
    out = rs.heal(trace, env)
    assert out["integrity_verified"] and out["repaired"] == trace


def test_legacy_invariant_matrix_is_not_run_when_the_decoder_is_unavailable(monkeypatch):  # mock-ok: only makes a real module unimportable; no behaviour is replaced
    """I27/I28 report NOT RUN (None), never PASS or an abort, without the decoder."""
    import importlib.util
    import sys
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "src" / "chronus" / "chronus_gpiu-v36.py"
    spec = importlib.util.spec_from_file_location("chronus_gpiu_v36_no_rs", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.MillenniumProblemsMatrix.verify_all_seven_millennium_problems() is True
    import chronus.security.al_haras as al_haras_pkg

    # As in a standalone run: the decoder module cannot be imported.
    monkeypatch.setitem(sys.modules, "chronus.security.al_haras.reed_solomon", None)  # mock-ok: module made unimportable; no behaviour is replaced
    monkeypatch.delattr(al_haras_pkg, "reed_solomon")  # mock-ok: drops the cached submodule so the import really fails
    assert module.DSWInstantonSelfHealer.heal_execution_trace(b"t", True)[2] is None
    assert module.MillenniumProblemsMatrix.verify_all_seven_millennium_problems() is None


@pytest.mark.parametrize("invalid", [1.5, -0.5, np.nan, np.inf, 257, 2**64 - 1, "1", 1 + 0j])
def test_batched_entry_points_reject_invalid_symbols_before_cast(invalid):
    with pytest.raises(rs.ReedSolomonError, match="symbols"):
        rs.decode_blocks(np.full((1, N), invalid), N, K)
    with pytest.raises(rs.ReedSolomonError, match="symbols"):
        rs.heal_blocks(bytes(K), np.full((1, N - K), invalid), N, K, "")


def test_batched_decoder_accepts_field_residue_256():
    words = np.full((1, N), 256, dtype=np.uint16)  # constant polynomial
    corrected, ok, _ = rs.decode_blocks(words, N, K)
    assert ok.all() and np.array_equal(corrected, words)
    out = rs.heal_blocks(bytes(K), np.full((1, N - K), 256), N, K, "")
    assert not out["integrity_verified"]


def test_repair_rejects_excessive_expansion_before_reading_parity():
    trace = bytes(8_000)  # within the trace cap, but 8,000 × 256 symbols
    with pytest.raises(rs.ReedSolomonError, match="expanded words"):
        rs.heal_blocks(trace, None, 256, 1, "")
    with pytest.raises(rs.ReedSolomonError, match="expanded words"):
        rs.heal(trace, {"n": 256, "k": 1, "length": len(trace), "blocks": len(trace), "parity": None})
