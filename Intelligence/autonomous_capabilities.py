"""Autonomous capabilities — training layer for the three HYBA autonomies.

This module carries the *training* machinery for the three autonomous
capabilities that already exist in the repository:

1. Self-healing    — a fault-handler registry and a heal loop that probes
                     registered subsystems, dispatches the registered repair,
                     verifies the subsystem is HEALTHY afterwards, and
                     escalates faults it cannot repair.
2. Self-optimising — a CUOP meter (Completed Useful Operations per Watt
                     per Dollar) fed by measured telemetry, plus a golden
                     step learner that tunes a scalar parameter against
                     measured CUOP only.
3. Agentic mining  — a ValidityLearner that scores precomputed candidates
                     so phase 4 probes them in a learned order (it never
                     marks a candidate invalid), and a CoolDownController
                     that adapts the next cycle's submission rate from the
                     measured rejection rate.

Every event is appended to a CassiniCycleLedger: entry ``n`` carries the
exact sign of the Cassini determinant ``L_n^2 - 5 F_n^2 = 4 (-1)^n`` as its
``cassini_fingerprint``, and each entry is hash-chained to its predecessor
like the TOE provenance ledger.

Honesty boundary (AGENTS.md):
- ``theorem_proven`` stays False everywhere.
- CUOP improvements are only ever deltas of two measured readings; any
  prediction is explicitly labelled a projection.
- A repair is claimed only when the post-repair probe reports HEALTHY.
- The ValidityLearner reorders probes; it cannot suppress a candidate.
- Local SHA256d is the sole acceptance authority — nothing here votes on
  share validity.

Purity note: this is a leaf subsystem module. It imports only stdlib,
numpy, the declared substrate ``hardened_unified_substrate``, and the
``lucas`` pool. Subsystems it supervises (Salamander engine, mining
workflow, telemetry collectors) are injected by the wiring layer.

LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel
inline below. MUST NOT import from any sibling algorithm.
Substrate route: gap
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

try:
    from toe.hardened_unified_substrate import CassiniVerifier
except ImportError:
    from toe.hardened_unified_substrate import CassiniVerifier

from kellogg.quantum_tensor import QuantumState

from Intelligence._born import (
    QUARTER_TURN,
    encode_state,
    rotate_state_in_plane,
)

logger = logging.getLogger("Intelligence.autonomous_capabilities")

THEOREM_PROVEN = False

PHI = (1.0 + float(np.sqrt(5.0))) / 2.0
INV_PHI = 1.0 / PHI


# ---------------------------------------------------------------------------
# Cassini cycle ledger
# ---------------------------------------------------------------------------


def cassini_fingerprint(n: int) -> int:
    """Exact Cassini fingerprint of cycle ``n``.

    The Cassini identity states ``L_n^2 - 5 F_n^2 = 4 (-1)^n``. The
    fingerprint is the *sign of the measured determinant* — it is computed
    from the exact integer Lucas/Fibonacci values, not from a parity flag,
    so every emitted fingerprint is itself a verified identity evaluation.
    """
    if n < 0:
        raise ValueError("cassini_fingerprint requires n >= 0")
    l_n = CassiniVerifier.lucas(n)
    f_n = CassiniVerifier.fibonacci(n)
    determinant = l_n * l_n - 5 * f_n * f_n
    if determinant != 4 * ((-1) ** n):
        raise ArithmeticError(
            f"Cassini identity violated at n={n}: {determinant} != {4 * ((-1) ** n)}"
        )
    return 1 if determinant > 0 else -1


@dataclass
class LedgerEntry:
    """One fingerprinted, hash-chained audit record."""

    index: int
    kind: str
    payload: Dict[str, Any]
    cassini_fingerprint: int
    timestamp: float = field(default_factory=time.time)
    prev_hash: str = ""
    provenance_hash: str = ""

    def __post_init__(self) -> None:
        self.payload = json.loads(json.dumps(self.payload, default=str))
        if not self.provenance_hash:
            self.provenance_hash = self.compute_hash()

    def compute_hash(self) -> str:
        seed = (
            f"{self.index}:{self.kind}:{self.cassini_fingerprint}:{self.timestamp}"
            f":{json.dumps(self.payload, sort_keys=True, default=str)}:{self.prev_hash}"
        )
        return hashlib.sha256(seed.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "kind": self.kind,
            "payload": self.payload,
            "cassini_fingerprint": self.cassini_fingerprint,
            "timestamp": self.timestamp,
            "prev_hash": self.prev_hash,
            "provenance_hash": self.provenance_hash,
            "theorem_proven": False,
        }


class CassiniCycleLedger:
    """Append-only audit log for autonomous-capability events.

    Entry ``n`` carries ``cassini_fingerprint = sign(L_n^2 - 5 F_n^2)`` and a
    hash chained to its predecessor, so reordering, insertion, or mutation is
    detectable through :meth:`verify`.
    """

    def __init__(self) -> None:
        self.entries: List[LedgerEntry] = []

    def log(self, kind: str, payload: Dict[str, Any]) -> LedgerEntry:
        entry = LedgerEntry(
            index=len(self.entries),
            kind=kind,
            payload=payload,
            cassini_fingerprint=cassini_fingerprint(len(self.entries)),
            prev_hash=self.entries[-1].provenance_hash if self.entries else "",
        )
        self.entries.append(entry)
        return entry

    def verify(self) -> bool:
        """Recompute every fingerprint, hash, and chain link."""
        prev = ""
        for entry in self.entries:
            if (
                entry.prev_hash != prev
                or entry.cassini_fingerprint != cassini_fingerprint(entry.index)
                or entry.provenance_hash != entry.compute_hash()
            ):
                return False
            prev = entry.provenance_hash
        return True

    def to_list(self) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self.entries]

    def seal(self) -> Dict[str, Any]:
        """Hash-seal the ledger — the artifact of a training session.

        Mirrors the repository's seal convention: a sha256 over the
        canonical JSON body, plus the Cassini fingerprint of the sealed
        entry count. ``chain_verified`` is recomputed, never assumed.
        """
        body = json.dumps(self.to_list(), sort_keys=True, default=str).encode("utf-8")
        return {
            "body_hash": hashlib.sha256(body).hexdigest(),
            "algorithm": "sha256",
            "entries": len(self.entries),
            "chain_verified": self.verify(),
            "seal_fingerprint": cassini_fingerprint(len(self.entries)),
            "theorem_proven": False,
        }


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Self-healing — fault handler registry and verified heal loop
# ---------------------------------------------------------------------------

# Every fault type the Salamander stack can currently raise. RepairEngine
# diagnoses the first four; HomeostasisMonitor raises the middle three;
# the workflow layer raises the last two.
KNOWN_FAULT_TYPES = frozenset(
    {
        "timeout",
        "memory_error",
        "numerical_drift",
        "circuit_open",
        "reduce_load",
        "circuit_break",
        "recalibrate",
        "subsystem_stall",
        "prediction_failure",
    }
)

# Canonical repair action name per fault type. Mirrors
# SelfRepairEngine.diagnose so the proposal and the executed repair agree.
DEFAULT_REPAIR_ACTIONS: Dict[str, str] = {
    "timeout": "reduce_batch_size",
    "memory_error": "reduce_memory_footprint",
    "numerical_drift": "switch_to_exact_arithmetic",
    "circuit_open": "half_open_probe",
    "reduce_load": "reduce_load",
    "circuit_break": "open_circuit_breaker",
    "recalibrate": "recalibrate",
    "subsystem_stall": "restart_subsystem",
    "prediction_failure": "recalibrate_predictor",
}

STATUS_HEALTHY = "HEALTHY"
STATUS_ESCALATED = "ESCALATED"


@dataclass
class FaultRecord:
    """Self-healing training record — detection AND repair, or escalation."""

    fault_type: str
    subsystem: str
    detected_at: str
    repaired_at: Optional[str]
    repair_action: str
    final_status: str
    cassini_fingerprint: int = 0
    escalated: bool = False
    proposal_id: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "fault_type": self.fault_type,
            "subsystem": self.subsystem,
            "detected_at": self.detected_at,
            "repaired_at": self.repaired_at,
            "repair_action": self.repair_action,
            "final_status": self.final_status,
            "cassini_fingerprint": self.cassini_fingerprint,
            "escalated": self.escalated,
            "proposal_id": self.proposal_id,
            "theorem_proven": False,
        }


@dataclass
class _SubsystemHandle:
    """A monitored subsystem: a health probe plus repair callables per fault."""

    name: str
    probe: Callable[[], str]
    repairs: Dict[str, Callable[[], bool]]


class SelfHealingLoop:
    """Verified heal loop driven by the Salamander engine.

    Each registered subsystem contributes a ``probe()`` that returns
    ``"HEALTHY"`` or a fault type, and repair callables keyed by fault type.
    A heal cycle:

      1. probes every registered subsystem (detection),
      2. asks the engine's ``self_repair`` to diagnose the fault (proposal),
      3. executes the registered repair callable (repair),
      4. re-probes the subsystem (verification),
      5. claims HEALTHY only when the post-repair probe says so — otherwise
         escalates, never silently ignores,
      6. logs the whole event to the Cassini ledger.
    """

    def __init__(self, engine: Any = None, ledger: Optional[CassiniCycleLedger] = None) -> None:
        self.engine = engine
        self.ledger = ledger or CassiniCycleLedger()
        # A repair action name is registered for every known fault type.
        self.repair_actions: Dict[str, str] = dict(DEFAULT_REPAIR_ACTIONS)
        self._handles: Dict[str, _SubsystemHandle] = {}
        self.escalations: List[FaultRecord] = []
        self.records: List[FaultRecord] = []

    # -- registration ------------------------------------------------------

    def register_handler(self, fault_type: str, action_name: str) -> None:
        """Register (or override) the repair action name for a fault type."""
        self.repair_actions[fault_type] = action_name

    def registered_fault_types(self) -> List[str]:
        return sorted(self.repair_actions)

    def register_subsystem(
        self,
        name: str,
        probe: Callable[[], str],
        repairs: Optional[Dict[str, Callable[[], bool]]] = None,
    ) -> None:
        """Monitor a subsystem.

        ``probe()`` returns ``"HEALTHY"`` or a fault type string.
        ``repairs[fault_type]() -> bool`` performs the repair and reports
        whether it executed; HEALTHY is still only claimed after the probe
        confirms it.
        """
        self._handles[name] = _SubsystemHandle(name=name, probe=probe, repairs=dict(repairs or {}))

    def unregister_subsystem(self, name: str) -> None:
        self._handles.pop(name, None)

    # -- the loop ------------------------------------------------------------

    def _diagnose(self, fault_type: str, subsystem: str) -> str:
        """Ask the Salamander engine for a repair proposal, if attached."""
        if self.engine is None or not hasattr(self.engine, "self_repair"):
            return ""
        proposal = self.engine.self_repair.diagnose(fault_type, {"component": subsystem})
        return proposal.proposal_id

    def heal_cycle(self) -> List[FaultRecord]:
        """Probe every registered subsystem; repair or escalate each fault."""
        cycle_records: List[FaultRecord] = []
        for name, handle in list(self._handles.items()):
            fault = handle.probe()
            if fault == STATUS_HEALTHY:
                continue

            record = FaultRecord(
                fault_type=fault,
                subsystem=name,
                detected_at=_utc_now_iso(),
                repaired_at=None,
                repair_action=self.repair_actions.get(fault, "log_and_escalate"),
                final_status=STATUS_ESCALATED,
                proposal_id=self._diagnose(fault, name),
            )

            repair = handle.repairs.get(fault)
            if repair is not None:
                try:
                    executed = bool(repair())
                except Exception as exc:  # repair attempt itself failed
                    logger.warning("[SELF-HEAL] repair of %s on %s raised: %s", fault, name, exc)
                    executed = False
                # Verification is a fresh probe, not the repair's own claim.
                post = handle.probe()
                if executed and post == STATUS_HEALTHY:
                    record.final_status = STATUS_HEALTHY
                    record.repaired_at = _utc_now_iso()
                    record.escalated = False
                else:
                    record.escalated = True
            else:
                # No repair registered for this fault type on this subsystem:
                # escalate, never ignore.
                record.escalated = True

            if record.escalated:
                self.escalations.append(record)
                if self.engine is not None and hasattr(self.engine, "self_repair"):
                    # Route the escalation through the diagnosis channel so it
                    # is visible in the engine's repair status.
                    self._diagnose("unclassified", name)

            entry = self.ledger.log("self_healing", record.as_dict())
            record.cassini_fingerprint = entry.cassini_fingerprint

            self.records.append(record)
            cycle_records.append(record)
        return cycle_records

    def status(self) -> Dict[str, Any]:
        return {
            "monitored_subsystems": sorted(self._handles),
            "registered_fault_types": self.registered_fault_types(),
            "total_faults": len(self.records),
            "healed": sum(1 for r in self.records if r.final_status == STATUS_HEALTHY),
            "escalated": len(self.escalations),
            "theorem_proven": False,
        }


# ---------------------------------------------------------------------------
# Self-optimising — CUOP metering and the golden-step parameter learner
# ---------------------------------------------------------------------------

JOULES_PER_KWH = 3.6e6
DEFAULT_USD_PER_KWH = 0.10


@dataclass
class CuopReading:
    """One measured CUOP observation.

    ``cuop = completed_useful_ops / (mean_power_w * cost_dollars)`` where
    ``cost_dollars`` is the measured energy spend over the window. Every
    field is measured or derived directly from measured fields — never a
    projection.
    """

    useful_ops: float
    mean_power_w: float
    window_s: float
    energy_joules: float
    cost_dollars: float
    cuop: float
    ops_per_joule: float
    is_projection: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "useful_ops": self.useful_ops,
            "mean_power_w": self.mean_power_w,
            "window_s": self.window_s,
            "energy_joules": self.energy_joules,
            "cost_dollars": self.cost_dollars,
            "cuop": self.cuop,
            "ops_per_joule": self.ops_per_joule,
            "is_projection": self.is_projection,
            "theorem_proven": False,
        }


class CuopMeter:
    """Computes CUOP from measured inputs only.

    CUOP — Completed Useful Operations per Watt per Dollar:

        cuop = useful_ops / (mean_power_w * cost_dollars)
        cost_dollars = (mean_power_w * window_s / JOULES_PER_KWH) * usd_per_kwh

    A baseline and a post-change reading produced by the same meter are
    directly comparable; the delta between them is the only quantity this
    system ever claims as an improvement.
    """

    def __init__(self, usd_per_kwh: float = DEFAULT_USD_PER_KWH) -> None:
        if usd_per_kwh <= 0:
            raise ValueError("usd_per_kwh must be positive")
        self.usd_per_kwh = float(usd_per_kwh)

    def measure(
        self,
        *,
        useful_ops: float,
        mean_power_w: float,
        window_s: float,
    ) -> CuopReading:
        ops = max(0.0, float(useful_ops))
        power = max(0.0, float(mean_power_w))
        seconds = max(0.0, float(window_s))
        energy_j = power * seconds
        cost = (energy_j / JOULES_PER_KWH) * self.usd_per_kwh
        denominator = power * cost
        cuop = ops / denominator if denominator > 0 else 0.0
        ops_per_joule = ops / energy_j if energy_j > 0 else 0.0
        return CuopReading(
            useful_ops=ops,
            mean_power_w=power,
            window_s=seconds,
            energy_joules=energy_j,
            cost_dollars=cost,
            cuop=cuop,
            ops_per_joule=ops_per_joule,
        )

    def measure_telemetry_window(
        self,
        *,
        before: Dict[str, float],
        telemetry: Any,
        mean_power_w: float,
    ) -> CuopReading:
        """Measured CUOP over a telemetry window.

        ``before`` is a snapshot ``{"work_items": ..., "busy_s": ...}`` taken
        before the window; the deltas against the live collector are the
        measured useful operations and busy seconds.
        """
        ops = float(telemetry.work_items_total) - float(before.get("work_items", 0.0))
        seconds = float(telemetry.busy_seconds) - float(before.get("busy_s", 0.0))
        return self.measure(useful_ops=ops, mean_power_w=mean_power_w, window_s=seconds)


def telemetry_snapshot(telemetry: Any) -> Dict[str, float]:
    """Snapshot the cumulative counters a CUOP window is measured against."""
    return {
        "work_items": float(telemetry.work_items_total),
        "busy_s": float(telemetry.busy_seconds),
    }


class CuopLearner:
    """Golden-step hill climber over one scalar parameter.

    Training data is the measured history ``(parameter_value, cuop)``.
    ``suggest()`` proposes the next value: continue in the direction that
    last improved CUOP, growing the step by ``phi``; on a measured
    regression, flip direction and contract the step by ``1/phi``. The
    first move explores upward (larger batches amortize dispatch cost in
    this substrate). ``predict()`` is an explicitly labelled projection —
    it is never mixed into a claimed improvement.
    """

    def __init__(
        self,
        name: str,
        getter: Callable[[], float],
        setter: Callable[[float], None],
        lo: float,
        hi: float,
        rel_step: float = 0.25,
    ) -> None:
        if hi <= lo:
            raise ValueError("CuopLearner requires hi > lo")
        self.name = name
        self._get = getter
        self._set = setter
        self.lo = float(lo)
        self.hi = float(hi)
        self.rel_step = float(rel_step)
        self.direction = 1
        self.history: List[Tuple[float, float]] = []

    @property
    def value(self) -> float:
        return float(self._get())

    def record(self, cuop: float) -> None:
        self.history.append((self.value, float(cuop)))

    def suggest(self) -> float:
        """Next parameter value to try, from measured history only."""
        if len(self.history) >= 2:
            (_, cuop_prev), (_, cuop_last) = self.history[-2], self.history[-1]
            if cuop_last >= cuop_prev:
                self.rel_step *= PHI  # keep going, grow confidence
            else:
                self.direction = -self.direction
                self.rel_step /= PHI  # regress: reverse and shrink
        candidate = self.value * (1.0 + self.direction * self.rel_step)
        return min(self.hi, max(self.lo, candidate))

    def apply(self, value: float) -> float:
        clamped = min(self.hi, max(self.lo, float(value)))
        self._set(clamped)
        return clamped

    def predict(self, value: float) -> Dict[str, Any]:
        """Labelled projection of CUOP at ``value`` — never a measurement."""
        if len(self.history) >= 2:
            (v1, c1), (v2, c2) = self.history[-2], self.history[-1]
            slope = (c2 - c1) / (v2 - v1) if v2 != v1 else 0.0
            projected = c2 + slope * (value - v2)
        else:
            projected = self.history[-1][1] if self.history else 0.0
        return {
            "parameter": self.name,
            "value": value,
            "projected_cuop": projected,
            "is_projection": True,
            "projection_is_measured": False,
            "theorem_proven": False,
        }


class SelfOptimisingLoop:
    """Measure -> tune -> re-measure cycle for CUOP.

    ``measure_fn()`` returns a fresh measured :class:`CuopReading`, or
    ``None`` when an input CUOP needs is Unavailable.
    Each optimisation step: the learner suggests a parameter value, it is
    applied, CUOP is re-measured, and the configuration is kept only when
    the measured CUOP is at least the running best — otherwise the previous
    best parameters are restored. The claimed delta is always the measured
    delta of the active configuration versus the recorded baseline. An
    Unavailable reading is never scored: the cycle stops, the parameter under
    test is restored, and the report carries no delta.
    """

    def __init__(
        self,
        meter: CuopMeter,
        learners: Optional[List[CuopLearner]] = None,
        ledger: Optional[CassiniCycleLedger] = None,
    ) -> None:
        self.meter = meter
        self.learners: List[CuopLearner] = list(learners or [])
        self.ledger = ledger or CassiniCycleLedger()
        self.baseline: Optional[CuopReading] = None
        self.latest: Optional[CuopReading] = None
        self.reports: List[Dict[str, Any]] = []

    def add_parameter(self, learner: CuopLearner) -> None:
        self.learners.append(learner)

    def measure_baseline(
        self, measure_fn: Callable[[], Optional[CuopReading]]
    ) -> Optional[CuopReading]:
        reading = measure_fn()
        if reading is None:
            return None
        self.baseline = reading
        self.latest = reading
        for learner in self.learners:
            learner.record(reading.cuop)
        return reading

    def optimise_cycle(
        self,
        measure_fn: Callable[[], Optional[CuopReading]],
        steps_per_learner: int = 3,
    ) -> Dict[str, Any]:
        """Run one measured tuning cycle over all registered parameters."""
        applied: List[Dict[str, Any]] = []
        if self.baseline is None and self.measure_baseline(measure_fn) is None:
            return self._record_unavailable(applied, reverted=False)
        assert self.baseline is not None

        best_cuop = max(self.baseline.cuop, self.latest.cuop if self.latest else 0.0)
        reverted = False

        for learner in self.learners:
            saved_value = learner.value
            for _ in range(steps_per_learner):
                suggestion = learner.suggest()
                learner.apply(suggestion)
                reading = measure_fn()
                if reading is None:
                    learner.apply(saved_value)
                    applied.append(
                        {
                            "parameter": learner.name,
                            "value": learner.value,
                            "samples": len(learner.history),
                        }
                    )
                    return self._record_unavailable(applied, reverted=True)
                learner.record(reading.cuop)
                if reading.cuop >= best_cuop:
                    best_cuop = reading.cuop
                    saved_value = learner.value
                else:
                    # Measured regression — restore the best measured value.
                    learner.apply(saved_value)
                    reverted = True
                    break
            applied.append(
                {
                    "parameter": learner.name,
                    "value": learner.value,
                    "samples": len(learner.history),
                }
            )

        latest = measure_fn()
        if latest is None:
            return self._record_unavailable(applied, reverted=reverted)
        self.latest = latest
        delta = self.latest.cuop - self.baseline.cuop
        return self._record(
            {
                "capability": "self_optimising",
                "evidence_class": "Measured",
                "baseline_cuop": self.baseline.cuop,
                "new_cuop": self.latest.cuop,
                "delta_cuop": delta,
                "improvement_measured": delta >= 0.0,
                "reverted": reverted,
                "applied": applied,
                "usd_per_kwh": self.meter.usd_per_kwh,
                "theorem_proven": False,
            }
        )

    def _record_unavailable(
        self, applied: List[Dict[str, Any]], *, reverted: bool
    ) -> Dict[str, Any]:
        return self._record(
            {
                "capability": "self_optimising",
                "evidence_class": "Unavailable",
                "reason": "cuop_unavailable",
                "baseline_cuop": self.baseline.cuop if self.baseline else None,
                "new_cuop": None,
                "delta_cuop": None,
                "improvement_measured": False,
                "reverted": reverted,
                "applied": applied,
                "usd_per_kwh": self.meter.usd_per_kwh,
                "theorem_proven": False,
            }
        )

    def _record(self, report: Dict[str, Any]) -> Dict[str, Any]:
        entry = self.ledger.log("self_optimising", report)
        report["cassini_fingerprint"] = entry.cassini_fingerprint
        self.reports.append(report)
        return report


# ---------------------------------------------------------------------------
# Agentic mining — ValidityLearner and CoolDownController
# ---------------------------------------------------------------------------

VALIDITY_SECTORS = 7


class ValidityLearner:
    """Learns which precomputed candidates deserve earlier probes.

    Training pairs are ``(features, accepted)`` where ``accepted`` is the
    outcome of the *local SHA256d check* for that candidate.

    The learned model is a ``QuantumState`` over the feature Hilbert
    space: ``predict_priority`` is the Born overlap
    ``|<model|x>|^2`` between the model state and the candidate's
    feature-encoded state — a genuine Born probability, not a logistic
    squash of a dot product. Each measured outcome rotates the model
    state by a real unitary inside the two-dimensional plane spanned by
    |model> and |x>: the rotation angle is the *measured* prediction
    error scaled by the declared gain ``lr`` — a full-strength error is
    a quarter-turn. Positive error rotates toward the evidence state,
    negative error rotates away from it. There is no sigmoid and no
    invented weight matrix anywhere.

    With zero training the model is the uniform superposition, so every
    candidate reports the flat prior 0.5 (insertion order preserved) —
    an untrained learner claims no preference.

    Phase 4 uses :meth:`order_candidates` to bias probe order — every
    candidate stays in the probe set, so no valid candidate can ever be
    suppressed.

    ``drift_error()`` reports the mean absolute prediction error over the
    most recent probes; Salamander uses it to trigger retraining.
    """

    def __init__(self, lr: float = 0.4, n_features: int = 13) -> None:
        self.lr = float(lr)  # declared gain: fraction of a quarter-turn per unit error
        self.n_features = int(n_features)
        self._model = QuantumState.uniform_superposition(self.n_features)
        self.pairs: List[Tuple[np.ndarray, bool]] = []
        self.recent_errors: List[float] = []
        self.trained_samples = 0

    # Read-only mirror of the model ray's real amplitudes — kept so
    # external inspection code written against the old weight vector does
    # not break. These are state amplitudes, not logits.
    @property
    def weights(self) -> np.ndarray:
        return np.array([a.re for a in self._model.amplitudes], dtype=np.float64)

    @property
    def bias(self) -> float:
        # The quantum model has no bias term; retained for API compat.
        return 0.0

    @staticmethod
    def features(candidate: Any) -> np.ndarray:
        """Feature vector for a PrecomputedCandidate-shaped object."""
        mask = int(getattr(candidate, "zeckendorf_mask", 0))
        sector = int(getattr(candidate, "sector_id", 0)) % VALIDITY_SECTORS
        sector_onehot = np.zeros(VALIDITY_SECTORS, dtype=np.float64)
        sector_onehot[sector] = 1.0
        base = np.array(
            [
                float(getattr(candidate, "born_probability", 0.0)),
                1.0 if getattr(candidate, "cassini_valid", False) else 0.0,
                1.0 if getattr(candidate, "zeckendorf_valid", False) else 0.0,
                bin(mask & 0xFFFFFFFF).count("1") / 32.0,
                (int(getattr(candidate, "nonce", 0)) & 0xFFFFFFFF) / 4294967295.0,
                float(int(getattr(candidate, "galois_composite", 0)) & 0xFF) / 255.0,
            ],
            dtype=np.float64,
        )
        return np.concatenate([base, sector_onehot])

    def _priority_from_features(self, x: np.ndarray) -> float:
        """Born probability |<model|x>|^2 of the candidate under the model state.

        With no measured evidence (untrained uniform superposition) the
        flat prior 0.5 is reported for every candidate — the honest
        "nothing learned yet" readout, which also preserves insertion
        order in :meth:`order_candidates`.
        """
        if self.trained_samples == 0:
            return 0.5
        return self._model.fidelity(encode_state(x))

    def predict_priority(self, candidate: Any) -> float:
        """Priority score in (0, 1); higher means probe earlier."""
        return self._priority_from_features(self.features(candidate))

    def learn(self, features: Any, accepted: bool) -> float:
        """One unitary evidence step on an (features, validity) pair.

        The measured prediction error (target minus current Born readout)
        sets the rotation angle; the model state is rotated toward the
        evidence state when it under-predicted and away when it
        over-predicted. Returns the error observed before the update —
        the measured signal the drift detector consumes.
        """
        x = np.asarray(features, dtype=np.float64).reshape(-1)
        y = 1.0 if accepted else 0.0
        p = self._priority_from_features(x)
        error = y - p
        angle = self.lr * QUARTER_TURN * error
        self._model = rotate_state_in_plane(self._model, encode_state(x), angle)
        self.pairs.append((x, bool(accepted)))
        self.recent_errors.append(abs(error))
        self.trained_samples += 1
        return abs(error)

    def learn_candidate(self, candidate: Any, accepted: bool) -> float:
        return self.learn(self.features(candidate), accepted)

    def order_candidates(self, candidates: Sequence[Any]) -> List[Any]:
        """All candidates, reordered by learned priority (stable, complete).

        The returned list contains every input candidate exactly once — this
        function can only permute, never remove.
        """
        scored = [(self.predict_priority(c), i, c) for i, c in enumerate(candidates)]
        scored.sort(key=lambda t: (-t[0], t[1]))
        return [c for _, _, c in scored]

    def drift_error(self, window: int = 16) -> float:
        """Mean absolute prediction error over the most recent probes."""
        if not self.recent_errors:
            return 0.0
        tail = self.recent_errors[-window:]
        return float(sum(tail) / len(tail))

    def retrain(self, epochs: int = 4) -> Dict[str, Any]:
        """Refit on the full recorded pair history — Salamander's drift fix."""
        if not self.pairs:
            return {"retrained": False, "reason": "no_pairs", "theorem_proven": False}
        before = self.drift_error(window=len(self.recent_errors))
        # Refit: reset to the uniform superposition and replay every
        # measured pair through the unitary update.
        self._model = QuantumState.uniform_superposition(self.n_features)
        saved_trained = self.trained_samples
        self.trained_samples = 0
        for _ in range(max(1, epochs)):
            for x, accepted in self.pairs:
                y = 1.0 if accepted else 0.0
                p = self._priority_from_features(x)
                self._model = rotate_state_in_plane(
                    self._model, encode_state(x), self.lr * QUARTER_TURN * (y - p)
                )
                self.trained_samples += 1
        self.trained_samples = saved_trained + self.trained_samples
        self.recent_errors.clear()
        return {
            "retrained": True,
            "pairs": len(self.pairs),
            "error_before": before,
            "theorem_proven": False,
        }


# CoolDownController bounds: the scale can never reach zero (the workflow
# must keep making progress) and never exceed 1.0 (never submit faster
# than the base cadence).
MIN_RATE_SCALE = INV_PHI**4  # ~ 0.1459 — golden floor
RECOVERY_GAIN = INV_PHI  # how fast the scale converges to its target


class CoolDownController:
    """Adapts next-cycle submission rate from the measured rejection rate.

    Training pairs are ``(rejection_rate, beneficial_adjustment)``: for each
    recorded pair the controller fits the gain ``k`` in
    ``target_scale = 1 - k * rejection_rate`` by averaging the implied gains
    ``k_i = (1 - adjustment_i) / rate_i``. ``observe()`` then servos
    ``rate_scale`` toward that target at ``RECOVERY_GAIN`` per session, so a
    session with a high measured rejection rate contracts the next session's
    submission cadence and a clean session lets it recover toward 1.0.
    """

    def __init__(self, initial_gain: float = PHI) -> None:
        self.gain = float(initial_gain)
        self.rate_scale = 1.0
        self.pairs: List[Tuple[float, float]] = []
        self.history: List[Dict[str, float]] = []

    def learn(self, rejection_rate: float, beneficial_adjustment: float) -> None:
        """Record a (rejection_rate, rate_adjustment) pair and refit the gain."""
        rate = min(1.0, max(0.0, float(rejection_rate)))
        adj = min(1.0, max(0.0, float(beneficial_adjustment)))
        self.pairs.append((rate, adj))
        implied = [(1.0 - a) / r for r, a in self.pairs if r > 0.0]
        if implied:
            self.gain = float(sum(implied) / len(implied))

    def observe(self, accepted: int, rejected: int) -> Dict[str, float]:
        """Adapt the rate scale from measured session outcomes."""
        total = max(1, int(accepted) + int(rejected))
        rejection_rate = int(rejected) / total
        target = max(MIN_RATE_SCALE, 1.0 - self.gain * rejection_rate)
        self.rate_scale += (target - self.rate_scale) * RECOVERY_GAIN
        self.rate_scale = min(1.0, max(MIN_RATE_SCALE, self.rate_scale))
        record = {
            "rejection_rate": rejection_rate,
            "target_scale": target,
            "rate_scale": self.rate_scale,
            "gain": self.gain,
        }
        self.history.append(record)
        return record

    def status(self) -> Dict[str, Any]:
        return {
            "rate_scale": self.rate_scale,
            "gain": self.gain,
            "pairs": len(self.pairs),
            "observations": len(self.history),
            "theorem_proven": False,
        }


# ---------------------------------------------------------------------------
# Supervisor — Salamander watches all three capabilities
# ---------------------------------------------------------------------------

DRIFT_THRESHOLD = 0.5  # mean |prediction error| that triggers retraining
CUOP_DROP_FRACTION = INV_PHI  # trigger when latest < baseline / phi


class AutonomySupervisor:
    """Salamander-level supervision across the three autonomous capabilities.

    Each supervision cycle checks, in order:

      1. **Learner drift** — if the mining workflow's ValidityLearner mean
         prediction error exceeds ``DRIFT_THRESHOLD``, the learner is
         retrained on its recorded pairs.
      2. **CUOP drop** — if the self-optimising loop's latest measured CUOP
         falls below ``baseline / phi``, a re-optimisation cycle runs.
      3. **Mining stall** — every registered subsystem probe runs through
         the heal loop; a ``subsystem_stall`` fault is repaired by the
         registered restart handler.

    Every action taken is logged to the shared Cassini ledger.
    """

    def __init__(
        self,
        engine: Any,
        heal_loop: Optional[SelfHealingLoop] = None,
        ledger: Optional[CassiniCycleLedger] = None,
    ) -> None:
        self.engine = engine
        self.ledger = ledger or CassiniCycleLedger()
        self.heal_loop = heal_loop or SelfHealingLoop(engine=engine, ledger=self.ledger)
        self.workflow: Any = None
        self.optimiser: Optional[SelfOptimisingLoop] = None
        self.measure_fn: Optional[Callable[[], Optional[CuopReading]]] = None
        self._last_telemetry_count = 0

    # -- attachment ----------------------------------------------------------

    def attach_workflow(self, workflow: Any) -> None:
        """Monitor an AgenticMiningWorkflow for stalls and learner drift."""
        self.workflow = workflow
        self._last_telemetry_count = len(getattr(workflow, "telemetry_history", []))

        def probe() -> str:
            if getattr(workflow, "is_mining", False) and not getattr(
                workflow, "is_cooled_down", False
            ):
                if len(workflow.telemetry_history) <= self._last_telemetry_count:
                    return "subsystem_stall"
            return STATUS_HEALTHY

        def restart() -> bool:
            workflow.is_mining = False
            workflow.restart()
            self._last_telemetry_count = len(workflow.telemetry_history)
            return workflow.is_initialized

        self.heal_loop.register_subsystem(
            name="hyba_data.mining_subsystem",
            probe=probe,
            repairs={"subsystem_stall": restart},
        )

    def attach_optimiser(
        self,
        optimiser: SelfOptimisingLoop,
        measure_fn: Callable[[], Optional[CuopReading]],
    ) -> None:
        self.optimiser = optimiser
        self.measure_fn = measure_fn

    # -- the cycle -------------------------------------------------------------

    def supervise_cycle(self) -> Dict[str, Any]:
        actions: List[Dict[str, Any]] = []

        # 1. Learner drift -> retrain.
        learner = getattr(self.workflow, "validity_learner", None) if self.workflow else None
        if learner is not None and learner.trained_samples > 0:
            err = learner.drift_error()
            if err > DRIFT_THRESHOLD:
                result = learner.retrain()
                actions.append(
                    self.ledger.log(
                        "supervision",
                        {
                            "trigger": "learner_drift",
                            "drift_error": err,
                            "action": "retrain",
                            "result": result,
                            "theorem_proven": False,
                        },
                    ).to_dict()
                )

        # 2. CUOP drop -> re-optimise. An Unavailable reading is not a drop,
        # and it must never keep step 3 from running.
        if self.optimiser is not None and self.measure_fn is not None:
            baseline = self.optimiser.baseline
            current = self.measure_fn() if baseline is not None and baseline.cuop > 0.0 else None
            if current is not None:
                self.optimiser.latest = current
                if current.cuop < baseline.cuop * CUOP_DROP_FRACTION:
                    report = self.optimiser.optimise_cycle(self.measure_fn)
                    actions.append(
                        self.ledger.log(
                            "supervision",
                            {
                                "trigger": "cuop_drop",
                                "measured_cuop": current.cuop,
                                "baseline_cuop": baseline.cuop,
                                "action": "reoptimise",
                                "delta_cuop": report["delta_cuop"],
                                "theorem_proven": False,
                            },
                        ).to_dict()
                    )

        # 3. Mining stall (and any other registered fault) -> heal loop.
        for record in self.heal_loop.heal_cycle():
            actions.append(
                {
                    "trigger": record.fault_type,
                    "subsystem": record.subsystem,
                    "action": record.repair_action,
                    "final_status": record.final_status,
                    "cassini_fingerprint": record.cassini_fingerprint,
                    "theorem_proven": False,
                }
            )

        return {
            "actions": actions,
            "healed": sum(1 for a in actions if a.get("final_status") == STATUS_HEALTHY),
            "escalated": sum(1 for a in actions if a.get("final_status") == STATUS_ESCALATED),
            "theorem_proven": False,
        }

    def status(self) -> Dict[str, Any]:
        return {
            "heal_loop": self.heal_loop.status(),
            "workflow_attached": self.workflow is not None,
            "optimiser_attached": self.optimiser is not None,
            "ledger_entries": len(self.ledger.entries),
            "theorem_proven": False,
        }


def lucas_bound(n: int = 10) -> dict:
    """Verify this module's Lucas route against the shared pool."""
    from lucas.pool import get as _lucas_get

    result = _lucas_get("gap_kernel")(np.diag([0.0, 1.0, 3.0]), n)
    result["module"] = __name__
    return result


__all__ = [
    "THEOREM_PROVEN",
    "PHI",
    "INV_PHI",
    "cassini_fingerprint",
    "LedgerEntry",
    "CassiniCycleLedger",
    "KNOWN_FAULT_TYPES",
    "DEFAULT_REPAIR_ACTIONS",
    "STATUS_HEALTHY",
    "STATUS_ESCALATED",
    "FaultRecord",
    "SelfHealingLoop",
    "JOULES_PER_KWH",
    "DEFAULT_USD_PER_KWH",
    "CuopReading",
    "CuopMeter",
    "telemetry_snapshot",
    "CuopLearner",
    "SelfOptimisingLoop",
    "VALIDITY_SECTORS",
    "ValidityLearner",
    "MIN_RATE_SCALE",
    "RECOVERY_GAIN",
    "CoolDownController",
    "DRIFT_THRESHOLD",
    "CUOP_DROP_FRACTION",
    "AutonomySupervisor",
    "lucas_bound",
]
