"""Dispositions for the claims documented across the workspace research pages.

The research pages assert a large catalogue of advantages.  This module gives
every substantive one of them exactly one disposition, so the system carries the
pages' *conclusions* — including the negative ones — instead of re-asserting a
claim by association with the page it came from.

``VERIFIED``
    Backed by an in-repo test or benchmark.  May be asserted.
``REFUTED``
    In-repo evidence contradicts it.  Must not be asserted.
``PROHIBITED``
    Must be absent from generated pages and release text.
``HYPOTHESIS``
    Plausible, unevidenced.  Stays isolated under ``experiments/``.
``UNBACKED``
    Asserted in a source page with no in-repo evidence either way.

``REFUTED`` and ``PROHIBITED`` entries are executable, not notes: the
``page_quote`` is the page's own phrasing, and the named in-repo linter must
catch it.  That is what makes a disposition a gate.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

_REPO_ROOT = Path(__file__).resolve().parents[2]

DOMAINS: tuple[str, ...] = ("mining", "intelligence", "quantum")

DISPOSITIONS: tuple[str, ...] = (
    "VERIFIED",
    "REFUTED",
    "PROHIBITED",
    "HYPOTHESIS",
    "UNBACKED",
)

#: Linters that may be named by a ``REFUTED`` or ``PROHIBITED`` entry.
LINTERS: dict[str, str] = {
    "al_haras": "al_haras.refuted_claims.assert_claims",
    "vqc-claim-boundary": "turing_universal_quantum_computer.capabilities.audit_claims",
}

#: Dispositions whose quote must be caught by the named linter.
LINTED: tuple[str, ...] = ("REFUTED", "PROHIBITED")


@dataclass(frozen=True)
class DocumentedClaim:
    id: str
    domain: str
    claim: str
    page_quote: str
    disposition: str
    source_page: str
    source_url: str
    evidence: str = ""
    lint: str = ""
    test_node: str = ""
    isolated_under: str = ""
    note: str = ""

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


CLAIMS: tuple[DocumentedClaim, ...] = (
    # -- mining ------------------------------------------------------------
    DocumentedClaim(
        id="m-phi-superiority",
        domain="mining",
        claim="phi-compression outperforms uniform quantization on transformer KV-cache data",
        page_quote=(
            "φ-compression outperforms uniform quantization (8-bit, 4-bit) on real "
            "transformer KV-cache data"
        ),
        disposition="REFUTED",
        source_page="CLAIMS_BOUNDARY_SHEET_V4",
        source_url="https://app.notion.com/p/3ecaf6c73d79817ca684ddfd6a11bc25",
        evidence=(
            "benchmarks/baseline_comparison_v4.py; the sheet's own decision criterion is "
            "met: phi does not beat uniform 8-bit on >= 2/3 data types and does not beat "
            "the NULL model"
        ),
        lint="al_haras",
        note=(
            "The decomposition attributes all compression to the engineering stack; "
            "phi-only is 0.92x with 0.2735 error, worse than baseline."
        ),
    ),
    DocumentedClaim(
        id="m-pulvini-32to1",
        domain="mining",
        claim="folding data onto the 32-face manifold achieves up to 32:1 compression",
        page_quote=(
            "Each data point maps to its nearest face centre, achieving up to 32:1 "
            "compression with phi-resonance quality scoring."
        ),
        disposition="PROHIBITED",
        source_page="USE_CASES (4.1 PULVINI)",
        source_url="https://app.notion.com/p/3ecaf6c73d79811cbb6af9b480b3760b",
        evidence="al_haras/refuted_claims.py already carries 'PULVINI is compression'",
        lint="al_haras",
        note="Face-index quantisation is a lossy codebook, not a compression result.",
    ),
    DocumentedClaim(
        id="m-phi-hash-collisions",
        domain="mining",
        claim="golden-ratio partitioning produces hash distributions that are harder to collide",
        page_quote=(
            "Advantage: Golden-ratio partitioning creates non-uniform hash distributions "
            "that are harder to collide."
        ),
        disposition="PROHIBITED",
        source_page="USE_CASES (3.2 Hash Function Optimization)",
        source_url="https://app.notion.com/p/3ecaf6c73d79811cbb6af9b480b3760b",
        evidence="No in-repo collision-resistance result exists for a phi partition.",
        lint="al_haras",
        note="Non-uniform output does not reduce collision probability in SHA-256d.",
    ),
    DocumentedClaim(
        id="m-manifold-pqc",
        domain="mining",
        claim="manifold key search yields quantum-resistant cryptography",
        page_quote=(
            "Advantage: Quantum-resistant manifold-based cryptography. Topological "
            "security substrate. Tamper-evident audit logging."
        ),
        disposition="PROHIBITED",
        source_page="USE_CASES (3.1 Post-Quantum Cryptography, 14.2)",
        source_url="https://app.notion.com/p/3ecaf6c73d79811cbb6af9b480b3760b",
        evidence=(
            "STRICT_QUANTUM_BOUNDARY.md category 3: quantum risk to ECDSA/BLS is a "
            "wallet and protocol-migration concern, not a mining escalation"
        ),
        lint="al_haras",
        note="Searching a manifold is not a post-quantum hardness assumption.",
    ),
    DocumentedClaim(
        id="m-phi-nonce-search",
        domain="mining",
        claim="manifold structure makes brute-force nonce search exponentially harder",
        page_quote="Manifold structure makes brute-force search exponentially harder.",
        disposition="PROHIBITED",
        source_page="USE_CASES (3.1 Post-Quantum Cryptography)",
        source_url="https://app.notion.com/p/3ecaf6c73d79811cbb6af9b480b3760b",
        evidence="al_haras/refuted_claims.py carries 'Exponential speed is universal'",
        lint="al_haras",
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
        disposition="PROHIBITED",
        source_page="USE_CASES (1.2 Neural Architecture Search)",
        source_url="https://app.notion.com/p/3ecaf6c73d79811cbb6af9b480b3760b",
        evidence="No in-repo architecture-search result exists.",
        lint="al_haras",
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
        disposition="PROHIBITED",
        source_page="USE_CASES (2.1 Quantum Error Correction)",
        source_url="https://app.notion.com/p/3ecaf6c73d79811cbb6af9b480b3760b",
        evidence="The in-tree decoder is a distance-3 reference decoder with no resonance weighting.",
        lint="al_haras",
        note="Correcting a single injected Pauli error is the registered invariant, not a fidelity gain.",
    ),
    DocumentedClaim(
        id="i-phi-dna-motifs",
        domain="intelligence",
        claim="phi-resonance scoring identifies functional DNA patterns",
        page_quote="Advantage: Phi-resonance identifies functional DNA patterns.",
        disposition="PROHIBITED",
        source_page="USE_CASES (7.4 Genomic Sequence Analysis)",
        source_url="https://app.notion.com/p/3ecaf6c73d79811cbb6af9b480b3760b",
        evidence="No in-repo genomic result exists.",
        lint="al_haras",
        note="Golden-ratio motifs in a sequence are not a functional annotation.",
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
        note="The six behaviours are not enumerated in the page and have no in-repo test.",
    ),
    DocumentedClaim(
        id="i-grassmannian-commitments",
        domain="intelligence",
        claim="Grassmannian subspaces give a natural commitment scheme",
        page_quote=(
            "Advantage: Grassmannian structure provides natural commitment scheme — "
            "subspaces are hard to distinguish without full information."
        ),
        disposition="UNBACKED",
        source_page="USE_CASES (3.3 Zero-Knowledge Proof Systems)",
        source_url="https://app.notion.com/p/3ecaf6c73d79811cbb6af9b480b3760b",
        note="No in-repo construction, proof, or hiding argument exists for this.",
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
        evidence="Registered in the executable research intake as vqc-stabilizer-full-width.",
        test_node=(
            "turing_universal_quantum_computer/tests/test_backend_boundary.py"
            "::BackendParityTests::test_full_width_clifford_runs_without_materialising"
        ),
        note="10,000 qubits, 20,000 tableau bits, one bit of cut entropy, no amplitudes materialised.",
    ),
    DocumentedClaim(
        id="q-quantum-walk-speedup",
        domain="quantum",
        claim="quantum walk gives exponential speedup for path finding",
        page_quote="Advantage: Quantum walk provides exponential speedup for path finding.",
        disposition="PROHIBITED",
        source_page="USE_CASES (10.1 Network Routing)",
        source_url="https://app.notion.com/p/3ecaf6c73d79811cbb6af9b480b3760b",
        evidence="al_haras/refuted_claims.py carries 'Exponential speedup'",
        lint="al_haras",
        note="The in-tree walk is exact and verifiable; the speedup claim is neither.",
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
        evidence="al_haras/refuted_claims.py carries 'Exponential speedup'",
        lint="al_haras",
        note="Variational methods are heuristics; no landscape is specified or measured.",
    ),
    DocumentedClaim(
        id="q-exponential-compression",
        domain="quantum",
        claim="tensor-network decomposition gives exponential compression",
        page_quote=(
            "Advantage: Exponential compression for low-entanglement data. Lossless for "
            "separable tensors."
        ),
        disposition="PROHIBITED",
        source_page="USE_CASES (4.2 Tensor Network Data Compression)",
        source_url="https://app.notion.com/p/3ecaf6c73d79811cbb6af9b480b3760b",
        evidence="al_haras/refuted_claims.py carries 'Exponential speed is universal'",
        lint="al_haras",
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
        evidence=(
            "turing_universal_quantum_computer/tests/test_backend_boundary.py"
            "::ClaimBoundaryTests::test_hardware_claim_is_flagged"
        ),
        lint="vqc-claim-boundary",
        test_node=(
            "turing_universal_quantum_computer/tests/test_backend_boundary.py"
            "::ClaimBoundaryTests::test_hardware_claim_is_flagged"
        ),
        note=(
            "Caught by the package's own claim audit rather than by al_haras; the doctrine "
            "page already keeps this sentence RESTRICTED/INTERNAL."
        ),
    ),
)


def linted_claims(claims: Iterable[DocumentedClaim] = CLAIMS) -> tuple[DocumentedClaim, ...]:
    return tuple(claim for claim in claims if claim.disposition in LINTED)


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
        if claim.disposition in LINTED:
            if claim.lint not in LINTERS:
                raise ValueError(f"{claim.id} is {claim.disposition} without a known linter")
            if not claim.evidence:
                raise ValueError(f"{claim.id} is {claim.disposition} without evidence")
        if claim.disposition == "HYPOTHESIS" and not claim.isolated_under:
            raise ValueError(f"{claim.id} is a hypothesis that is not isolated")
        if claim.test_node and not (_REPO_ROOT / claim.test_node.split("::", 1)[0]).is_file():
            raise ValueError(f"{claim.id} names a test node outside this checkout")


__all__ = [
    "CLAIMS",
    "DISPOSITIONS",
    "DOMAINS",
    "LINTED",
    "LINTERS",
    "DocumentedClaim",
    "by_domain",
    "linted_claims",
    "validate_claims",
]
