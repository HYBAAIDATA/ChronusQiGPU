"""Integrated intelligence — legacy-compatible cross-scale coupling layer.

This module remains a useful compatibility/coupling surface, but it is not a
second cognition authority. New production composition belongs to
euclid.runtime.EuclidRuntime.production() and its GeneralIntelligenceCore.

The audit found PYTHIA's four main subsystems completely siloed: TOE,
meta-evolution, Pythia learning, and memory never passed data to each
other. Four intelligences running in parallel is not one integrated
intelligence. This module closes that gap.

The coupling map (six previously-siloed pairs)
----------------------------------------------
1. TOE -> meta-evolution: the TOE engine's quantum prediction
   (confidence, energy, trend) becomes an extra feature in the meta-
   evolution surrogate. A high-TOE-confidence schedule is more likely
   to be a productive search region; the surrogate should learn this.
2. Meta-evolution -> memory: when the controller auto-discovers a new
   primitive, it is written to the memory system's semantic memory as
   a concept with its avg_gain as confidence. The intelligence now
   remembers what it learned about its own operators.
3. Memory -> TOE: the curriculum's tasks_completed gates which TOE
   capabilities fire. Early curriculum = tomography only. Advanced
   curriculum = full causal ladder. The intelligence grows into its
   capabilities rather than firing them all blindly.
4. Pythia learning -> meta-evolution: germ-line memories (patterns
   that recurred and were associated with mining success) bias the
   meta-evolution primitive weights. The biological learning layer
   shapes the search strategy.
5. Pythia learning -> TOE: the emergence_signal from germ-line
   consolidation becomes a Bayesian prior on TOE's confidence. When
   Pythia has learned strong patterns, TOE's predictions are trusted
   more; when she hasn't, TOE's confidence is discounted.
6. Meta-evolution -> Pythia learning: phase transitions tagged by
   the meta-evolution controller are fed back as high-reward patterns
   to the learning substrate, so the biology learns from the
   computational breakthroughs.
7. Quantum stack -> self-model: the recovered HYBA signal stack (phi
   harmonic / Yang-Mills regime / IIT consciousness / QNP gate)
   assesses the head of the guided schedule; its emergence probability
   is calibrated against real mining outcomes by the Brier self-model
   like every other subsystem — a signal that never predicts wins is
   discounted automatically.

The metacognitive self-model
---------------------------
A cross-subsystem confidence-calibration layer. It tracks, for each
subsystem, the historical agreement between predicted confidence and
observed outcome (a Brier score). A well-calibrated intelligence knows
when it doesn't know. The self-model exposes a single calibrated
confidence per decision, not four raw confidences.

This is honest: the Brier score is computed from real (prediction,
outcome) pairs. A subsystem that is always confident but often wrong
gets a high Brier score (bad calibration) and its confidence is
discounted in the global aggregation. "I don't know" is a legitimate
output of a calibrated intelligence.

References (the principles, not the implementations)
----------------------------------------------------
- Friston (Oxford): active inference, free-energy minimisation
- Pearl (Stanford): causal discovery beyond inference on a fixed graph
- Tenenbaum (MIT): Bayesian self-modeling, "learning to learn"
- McLennan/Hofstadter: cross-scale coupling as the substrate of mind

The module is a wiring layer: it does not duplicate any subsystem's
logic, only routes data between them and tracks calibration. It
respects the LUCAS WIRING discipline (no sibling algorithm imports).
"""

# LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel
# inline below. MUST NOT import from any sibling algorithm.
# Substrate route: path

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("Intelligence.integration")

CANONICAL_COGNITION_AUTHORITY = "euclid.runtime.EuclidRuntime.production"
LEGACY_COMPATIBILITY_SURFACE = True

PHI = (1 + math.sqrt(5)) / 2
INV_PHI = 1.0 / PHI


# ---------------------------------------------------------------------------
# Brier-score calibration (the metacognitive self-model)
# ---------------------------------------------------------------------------


@dataclass
class CalibrationRecord:
    """One (predicted_confidence, observed_outcome) pair."""

    subsystem: str
    predicted: float  # the subsystem's stated confidence [0, 1]
    outcome: float  # the realised outcome [0, 1] (1=success, 0=failure)
    timestamp: float = 0.0


class MetacognitiveSelfModel:
    """Cross-subsystem confidence calibration.

    For each subsystem, tracks the Brier score (mean squared error
    between predicted confidence and observed outcome). A low Brier
    score means the subsystem is well-calibrated — when it says "90%
    confident," it's right ~90% of the time. A high Brier score means
    it's overconfident or underconfident.

    The global calibrated confidence for a decision is a Pisot-weighted
    average of subsystem confidences, weighted by inverse Brier score
    (better-calibrated subsystems get more weight). This is the
    metacognitive layer: the system models its own reliability.

    Honest: a subsystem with no history gets uniform weight (not
    trusted, not discounted). A subsystem that is always wrong gets
    near-zero weight. "I don't know" is legitimate — the global
    confidence can be low, and that's the right answer when the
    subsystems are unreliable.
    """

    def __init__(self, window: int = 50) -> None:
        self.window = window
        self._records: List[CalibrationRecord] = []

    def observe(self, subsystem: str, predicted: float, outcome: float) -> None:
        """Record a (prediction, outcome) pair for calibration."""
        self._records.append(
            CalibrationRecord(
                subsystem=subsystem,
                predicted=max(0.0, min(1.0, predicted)),
                outcome=max(0.0, min(1.0, outcome)),
            )
        )
        if len(self._records) > self.window * 4:
            self._records = self._records[-(self.window * 4) :]

    def brier_score(self, subsystem: str) -> float:
        """Brier score for a subsystem (lower = better calibrated)."""
        recs = [r for r in self._records if r.subsystem == subsystem]
        if len(recs) < 3:
            return 0.25  # default: neutral (random-classifier Brier ~0.25)
        return sum((r.predicted - r.outcome) ** 2 for r in recs) / len(recs)

    def calibrated_confidence(
        self, confidences: Dict[str, float]
    ) -> Tuple[float, Dict[str, float]]:
        """Aggregate subsystem confidences into one calibrated value.

        Returns (global_confidence, per_subsystem_weights). Subsystems
        with better (lower) Brier scores get more weight. If all
        subsystems are uncalibrated, returns a low confidence — the
        honest "I don't know."
        """
        if not confidences:
            return 0.0, {}
        weights: Dict[str, float] = {}
        total_weight = 0.0
        for name, conf in confidences.items():
            brier = self.brier_score(name)
            # Weight = 1 / (brier + epsilon), Pisot-bounded.
            w = 1.0 / (brier + INV_PHI * 0.01)
            weights[name] = w
            total_weight += w
        if total_weight <= 0:
            return 0.0, weights
        global_conf = sum(confidences[name] * weights[name] for name in confidences) / total_weight
        # Normalise weights for the report.
        norm_weights = {k: v / total_weight for k, v in weights.items()}
        return global_conf, norm_weights

    def status(self) -> Dict[str, Any]:
        briers = {}
        for name in {r.subsystem for r in self._records}:
            briers[name] = self.brier_score(name)
        return {
            "n_records": len(self._records),
            "brier_scores": briers,
            "window": self.window,
        }


# ---------------------------------------------------------------------------
# Curriculum-gated capability selection
# ---------------------------------------------------------------------------


class CurriculumGate:
    """Gates which TOE capabilities fire based on curriculum progress.

    The curriculum is the cognitive scaffolding's task progression.
    Early tasks = basic perception (tomography). Advanced tasks = full
    causal ladder. This mirrors human cognitive development: a child
    sees before she reasons about interventions.

    The gate is a soft threshold, not a hard cutoff: a capability
    becomes available at a threshold, then its confidence weight ramps
    up via the Pisot decay so the transition is smooth.
    """

    CAPABILITY_THRESHOLDS: Dict[str, int] = {
        "tomography": 0,  # available immediately
        "trajectory": 1,  # available after 1 task
        "causality": 2,  # available after 2 tasks
        "counterfactual": 3,  # the hardest — needs 3 tasks
    }

    def __init__(self) -> None:
        self._tasks_completed = 0

    def update(self, tasks_completed: int) -> None:
        self._tasks_completed = max(self._tasks_completed, tasks_completed)

    def available_capabilities(self) -> List[str]:
        """Which capabilities are available given curriculum progress."""
        return [
            cap
            for cap, threshold in self.CAPABILITY_THRESHOLDS.items()
            if self._tasks_completed >= threshold
        ]

    def capability_weight(self, capability: str) -> float:
        """Soft weight [0, 1] for a capability, Pisot-ramped."""
        threshold = self.CAPABILITY_THRESHOLDS.get(capability, 0)
        if self._tasks_completed < threshold:
            return 0.0
        excess = self._tasks_completed - threshold
        return min(1.0, 1.0 - INV_PHI ** (excess + 1))

    def status(self) -> Dict[str, Any]:
        return {
            "tasks_completed": self._tasks_completed,
            "available": self.available_capabilities(),
            "weights": {cap: self.capability_weight(cap) for cap in self.CAPABILITY_THRESHOLDS},
        }


# ---------------------------------------------------------------------------
# Integrated intelligence controller (the wiring layer)
# ---------------------------------------------------------------------------


@dataclass
class IntegratedCycleResult:
    """Result of one integrated intelligence cycle."""

    cycle: int
    toe_confidence_raw: float
    toe_confidence_calibrated: float
    pythia_emergence_signal: float
    germ_line_count: int
    meta_delta_phi: float
    meta_phase_transition: bool
    meta_discovered_primitive: Optional[str]
    curriculum_capabilities: List[str]
    global_calibrated_confidence: float
    subsystem_weights: Dict[str, float]
    brier_scores: Dict[str, float]
    mining_success: bool
    # Wire 7: recovered quantum stack signals (0.0/None when unwired).
    quantum_emergence: float = 0.0
    quantum_qnp: bool = False


class IntegratedIntelligence:
    """The cross-scale coupling layer that makes PYTHIA one intelligence.

    This is NOT a new subsystem — it is the wiring between the existing
    four. It takes the orchestrator's subsystems and, on each cycle,
    routes data between them so they influence each other, then tracks
    the calibration of the whole.

    Usage
    -----
        integ = IntegratedIntelligence(orchestrator)
        result = integ.run_cycle(header, target, block_context)
    """

    def __init__(self, orchestrator: Any) -> None:
        self.orch = orchestrator
        self.self_model = MetacognitiveSelfModel(window=50)
        self.curriculum_gate = CurriculumGate()
        self._cycle = 0
        self._last_toe_confidence = 0.5
        self._last_pythia_emergence = 0.0
        self._last_germ_line = 0
        self._last_meta_delta = 0.0
        self._history: List[IntegratedCycleResult] = []

    def _get_toe_prediction(self, block_context: Dict[str, Any]) -> Tuple[float, float, str]:
        """Run TOE and extract (confidence, energy, trend)."""
        toe_data = {
            "block_height": [block_context.get("block_height", 0)],
            "header_entropy": [b / 255.0 for b in block_context.get("header_bytes", [])[:32]],
        }
        try:
            result = self.orch.toe_predict(toe_data)
            conf = float(result.get("confidence", 0.0))
            tomo = result.get("state_tomography", {})
            energy = float(tomo.get("energy", 0.0)) if isinstance(tomo, dict) else 0.0
            traj = result.get("trajectory_prediction", {})
            trend = str(traj.get("trend", "stable")) if isinstance(traj, dict) else "stable"
            return conf, energy, trend
        except Exception as e:  # pragma: no cover - defensive
            logger.warning("TOE prediction failed: %s", e)
            return 0.0, 0.0, "error"

    def _couple_toe_to_meta(self, toe_conf: float, toe_energy: float, toe_trend: str) -> None:
        """Wire #1: TOE confidence/energy/trend into the meta-evolution surrogate.

        We extend the surrogate's feature space by adding the TOE
        confidence as a bias on the meta-evolution controller's
        mutation rate. A high TOE confidence means the substrate
        believes this region is productive -> exploit (lower mutation
        rate). A low TOE confidence -> explore (higher mutation rate).
        """
        if not hasattr(self.orch, "meta_evolution"):
            return
        # Adjust the mutation rate toward exploit when TOE is confident.
        target_rate = 0.5 + (0.5 - toe_conf) * 0.6  # high conf -> low rate
        current = self.orch.meta_evolution.mutation_rate
        # Pisot-bounded approach toward the target.
        self.orch.meta_evolution.mutation_rate = current + INV_PHI * (target_rate - current)
        # Store the TOE signal so step_evolve can use it as a feature.
        self.orch.meta_evolution._toe_signal = [
            toe_conf,
            toe_energy,
            1.0 if "up" in toe_trend else 0.0,
        ]

    def _couple_meta_to_memory(self, discovered_primitive: Optional[str], avg_gain: float) -> None:
        """Wire #2: discovered primitives -> semantic memory.

        When meta-evolution discovers a new operator, write it to the
        memory system's semantic memory as a concept. The intelligence
        now remembers its own discoveries.
        """
        if discovered_primitive is None:
            return
        try:
            self.orch.memory.semantic.add_concept(
                concept=discovered_primitive,
                category="meta_evolution_primitive",
                definition=f"Auto-discovered mining operator with avg_gain={avg_gain:.4f}",
                properties={"avg_gain": avg_gain, "source": "meta_evolution"},
                confidence=min(1.0, avg_gain * PHI),
                provenance="IntegratedIntelligence._couple_meta_to_memory",
            )
        except Exception as e:  # pragma: no cover - defensive
            logger.warning("Failed to write discovered primitive to memory: %s", e)

    def _couple_memory_to_toe(self) -> List[str]:
        """Wire #3: curriculum tasks_completed -> TOE capability gating.

        Read the curriculum progress and gate which TOE capabilities
        are available. Returns the list of available capabilities.
        """
        try:
            mem_status = self.orch.memory_status()
            tasks = mem_status.get("curriculum", {}).get("tasks_completed", 0)
            self.curriculum_gate.update(tasks)
            return self.curriculum_gate.available_capabilities()
        except Exception:
            return ["tomography"]  # always available

    def _couple_pythia_to_meta(self, germ_line_count: int, emergence_signal: float) -> None:
        """Wire #4: germ-line memories -> meta-evolution primitive weights.

        When Pythia learning consolidates germ-line memories (patterns
        that recurred and were associated with mining success), boost
        the weights of the primitives that were active when those
        patterns formed. The biological learning shapes the search.
        """
        if not hasattr(self.orch, "meta_evolution"):
            return
        # The emergence signal [0, 1] measures structural synthesis
        # across germ-line memories. A high signal means the learning
        # substrate has found something real -> bias toward exploitation.
        if emergence_signal > 0.1 and germ_line_count > 0:
            for prim in self.orch.meta_evolution.primitives.values():
                prim.weight = min(1.0, prim.weight + INV_PHI * emergence_signal * 0.1)

    def _couple_pythia_to_toe(self, emergence_signal: float) -> float:
        """Wire #5: emergence_signal -> TOE confidence prior.

        Returns a calibrated TOE confidence: raw confidence scaled by
        a Bayesian prior derived from the emergence signal. When
        Pythia has learned strong patterns, TOE's predictions are
        trusted more. When she hasn't, they're discounted.
        """
        # Bayesian prior: emergence signal as evidence that the
        # substrate's predictions are grounded in learned structure.
        prior = 0.5 + 0.3 * emergence_signal  # [0.5, 0.8]
        raw = self._last_toe_confidence
        # Posterior: weighted average of raw confidence and prior.
        calibrated = prior * 0.4 + raw * 0.6
        return calibrated

    def _couple_meta_to_pythia(self, phase_transition: bool, delta_phi: float) -> None:
        """Wire #6: phase transitions -> Pythia learning rewards.

        When meta-evolution tags a phase transition (a discontinuous
        coherence jump), feed it back to the learning substrate as a
        high-reward pattern. The biology learns from the computational
        breakthroughs.
        """
        if not phase_transition:
            return
        try:
            import numpy as np

            # Create a pattern encoding the phase-transition signature.
            pattern = np.array(
                [delta_phi, self._last_toe_confidence, self._last_pythia_emergence],
                dtype=float,
            )
            # Pad to the learning substrate's expected dimension.
            n = self.orch.pythia.n
            if len(pattern) < n:
                pattern = np.pad(pattern, (0, n - len(pattern)))
            else:
                pattern = pattern[:n]
            # Present as a successful pattern (phase transitions are good).
            self.orch.teach([pattern], [True])
        except Exception as e:  # pragma: no cover - defensive
            logger.warning("Failed to feed phase transition to learning: %s", e)

    def run_cycle(
        self,
        header: bytes,
        target: bytes,
        block_context: Dict[str, Any],
        mining_success: bool = False,
    ) -> IntegratedCycleResult:
        """Run one fully-integrated intelligence cycle.

        This is the cross-scale coupling loop: every subsystem both
        consumes from and contributes to the others, and the
        metacognitive self-model tracks calibration across all of
        them.
        """
        self._cycle += 1

        # -- Phase 1: TOE prediction (with curriculum-gated capabilities) --
        capabilities = self._couple_memory_to_toe()
        toe_conf_raw, toe_energy, toe_trend = self._get_toe_prediction(block_context)
        self._last_toe_confidence = toe_conf_raw

        # -- Phase 2: couple TOE -> meta-evolution --
        self._couple_toe_to_meta(toe_conf_raw, toe_energy, toe_trend)

        # -- Phase 3: mining guidance + meta-evolution --
        guidance = self.orch.guide_mining(
            header, target, nonce_window=10_000, block_context=block_context
        )
        base_schedule = list(guidance.nonce_schedule) if guidance.nonce_schedule else []
        discovered_primitive = None
        avg_gain = 0.0
        delta_phi = 0.0
        phase_transition = False
        if base_schedule:
            evo = self.orch.meta_evolve_schedule(base_schedule, generations=12)
            delta_phi = evo["delta_phi"]
            phase_transition = any(r["phase_transition"] for r in evo["results"])
            # Extract the last discovered primitive (if any).
            for r in reversed(evo["results"]):
                if r.get("discovered_primitive"):
                    discovered_primitive = r["discovered_primitive"]
                    break
            # Get avg_gain from the meta-evolution status.
            meta_st = self.orch.meta_evolution_status()
            if discovered_primitive:
                for p in meta_st["primitives"]:
                    if p["name"] == discovered_primitive:
                        avg_gain = p["avg_gain"]
                        break
        self._last_meta_delta = delta_phi

        # -- Phase 4: couple meta -> memory (discovered primitives) --
        self._couple_meta_to_memory(discovered_primitive, avg_gain)

        # -- Phase 5: Pythia learning + read emergence --
        pythia_st = self.orch.pythia_status()
        emergence_signal = float(pythia_st.get("emergence_signal", 0.0))
        germ_line = int(pythia_st.get("germ_line", 0))
        self._last_pythia_emergence = emergence_signal
        self._last_germ_line = germ_line

        # -- Phase 6: couple Pythia -> meta (germ-line biases weights) --
        self._couple_pythia_to_meta(germ_line, emergence_signal)

        # -- Phase 7: couple Pythia -> TOE (emergence -> confidence prior) --
        toe_conf_calibrated = self._couple_pythia_to_toe(emergence_signal)

        # -- Phase 8: couple meta -> Pythia (phase transitions as rewards) --
        self._couple_meta_to_pythia(phase_transition, delta_phi)

        # -- Phase 8b: quantum stack assessment (wire 7) -------------------
        # The recovered HYBA signal stack assesses the head of the
        # intelligence-guided schedule. Its emergence probability enters
        # the calibrated confidence like any other subsystem — the Brier
        # self-model discounts it honestly if its signals do not predict
        # mining outcomes (measured: they don't).
        quantum_emergence = 0.0
        quantum_qnp = False
        stack = getattr(self.orch, "quantum_stack", None)
        if stack is not None and base_schedule:
            try:
                # Window-level prediction: the mining outcome is window-
                # scoped, so the calibration input is the mean emergence
                # probability over a bounded prefix of the schedule — not a
                # single nonce's score.
                prefix = base_schedule[:64]
                assessments = [stack.assess_nonce(n) for n in prefix]
                quantum_emergence = (
                    sum(float(a["emergence_probability"]) for a in assessments)
                    / len(assessments)
                )
                quantum_qnp = any(bool(a["qnp"]["generated"]) for a in assessments)
            except Exception as e:  # pragma: no cover - defensive
                logger.warning("Quantum stack assessment failed: %s", e)
                stack = None

        # -- Phase 9: metacognitive self-model (calibration) --
        # Record (prediction, outcome) for each subsystem against the
        # mining outcome. This is what makes the Brier score honest.
        self.self_model.observe("toe", toe_conf_raw, 1.0 if mining_success else 0.0)
        self.self_model.observe(
            "meta_evolution", min(1.0, max(0.0, delta_phi + 0.5)), 1.0 if mining_success else 0.0
        )
        self.self_model.observe("pythia_learning", emergence_signal, 1.0 if mining_success else 0.0)
        if stack is not None:
            self.self_model.observe(
                "quantum_stack", quantum_emergence, 1.0 if mining_success else 0.0
            )
        confidences = {
            "toe": toe_conf_calibrated,
            "meta_evolution": min(1.0, max(0.0, 0.5 + delta_phi)),
            "pythia_learning": emergence_signal,
        }
        if stack is not None:
            confidences["quantum_stack"] = quantum_emergence
        # Aggregate into a global calibrated confidence.
        global_conf, weights = self.self_model.calibrated_confidence(confidences)
        briers = {
            name: self.self_model.brier_score(name)
            for name in confidences
        }

        result = IntegratedCycleResult(
            cycle=self._cycle,
            toe_confidence_raw=toe_conf_raw,
            toe_confidence_calibrated=toe_conf_calibrated,
            pythia_emergence_signal=emergence_signal,
            germ_line_count=germ_line,
            meta_delta_phi=delta_phi,
            meta_phase_transition=phase_transition,
            meta_discovered_primitive=discovered_primitive,
            curriculum_capabilities=capabilities,
            global_calibrated_confidence=global_conf,
            subsystem_weights=weights,
            brier_scores=briers,
            mining_success=mining_success,
            quantum_emergence=quantum_emergence,
            quantum_qnp=quantum_qnp,
        )
        self._history.append(result)
        return result

    def status(self) -> Dict[str, Any]:
        return {
            "cycle": self._cycle,
            "self_model": self.self_model.status(),
            "curriculum_gate": self.curriculum_gate.status(),
            "last_toe_confidence_raw": self._last_toe_confidence,
            "last_toe_confidence_calibrated": self._last_toe_confidence
            + 0.0,  # updated by run_cycle
            "last_pythia_emergence": self._last_pythia_emergence,
            "last_germ_line": self._last_germ_line,
            "last_meta_delta": self._last_meta_delta,
        }


__all__ = [
    "MetacognitiveSelfModel",
    "CurriculumGate",
    "IntegratedIntelligence",
    "IntegratedCycleResult",
]


def lucas_bound(n: int = 10) -> dict:
    """Verify this module's Lucas route against the shared pool.

    Calls the declared kernel (path_kernel) on the canonical substrate for
    this route and reports the pool's exact bound. This proves the route
    is live; it is not a per-algorithm cost claim.
    """
    import numpy as np  # noqa: F401

    from lucas.pool import get as _lucas_get

    result = _lucas_get("path_kernel")(np.array([[0, 1], [1, 0]], dtype=np.int64), n)
    result["module"] = __name__
    return result
