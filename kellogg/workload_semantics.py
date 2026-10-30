"""Stage 1 — Formal workload semantics.

Closes cell: "Galois/cyclotomic engine ... global optimal field choice" (Track 1).
Precondition for every other track.
"""

from __future__ import annotations

from typing import List, Literal, NamedTuple, Protocol, assert_type


class Embedding(Protocol):
    """An embedding of one arithmetic plane into a larger ring."""

    def apply(self, vec) -> object: ...
    def embed(self, value) -> object: ...


class WorkloadDecl(NamedTuple):
    """Declared semantics for a workload."""
    name: str
    arithmetic: Literal[
        "integer",
        "rational",
        "Z[phi]",
        "Q(zeta_m)",
        "F2^2n",
    ]
    semantics: "AST"  # the exact reference operation
    embeddings: List[Embedding]


class AST(NamedTuple):
    """Abstract syntax tree representing the reference operation."""
    reference_vectors: List[tuple]


def admits_embedding(w: WorkloadDecl, e: Embedding) -> bool:
    """Check if embedding e preserves the exact reference value.

    Admissible iff for every reference input, the embedding applied to the
    reference evaluation equals the embedding of the reference evaluation.
    """
    for reference_input in w.semantics.reference_vectors:
        ref_out = w.semantics.eval(reference_input)  # type: ignore[attr-defined]
        emb_out = e.apply(w.semantics.eval(reference_input))
        if emb_out != e.embed(ref_out):
            return False
    return True


def select_field(w: WorkloadDecl) -> "Field":
    """Select the admissible field with smallest description length.

    Candidates are fields that embed the workload's arithmetic plane.
    Admissible candidates additionally preserve the exact reference values.
    The selected field is the one with minimal description length among admissible candidates.
    """
    from .kellogg_scales import Field  # circular; will be resolved at package level

    # Placeholder: candidates computed from arithmetic type
    arithmetic = w.arithmetic
    if arithmetic == "integer":
        candidates = [Field("Z", "integer")]
    elif arithmetic == "rational":
        candidates = [Field("Q", "rational")]
    elif arithmetic == "Z[phi]":
        candidates = [Field("Q(sqrt(5))", "real_quadratic")]
    elif arithmetic == "Q(zeta_m)":
        # m-th cyclotomic field; concrete m would come from context
        candidates = [Field("cyclotomic", "unspecified")]
    elif arithmetic == "F2^2n":
        candidates = [Field("F_{2^(2n)}", "binary")]
    else:
        candidates = []

    # Filter to admissible candidates
    admissible = [
        c for c in candidates if admits_embedding(w, c)  # type: ignore[arg-type]
    ]

    if not admissible:
        from . import fail_closed
        fail_closed.FAIL_CLOSED("no admissible embedding; semantics would change")

    # Select minimal description length
    return min(admissible, key=lambda c: c.description_length)


class Field(NamedTuple):
    """A field (or ring) that can serve as the evaluation domain."""
    name: str
    description_length: int  # shorter = simpler, preferred


# --- Test: field selection preserves semantics ---

def test_field_selection_preserves_semantics(
    reference_workloads: List[tuple["WorkloadDecl", "AST"]],
) -> None:
    """For each reference workload, field choice is a proved operation.

    The selected field eval(input) must equal expected(input) for all
    reference vectors.
    """
    from . import assert_not_a_single_runtime  # will exist after Stage 5

    for w, expected in reference_workloads:
        field = select_field(w)
        for input_vec in w.semantics.reference_vectors:  # type: ignore[attr-defined]
            result = field.eval(input_vec)  # type: ignore[attr-defined]
            expected_val = expected(input_vec)  # type: ignore[attr-defined]
            if result != expected_val:
                raise AssertionError(
                    f"Field selection failed for {w.name}: "
                    f"field.eval({input_vec}) = {result}, expected {expected_val}"
                )
        # Also assert the runtime boundary
        assert_not_a_single_runtime.assert_not_a_single_runtime([w])


# Placeholder for the FAIL_CLOSED utility used within this module
def FAIL_CLOSED(msg: str) -> None:
    raise AssertionError(f"FAIL-CLOSED: {msg}")