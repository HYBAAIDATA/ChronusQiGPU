"""Dispositions for the claims documented across the workspace research pages.

The research pages assert a large catalogue of advantages.  This module gives
every substantive one of them exactly one disposition, so the system carries the
pages' *epistemic state* instead of re-asserting a claim by association with the
page it came from.

The governing rule
------------------
**Nothing is refuted unless it was tested.**  A claim is ``TESTED_AND_REFUTED``
only when an experiment ran, in a stated regime, and failed *there*.  A claim
that no experiment has addressed is ``UNTESTED``, and it is not refuted: an
experiment on a different question, in a different regime, does not settle it.
That is why ``TESTED_AND_REFUTED`` requires a ``regime`` and an ``outcome``,
``UNTESTED`` requires the ``falsification`` that would settle it, and neither may
borrow the other's evidence.

``VERIFIED``
    Tested in this repository, in the stated regime, and passes.  May be
    asserted within that regime.
``TESTED_AND_REFUTED``
    An experiment ran and the claim failed **in the stated regime**.  Must not
    be asserted in that regime, and this says nothing about any other.
``UNTESTED``
    No experiment addresses it.  Must not be asserted, and must not be called
    refuted.  Carries the experiment that would settle it.
``PROHIBITED``
    A boundary rather than a test result: barred from generated pages and
    release text by policy, whatever any experiment would say.
``HYPOTHESIS``
    Plausible, unevidenced.  Stays isolated under ``experiments/``.

``UNTESTED`` and ``PROHIBITED`` entries are executable: the page's own phrasing
is stored and the named in-repo linter must catch it.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

_REPO_ROOT = Path(__file__).resolve().parents[2]

DOMAINS: tuple[str, ...] = ("mining", "intelligence", "quantum")

DISPOSITIONS: tuple[str, ...] = (
    "VERIFIED",
    "TESTED_AND_REFUTED",
    "UNTESTED",
    "PROHIBITED",
    "HYPOTHESIS",
)

#: Dispositions that assert a test result, and therefore need a regime.
TESTED: tuple[str, ...] = ("VERIFIED", "TESTED_AND_REFUTED")

#: Linters that may be named by an ``UNTESTED`` or ``PROHIBITED`` entry.
LINTERS: dict[str, str] = {
    "unmeasured": "al_haras.unmeasured_claims.assert_no_unmeasured_claims",
    "refuted-register": "al_haras.refuted_claims.assert_claims",
    "vqc-claim-boundary": "turing_universal_quantum_computer.capabilities.audit_claims",
}


@dataclass(frozen=True)
class DocumentedClaim:
    id: str
    domain: str
    claim: str
    page_quote: str
    disposition: str
    source_page: str
    source_url: str
    regime: str = ""
    outcome: str = ""
    evidence: str = ""
    falsification: str = ""
    lint: str = ""
    reason: str = ""
    test_node: str = ""
    isolated_under: str = ""
    note: str = ""

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


CLAIMS: tuple[DocumentedClaim, ...] = (
    # -- mining ------------------------------------------------------------
    DocumentedClaim(
        id="m-phi-vs-uniform-sinusoidal",
        domain="mining",
        claim="phi-compression matches or beats uniform 4-bit quantization on structured data",
        page_quote=(
            "Uniform 4-bit: 4.00× compression, 0.0803 error (sinusoidal); "
            "φ-compression: 3.06× compression, 0.1022 error (sinusoidal); "
            "φ vs NULL model: No improvement (+0.0%)"
        ),
        disposition="TESTED_AND_REFUTED",
        source_page="CLAIMS_BOUNDARY_SHEET_V4",
        source_url="https://app.notion.com/p/3ecaf6c73d79817ca684ddfd6a11bc25",
        regime="sinusoidal synthetic tensors, `benchmarks/baseline_comparison_v4.py`",
        outcome=(
            "phi 3.06x compression at 0.1022 error against uniform 4-bit at 4.00x and "
            "0.0803 error; no improvement over the NULL model"
        ),
        evidence="benchmarks/baseline_comparison_v4.py; benchmarks/llm_kv_cache_structured_benchmark.py",
        note=(
            "Refuted in this regime only. The sheet's own decision criterion is met in "
            "the negative here; it says nothing about real activations."
        ),
    ),
    DocumentedClaim(
        id="m-phi-vs-uniform-real-kv",
        domain="mining",
        claim="phi-compression outperforms uniform quantization on real transformer KV-cache data",
        page_quote=(
            "Claim: φ-compression outperforms uniform quantization (8-bit, 4-bit) on "
            "real transformer KV-cache data"
        ),
        disposition="UNTESTED",
        source_page="CLAIMS_BOUNDARY_SHEET_V4",
        source_url="https://app.notion.com/p/3ecaf6c73d79817ca684ddfd6a11bc25",
        falsification=(
            "run `benchmarks/llm_kv_cache_real_model.py` on LLaMA-2/7B activations; "
            "perplexity on WikiText-2 / LongBench; no compression vs 4-bit vs phi at "
            "equal ratio, decision criterion PPL degradation <= 0.5 at 2x"
        ),
        lint="unmeasured",
        note=(
            "The sheet marks this Pending, not Failed. The sinusoidal result does not "
            "settle it: different statistical properties, different regime."
        ),
    ),
    DocumentedClaim(
        id="m-phi-components-contribute",
        domain="mining",
        claim="the phi-specific components (lattice, multiscale) contribute to compression",
        page_quote=(
            "The φ-specific components (lattice, multiscale) provide no measurable "
            "benefit over engineering improvements alone. φ interacts negatively with "
            "the engineering stack."
        ),
        disposition="TESTED_AND_REFUTED",
        source_page="CLAIMS_BOUNDARY_SHEET_V4",
        source_url="https://app.notion.com/p/3ecaf6c73d79817ca684ddfd6a11bc25",
        regime=(
            "`benchmarks/rate_distortion_decomposition.py`, the sheet's synthetic "
            "'realistic' activation data; no real transformer run"
        ),
        outcome=(
            "phi-only 0.92x at 0.2735 error; engineering-only 4.00x at 0.1072; full "
            "system matches engineering-only compression with worse error, 0.4103"
        ),
        evidence="benchmarks/rate_distortion_decomposition.py",
        note="Refuted for this decomposition. The sheet marks gate G3 CONFIRMED on it.",
    ),
    DocumentedClaim(
        id="m-pulvini-32to1",
        domain="mining",
        claim="folding data onto the 32-face manifold achieves up to 32:1 compression",
        page_quote=(
            "Each data point maps to its nearest face centre, achieving up to 32:1 "
            "compression with phi-resonance quality scoring."
        ),
        disposition="UNTESTED",
        source_page="USE_CASES (4.1 PULVINI)",
        source_url="https://app.notion.com/p/3ecaf6c73d79811cbb6af9b480b3760b",
        falsification=(
            "serialise to bytes and measure the sheet's own `compression_ratio` over "
            "payload plus metadata on a stated corpus; no benchmark covers folding"
        ),
        lint="unmeasured",
        note="32 is the number of faces, not a measured ratio.",
    ),
    DocumentedClaim(
        id="m-phi-hash-collisions",
        domain="mining",
        claim="golden-ratio partitioning produces hash distributions that are harder to collide",
        page_quote=(
            "Advantage: Golden-ratio partitioning creates non-uniform hash distributions "
            "that are harder to collide."
        ),
        disposition="UNTESTED",
        source_page="USE_CASES (3.2 Hash Function Optimization)",
        source_url="https://app.notion.com/p/3ecaf6c73d79811cbb6af9b480b3760b",
        falsification=(
            "birthday search against the phi partition versus a uniform schedule at "
            "equal nonce budget, on the full double-SHA256 predicate"
        ),
        lint="unmeasured",
        note="Non-uniform output is an argument, not a measurement.",
    ),
    DocumentedClaim(
        id="m-manifold-pqc",
        domain="mining",
        claim="manifold key search yields quantum-resistant cryptography",
        page_quote=(
            "Advantage: Quantum-resistant manifold-based cryptography. Topological "
            "security substrate. Tamper-evident audit logging."
        ),
        disposition="UNTESTED",
        source_page="USE_CASES (3.1 Post-Quantum Cryptography, 14.2)",
        source_url="https://app.notion.com/p/3ecaf6c73d79811cbb6af9b480b3760b",
        falsification=(
            "state the hardness assumption, then a reduction or an attack-cost analysis; "
            "no assumption is stated, so there is nothing yet to attack"
        ),
        lint="unmeasured",
        note="STRICT_QUANTUM_BOUNDARY.md category 3 treats signature risk as a migration concern.",
    ),
    DocumentedClaim(
        id="m-phi-nonce-search",
        domain="mining",
        claim="manifold structure makes brute-force nonce search exponentially harder",
        page_quote="Manifold structure makes brute-force search exponentially harder.",
        disposition="UNTESTED",
        source_page="USE_CASES (3.1 Post-Quantum Cryptography)",
        source_url="https://app.notion.com/p/3ecaf6c73d79811cbb6af9b480b3760b",
        falsification=(
            "measure candidates per second on the phi schedule against a uniform "
            "schedule at equal accepted-work accounting"
        ),
        lint="unmeasured",
        note="Every candidate is still checked against the full double-SHA256 predicate.",
    ),
    # -- intelligence ------------------------------------------------------
    DocumentedClaim(
        id="i-tensor-network-nas",
        domain="intelligence",
        claim="MPS compression makes architecture search polynomial in depth",
        page_quote=(
            "Advantage: MPS compression reduces the effective search space from "
            "exponential to polynomial in depth."
        ),
        disposition="UNTESTED",
        source_page="USE_CASES (1.2 Neural Architecture Search)",
        source_url="https://app.notion.com/p/3ecaf6c73d79811cbb6af9b480b3760b",
        falsification=(
            "run the search with and without MPS compression at an equal evaluation "
            "budget and count configurations evaluated to equal quality"
        ),
        lint="unmeasured",
        note="Bond dimension bounds representable entanglement; it does not bound the search.",
    ),
    DocumentedClaim(
        id="i-qec-resonance-fidelity",
        domain="intelligence",
        claim="phi-resonance-weighted correction improves correction fidelity",
        page_quote=(
            "Advantage: Phi-resonance-weighted correction prioritizes high-resonance "
            "qubits for correction, improving correction fidelity."
        ),
        disposition="UNTESTED",
        source_page="USE_CASES (2.1 Quantum Error Correction)",
        source_url="https://app.notion.com/p/3ecaf6c73d79811cbb6af9b480b3760b",
        falsification=(
            "inject a depolarising channel at fixed rate and compare logical error rate "
            "with and without resonance weighting on the distance-3 reference decoder"
        ),
        lint="unmeasured",
        note="The registered invariant is single-error correction, not a fidelity gain.",
    ),
    DocumentedClaim(
        id="i-phi-dna-motifs",
        domain="intelligence",
        claim="phi-resonance scoring identifies functional DNA patterns",
        page_quote="Advantage: Phi-resonance identifies functional DNA patterns.",
        disposition="UNTESTED",
        source_page="USE_CASES (7.4 Genomic Sequence Analysis)",
        source_url="https://app.notion.com/p/3ecaf6c73d79811cbb6af9b480b3760b",
        falsification=(
            "a labelled functional-annotation corpus and a precision/recall comparison "
            "against a sequence-motif baseline"
        ),
        lint="unmeasured",
        note="No in-repo genomic result exists.",
    ),
    DocumentedClaim(
        id="i-self-healing-emergence",
        domain="intelligence",
        claim="self-healing behaviour emerges from the architecture",
        page_quote="Self-healing emerges from architecture (6 verified behaviors).",
        disposition="HYPOTHESIS",
        source_page="USE_CASES (15.4 EUCLID)",
        source_url="https://app.notion.com/p/3ecaf6c73d79811cbb6af9b480b3760b",
        isolated_under="experiments/",
        note="The six behaviours are not enumerated and have no in-repo test.",
    ),
    DocumentedClaim(
        id="i-grassmannian-commitments",
        domain="intelligence",
        claim="Grassmannian subspaces give a natural commitment scheme",
        page_quote=(
            "Advantage: Grassmannian structure provides natural commitment scheme — "
            "subspaces are hard to distinguish without full information."
        ),
        disposition="UNTESTED",
        source_page="USE_CASES (3.3 Zero-Knowledge Proof Systems)",
        source_url="https://app.notion.com/p/3ecaf6c73d79811cbb6af9b480b3760b",
        falsification=(
            "a hiding and binding argument, or a distinguishing attack cost; no "
            "construction exists in-repo to test"
        ),
        lint="unmeasured",
        note="Untested, and currently untestable without a construction.",
    ),
    # -- quantum -----------------------------------------------------------
    DocumentedClaim(
        id="q-exact-tableau",
        domain="quantum",
        claim="the wide register is exact for the stabilizer state class",
        page_quote=(
            "the stabilizer tableau is not a fallback; it is the correct representation "
            "for that state class"
        ),
        disposition="VERIFIED",
        source_page="TURING VQC — Product Boundary Elevation (v1.2)",
        source_url="https://app.notion.com/p/ef634a9a2941468abd2da3a3400edb8d",
        regime="10,000 qubits, Clifford program h 0; cx 0 9999",
        outcome="tableau_bits 20000, cut entropy 1, materialised False, truth_class EXACT",
        evidence="Registered in the executable research intake as vqc-stabilizer-full-width.",
        test_node=(
            "turing_universal_quantum_computer/tests/test_backend_boundary.py"
            "::BackendParityTests::test_full_width_clifford_runs_without_materialising"
        ),
    ),
    DocumentedClaim(
        id="q-quantum-walk-speedup",
        domain="quantum",
        claim="quantum walk gives exponential speedup for path finding",
        page_quote="Advantage: Quantum walk provides exponential speedup for path finding.",
        disposition="PROHIBITED",
        source_page="USE_CASES (10.1 Network Routing)",
        source_url="https://app.notion.com/p/3ecaf6c73d79811cbb6af9b480b3760b",
        reason=(
            "A boundary, not a test result: the repository's own register already bars "
            "'Exponential speedup' as a promotional claim. The in-tree walk is exact and "
            "verifiable; the speedup is unmeasured and barred."
        ),
        lint="refuted-register",
    ),
    DocumentedClaim(
        id="q-interference-speedup",
        domain="quantum",
        claim="quantum interference provides exponential speedup for optimization landscapes",
        page_quote=(
            "Advantage: Quantum interference provides exponential speedup for certain "
            "optimization landscapes."
        ),
        disposition="PROHIBITED",
        source_page="USE_CASES (1.4 Variational Quantum Circuit Training)",
        source_url="https://app.notion.com/p/3ecaf6c73d79811cbb6af9b480b3760b",
        reason=(
            "A boundary, not a test result: barred by the repository's own register for "
            "'Exponential speedup'. Variational methods are heuristics, and no landscape "
            "is named, so the claim is also unfalsifiable as written."
        ),
        lint="refuted-register",
    ),
    DocumentedClaim(
        id="q-exponential-compression",
        domain="quantum",
        claim="tensor-network decomposition gives exponential compression",
        page_quote=(
            "Advantage: Exponential compression for low-entanglement data. Lossless for "
            "separable tensors."
        ),
        disposition="UNTESTED",
        source_page="USE_CASES (4.2 Tensor Network Data Compression)",
        source_url="https://app.notion.com/p/3ecaf6c73d79811cbb6af9b480b3760b",
        falsification=(
            "report bits per element on a stated tensor family against a fixed-rank "
            "baseline at equal error"
        ),
        lint="unmeasured",
        note="Low entanglement bounds the representation, not the compression ratio.",
    ),
    DocumentedClaim(
        id="q-physical-qpu",
        domain="quantum",
        claim="the system is a physical quantum computer",
        page_quote="We built a physical quantum computer.",
        disposition="PROHIBITED",
        source_page="QUANTUM_FOR_DATA",
        source_url="https://app.notion.com/p/3ecaf6c73d79810cad57d13f471cf9a9",
        reason=(
            "A boundary, not a test result: no QPU provider is bound, and the doctrine "
            "page already keeps this sentence RESTRICTED/INTERNAL. No experiment is "
            "required to bar it, and none would make it assertable."
        ),
        lint="vqc-claim-boundary",
        evidence=(
            "turing_universal_quantum_computer/tests/test_backend_boundary.py"
            "::ClaimBoundaryTests::test_hardware_claim_is_flagged"
        ),
        test_node=(
            "turing_universal_quantum_computer/tests/test_backend_boundary.py"
            "::ClaimBoundaryTests::test_hardware_claim_is_flagged"
        ),
    ),
)


def claims_with_test_results(claims: Iterable[DocumentedClaim] = CLAIMS) -> tuple[DocumentedClaim, ...]:
    return tuple(claim for claim in claims if claim.disposition in TESTED)


def claims_untested(claims: Iterable[DocumentedClaim] = CLAIMS) -> tuple[DocumentedClaim, ...]:
    return tuple(claim for claim in claims if claim.disposition == "UNTESTED")


def linted_claims(claims: Iterable[DocumentedClaim] = CLAIMS) -> tuple[DocumentedClaim, ...]:
    return tuple(claim for claim in claims if claim.lint)


def by_domain(domain: str, claims: Iterable[DocumentedClaim] = CLAIMS) -> tuple[DocumentedClaim, ...]:
    return tuple(claim for claim in claims if claim.domain == domain)


def validate_claims(claims: Iterable[DocumentedClaim] = CLAIMS) -> None:
    seen: set[str] = set()
    for claim in claims:
        if claim.id in seen:
            raise ValueError(f"duplicate documented claim id: {claim.id}")
        seen.add(claim.id)
        if claim.domain not in DOMAINS:
            raise ValueError(f"unknown domain for {claim.id}: {claim.domain}")
        if claim.disposition not in DISPOSITIONS:
            raise ValueError(f"unknown disposition for {claim.id}: {claim.disposition}")
        if not claim.source_url.startswith("https://"):
            raise ValueError(f"non-HTTPS source for {claim.id}")
        if not claim.page_quote:
            raise ValueError(f"no page quote for {claim.id}")

        if claim.disposition in TESTED:
            # A test result needs the regime it was obtained in, and the artefact.
            if not claim.regime:
                raise ValueError(f"{claim.id} asserts a test result with no regime")
            if not claim.evidence:
                raise ValueError(f"{claim.id} asserts a test result with no evidence")
            if claim.lint:
                raise ValueError(f"{claim.id} asserts a test result and should not need a lint")
        if claim.disposition == "TESTED_AND_REFUTED" and not claim.outcome:
            raise ValueError(f"{claim.id} is refuted with no recorded outcome")
        if claim.disposition == "UNTESTED":
            # An untested claim is not refuted, so it must carry no test result at
            # all: only the experiment that would settle it.
            if not claim.falsification:
                raise ValueError(f"{claim.id} is untested with no falsification design")
            if claim.regime or claim.outcome:
                raise ValueError(f"{claim.id} is untested but carries a test result")
        if claim.disposition == "PROHIBITED":
            # A boundary is not a result, so it may not borrow one.
            if not claim.reason:
                raise ValueError(f"{claim.id} is prohibited with no stated reason")
            if claim.regime or claim.outcome:
                raise ValueError(f"{claim.id} is prohibited but carries a test result")
        if claim.lint and claim.lint not in LINTERS:
            raise ValueError(f"{claim.id} names an unknown linter: {claim.lint}")
        if claim.disposition in ("UNTESTED", "PROHIBITED") and not claim.lint:
            raise ValueError(f"{claim.id} is {claim.disposition} with no executable lint")
        if claim.disposition == "HYPOTHESIS" and not claim.isolated_under:
            raise ValueError(f"{claim.id} is a hypothesis that is not isolated")
        if claim.test_node and not (_REPO_ROOT / claim.test_node.split("::", 1)[0]).is_file():
            raise ValueError(f"{claim.id} names a test node outside this checkout")


__all__ = [
    "CLAIMS",
    "DISPOSITIONS",
    "DOMAINS",
    "LINTERS",
    "TESTED",
    "DocumentedClaim",
    "by_domain",
    "linted_claims",
    "claims_with_test_results",
    "claims_untested",
    "validate_claims",
]
