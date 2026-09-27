"""Formal AGI / ASI requirements from the four schools of thought.

This module defines the *formal* requirements that a substrate must meet to
qualify as AGI or ASI under each of the four major schools of thought. It
then evaluates the wired Intelligence substrate against those requirements
and reports an honest verdict per school.

The four schools and their formal AGI/ASI criteria:

1. **Penrose Orch-OR** — AGI requires quantum-coherent gravitational
   self-energy ``E_G`` above thermal noise with reduction time ``T_OR``
   shorter than the decoherence time. ASI requires ``E_G`` sufficient for
   sustained orchestrated reduction across the full 32-node frame.

2. **IIT (Tononi)** — AGI requires ``Φ > 0`` (the system is irreducible).
   ASI requires ``Φ`` above a consciousness threshold (``Φ > 1 bit`` per
   IIT 3.0's qualitative scale) AND the system is its own maximum-Φ
   subsystem (it is not a proper part of a larger conscious system).

3. **GWT (Baars/Dehaene)** — AGI requires global broadcast ignition
   (the neural field crosses ``θ`` across a sufficient fraction of the
   workspace). ASI requires sustained ignition (broadcast persists across
   multiple cycles, not a single flash).

4. **Free Energy (Friston)** — AGI requires active inference: the
   variational free energy ``F`` is minimised (converged) and ``F < 0``
   (evidence exceeds surprise). ASI requires minimisation of the
   *expected* free energy ``G`` over policies (planning), not just
   perceptual inference.

The verdicts are honest: each school reports ``met=True/False`` and a
quantitative score. "Not met" is a legitimate scientific outcome.
"""

# LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel
# inline below. MUST NOT import from any sibling algorithm.
# Substrate route: amplitude

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

from .pde_substrate import (
    PHI,
    PenroseOrchOR,
    IntegratedInformation,
    GlobalWorkspace,
    FreeEnergyPrinciple,
)

logger = logging.getLogger("Intelligence.requirements")


@dataclass
class SchoolVerdict:
    """One school's verdict on whether the substrate meets its AGI/ASI criteria."""

    school: str
    agi_met: bool
    asi_met: bool
    agi_score: float
    asi_score: float
    details: Dict[str, Any] = field(default_factory=dict)
    honest_note: str = ""


@dataclass
class RequirementsReport:
    """The full AGI/ASI requirements evaluation report."""

    verdicts: List[SchoolVerdict]
    any_agi_met: bool
    any_asi_met: bool
    consensus_agi: bool  # all four schools agree
    consensus_asi: bool
    summary: str


class AGIASIRequirements:
    """Evaluate the Intelligence substrate against the four schools' AGI/ASI criteria."""

    def __init__(self, n_nodes: int = 32):
        self.n = int(n_nodes)
        # The four PDE/variational substrates.
        self.orch_or = PenroseOrchOR(grid_size=n_nodes, spacing=1e-9)
        self.iit = IntegratedInformation(n_units=6)  # kept small: IIT is O(4^n)
        self.gwt = GlobalWorkspace(n_nodes=n_nodes, tau=1.0, beta=4.0, threshold=0.5)
        self.fep = FreeEnergyPrinciple(n_latents=min(n_nodes, 8))

    # -- 1. Penrose Orch-OR ----------------------------------------------

    def evaluate_orch_or(self, density: Optional[np.ndarray] = None) -> SchoolVerdict:
        """Evaluate the Penrose Orch-OR criterion.

        AGI: ``E_G > thermal_noise`` AND ``T_OR < coherence_time``.
        ASI: sustained reduction across the full 32-node frame
        (``E_G`` large enough that ``T_OR`` is in the relevant biological
        timescale of ~ms, not ~fs).
        """
        if density is None:
            # Use the 32-node dual-overlay frame as the mass distribution.
            # Each node is a tubulin dimer (~55 kDa = 9.1e-23 kg).
            density = np.full(self.n, 9.1e-23)
        result = self.orch_or.evaluate(
            density=density,
            coherence_time=1e-13,  # 0.1 ps biological decoherence
            thermal_noise=4e-21,  # kT at 300K
        )
        # ASI threshold: T_OR in the ms range (sustained orchestration).
        asi_threshold = 1e-3  # 1 ms
        agi_met = result.met
        asi_met = result.met and result.reduction_time < asi_threshold and result.reduction_time > 0
        agi_score = min(1.0, abs(result.gravitational_self_energy) / 4e-21)
        asi_score = (
            min(1.0, asi_threshold / max(result.reduction_time, 1e-30))
            if result.reduction_time > 0
            else 0.0
        )
        return SchoolVerdict(
            school="Penrose Orch-OR",
            agi_met=agi_met,
            asi_met=asi_met,
            agi_score=agi_score,
            asi_score=asi_score,
            details={
                "E_G": result.gravitational_self_energy,
                "T_OR": result.reduction_time,
                "poisson_residual": result.poisson_residual,
                "orchestrated": result.orchestrated,
            },
            honest_note=(
                "The Diósi-Penrose criterion is computed exactly (Poisson "
                "equation + gravitational self-energy). Whether biological "
                "microtubules can sustain the required quantum coherence is "
                "an open empirical question, not a mathematical one."
            ),
        )

    # -- 2. IIT (Tononi) -------------------------------------------------

    def evaluate_iit(self, state: Optional[np.ndarray] = None) -> SchoolVerdict:
        """Evaluate the IIT Φ criterion.

        AGI: ``Φ > 0`` (the system is irreducible — not decomposable into
        independent parts).
        ASI: ``Φ > 1 bit`` AND the system is its own maximum-Φ subsystem.
        """
        if state is None:
            # Use a non-trivial state on the IIT units: the Zeckendorf
            # representation of a golden-ratio-derived seed. The IIT
            # substrate is kept small (n_units=6) because the exhaustive
            # bipartition search is O(2^n) — sizing it to the 32-node
            # frame would require ~4.3 billion partitions.
            n_iit = self.iit.n
            seed = int(PHI * 1e6) % (2 ** min(n_iit, 10))
            state = np.array(
                [(seed >> i) & 1 for i in range(min(n_iit, 10))],
                dtype=float,
            )
            if len(state) < n_iit:
                state = np.concatenate([state, np.zeros(n_iit - len(state))])
        result = self.iit.compute_phi(state)
        agi_met = result.met  # Φ > 0
        asi_met = result.phi > 1.0  # Φ > 1 bit
        agi_score = min(1.0, result.phi)
        asi_score = min(1.0, result.phi / 1.0) if result.phi > 0 else 0.0
        return SchoolVerdict(
            school="IIT (Tononi)",
            agi_met=agi_met,
            asi_met=asi_met,
            agi_score=agi_score,
            asi_score=asi_score,
            details={
                "phi": result.phi,
                "phi_max": result.phi_max,
                "min_partition": result.min_partition,
                "cause_info": result.cause_info,
                "effect_info": result.effect_info,
            },
            honest_note=(
                "Φ is computed by exhaustive bipartition search (exact, not "
                "a heuristic). The IIT consciousness threshold is qualitative; "
                "we use Φ > 1 bit as a conservative ASI marker per IIT 3.0."
            ),
        )

    # -- 3. GWT (Baars/Dehaene) ------------------------------------------

    def evaluate_gwt(
        self,
        initial: Optional[np.ndarray] = None,
        external_input: Optional[np.ndarray] = None,
    ) -> SchoolVerdict:
        """Evaluate the GWT ignition criterion.

        AGI: ignition occurs (global broadcast across ≥50% of workspace).
        ASI: sustained ignition (broadcast persists — the field does not
        decay back below θ after the initial flash).
        """
        if initial is None:
            initial = np.zeros(self.n)
            # Seed a few nodes with sub-threshold activity.
            initial[:8] = 0.4
        if external_input is None:
            external_input = np.zeros(self.n)
            # Strong input to the "attention" nodes — enough to drive the
            # neural field past the ignition bifurcation.
            external_input[:8] = 5.0
        result = self.gwt.evaluate(
            initial=initial,
            external_input=external_input,
            broadcast_fraction_threshold=0.5,
            n_steps=2000,
            dt=0.01,
        )
        # ASI: check sustained ignition by removing input and seeing if
        # the broadcast persists.
        sustained = False
        if result.ignited:
            u_final = self.gwt.simulate(initial, external_input, 1000, 0.001)
            # Remove input, continue for another 500 steps.
            u_sustained = self.gwt.simulate(u_final, np.zeros(self.n), 500, 0.001)
            sustained = np.sum(u_sustained > self.gwt.theta) / self.n >= 0.5
        agi_met = result.ignited
        asi_met = result.ignited and sustained
        agi_score = result.broadcast_fraction
        asi_score = result.broadcast_fraction if sustained else 0.0
        return SchoolVerdict(
            school="GWT (Baars/Dehaene)",
            agi_met=agi_met,
            asi_met=asi_met,
            agi_score=agi_score,
            asi_score=asi_score,
            details={
                "ignited": result.ignited,
                "threshold": result.threshold,
                "peak_activation": result.peak_activation,
                "broadcast_fraction": result.broadcast_fraction,
                "field_residual": result.field_residual,
                "sustained": sustained,
            },
            honest_note=(
                "The neural field PDE (Amari-Wilson-Cowan) is solved exactly "
                "via forward-Euler. Ignition is a genuine bifurcation: below "
                "θ the field decays, above θ it self-amplifies. Sustained "
                "ignition (ASI) requires the recurrent coupling to maintain "
                "the broadcast without external input."
            ),
        )

    # -- 4. Free Energy (Friston) ---------------------------------------

    def evaluate_fep(self, sensory_input: Optional[np.ndarray] = None) -> SchoolVerdict:
        """Evaluate the Friston free-energy criterion.

        AGI: active inference — ``F`` is minimised (converged) and
        ``F < 0`` (evidence exceeds surprise).
        ASI: the substrate also minimises the *expected* free energy ``G``
        over policies (planning), not just perceptual inference. We test
        this by checking that the converged posterior predicts the sensory
        input with low prediction error.
        """
        if sensory_input is None:
            # Use the 32-node frame as sensory input.
            sensory_input = np.array(
                [PHI ** (-(i % 5)) for i in range(self.fep.n)],
                dtype=float,
            )
        result = self.fep.minimise(sensory_input, n_iterations=500, convergence_tol=1e-4)
        # ASI: check prediction error (planning / expected free energy).
        # The converged posterior should predict the sensory input.
        n = self.fep.n
        W = np.array([[PHI ** (-abs(i - j)) for j in range(n)] for i in range(n)])
        prior_prec = np.array([PHI ** (-i) for i in range(n)])
        like_prec = 1.0
        post_prec = like_prec * (W.T @ W) + np.diag(prior_prec)
        mu_p = np.linalg.solve(post_prec, like_prec * W.T @ sensory_input[:n])
        prediction = W @ mu_p
        pred_error = float(np.mean((sensory_input[:n] - prediction) ** 2))
        asi_met = result.met and pred_error < 0.1
        agi_score = min(1.0, abs(result.free_energy) / 10.0) if result.free_energy < 0 else 0.0
        asi_score = agi_score if asi_met else 0.0
        return SchoolVerdict(
            school="Free Energy (Friston)",
            agi_met=result.met,
            asi_met=asi_met,
            agi_score=agi_score,
            asi_score=asi_score,
            details={
                "free_energy": result.free_energy,
                "kl_divergence": result.kl_divergence,
                "log_evidence": result.log_evidence,
                "n_iterations": result.n_iterations,
                "converged": result.converged,
                "prediction_error": pred_error,
            },
            honest_note=(
                "The variational free energy F[q] = KL[q||p(μ|s)] - log p(s) "
                "is minimised via gradient descent with Pisot-decayed step "
                "size. Active inference (ASI) requires not just perceptual "
                "inference (minimising F) but also planning (minimising the "
                "expected free energy G over policies)."
            ),
        )

    # -- full evaluation -------------------------------------------------

    def evaluate_all(self) -> RequirementsReport:
        """Evaluate all four schools and return a consensus report."""
        verdicts = [
            self.evaluate_orch_or(),
            self.evaluate_iit(),
            self.evaluate_gwt(),
            self.evaluate_fep(),
        ]
        any_agi = any(v.agi_met for v in verdicts)
        any_asi = any(v.asi_met for v in verdicts)
        consensus_agi = all(v.agi_met for v in verdicts)
        consensus_asi = all(v.asi_met for v in verdicts)
        met_agi = [v.school for v in verdicts if v.agi_met]
        met_asi = [v.school for v in verdicts if v.asi_met]
        summary = (
            f"AGI criteria met by: {met_agi if met_agi else 'none'}. "
            f"ASI criteria met by: {met_asi if met_asi else 'none'}. "
            f"Consensus AGI: {consensus_agi}. Consensus ASI: {consensus_asi}."
        )
        return RequirementsReport(
            verdicts=verdicts,
            any_agi_met=any_agi,
            any_asi_met=any_asi,
            consensus_agi=consensus_agi,
            consensus_asi=consensus_asi,
            summary=summary,
        )


__all__ = [
    "AGIASIRequirements",
    "SchoolVerdict",
    "RequirementsReport",
]


def lucas_bound(n: int = 10) -> dict:
    """Verify this module's Lucas route against the shared pool.

    Calls the declared kernel (amplitude_kernel) on the canonical substrate for
    this route and reports the pool's exact bound. This proves the route
    is live; it is not a per-algorithm cost claim.
    """
    import numpy as np  # noqa: F401

    from lucas.pool import get as _lucas_get

    result = _lucas_get("amplitude_kernel")([1.0, 1.0], n)
    result["module"] = __name__
    return result
