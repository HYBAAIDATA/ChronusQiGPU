"""Oracle + Lucas scale program: falsification tests over real substrates.

The budget-scaling experiment measured nonces scanned. These measure the
Lucas/Pisot identities the ladder is actually defined over, through the live
TOE arbiter, and check that the checkers can fail.
"""

import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lucas.ladder import FULL_LADDER, ladder_values, verify_ladder  # noqa: E402
from orcle import (  # noqa: E402
    LUCAS_LADDER,
    UNKNOWN,
    BlockRecord,
    Oracle,
    compact_target,
    toe_scale_program,
)
from toe.system import TOESystem  # noqa: E402


class _Cand:
    def __init__(self, nonce=1, mask=0b1010101, born=0.9, galois=10**12):
        self.nonce = nonce
        self.zeckendorf_mask = mask
        self.born_probability = born
        self.galois_composite = galois


def _mine_block(height, timestamp, nonce, bits=0x201C3CFF):
    """Build a real header and grind a nonce that actually meets the target.

    0x201C3CFF is a deliberately easy difficulty so the test mines a real
    winning nonce quickly. The difficulty value is irrelevant to what is being
    tested -- the point is that the header genuinely satisfies its own target.
    """
    import hashlib

    target = compact_target(bits)
    base = bytearray(80)
    struct.pack_into("<I", base, 0, 1)
    struct.pack_into("<I", base, 68, timestamp)
    struct.pack_into("<I", base, 72, bits)
    for candidate_nonce in range(20000):
        struct.pack_into("<I", base, 76, candidate_nonce)
        digest = hashlib.sha256(hashlib.sha256(bytes(base)).digest()).digest()
        if int.from_bytes(digest, "little") <= target:
            return BlockRecord(height=height, raw_header=bytes(base))
    raise RuntimeError("no nonce found; use an easier bits value")


# === ladder integrity ======================================================


def test_oracle_uses_the_canonical_ladder_not_an_invented_one():
    assert LUCAS_LADDER == tuple(FULL_LADDER) == (10, 12, 15, 18, 20)
    assert 15 in LUCAS_LADDER and 20 in LUCAS_LADDER


def test_ladder_values_are_exact_and_monotonic():
    v = verify_ladder()
    assert v["valid"] and v["monotonic"]
    assert ladder_values() == [123, 322, 1364, 5778, 15127]


# === TOE scale program =====================================================


def test_toe_scale_program_passes_at_every_rung():
    verdicts = toe_scale_program(TOESystem(), _Cand())
    assert len(verdicts) == len(LUCAS_LADDER)
    for v in verdicts:
        assert v.all_pass, f"{v} failed: {v.failing}"
        assert v.n_theorems == 12


# === Oracle ingestion ======================================================


def test_open_session_ingests_once_and_refuses_a_second():
    blocks = [_mine_block(i, 1700000000 + i * 600, 0) for i in range(3)]
    oracle = Oracle()
    rep = oracle.open_session(blocks)
    assert rep["accepted"] == 3
    assert rep["rejected"] == 0
    with pytest.raises(RuntimeError, match="already ingested"):
        oracle.open_session(blocks)


def test_target_mismatch_is_rejected_not_ingested():
    bad = bytearray(_mine_block(0, 1700000000, 0).raw_header)
    struct.pack_into("<I", bad, 76, 12345)  # tamper the winning nonce
    tampered = BlockRecord(height=0, raw_header=bytes(bad))
    rep = Oracle().open_session([tampered])
    assert rep["accepted"] == 0
    assert rep["rejections"][0]["reason"] == "TARGET_MISMATCH"


def test_duplicate_headers_are_rejected():
    blk = _mine_block(0, 1700000000, 0)
    rep = Oracle().open_session([blk, blk])
    assert rep["accepted"] == 1
    assert any(r["reason"] == "DUPLICATE_HEADER" for r in rep["rejections"])


# === honesty of answers ====================================================


def test_empty_oracle_returns_unknown_not_zero():
    ans = Oracle().ask("difficulty_mean")
    assert ans.value is UNKNOWN
    assert ans.is_unknown
    assert ans.measured is False


def test_unknown_question_returns_unknown_with_known_set():
    ans = Oracle().ask("will_the_next_block_hash_be_7f3a")
    assert ans.value is UNKNOWN
    assert "difficulty" in ans.evidence["known_questions"]


def test_toe_theorems_unknown_without_toe_substrate():
    ans = Oracle().ask("toe_theorems")
    assert ans.value is UNKNOWN
    assert ans.evidence["reason"] == "NO_TOE_SUBSTRATE"


def test_toe_theorems_live_through_the_oracle():
    oracle = Oracle(toe=TOESystem(), candidate=_Cand())
    ans = oracle.ask("toe_theorems")
    assert ans.measured is True
    assert ans.basis == "toe.system"
    assert [r["rung"] for r in ans.value] == list(LUCAS_LADDER)
    assert all(r["all_pass"] for r in ans.value)


def test_oracle_never_predicts_a_future_nonce():
    blocks = [_mine_block(i, 1700000000 + i * 600, 0) for i in range(3)]
    oracle = Oracle()
    oracle.open_session(blocks)
    ans = oracle.ask("next_nonce")
    assert ans.value is None
    assert ans.measured is False
    assert ans.evidence["refusal"] == "PREDICTION_NOT_ATTEMPTED"


# === measured chain facts ==================================================


def test_intervals_are_measured_from_real_timestamps():
    blocks = [
        _mine_block(0, 1700000000, 0),
        _mine_block(1, 1700000600, 0),
        _mine_block(2, 1700001500, 0),
    ]
    oracle = Oracle()
    oracle.open_session(blocks)
    ans = oracle.ask("intervals")
    assert ans.measured is True
    assert ans.value["count"] == 2
    assert ans.value["mean_seconds"] == pytest.approx(750.0)


def test_nonce_fingerprint_is_deterministic():
    blocks = [_mine_block(i, 1700000000 + i * 600, 0) for i in range(3)]
    a, b = Oracle(), Oracle()
    a.open_session(blocks)
    b.open_session(list(reversed(blocks)))
    assert a.ask("nonce").value["fingerprint"] == b.ask("nonce").value["fingerprint"]


@pytest.mark.parametrize(
    "kwargs,expect_key",
    [
        ({"mask": 0b11}, "T5_zeckendorf_spacing"),
        ({"born": 0.1}, "T11_born_rule_threshold"),
        ({"galois": (2**61) + 1}, "T12_galois_bound"),
    ],
)
def test_toe_checkers_can_actually_fail(kwargs, expect_key):
    """A checker that cannot fail proves nothing. Each control must be caught."""
    verdicts = toe_scale_program(TOESystem(), _Cand(**kwargs))
    assert not verdicts[0].all_pass
    assert expect_key in verdicts[0].failing


def test_lucas_pisot_identity_holds_exactly_at_every_rung():
    """T4 is L_{n+1} - L_n == L_{n-1}; verify independently of TOE."""
    from lucas.core import lucas as L

    for n in LUCAS_LADDER:
        assert L(n + 1) - L(n) == L(n - 1)
