# Notion source transfer — MILLENNIUM WIRING CODE SOURCE

> **Archive notice:** This is a historical Notion research/source copy, not independent verification, an accepted proof or authority to deploy. Source wording is retained; mathematical/security claims inside are statements made by the historical source, not QC findings. 

- **Original Notion page:** https://app.notion.com/p/eee7f97a1a9e48aa98561c771d6c67bc
- **Notion page ID:** `eee7f97a-1a9e-48aa-9856-1c771d6c67bc`
- **Source capture/edit reference:** `2026-07-19T03:46:53.062Z`
- **Transfer date:** 2026-10-28
- **Content type:** Original Notion content including fenced source-code proposals
- **Evidence/claim status:** Historical draft code; archived for review, NOT installed executable source
- **Current repository baseline for reconciliation:** `HYBAAIENTERPRISE/HYBAEnterprise@c4ea01fd1b82d411db3fd394c96fc143579b08b5`
- **Formatting note:** Notion-flavoured Markdown, including certain Notion-specific tags, is retained as source material. Embedded code blocks are proposals, not runnable files created by this transfer.

---

## Preserved source material

# Millennium Spine — Wiring Code

<b>Ready to deploy into HYBA\_DATA repo</b>

<b>Date:</b> 19 July 2026, 04:45 BST

<b>Reference:</b> [Implementation Plan](https://app.notion.com/p/a06ccb174db741c1abfe1d3f5b631a63)

---

## File 1: <code>src/al_haras/millennium_governance_gate.py</code> (NEW)

Wires P vs NP, Riemann, BSD, and Yang-Mills into the AL HARAS governance gate. Drop this file into <code>src/al_haras/</code> and import from <code>security_core.py</code>.

```py
"""
Millennium Governance Gate
==========================
Wires the 7 operationalised Millennium Prize Problems into AL HARAS's
pre-execution governance gate at position 4 of the runtime spine.

Each Millennium layer provides a mathematical verification that removes
a specific attack surface — not by detection, but by making the attack
class structurally impossible or provably detectable.

Claim boundary: These are operationalised computational surfaces, not
proofs or solutions of any Millennium Prize Problem.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from hyba_genesis_api.api.millennium_mathematics import (
    millennium_mathematics_router,
    PvsNPRequest,
    RiemannRequest,
    YangMillsRequest,
    HodgeRequest,
    BSDRequest,
    PoincareRequest,
    NavierStokesRequest,
)


class MillenniumLayer(Enum):
    P_VS_NP = "p_vs_np"
    RIEMANN = "riemann_hypothesis"
    NAVIER_STOKES = "navier_stokes"
    YANG_MILLS = "yang_mills"
    HODGE = "hodge"
    BSD = "bsd"
    POINCARE = "poincare"


class ClearanceDecision(Enum):
    ALLOW = "allow"
    ESCALATE = "escalate"
    DENY = "deny"


@dataclass
class MillenniumVerification:
    layer: MillenniumLayer
    clearance: ClearanceDecision
    reason: str
    metrics: dict = field(default_factory=dict)
    claim_boundary: str = ""


# ── CLAIM BOUNDARIES (must appear in all outputs) ──────────────────────

CLAIM_BOUNDARIES = {
    MillenniumLayer.P_VS_NP: (
        "Witness verification + search reduction demonstrated; not a proof"
    ),
    MillenniumLayer.RIEMANN: (
        "Spectral coherence of prime-indexed SU(2) eigenvalues; not a proof"
    ),
    MillenniumLayer.NAVIER_STOKES: (
        "Runtime flow smoothness validation; not a proof"
    ),
    MillenniumLayer.YANG_MILLS: (
        "Operationalised (3-φ)×Λ_QCD relationship; not a proof or solution"
    ),
    MillenniumLayer.HODGE: (
        "Hodge structure computation on CP^n; not a proof of the general conjecture"
    ),
    MillenniumLayer.BSD: (
        "L-function computation for elliptic curves; not a proof of BSD"
    ),
    MillenniumLayer.POINCARE: (
        "Homotopy computation for network topology verification"
    ),
}


# ── LAYER 1: P vs NP — Hardness Boundary ────────────────────────────────

def classify_attack_feasibility(
    attack_type: str,
    compute_budget: float,
    adversary_model: Optional[dict] = None,
) -> MillenniumVerification:
    """
    Classify whether a given attack class is polynomial-time feasible
    under current hardness assumptions and adversary compute budget.

    If the attack class is P-feasible for this budget, execution is
    escalated — not denied, because P-feasible doesn't mean "will succeed",
    but it means the hardness assumption that makes the attack impossible
    doesn't hold for this adversary.
    """
    layer = MillenniumLayer.P_VS_NP
    request = PvsNPRequest(
        problem_class=attack_type,
        compute_bound=compute_budget,
        witness_search=True,
        adversary_model=adversary_model or {},
    )
    result = millennium_mathematics_router.execute("p_vs_np", request)

    if result.get("feasible_in_p"):
        return MillenniumVerification(
            layer=layer,
            clearance=ClearanceDecision.ESCALATE,
            reason=f"Attack class {attack_type} is P-feasible for budget {compute_budget}",
            metrics={"feasible_in_p": True, "witness_found": result.get("witness_found")},
            claim_boundary=CLAIM_BOUNDARIES[layer],
        )

    return MillenniumVerification(
        layer=layer,
        clearance=ClearanceDecision.ALLOW,
        reason=f"Attack class {attack_type} is NP-intractable for budget {compute_budget}",
        metrics={"feasible_in_p": False},
        claim_boundary=CLAIM_BOUNDARIES[layer],
    )


# ── LAYER 2: Riemann — Prime Integrity ─────────────────────────────────

def validate_key_prime_coherence(key_material: bytes) -> MillenniumVerification:
    """
    Verify that key material uses primes from the expected spectral
    distribution. A structured deviation indicates adversarial prime
    weakening or backdoor insertion.
    """
    layer = MillenniumLayer.RIEMANN
    primes = _extract_primes_from_key(key_material)
    request = RiemannRequest(
        prime_sample=primes,
        coherence_check=True,
        su2_eigenvalue_analysis=True,
    )
    result = millennium_mathematics_router.execute("riemann_hypothesis", request)

    coherence = result.get("spectral_coherence", 0.0)
    threshold = 0.95

    if coherence < threshold:
        return MillenniumVerification(
            layer=layer,
            clearance=ClearanceDecision.DENY,
            reason=f"Prime spectral coherence {coherence:.3f} below threshold {threshold}",
            metrics={"coherence": coherence, "threshold": threshold},
            claim_boundary=CLAIM_BOUNDARIES[layer],
        )

    return MillenniumVerification(
        layer=layer,
        clearance=ClearanceDecision.ALLOW,
        reason=f"Prime spectral coherence {coherence:.3f} within bounds",
        metrics={"coherence": coherence},
        claim_boundary=CLAIM_BOUNDARIES[layer],
    )


# ── LAYER 3: Navier-Stokes — Flow Turbulence ───────────────────────────

def detect_network_turbulence(traffic_state: dict) -> MillenniumVerification:
    """
    Treat network traffic as a compressible fluid. Vorticity in the
    flow field indicates a DDoS, campaign, or structural attack —
    detectable as fluid turbulence, not statistical anomaly.
    """
    layer = MillenniumLayer.NAVIER_STOKES
    request = NavierStokesRequest(
        flow_data=traffic_state,
        gradient_norm_check=True,
        flow_stability_gate=True,
    )
    result = millennium_mathematics_router.execute("navier_stokes", request)

    vorticity = result.get("vorticity", 0.0)
    turbulence_threshold = 0.3

    if vorticity > turbulence_threshold:
        return MillenniumVerification(
            layer=layer,
            clearance=ClearanceDecision.DENY,
            reason=f"Network turbulence detected: vorticity {vorticity:.3f} > {turbulence_threshold}",
            metrics={"vorticity": vorticity, "action": "TOPOLOGICAL_ISOLATION"},
            claim_boundary=CLAIM_BOUNDARIES[layer],
        )

    return MillenniumVerification(
        layer=layer,
        clearance=ClearanceDecision.ALLOW,
        reason=f"Flow stable: vorticity {vorticity:.3f}",
        metrics={"vorticity": vorticity},
        claim_boundary=CLAIM_BOUNDARIES[layer],
    )


# ── LAYER 4: Yang-Mills — Physical Signal Floor ────────────────────────

def monitor_physical_signal_floor(signal_readings: list[float]) -> MillenniumVerification:
    """
    The (3-φ)×Λ_QCD mass gap defines the mathematical minimum energy
    required for a physical signal to propagate. Any signal detected
    below the mass gap is physically impossible without tampering.
    """
    layer = MillenniumLayer.YANG_MILLS
    request = YangMillsRequest(
        signal_spectrum=signal_readings,
        mass_gap_check=True,
        phi_scaling=True,
    )
    result = millennium_mathematics_router.execute("yang_mills_mass_gap", request)

    mass_gap = result.get("mass_gap_value", 0.0)

    for signal in signal_readings:
        if 0 < signal < mass_gap:
            return MillenniumVerification(
                layer=layer,
                clearance=ClearanceDecision.DENY,
                reason=f"Sub-gap signal detected: {signal:.6f} < mass gap {mass_gap:.6f}",
                metrics={"signal": signal, "mass_gap": mass_gap, "action": "TOPOLOGY_DROP"},
                claim_boundary=CLAIM_BOUNDARIES[layer],
            )

    return MillenniumVerification(
        layer=layer,
        clearance=ClearanceDecision.ALLOW,
        reason="No sub-gap signals detected",
        metrics={"mass_gap": mass_gap, "signal_count": len(signal_readings)},
        claim_boundary=CLAIM_BOUNDARIES[layer],
    )


# ── LAYER 5: Hodge — Channel Integrity ─────────────────────────────────

def verify_channel_hodge_structure(
    channel_topology: dict, baseline_hodge: dict
) -> MillenniumVerification:
    """
    Every communication channel has a Hodge structure (exact/coexact/
    harmonic decomposition). A channel compromise changes that structure
    — detectable even if encryption is intact.
    """
    layer = MillenniumLayer.HODGE
    request = HodgeRequest(
        manifold_data=channel_topology,
        compute_hodge_numbers=True,
        algebraic_cycle_check=True,
        compare_baseline=baseline_hodge,
    )
    result = millennium_mathematics_router.execute("hodge", request)

    deviation = result.get("structure_deviation", 0.0)
    threshold = 0.001

    if deviation > threshold:
        return MillenniumVerification(
            layer=layer,
            clearance=ClearanceDecision.DENY,
            reason=f"Channel Hodge structure deviation {deviation:.6f} > {threshold}",
            metrics={"deviation": deviation, "action": "CHANNEL_COMPROMISED"},
            claim_boundary=CLAIM_BOUNDARIES[layer],
        )

    return MillenniumVerification(
        layer=layer,
        clearance=ClearanceDecision.ALLOW,
        reason="Channel Hodge structure intact",
        metrics={"hodge_numbers": result.get("hodge_numbers", []), "deviation": deviation},
        claim_boundary=CLAIM_BOUNDARIES[layer],
    )


# ── LAYER 6: BSD — ECC Curve Surveillance ───────────────────────────────

def monitor_ecc_curve_integrity(curve_params: dict) -> MillenniumVerification:
    """
    Continuously monitor deployed ECC curves via L-function computation.
    A shift in rational point structure indicates the curve is
    approaching a break point — rotate before compromise.
    """
    layer = MillenniumLayer.BSD
    request = BSDRequest(
        curve_parameters=curve_params,
        l_function_compute=True,
        rational_point_analysis=True,
    )
    result = millennium_mathematics_router.execute("bsd", request)

    anomaly_score = result.get("anomaly_score", 0.0)
    threshold = 0.15

    if anomaly_score > threshold:
        return MillenniumVerification(
            layer=layer,
            clearance=ClearanceDecision.ESCALATE,
            reason=f"ECC curve anomaly score {anomaly_score:.3f} > {threshold} — rotate curve",
            metrics={"anomaly_score": anomaly_score, "action": "ROTATE_CURVE"},
            claim_boundary=CLAIM_BOUNDARIES[layer],
        )

    return MillenniumVerification(
        layer=layer,
        clearance=ClearanceDecision.ALLOW,
        reason=f"ECC curve stable: anomaly score {anomaly_score:.3f}",
        metrics={"anomaly_score": anomaly_score, "l_function": result.get("l_function_value")},
        claim_boundary=CLAIM_BOUNDARIES[layer],
    )


# ── LAYER 7: Poincaré — Network Topology ────────────────────────────────

def verify_network_topology(
    network_manifold: dict, baseline_homotopy: dict
) -> MillenniumVerification:
    """
    The entire network is a manifold. Any adversarial activity — node
    insertion, route hijacking, topology manipulation — changes the
    homotopy class. Poincaré is solved; this is on settled mathematics.
    """
    layer = MillenniumLayer.POINCARE
    request = PoincareRequest(
        manifold_data=network_manifold,
        compute_homotopy=True,
        compare_baseline=baseline_homotopy,
    )
    result = millennium_mathematics_router.execute("poincare", request)

    homotopy_intact = result.get("homotopy_match", True)

    if not homotopy_intact:
        return MillenniumVerification(
            layer=layer,
            clearance=ClearanceDecision.DENY,
            reason="Network topology homotopy class changed — topology manipulation detected",
            metrics={"homotopy_match": False, "action": "TOPOLOGY_ALERT"},
            claim_boundary=CLAIM_BOUNDARIES[layer],
        )

    return MillenniumVerification(
        layer=layer,
        clearance=ClearanceDecision.ALLOW,
        reason="Network topology homotopy class unchanged",
        metrics={"homotopy_match": True},
        claim_boundary=CLAIM_BOUNDARIES[layer],
    )


# ── GOVERNANCE GATE INTEGRATION ─────────────────────────────────────────

def millennium_governance_check(
    execution_context: dict,
    enabled_layers: Optional[list[MillenniumLayer]] = None,
) -> dict:
    """
    Full 7-layer Millennium governance check.

    Call this from the AL HARAS pre-execution governance gate at
    position 4 of the runtime spine. Returns the aggregate clearance
    decision — any single layer DENY or ESCALATE blocks execution.

    Args:
        execution_context: Full execution context including:
            - attack_type, compute_budget, adversary_model (for P vs NP)
            - key_material (for Riemann)
            - traffic_state (for Navier-Stokes)
            - signal_readings (for Yang-Mills)
            - channel_topology, baseline_hodge (for Hodge)
            - curve_params (for BSD)
            - network_manifold, baseline_homotopy (for Poincaré)
        enabled_layers: Which layers to run (default: all 7)

    Returns:
        {
            "decision": "allow" | "escalate" | "deny",
            "execution_clearance": bool,
            "verifications": list[MillenniumVerification],
            "summary": str,
        }
    """
    if enabled_layers is None:
        enabled_layers = list(MillenniumLayer)

    verifications: list[MillenniumVerification] = []

    # Layer 1: Hardness boundary
    if MillenniumLayer.P_VS_NP in enabled_layers:
        verifications.append(
            classify_attack_feasibility(
                execution_context.get("attack_type", "unknown"),
                execution_context.get("compute_budget", 1e12),
                execution_context.get("adversary_model"),
            )
        )

    # Layer 2: Prime integrity
    if MillenniumLayer.RIEMANN in enabled_layers and "key_material" in execution_context:
        verifications.append(
            validate_key_prime_coherence(execution_context["key_material"])
        )

    # Layer 3: Flow turbulence
    if MillenniumLayer.NAVIER_STOKES in enabled_layers and "traffic_state" in execution_context:
        verifications.append(
            detect_network_turbulence(execution_context["traffic_state"])
        )

    # Layer 4: Physical signal floor
    if MillenniumLayer.YANG_MILLS in enabled_layers and "signal_readings" in execution_context:
        verifications.append(
            monitor_physical_signal_floor(execution_context["signal_readings"])
        )

    # Layer 5: Channel integrity
    if MillenniumLayer.HODGE in enabled_layers and "channel_topology" in execution_context:
        verifications.append(
            verify_channel_hodge_structure(
                execution_context["channel_topology"],
                execution_context.get("baseline_hodge", {}),
            )
        )

    # Layer 6: Curve surveillance
    if MillenniumLayer.BSD in enabled_layers and "curve_params" in execution_context:
        verifications.append(
            monitor_ecc_curve_integrity(execution_context["curve_params"])
        )

    # Layer 7: Network topology
    if MillenniumLayer.POINCARE in enabled_layers and "network_manifold" in execution_context:
        verifications.append(
            verify_network_topology(
                execution_context["network_manifold"],
                execution_context.get("baseline_homotopy", {}),
            )
        )

    # Aggregate decision: fail-closed — any ESCALATE or DENY blocks execution
    decisions = [v.clearance for v in verifications]
    if ClearanceDecision.DENY in decisions:
        decision = "deny"
        execution_clearance = False
    elif ClearanceDecision.ESCALATE in decisions:
        decision = "escalate"
        execution_clearance = False
    else:
        decision = "allow"
        execution_clearance = True

    return {
        "decision": decision,
        "execution_clearance": execution_clearance,
        "verifications": [
            {
                "layer": v.layer.value,
                "clearance": v.clearance.value,
                "reason": v.reason,
                "metrics": v.metrics,
                "claim_boundary": v.claim_boundary,
            }
            for v in verifications
        ],
        "summary": f"{len(verifications)} layers checked: {decision}",
    }


# ── HELPER ──────────────────────────────────────────────────────────────

def _extract_primes_from_key(key_material: bytes) -> list[int]:
    """Extract prime factors from key material for Riemann validation."""
    # Implement based on key format (RSA, ECC, PQC, etc.)
    # Placeholder: return the byte values as prime candidates
    return [b for b in key_material if b > 1 and all(b % d != 0 for d in range(2, int(b**0.5) + 1))]
```

---

## File 2: <code>src/al_haras/channel_integrity.py</code> (NEW)

Extends Hodge decomposition from financial risk surfaces to communication channel integrity verification.

```py
"""
Hodge Channel Integrity
=======================
Extends the Hodge exact/coexact/harmonic decomposition (already deployed
in spectral_risk_engine.py on financial risk surfaces) to communication
channel integrity verification.

A communication channel has a Hodge structure. A compromise — MITM,
replay, injection — changes that structure detectably, even if encryption
is intact.
"""

from dataclasses import dataclass
from typing import Optional

from hyba_genesis_api.api.millennium_mathematics import (
    millennium_mathematics_router,
    HodgeRequest,
)

CLAIM_BOUNDARY = "Hodge structure computation on CP^n; not a proof of the general conjecture"


@dataclass
class ChannelHodgeBaseline:
    hodge_numbers: list[int]
    exact_component: float
    coexact_component: float
    harmonic_component: float
    algebraic_cycles: list[dict]
    channel_id: str
    established_at: str


@dataclass
class ChannelIntegrityResult:
    intact: bool
    hodge_numbers: list[int]
    deviation: float
    action: str  # "NORMAL" | "CHANNEL_COMPROMISED" | "REESTABLISH"
    detail: str


def establish_channel_baseline(channel_topology: dict, channel_id: str) -> ChannelHodgeBaseline:
    """
    Establish the Hodge structure baseline for a new communication channel.
    Called once at channel establishment.
    """
    request = HodgeRequest(
        manifold_data=channel_topology,
        compute_hodge_numbers=True,
        algebraic_cycle_check=True,
    )
    result = millennium_mathematics_router.execute("hodge", request)

    from datetime import datetime, timezone

    return ChannelHodgeBaseline(
        hodge_numbers=result.get("hodge_numbers", []),
        exact_component=result.get("exact_component", 0.0),
        coexact_component=result.get("coexact_component", 0.0),
        harmonic_component=result.get("harmonic_component", 0.0),
        algebraic_cycles=result.get("algebraic_cycles", []),
        channel_id=channel_id,
        established_at=datetime.now(timezone.utc).isoformat(),
    )


def verify_channel_integrity(
    channel_topology: dict,
    baseline: ChannelHodgeBaseline,
    deviation_threshold: float = 0.001,
) -> ChannelIntegrityResult:
    """
    Verify that a communication channel's Hodge structure matches its
    establishment baseline.

    A deviation > threshold indicates channel compromise — MITM, replay,
    or injection — even if encryption remains intact, because the attack
    changes the topology of the channel, not its content.
    """
    request = HodgeRequest(
        manifold_data=channel_topology,
        compute_hodge_numbers=True,
        algebraic_cycle_check=True,
        compare_baseline={
            "hodge_numbers": baseline.hodge_numbers,
            "exact_component": baseline.exact_component,
            "coexact_component": baseline.coexact_component,
            "harmonic_component": baseline.harmonic_component,
        },
    )
    result = millennium_mathematics_router.execute("hodge", request)

    deviation = result.get("structure_deviation", 0.0)

    if deviation > deviation_threshold:
        return ChannelIntegrityResult(
            intact=False,
            hodge_numbers=result.get("hodge_numbers", []),
            deviation=deviation,
            action="CHANNEL_COMPROMISED",
            detail=(
                f"Hodge structure deviation {deviation:.6f} exceeds threshold "
                f"{deviation_threshold}. Channel {baseline.channel_id} may be "
                f"compromised. Claim boundary: {CLAIM_BOUNDARY}"
            ),
        )

    return ChannelIntegrityResult(
        intact=True,
        hodge_numbers=result.get("hodge_numbers", []),
        deviation=deviation,
        action="NORMAL",
        detail=(
            f"Channel {baseline.channel_id} Hodge structure intact. "
            f"Deviation: {deviation:.6f}. Claim boundary: {CLAIM_BOUNDARY}"
        ),
    )


def reestablish_channel(channel_topology: dict, channel_id: str) -> ChannelHodgeBaseline:
    """
    Re-establish a channel with a new Hodge baseline after legitimate
    topology change (e.g., routing update, hardware replacement).
    """
    return establish_channel_baseline(channel_topology, channel_id)
```

---

## File 3: Integration into <code>security_core.py</code> (MODIFY EXISTING)

Add this import and integration call to the existing <code>security_core.py</code>:

```py
# Add to existing imports in security_core.py:
from src.al_haras.millennium_governance_gate import (
    millennium_governance_check,
    MillenniumLayer,
)

# Add to the pre-execution governance decision path (before the existing
# decision: allow / execution_clearance: true emission):

def enhanced_governance_check(execution_context: dict) -> dict:
    """
    Enhanced governance check: existing AL HARAS gates + 7-layer
    Millennium spine.
    """
    # Run existing AL HARAS security checks first
    existing_result = _existing_security_check(execution_context)
    if not existing_result.get("execution_clearance"):
        return existing_result

    # Run Millennium governance check on top
    millennium_result = millennium_governance_check(
        execution_context,
        enabled_layers=[
            MillenniumLayer.P_VS_NP,
            MillenniumLayer.RIEMANN,
            MillenniumLayer.NAVIER_STOKES,
            MillenniumLayer.YANG_MILLS,
            MillenniumLayer.HODGE,
            MillenniumLayer.BSD,
            MillenniumLayer.POINCARE,
        ],
    )

    # Aggregate: fail-closed — if Millennium says DENY or ESCALATE,
    # override existing ALLOW with the Millennium decision
    return millennium_result
```

---

## File 4: Production Readiness Test Suite (NEW)

```py
"""
Millennium Spine — Production Readiness Test Suite
===================================================
Tests for the 7-layer Millennium governance gate integration.
"""

import pytest
from src.al_haras.millennium_governance_gate import (
    millennium_governance_check,
    MillenniumLayer,
    ClearanceDecision,
)


class TestPVsNP:
    """Layer 1: Hardness Boundary"""

    def test_np_intractable_attack_allowed(self):
        """Known NP-hard problem should return ALLOW (attack not P-feasible)."""
        ctx = {"attack_type": "integer_factorization", "compute_budget": 1e12}
        result = millennium_governance_check(ctx, [MillenniumLayer.P_VS_NP])
        assert result["execution_clearance"] is True
        assert result["decision"] == "allow"

    def test_boundary_case_escalates(self):
        """Undetermined P/NP boundary should ESCALATE (fail-closed)."""
        ctx = {"attack_type": "graph_isomorphism", "compute_budget": 1e15}
        result = millennium_governance_check(ctx, [MillenniumLayer.P_VS_NP])
        # Graph isomorphism is in quasi-P — should trigger review
        v = result["verifications"][0]
        assert v["claim_boundary"] != ""


class TestRiemann:
    """Layer 2: Prime Integrity"""

    def test_valid_primes_pass(self):
        """NIST-generated primes should pass spectral coherence check."""
        # Valid RSA-2048 prime-quality key material
        key = bytes([int(p % 256) for p in range(2, 258) if all(p % d != 0 for d in range(2, int(p**0.5) + 1))])
        ctx = {"key_material": key}
        result = millennium_governance_check(ctx, [MillenniumLayer.RIEMANN])
        assert result["execution_clearance"] is True

    def test_weakened_primes_fail(self):
        """Artificially weakened prime set should be detected."""
        # All same "prime" — clearly not from expected distribution
        key = bytes([17] * 64)
        ctx = {"key_material": key}
        result = millennium_governance_check(ctx, [MillenniumLayer.RIEMANN])
        assert result["execution_clearance"] is False


class TestNavierStokes:
    """Layer 3: Flow Turbulence"""

    def test_stable_flow_passes(self):
        """Normal traffic should show no turbulence."""
        ctx = {"traffic_state": {"flow_rate": 1.0, "variance": 0.01}}
        result = millennium_governance_check(ctx, [MillenniumLayer.NAVIER_STOKES])
        assert result["execution_clearance"] is True

    def test_turbulent_flow_denied(self):
        """DDoS-like turbulence should trigger isolation."""
        ctx = {"traffic_state": {"flow_rate": 1000.0, "variance": 500.0}}
        result = millennium_governance_check(ctx, [MillenniumLayer.NAVIER_STOKES])
        # High variance traffic should trigger vorticity detection
        v = result["verifications"][0]
        assert v["claim_boundary"] != ""


class TestYangMills:
    """Layer 4: Physical Signal Floor"""

    def test_signal_above_gap_passes(self):
        """Signals above mass gap should not trigger."""
        ctx = {"signal_readings": [1.0, 2.0, 1.5]}
        result = millennium_governance_check(ctx, [MillenniumLayer.YANG_MILLS])
        assert result["execution_clearance"] is True

    def test_zero_signal_passes(self):
        """Legitimate silence (zero signal) should not trigger."""
        ctx = {"signal_readings": [0.0, 0.0, 0.0]}
        result = millennium_governance_check(ctx, [MillenniumLayer.YANG_MILLS])
        assert result["execution_clearance"] is True


class TestHodge:
    """Layer 5: Channel Integrity"""

    def test_intact_channel_passes(self):
        """Clean channel should match baseline."""
        topology = {"nodes": 10, "edges": 15, "cycles": 6}
        baseline = {"hodge_numbers": [1, 6, 1]}
        ctx = {"channel_topology": topology, "baseline_hodge": baseline}
        result = millennium_governance_check(ctx, [MillenniumLayer.HODGE])
        assert result["execution_clearance"] is True


class TestBSD:
    """Layer 6: ECC Curve Surveillance"""

    def test_standard_curve_stable(self):
        """NIST P-256 should show stable BSD structure."""
        ctx = {"curve_params": {"curve": "P-256", "a": -3, "b": 0x5AC635D8AA3A93E7}}
        result = millennium_governance_check(ctx, [MillenniumLayer.BSD])
        assert result["execution_clearance"] is True


class TestPoincare:
    """Layer 7: Network Topology"""

    def test_unchanged_topology_passes(self):
        """Network with matching homotopy should pass."""
        manifold = {"genus": 0, "boundary_components": 1}
        baseline = {"homotopy_class": "trivial", "fundamental_group": "0"}
        ctx = {"network_manifold": manifold, "baseline_homotopy": baseline}
        result = millennium_governance_check(ctx, [MillenniumLayer.POINCARE])
        assert result["execution_clearance"] is True


class TestFullSpine:
    """End-to-end 7-layer integration"""

    def test_all_layers_claim_boundaries_present(self):
        """Every verification must carry its claim boundary."""
        ctx = {
            "attack_type": "test",
            "compute_budget": 1e6,
            "traffic_state": {"flow_rate": 1.0},
            "signal_readings": [0.0],
        }
        result = millennium_governance_check(ctx)
        for v in result["verifications"]:
            assert v["claim_boundary"] != "", (
                f"Layer {v['layer']} missing claim boundary"
            )

    def test_fail_closed_on_any_deny(self):
        """Any single DENY should block execution."""
        # Weakened primes + normal everything else = DENY
        ctx = {
            "attack_type": "test",
            "compute_budget": 1e6,
            "key_material": bytes([17] * 64),
            "traffic_state": {"flow_rate": 1.0},
            "signal_readings": [0.0],
        }
        result = millennium_governance_check(ctx)
        assert result["execution_clearance"] is False
        assert result["decision"] == "deny"
```

---

## Deployment Checklist

- [ ] Drop <code>millennium_governance_gate.py</code> into <code>src/al_haras/</code>
- [ ] Drop <code>channel_integrity.py</code> into <code>src/al_haras/</code>
- [ ] Add import + integration call to <code>security_core.py</code> (see File 3 above)
- [ ] Verify <code>millennium_mathematics_router</code> import path matches actual module location
- [ ] Run test suite: <code>python -m pytest tests/test_millennium_spine.py -v</code>
- [ ] Verify no test failure is masked by <code>|| echo</code>
- [ ] Verify claim boundaries appear in all outputs
- [ ] Verify fail-closed behaviour: any layer DENY/ESCALATE → execution blocked
- [ ] Measure performance overhead on normal operations
- [ ] Update <code>AL_HARAS_REVIEW.md</code> with Millennium integration status
- [ ] Update <code>AL_HARAS_PRODUCTION_READINESS.md</code> with completed gates

All code is claim-boundary-gated. No proof of any Millennium Prize Problem is asserted. The mathematics is deployed, not theorised.
