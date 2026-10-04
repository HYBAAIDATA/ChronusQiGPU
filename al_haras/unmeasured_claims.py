"""Claims that assert a result no experiment in this repository produced.

Deliberately separate from ``refuted_claims``.  A claim here has **not** been
tested, so it is not refuted — it is unmeasured, and it must not be promoted
either way.  Refutation requires a test that ran and failed; conflating the two
lets an untested claim be dismissed by someone else's experiment on a different
question.

Each string is the phrasing a workspace research page actually uses, so the lint
fires on the page rather than on a paraphrase of it.  The experiment that would
settle each claim is registered in
``chronus/v33/research_reconciliation.py``.
"""

CLAIMS_UNMEASURED = (
    "φ-compression outperforms uniform quantization",
    "32:1 compression",
    "harder to collide",
    "hard to distinguish without full information",
    "Quantum-resistant manifold-based cryptography",
    "exponentially harder",
    "from exponential to polynomial",
    "identifies functional DNA",
    "improving correction fidelity",
    "Exponential compression",
)


class ClaimUnmeasured(ValueError):
    pass


def assert_no_unmeasured_claims(text: str) -> None:
    folded = text.casefold()
    for claim in CLAIMS_UNMEASURED:
        if claim.casefold() in folded:
            raise ClaimUnmeasured(claim)
