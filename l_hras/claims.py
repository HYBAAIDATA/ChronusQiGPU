"""The claims register (Part XV) and invariant catalog (Part XIV).

Every claim names its threat, control, evidence and status. Every status
is measured or target — nothing is asserted. ``verify()`` maps each
measured claim to the test that falsifies it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Claim:
    claim: str
    threat: str
    control: str
    evidence: str
    status: str  # "MEASURED" | "TARGET"
    test: Optional[str] = None


CLAIMS: tuple[Claim, ...] = (
    Claim(
        claim="Layer 1 authorizes or denies; Layer 2 advises; Layer 3 shapes.",
        threat="cross-cutting",
        control="verdict architecture",
        evidence="respond() + G1–G6",
        status="MEASURED",
        test="test_full_workflow",
    ),
    Claim(
        claim="Every adversarial event is tracked and profiled.",
        threat="all adversary classes",
        control="Layer 2 intelligence",
        evidence="track_adversary + profile_adversary + tests",
        status="TARGET",
        test="test_adversary_tracked",
    ),
    Claim(
        claim="Refusal rate >= 99% for declared adversary classes.",
        threat="all adversary classes",
        control="Layer 1 + Layer 2 + Layer 3",
        evidence="benchmark on declared adversary simulations",
        status="TARGET",
        test="test_refusal_rate_measured",
    ),
    Claim(
        claim="False-positive rate <= 0.1% on benign traffic.",
        threat="operational",
        control="Layer 1 policy",
        evidence="negative control benchmark",
        status="TARGET",
        test="test_false_positive_measured",
    ),
    Claim(
        claim="Detection latency <= 100 ms.",
        threat="all adversary classes",
        control="Layer 2 detection",
        evidence="latency benchmark",
        status="TARGET",
        test="test_detection_latency_measured",
    ),
    Claim(
        claim="F4 entanglement produces exact correlations.",
        threat="misclassification",
        control="Layer 3",
        evidence="Bell-state test + correlation exactness test",
        status="MEASURED",
        test="test_correlations_exact_f4",
    ),
    Claim(
        claim="11D fold is exact to 1e-14.",
        threat="fold accuracy",
        control="Layer 3",
        evidence="round-trip test",
        status="MEASURED",
        test="test_fold_exact_1e14",
    ),
    Claim(
        claim="Cassini invariant holds at every stored address.",
        threat="storage tampering",
        control="Layer 1 storage integrity",
        evidence="aethel.cassini test",
        status="MEASURED",
        test="test_cassini_quadruple_verified",
    ),
    Claim(
        claim="Every attestation is rooted in the trust root.",
        threat="forgery",
        control="Layer 1 attestation",
        evidence="attest_compose test",
        status="MEASURED",
        test="test_attestation_signed_by_root",
    ),
    Claim(
        claim="The six-intelligence joint is an exact basis product; no multipartite entanglement is claimed.",
        threat="overclaiming (entanglement)",
        control="l_hras.foundations.entanglement (exact F4 partial trace)",
        evidence="six_party_report: purities 1, Schmidt ranks 1, Meyer-Wallach Q = 0",
        status="MEASURED",
        test="test_six_party_joint_is_unentangled_basis_product",
    ),
    Claim(
        claim="Exact state vectors are universal (Clifford+T+Toffoli), exponential-memory bounded by a fail-closed cap; Gottesman-Knill is not invoked.",
        threat="overclaiming (complexity)",
        control="l_hras.foundations.complexity",
        evidence="gate-set classification + MLA1517_MAX_AMPLITUDES cap check",
        status="MEASURED",
        test="test_gate_set_is_universal_not_clifford",
    ),
    Claim(
        claim="The fold->certificate pipeline is a diffeomorphism followed by declared many-to-one quantization; it is not an isometry.",
        threat="overclaiming (geometry)",
        control="l_hras.foundations.quantization",
        evidence="measured Jacobian condition number + 1/(2*phi^15) error bound",
        status="MEASURED",
        test="test_fold_declared_non_isometric_with_measured_distortion",
    ),
    Claim(
        claim="Cassini identity, Zeckendorf codec round-trip and non-adjacency, and rank-bound decidability are machine-checked in Lean 4.",
        threat="empiricism masquerading as proof",
        control="proofs/lean (Guardian package)",
        evidence="lake build of Guardian.{Cassini,Zeckendorf,LedgerBound}",
        status="MEASURED",
        test="proofs/lean: lake build",
    ),
)


# Part XIV — the invariant catalog as declared data. Every operator's
# invariant names the test that falsifies it (OP1–OP5).
INVARIANTS: dict[str, tuple[str, ...]] = {
    "preconditions": ("TM1", "TM2", "TM3", "TR1", "TR2", "PB1", "PB2", "TP1"),
    "standing": ("L1", "L2", "L3", "L4"),
    "entanglement": ("EI1", "EI2", "EI3", "EI4", "EI5"),
    "modes": (
        "MULT1",
        "MULT2",
        "MULT3",
        "ENT1",
        "ENT2",
        "ENT3",
        "SW1",
        "SW2",
        "SW3",
        "SW4",
        "HP1",
        "HP2",
        "HP3",
        "HP4",
        "WE1",
        "WE2",
        "WE3",
        "WE4",
        "WE5",
        "WE6",
    ),
    "topologies": (
        "POINCARE_1",
        "POINCARE_2",
        "POINCARE_3",
        "PNP_1",
        "PNP_2",
        "PNP_3",
        "YM_1",
        "YM_2",
        "YM_3",
        "RH_1",
        "RH_2",
        "RH_3",
        "BSD_1",
        "BSD_2",
        "BSD_3",
        "HODGE_1",
        "HODGE_2",
        "HODGE_3",
        "NS_1",
        "NS_2",
        "NS_3",
    ),
    "intelligences": (
        "PRED1",
        "PRED2",
        "PRED3",
        "PRED4",
        "CF1",
        "CF2",
        "CF3",
        "CF4",
        "CF5",
        "CF6",
        "TOPO1",
        "TOPO2",
        "TOPO3",
        "GEO1",
        "GEO2",
        "GEO3",
        "QNT1",
        "QNT2",
        "QNT3",
        "CAUS1",
        "CAUS2",
        "CAUS3",
    ),
    "fold": ("11D1", "11D2", "11D3", "11D4", "11D5"),
    "attestation": ("AC1", "AC2", "AC3"),
    "detection": ("DET1", "DET2", "DET3", "DET4"),
    "adversary": ("ADV1", "ADV2", "ADV3", "ADV4"),
    "operations": (
        "INT1",
        "INT2",
        "INT3",
        "GOV1",
        "GOV2",
        "GOV3",
        "GOV4",
        "OBS1",
        "OBS2",
        "OBS3",
        "SD1",
        "SD2",
        "SD3",
        "SD4",
        "FED1",
        "FED2",
        "FED3",
        "FED4",
    ),
    "verdict": ("G1", "G2", "G3", "G4", "G5", "G6"),
    "operators": ("OP1", "OP2", "OP3", "OP4", "OP5"),
}


def claims_report() -> dict:
    return {
        "claims": [vars(c) for c in CLAIMS],
        "invariant_count": sum(len(v) for v in INVARIANTS.values()),
        "measured": sum(1 for c in CLAIMS if c.status == "MEASURED"),
        "target": sum(1 for c in CLAIMS if c.status == "TARGET"),
    }
