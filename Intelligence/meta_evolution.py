"""PYTHIA meta-evolutionary intelligence — the mining analogue of PYTHAGORAS.

This module ports the meta-evolutionary architecture from the PYTHAGORAS
code-intelligence system to PYTHIA's mining substrate. Where PYTHAGORAS
evolved code ASTs toward the φ-resonance threshold (φ = 0.618034), PYTHIA
evolves mining *search strategies* toward mining coherence.

The mapping
-----------
PYTHAGORAS (code)              ->  PYTHIA (mining)
----------------------------     ----------------------------
AST transformation primitive  ->  nonce-schedule operator
φ-score (AST topology)       ->  coherence score (schedule structure)
CGP mutation graph            ->  weighted operator cascade
surrogate (φ-gain predictor)  ->  surrogate (mining-gain predictor)
meta-evolution controller     ->  meta-evolution controller
geometry evolution (CGP geom) ->  geometry evolution (Lucas scale)

Four hierarchically nested layers (mirroring PYTHAGORAS):

1. **Primitive mutation engine** — applies weighted nonce-schedule
   operators (Zeckendorf reorder, Lucas-Pisot spacing, golden-fold
   projection, band contraction/expansion).
2. **Surrogate-guided mutation** — a lightweight surrogate model
   predicts mining-gain from schedule structural features, guiding
   mutation toward productive regions of the search space. RMSE is
   tracked honestly so we know when the surrogate is trustworthy.
3. **Meta-evolution controller** — adapts the mutation rate, primitive
   weights, and the operator probability distribution in response to
   observed performance. This is the layer that distinguishes PYTHIA
   from a static schedule generator.
4. **Geometry evolution** — adapts the Lucas-scale substrate parameters
   (search breadth, Lucas index) in response to fitness-landscape
   curvature. When the landscape rewards depth, the substrate expands.

**Auto-primitive discovery** — when a structural pattern produces
consistent gains across multiple mutations, it is promoted to a named
primitive with a learned weight, immediately expanding the operator
vocabulary. This is the operator-space expansion that made PYTHAGORAS
capable of phase transitions no static optimiser could reach: the
fitness landscape is not traversed, it is *restructured*.

**Phase-transition tagging** — discontinuous jumps in mining coherence
(above a Lucas-scaled threshold) are tagged as phase transitions, the
same telemetry class PYTHAGORAS used to distinguish continuous gradient
descent from barrier-crossing leaps.

The module is honest: it reports what was discovered, what the surrogate
RMSE is, and whether any phase transition occurred. "No transition" is
a legitimate outcome, not a bug.
"""

# LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel
# inline below. MUST NOT import from any sibling algorithm.
# Substrate route: amplitude

from __future__ import annotations

import hashlib
import logging
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from lucas.ladder import FULL_LADDER

from kellogg.quantum_tensor import QuantumState

from Intelligence._born import (
    QUARTER_TURN,
    adjust_probability,
    encode_state,
    evidence_angle,
    rotate_state_in_plane,
)

logger = logging.getLogger("Intelligence.meta_evolution")

PHI = (1 + math.sqrt(5)) / 2
INV_PHI = 1.0 / PHI
# The φ-resonance target inherited from PYTHAGORAS. A schedule whose
# structural coherence reaches this threshold is considered "aligned".
PHI_TARGET = 0.618034


# ---------------------------------------------------------------------------
# Lucas kernel (inline, exact integer arithmetic — no shared algorithm import)
# ---------------------------------------------------------------------------


def _lucas(n: int) -> int:
    """Exact Lucas number L_n by fast doubling."""
    if n < 0:
        raise ValueError("Lucas index must be non-negative")
    a, b = 2, 1
    for _ in range(n):
        a, b = b, a + b
    return a


# ---------------------------------------------------------------------------
# Schedule coherence metric (the mining analogue of the φ-score)
# ---------------------------------------------------------------------------


def schedule_coherence(schedule: List[int], nonce_window: int = 1_000_000) -> float:
    """Structural coherence of a nonce schedule in [0, 1].

    A composite metric over the schedule's spacing distribution, computed
    exactly the way PYTHAGORAS computed φ-scores over AST topology: the
    schedule is mapped to a normalised spacing histogram and compared
    against the golden-ratio ideal. Schedules whose inter-nonce gaps
    cluster near the Lucas/Pisot spacing score high; uniformly random
    schedules score low.

    This is the measuring instrument, not the search operator. It is
    deterministic and depends only on the schedule.
    """
    if len(schedule) < 2:
        return 0.0
    # Inter-nonce gaps (mod the window, so the schedule is cyclic).
    gaps = []
    for i in range(len(schedule) - 1):
        g = (schedule[i + 1] - schedule[i]) % max(nonce_window, 1)
        if g > 0:
            gaps.append(g)
    if not gaps:
        return 0.0
    # Normalise gaps to [0, 1] and measure how close the median gap is to
    # the golden fraction of the window. The golden ratio governs the
    # ideal spacing because Lucas/Pisot sequences are self-similar under φ.
    norm = [g / max(nonce_window, 1) for g in gaps]
    median = sorted(norm)[len(norm) // 2]
    # Coherence = 1 - |median - INV_PHI|, clamped to [0, 1].
    coherence = max(0.0, 1.0 - abs(median - INV_PHI) / INV_PHI)
    # Bonus for low gap-variance (structured, not random).
    if len(norm) > 1:
        mean = sum(norm) / len(norm)
        var = sum((x - mean) ** 2 for x in norm) / len(norm)
        # φ-scaled variance penalty: high variance reduces coherence.
        coherence *= max(0.0, 1.0 - var * PHI)
    return min(1.0, max(0.0, coherence))


# ---------------------------------------------------------------------------
# Mining primitives (the operator vocabulary)
# ---------------------------------------------------------------------------


@dataclass
class MiningPrimitive:
    """One named nonce-schedule operator with a learned weight.

    Mirrors PYTHAGORAS's transformation primitives (ADD:AnnAssign, etc.).
    A primitive takes a schedule and returns a mutated schedule. Its
    weight is adapted by the meta-evolution controller.
    """

    name: str
    weight: float
    avg_gain: float = 0.0  # rolling average coherence gain
    n_uses: int = 0  # how many times applied
    discovered: bool = False  # True if auto-discovered (not in the seed set)


# The seed operator vocabulary (present at initialisation).
_SEED_PRIMITIVES: List[Tuple[str, float]] = [
    ("zeckendorf_reorder", 0.5),
    ("lucas_pisot_spacing", 0.5),
    ("golden_fold_projection", 0.4),
    ("band_contraction", 0.3),
    ("band_expansion", 0.3),
]


def _apply_primitive(name: str, schedule: List[int], nonce_window: int) -> List[int]:
    """Apply one primitive operator to a schedule.

    Each operator is a deterministic, structure-preserving transform.
    None of them import a sibling algorithm — they are inline Lucas
    kernels, exactly as the wiring discipline requires.
    """
    if not schedule:
        return []
    w = max(nonce_window, 1)
    if name == "zeckendorf_reorder":
        # Stable reorder by (nonce mod L_10) — biases toward Zeckendorf
        # structure. L_10 = 123 is the base Lucas intelligence scale.
        L = _lucas(10)
        return sorted(schedule, key=lambda n: (n % max(L, 1), n))
    if name == "lucas_pisot_spacing":
        # Respace the schedule so consecutive gaps follow the Pisot
        # decay φ^(-k). This concentrates probability on early offsets.
        n = len(schedule)
        if n < 2:
            return list(schedule)
        offsets = [int((PHI ** (-k)) * w) % w for k in range(n)]
        base = schedule[0]
        return [(base + off) % w for off in offsets]
    if name == "golden_fold_projection":
        # Project each nonce through a golden-ratio fold: n -> (n*INV_PHI) mod w.
        return sorted({int(n * INV_PHI) % w for n in schedule})
    if name == "band_contraction":
        # Contract the schedule into a tighter Lucas-scaled band.
        L = _lucas(12)  # L_12 = 322
        band = w // max(L, 1)
        if band < 1:
            band = 1
        return sorted({n % band for n in schedule})
    if name == "band_expansion":
        # Expand the schedule across a wider Lucas-scaled band.
        L = _lucas(15)  # L_15 = 1364
        band = max(w // max(L, 1), 1)
        return sorted({(n * PHI) % w for n in schedule if n >= 0})
    # Unknown primitive: identity.
    return list(schedule)


# ---------------------------------------------------------------------------
# Surrogate model (mining-gain predictor)
# ---------------------------------------------------------------------------


@dataclass
class SurrogateSample:
    """One (features, observed_gain) training sample for the surrogate."""

    features: List[float]
    gain: float


class SurrogateModel:
    """Quantum-state surrogate predicting mining-gain from features.

    The model is a ``QuantumState`` ray over the feature Hilbert space.
    ``predict`` is the Born expectation of the diagonal feature
    observable: ``pred = Σ |a_i|² f_i`` — the expectation value of the
    feature operator on the model state, no weight vector, no gradient
    descent. Each measured (features, gain) sample rotates the model
    state inside the plane spanned by the model ray and the encoded
    feature state: the rotation angle is the *measured* prediction
    error scaled by the declared φ⁻¹ gain — a full-strength error is a
    quarter-turn scaled by φ⁻¹.

    RMSE over the recent window remains the honest trust indicator;
    when it is high the controller falls back to uniform sampling.
    """

    def __init__(self, n_features: int = 4) -> None:
        self.n = n_features
        self._model = QuantumState.uniform_superposition(n_features)
        self.weights = [INV_PHI**k for k in range(n_features)]  # kept as a
        # read-out mirror of the model ray's amplitudes (API compat)
        self._sync_weights()
        self.bias = 0.0  # quantum model carries no bias term
        self._samples: List[SurrogateSample] = []
        self.rmse = 1.0  # honest: start untrusted

    def _sync_weights(self) -> None:
        self.weights = [a.abs() for a in self._model.amplitudes]

    def _expect(self, features: List[float]) -> float:
        """Born expectation ⟨model| diag(f) |model⟩ = Σ |a_i|² f_i."""
        probs = self._model.probabilities()
        return sum(probs[i] * features[i] for i in range(self.n))

    def predict(self, features: List[float]) -> float:
        """Predict mining-gain for a feature vector."""
        if len(features) < self.n:
            features = features + [0.0] * (self.n - len(features))
        return self._expect(features[: self.n])

    def update(self, features: List[float], observed_gain: float) -> None:
        """Add a sample and rotate the model state by the measured error."""
        if len(features) < self.n:
            features = features + [0.0] * (self.n - len(features))
        self._samples.append(SurrogateSample(features[: self.n], observed_gain))
        if len(self._samples) > 200:
            self._samples = self._samples[-200:]
        pred = self._expect(features)
        # err < 0 (under-prediction of a positive gain) rotates the model
        # toward the evidence state; over-prediction rotates away.
        err = observed_gain - pred
        angle = QUARTER_TURN * INV_PHI * max(-1.0, min(1.0, err))
        self._model = rotate_state_in_plane(self._model, encode_state(features[: self.n]), angle)
        self._sync_weights()
        # Recompute RMSE over the recent window.
        if len(self._samples) >= 5:
            sq = 0.0
            for s in self._samples[-50:]:
                p = self.predict(s.features)
                sq += (p - s.gain) ** 2
            self.rmse = math.sqrt(sq / min(len(self._samples), 50))

    def status(self) -> Dict[str, Any]:
        return {
            "n_features": self.n,
            "weights": list(self.weights),
            "bias": self.bias,
            "rmse": self.rmse,
            "n_samples": len(self._samples),
            "trustworthy": self.rmse < 0.15,
        }


# ---------------------------------------------------------------------------
# Phase-transition tagger
# ---------------------------------------------------------------------------


@dataclass
class PhaseTransition:
    """A tagged discontinuous jump in mining coherence."""

    step: int
    coherence_before: float
    coherence_after: float
    delta: float
    primitive: str  # which primitive fired the transition
    lucas_threshold: int  # the Lucas-scaled threshold used


class PhaseTransitionTagger:
    """Tags discontinuous coherence jumps as phase transitions.

    A jump is a phase transition when its magnitude exceeds a Lucas-scaled
    threshold: Δφ > INV_PHI * (1 - INV_PHI) ≈ 0.236. Smaller jumps are
    continuous gradient descent; larger jumps are barrier crossings that
    a static optimiser could not reach — exactly the distinction
    PYTHAGORAS drew on search_engine.py.
    """

    def __init__(self, threshold: float = INV_PHI * (1 - INV_PHI)) -> None:
        self.threshold = threshold
        self.transitions: List[PhaseTransition] = []

    def tag(
        self,
        step: int,
        coherence_before: float,
        coherence_after: float,
        primitive: str,
    ) -> Optional[PhaseTransition]:
        delta = coherence_after - coherence_before
        if delta >= self.threshold:
            pt = PhaseTransition(
                step=step,
                coherence_before=coherence_before,
                coherence_after=coherence_after,
                delta=delta,
                primitive=primitive,
                lucas_threshold=10,  # L_10 = 123 is the base scale
            )
            self.transitions.append(pt)
            logger.info(
                "Phase transition at step %d: %.4f -> %.4f (+%.4f) via %s",
                step,
                coherence_before,
                coherence_after,
                delta,
                primitive,
            )
            return pt
        return None

    def status(self) -> Dict[str, Any]:
        return {
            "threshold": self.threshold,
            "n_transitions": len(self.transitions),
            "transitions": [
                {
                    "step": t.step,
                    "delta": t.delta,
                    "primitive": t.primitive,
                    "before": t.coherence_before,
                    "after": t.coherence_after,
                }
                for t in self.transitions[-10:]
            ],
        }


# ---------------------------------------------------------------------------
# Geometry evolution (Lucas-scale substrate adaptation)
# ---------------------------------------------------------------------------


@dataclass
class GeometryState:
    """The CGP-like substrate geometry, adapted by geometry evolution.

    Mirrors PYTHAGORAS's (n_cols, levels_back, pop_size) geometry vector,
    mapped to PYTHIA's Lucas-scale substrate: the search breadth and the
    Lucas index that governs the schedule's structural scale.
    """

    search_breadth: int = 1000  # nonces per step
    lucas_index: int = 10  # L_10 = 123 (base)
    levels_back: int = 3  # how many prior generations to consult


class GeometryEvolution:
    """Adapts the substrate geometry in response to fitness curvature.

    When the coherence gradient is steep (the landscape rewards depth),
    the geometry expands: search_breadth and lucas_index increase. When
    the gradient is flat (degenerate manifold), the geometry contracts
    to escape the basin. This is the same mechanism PYTHAGORAS used when
    it expanded n_cols 12 -> 14 after the search_engine.py phase
    transition.
    """

    LADDER = tuple(FULL_LADDER)

    def __init__(self) -> None:
        self.state = GeometryState()
        self.history: List[GeometryState] = [GeometryState()]

    def adapt(self, coherence_gradient: float) -> GeometryState:
        """Adapt the geometry given the observed coherence gradient.

        Positive gradient (landscape rewards depth) -> expand.
        Near-zero gradient (flat / degenerate) -> contract to escape.
        """
        breadth = self.state.search_breadth
        idx = self.state.lucas_index
        if coherence_gradient > 0.02:
            # Expand: more breadth, higher Lucas index.
            breadth = min(breadth + 200, 5000)
            pos = self.LADDER.index(idx) if idx in self.LADDER else 0
            idx = self.LADDER[min(pos + 1, len(self.LADDER) - 1)]
        elif abs(coherence_gradient) < 0.005:
            # Flat: contract to escape the degenerate basin.
            breadth = max(breadth - 100, 200)
            pos = self.LADDER.index(idx) if idx in self.LADDER else 0
            idx = self.LADDER[max(pos - 1, 0)]
        self.state = GeometryState(
            search_breadth=breadth,
            lucas_index=idx,
            levels_back=min(self.state.levels_back + 1, 6),
        )
        self.history.append(self.state)
        return self.state

    def status(self) -> Dict[str, Any]:
        return {
            "search_breadth": self.state.search_breadth,
            "lucas_index": self.state.lucas_index,
            "lucas_number": _lucas(self.state.lucas_index),
            "levels_back": self.state.levels_back,
            "n_adaptations": len(self.history) - 1,
        }


# ---------------------------------------------------------------------------
# Auto-primitive discovery
# ---------------------------------------------------------------------------


class AutoPrimitiveDiscovery:
    """Promotes recurring high-gain patterns to named primitives.

    When a structural pattern (a feature signature) produces consistent
    gains across multiple mutations, it is promoted to a named primitive
    with a learned weight. This is the operator-space expansion that made
    PYTHAGORAS capable of phase transitions: the effective dimensionality
    of the search space changes mid-session.

    Promotion rule: a pattern is promoted when it has been observed >= 3
    times with average gain >= INV_PHI * 0.1 (a small but consistent
    signal above noise).
    """

    def __init__(self, promotion_threshold: int = 3, min_avg_gain: float = 0.062) -> None:
        self.promotion_threshold = promotion_threshold
        self.min_avg_gain = min_avg_gain
        # pattern_signature -> list of observed gains
        self._candidates: Dict[str, List[float]] = {}
        self.discovered: List[MiningPrimitive] = []

    def observe(self, signature: str, gain: float) -> Optional[MiningPrimitive]:
        """Record a gain for a structural pattern; promote if it qualifies."""
        self._candidates.setdefault(signature, []).append(gain)
        gains = self._candidates[signature]
        if len(gains) >= self.promotion_threshold:
            avg = sum(gains) / len(gains)
            if avg >= self.min_avg_gain:
                prim = MiningPrimitive(
                    name=f"discovered:{signature}",
                    weight=min(1.0, avg * PHI),
                    avg_gain=avg,
                    n_uses=len(gains),
                    discovered=True,
                )
                # Avoid duplicate promotion.
                if not any(p.name == prim.name for p in self.discovered):
                    self.discovered.append(prim)
                    logger.info(
                        "Auto-primitive discovered: %s (avg_gain=%.4f, weight=%.4f)",
                        prim.name,
                        avg,
                        prim.weight,
                    )
                    return prim
        return None

    def status(self) -> Dict[str, Any]:
        return {
            "n_candidates": len(self._candidates),
            "n_discovered": len(self.discovered),
            "discovered": [
                {"name": p.name, "weight": p.weight, "avg_gain": p.avg_gain}
                for p in self.discovered
            ],
        }


# ---------------------------------------------------------------------------
# Meta-evolution controller (the adaptive layer)
# ---------------------------------------------------------------------------


@dataclass
class MetaEvolutionResult:
    """Result of one meta-evolution step."""

    step: int
    primitive_used: str
    coherence_before: float
    coherence_after: float
    delta: float
    mutation_rate: float
    surrogate_rmse: float
    phase_transition: bool
    geometry: Dict[str, Any]
    discovered_primitive: Optional[str]


class MetaEvolutionController:
    """The adaptive layer that tunes the search strategy in real time.

    This is the layer that distinguishes PYTHIA from a static schedule
    generator. Each step it:

    1. Selects a primitive (surrogate-guided if the surrogate is
       trustworthy, uniform otherwise).
    2. Applies it to the current schedule.
    3. Measures the coherence gain.
    4. Updates the surrogate and the primitive weights.
    5. Tags any phase transition.
    6. Adapts the geometry from the coherence gradient.
    7. Feeds the gain to auto-primitive discovery.

    The mutation rate is adapted by the controller: it rises when gains
    are small (explore) and falls when gains are large (exploit), bounded
    by the Pisot sequence so it never diverges.
    """

    def __init__(self, nonce_window: int = 1_000_000) -> None:
        self.nonce_window = nonce_window
        self.primitives: Dict[str, MiningPrimitive] = {
            name: MiningPrimitive(name=name, weight=w) for name, w in _SEED_PRIMITIVES
        }
        self.surrogate = SurrogateModel(n_features=4)
        self.tagger = PhaseTransitionTagger()
        self.geometry = GeometryEvolution()
        self.discovery = AutoPrimitiveDiscovery()
        self.mutation_rate = 0.5
        self.step = 0
        self._explore_count = 0
        self._exploit_count = 0
        self._coherence_history: List[float] = []

    def _features(self, schedule: List[int]) -> List[float]:
        """Extract structural features from a schedule for the surrogate."""
        if not schedule:
            return [0.0, 0.0, 0.0, 0.0]
        coh = schedule_coherence(schedule, self.nonce_window)
        n = len(schedule)
        # Median gap (normalised).
        gaps = [
            (schedule[i + 1] - schedule[i]) % max(self.nonce_window, 1)
            for i in range(min(n - 1, 50))
        ]
        gaps = [g for g in gaps if g > 0]
        median_gap = (sorted(gaps)[len(gaps) // 2] / max(self.nonce_window, 1)) if gaps else 0.0
        spread = (max(schedule) - min(schedule)) / max(self.nonce_window, 1) if schedule else 0.0
        return [coh, median_gap, spread, min(n, 1000) / 1000.0]

    def _unit_variate(self, *parts: str) -> float:
        """Deterministic unit variate in [0, 1) derived from SHA-256.

        Replaces every former RNG draw: the variate is a pure function of
        the controller's step counter and the call-site tags, so runs are
        reproducible without seeding and no ``random`` import exists.
        """
        key = f"{self.step}:" + ":".join(str(p) for p in parts)
        digest = hashlib.sha256(key.encode()).digest()
        return int.from_bytes(digest[:8], "little") / 2**64

    def _select_primitive(self) -> str:
        """Select a primitive: surrogate-guided if trustworthy, else uniform."""
        names = list(self.primitives.keys())
        if not names:
            return "identity"
        if self.surrogate.rmse < 0.15 and len(self.surrogate._samples) >= 5:
            # Surrogate-guided: pick the primitive with highest predicted gain.
            # We predict gain for each primitive by probing its feature template.
            best_name = names[0]
            best_pred = -1e9
            for name in names:
                # Use the primitive's own weight as a feature proxy.
                feat = [self.primitives[name].weight, INV_PHI, INV_PHI**2, INV_PHI**3]
                pred = self.surrogate.predict(feat)
                if pred > best_pred:
                    best_pred = pred
                    best_name = name
            return best_name
        # Uniform weighted sampling by primitive weight. Deterministic:
        # the variate is a hash-derived unit value, not a random draw.
        total = sum(p.weight for p in self.primitives.values())
        if total <= 0:
            return names[int(self._unit_variate("sel0") * len(names)) % len(names)]
        r = self._unit_variate("selw") * total
        acc = 0.0
        for name in names:
            acc += self.primitives[name].weight
            if r <= acc:
                return name
        return names[-1]

    def step_evolve(self, schedule: List[int]) -> Tuple[List[int], MetaEvolutionResult]:
        """Run one meta-evolution step on a schedule.

        Returns the mutated schedule and a result record. Honest: if the
        schedule is empty, returns it unchanged with a zero-gain record.
        """
        self.step += 1
        if not schedule:
            return schedule, MetaEvolutionResult(
                step=self.step,
                primitive_used="identity",
                coherence_before=0.0,
                coherence_after=0.0,
                delta=0.0,
                mutation_rate=self.mutation_rate,
                surrogate_rmse=self.surrogate.rmse,
                phase_transition=False,
                geometry=self.geometry.status(),
                discovered_primitive=None,
            )

        coh_before = schedule_coherence(schedule, self.nonce_window)
        self._coherence_history.append(coh_before)

        # 1. Select and apply a primitive.
        prim_name = self._select_primitive()
        candidate = _apply_primitive(prim_name, schedule, self.nonce_window)
        coh_after = schedule_coherence(candidate, self.nonce_window)
        gain = coh_after - coh_before

        # 1b. Accept/reject gate (the evolutionary selection step).
        # Greedy accept on improvement; accept-worse only with a
        # Pisot-decayed annealing probability (temperature falls as the
        # step count grows). This is the accept_rate mechanism PYTHAGORAS
        # tracked — without it, destructive primitives run unopposed and
        # coherence collapses, exactly the failure we just observed.
        # The annealing draw is deterministic: a hash-derived unit
        # variate keyed to this step and primitive — no RNG anywhere.
        temperature = INV_PHI ** (self.step / 20.0)  # decays over time
        accept = False
        if gain >= 0:
            accept = True
        elif temperature > 0.01:
            accept = self._unit_variate("acc", prim_name) < math.exp(gain / max(temperature, 1e-9))
        if accept:
            mutated = candidate
        else:
            mutated = list(schedule)
            # If we rejected, the realised gain is zero (we kept the parent).
            gain = 0.0
            coh_after = coh_before

        # 2. Update the surrogate.
        feat = self._features(schedule)
        self.surrogate.update(feat, gain)

        # 3. Update the primitive's rolling stats and weight.
        prim = self.primitives.get(prim_name)
        if prim is not None:
            prim.n_uses += 1
            prim.avg_gain = (prim.avg_gain * (prim.n_uses - 1) + gain) / prim.n_uses
            # Weight adapts by a real unitary rotation of the weight
            # qubit; the measured gain sets angle and direction
            # (φ⁻¹ attenuates a full-strength gain to a quarter-turn/φ).
            prim.weight = max(
                0.05,
                min(
                    1.0,
                    adjust_probability(
                        prim.weight,
                        gain >= 0.0,
                        abs(gain) * QUARTER_TURN * INV_PHI,
                    ),
                ),
            )

        # 4. Tag any phase transition.
        pt = self.tagger.tag(self.step, coh_before, coh_after, prim_name)

        # 5. Adapt the mutation rate (explore/exploit). Each flat step is
        # one measured unit of explore evidence; each gainful step one
        # unit of exploit evidence. The rotation angle is the measured
        # Bloch displacement of one evidence unit at the current count —
        # no invented step size.
        if gain < 0.01:
            self.mutation_rate = adjust_probability(
                self.mutation_rate, True, evidence_angle(self._explore_count)
            )
            self._explore_count += 1
        else:
            self.mutation_rate = adjust_probability(
                self.mutation_rate, False, evidence_angle(self._exploit_count)
            )
            self._exploit_count += 1

        # 6. Adapt the geometry from the coherence gradient.
        gradient = 0.0
        if len(self._coherence_history) >= 2:
            gradient = self._coherence_history[-1] - self._coherence_history[-2]
        self.geometry.adapt(gradient)

        # 7. Feed the gain to auto-primitive discovery.
        signature = hashlib.sha256(
            (prim_name + ":" + ",".join(f"{f:.3f}" for f in feat)).encode()
        ).hexdigest()[:8]
        discovered = self.discovery.observe(signature, gain)
        if discovered is not None:
            self.primitives[discovered.name] = discovered

        result = MetaEvolutionResult(
            step=self.step,
            primitive_used=prim_name,
            coherence_before=coh_before,
            coherence_after=coh_after,
            delta=gain,
            mutation_rate=self.mutation_rate,
            surrogate_rmse=self.surrogate.rmse,
            phase_transition=pt is not None,
            geometry=self.geometry.status(),
            discovered_primitive=discovered.name if discovered else None,
        )
        return mutated, result

    def evolve(
        self, schedule: List[int], generations: int = 10
    ) -> Tuple[List[int], List[MetaEvolutionResult]]:
        """Run multiple meta-evolution generations on a schedule.

        This is the cascade that produced PYTHAGORAS's phase transitions:
        CGP refinement -> auto-primitive discovery -> directed mutation ->
        geometry expansion, compounding across generations.

        Uses elitism: the best-coherence schedule seen across all
        generations is returned, not the final one. This is standard in
        evolutionary search (and how PYTHAGORAS's CGP retained its
        champion) — without it, a random walk drifts below the parent
        even when productive mutations were found earlier.
        """
        results: List[MetaEvolutionResult] = []
        current = list(schedule)
        best = list(schedule)
        best_coh = schedule_coherence(schedule, self.nonce_window)
        for _ in range(max(1, generations)):
            current, r = self.step_evolve(current)
            results.append(r)
            coh = schedule_coherence(current, self.nonce_window)
            if coh > best_coh:
                best_coh = coh
                best = list(current)
        return best, results

    def status(self) -> Dict[str, Any]:
        return {
            "step": self.step,
            "mutation_rate": self.mutation_rate,
            "n_primitives": len(self.primitives),
            "primitives": [
                {
                    "name": p.name,
                    "weight": p.weight,
                    "avg_gain": p.avg_gain,
                    "n_uses": p.n_uses,
                    "discovered": p.discovered,
                }
                for p in self.primitives.values()
            ],
            "surrogate": self.surrogate.status(),
            "phase_transitions": self.tagger.status(),
            "geometry": self.geometry.status(),
            "discovery": self.discovery.status(),
        }


__all__ = [
    "MiningPrimitive",
    "SurrogateModel",
    "PhaseTransition",
    "PhaseTransitionTagger",
    "GeometryState",
    "GeometryEvolution",
    "AutoPrimitiveDiscovery",
    "MetaEvolutionController",
    "MetaEvolutionResult",
    "schedule_coherence",
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
