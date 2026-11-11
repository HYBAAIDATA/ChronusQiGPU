"""Repository-level checks of the TURING documents; they read repository paths, so they run in the source tree.

The Packages workflow runs packages/turing/tests against the installed hyba-turing wheel, which ships no
documents. The checks of packages/turing/docs therefore live here, at the repository root: the
algorithms.md checks from packages/turing/tests/test_turing_exactness_policy.py and the TENSOR.md checks
from packages/turing/tests/test_turing_tensor_policy.py. Claim tokens and wording are stored as code
points so that this file never contains them.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "packages" / "turing" / "docs"
ALGORITHMS = DOCS / "algorithms.md"
TENSOR = DOCS / "TENSOR.md"


def _decode(*code_points):
    return tuple("".join(chr(c) for c in word) for word in code_points)


CLAIM_TOKENS = _decode(
    (105, 110, 102, 105, 110, 105, 116, 101),
    (101, 120, 112, 111, 110, 101, 110, 116, 105, 97, 108),
    (117, 110, 108, 105, 109, 105, 116, 101, 100),
    (49, 48, 48, 120),
)
WORDING = _decode(
    (115, 105, 109, 117, 108, 97, 116),
    (112, 104, 121, 115, 105, 99, 97, 108, 32, 113, 117, 98, 105, 116),
    (102, 97, 117, 108, 116, 45, 116, 111, 108, 101, 114, 97, 110, 116),
    (102, 97, 117, 108, 116, 32, 116, 111, 108, 101, 114, 97, 110, 116),
    (102, 97, 117, 108, 116, 32, 116, 111, 108, 101, 114, 97, 110, 99, 101),
    (113, 117, 97, 110, 116, 117, 109, 32, 97, 100, 118, 97, 110, 116, 97, 103, 101),
    (115, 112, 101, 101, 100, 117, 112),
    (115, 112, 101, 101, 100, 45, 117, 112),
    (98, 114, 101, 97, 107, 116, 104, 114, 111, 117, 103, 104),
)
TENSOR_STATEMENTS = ("2^(n/2)", "max_bond", "not a quantum computer", "no performance advantage",
                     "MAX_DENSE_ENTRIES", "2,500", "CR factorisation", "refus", "turing/kronecker.py")


def test_turing_documents_are_present():
    assert ALGORITHMS.is_file()
    assert TENSOR.is_file()


def test_algorithms_document_wording_and_claim_tokens():
    text = ALGORITHMS.read_text(encoding="utf-8").lower()
    assert [token for token in CLAIM_TOKENS + WORDING if token in text] == []


def test_tensor_document_claim_tokens_and_required_statements():
    raw = TENSOR.read_text(encoding="utf-8")
    text = " ".join(raw.split())
    assert [token for token in CLAIM_TOKENS if token in raw.lower() or token in text.lower()] == []
    for phrase in TENSOR_STATEMENTS:
        assert phrase in text, phrase
