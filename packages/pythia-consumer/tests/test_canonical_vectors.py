"""Canonical-binding cross-validation vectors.

Each row was produced by the GENUINE producer
(toe.poincare_golden_11d.compute_zeckendorf_certificate) across varied
states and contexts — zero vector, in/out-of-ball folds, unicode and
empty contexts. Expected values are producer output recorded verbatim;
the verifier's independent canonical_accumulator must reproduce them.

This guards against circular verification: the test's expected values
predate and are independent of the implementation under test.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pythia_consumer.verify import canonical_accumulator, verify_receipt  # noqa: E402

# (context_id, coordinate_masks, canonical_int, token_hex, non_adjacent_mask)
VECTORS = [
    ("", [0]*11, 1693898459760322, "ZECK-0006049777FAC6C2", 1365),
    ("v-1", [20756, 17428, 10272, 5284, 2216, 0, 2216, 5284, 10272, 17428, 20756],
     14629096612642336292, "ZECK-CB04FDDC656AAE24", 1365),
    ("φ-ctx", [2084]*11, 16533070979089437161, "ZECK-E5714475A2F211E9", 1365),
    ("v-3", [21512, 16416, 1344, 9364, 33344, 676, 8, 21568, 9512, 0, 8272],
     10697745754808565694, "ZECK-94760715BCCEBFBE", 1365),
    ("", [42152, 10772, 75792, 33092, 73888, 41224, 4100, 75048, 83092, 9360, 76436],
     16444799871977179859, "ZECK-E437AA5AF396CAD3", 1365),
    ("v-5", [35344, 2628, 68132, 65668, 1092, 33952, 17728, 1364, 37524, 276, 10528],
     9030522993588670784, "ZECK-7D52DCD120D99140", 1365),
]


@pytest.mark.parametrize("ctx,cm,ci,tok,nm", VECTORS)
def test_independent_derivation_matches_producer(ctx, cm, ci, tok, nm):
    assert canonical_accumulator(cm, ctx) == ci
    assert tok == f"ZECK-{ci:016X}"


@pytest.mark.parametrize("ctx,cm,ci,tok,nm", VECTORS)
def test_full_verdict_canonical_binding(ctx, cm, ci, tok, nm):
    v = verify_receipt({
        "token_hex": tok, "non_adjacent_mask": nm,
        "canonical_int": ci, "coordinate_masks": cm, "context_id": ctx,
    })
    assert v["verdict"] == "pass"
    assert v["levels"]["canonical_binding"] is True
    assert v["levels"]["provenance_authentication"] == "unsupported"
