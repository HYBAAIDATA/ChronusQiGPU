"""Intelligence feedback core integrating calibration and causal credit assignment.

Learned module weights are not scalar accumulators driven by an invented
learning-rate constant: each weight is the Born readout of a per-module
qubit. ``model_parameters[name]`` is the measured z-component of the
module's Bloch vector, ``w = <sigma_z> = |a0|^2 - |a1|^2`` in [-1, 1],
read from a ``kellogg.quantum_tensor.QuantumState``. An outcome applies a
unitary rotation ``R_y(theta) = exp(-i theta sigma_y / 2)`` to that state,
where the rotation angle is the *measured* attribution — damped by the
*measured* reliability ``1 - calibration_error`` when the decision carried
a reported confidence, undamped when calibration is unmeasured (declared,
not a fabricated 0.5 midpoint). There is no learning-rate constant anywhere:
the applied angle is the measurement itself, normalised so a full-strength
attribution applies a quarter-turn on the Bloch sphere.

The causal attribution is interventional (leave-one-out — honest classical
do-calculus, labelled as such) and the calibration series is named
classical statistics (absolute/Brier/ECE error); neither is presented as
quantum. Every learned parameter reported downstream is a Born-rule
measurement of the evolved qubit state.
"""
from __future__ import annotations

import math
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from kellogg.quantum_tensor import Complex, ComplexMatrix, QuantumState

from .causal_attribution import AttributionReport, CausalAttributionEngine, ModuleContribution
from .truth_calibration import TruthCalibrationEngine

# A full-strength unit attribution applies a quarter-turn: the pole-to-pole
# Bloch sweep is pi and this constant is that geometric normalisation, not
# a tuned hyperparameter.
_QUARTER_TURN = math.pi / 2.0


def _weight_to_state(weight: float) -> QuantumState:
    """Embed a scalar weight w = <sigma_z> as the qubit ray at Bloch angle arccos(w).

    |psi> = cos(phi/2)|0> + sin(phi/2)|1> with phi = arccos(w), so the Born
    probabilities |a0|^2, |a1|^2 reproduce w = |a0|^2 - |a1|^2 exactly.
    """
    phi = math.acos(max(-1.0, min(1.0, float(weight))))
    return QuantumState(
        2,
        [Complex(math.cos(phi / 2), 0.0), Complex(math.sin(phi / 2), 0.0)],
    )


def _rotate_weight(weight: float, angle: float) -> float:
    """Apply R_y(angle) to the module qubit and read <sigma_z> via the Born rule."""
    c, s = math.cos(angle / 2), math.sin(angle / 2)
    # R_y(angle) = exp(-i angle sigma_y / 2) — a real unitary rotation on the
    # Bloch sphere, the same Schrödinger-evolution primitive the engine's
    # channels use (ComplexMatrix, QuantumState.apply_unitary).
    unitary = ComplexMatrix.from_real([[c, -s], [s, c]])
    probs = _weight_to_state(weight).apply_unitary(unitary).probabilities()
    return probs[0] - probs[1]


@dataclass
class DecisionRecord:
    decision_id: str
    decision: Any
    confidence: float | None
    module_outputs: dict[str, Any]
    context: dict[str, Any]
    source_id: str = "default"
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LearningUpdate:
    update_id: str
    decision_id: str
    attribution: dict[str, float]
    calibration_error: float | None
    model_changes: dict[str, float]
    timestamp: float = field(default_factory=time.time)


@dataclass
class FeedbackReport:
    report_id: str
    decision_id: str
    decision: Any
    outcome: Any
    attribution: dict[str, ModuleContribution]
    calibration_score: float | None
    learning_signal: float
    timestamp: float = field(default_factory=time.time)
    recommendations: list[str] = field(default_factory=list)


class IntelligenceFeedbackCore:
    """Closed-loop decision/outcome learner with bounded parameter updates."""

    def __init__(self, calibration_engine: TruthCalibrationEngine | None = None,
                 causal_engine: CausalAttributionEngine | None = None,
                 enable_auto_learning: bool = True):
        self.calibration_engine = calibration_engine or TruthCalibrationEngine()
        self.causal_engine = causal_engine or CausalAttributionEngine()
        self.enable_auto_learning = bool(enable_auto_learning)
        self.decision_records: dict[str, DecisionRecord] = {}
        self.learning_updates: list[LearningUpdate] = []
        self.feedback_reports: list[FeedbackReport] = []
        self.model_parameters: dict[str, float] = {}
        self._processed: dict[str, FeedbackReport] = {}

    def record_decision(self, decision: Any, confidence: float | None,
                        module_outputs: Mapping[str, Any], context: Mapping[str, Any] | None = None,
                        source_id: str = "default") -> str:
        # ``None`` means the deciding engine reported no confidence — the
        # record is kept so outcome feedback still closes, but nothing is
        # injected into the calibration series.
        value = None if confidence is None else float(confidence)
        if value is not None and (not math.isfinite(value) or not 0 <= value <= 1):
            raise ValueError("confidence must be finite and in [0, 1]")
        if not module_outputs:
            raise ValueError("module_outputs must not be empty")
        self.calibration_engine.register_source(source_id)
        decision_id = str(uuid.uuid4())
        self.decision_records[decision_id] = DecisionRecord(
            decision_id, decision, value, dict(module_outputs), dict(context or {}), source_id
        )
        return decision_id

    def process(self, decision_id: str, outcome: Any, source_id: str | None = None,
                decision_fn: Callable[[Mapping[str, Any]], Any] | None = None) -> FeedbackReport:
        if decision_id not in self.decision_records:
            raise ValueError(f"Decision ID {decision_id} not found")
        if decision_id in self._processed:
            raise ValueError(f"Decision ID {decision_id} has already been processed")
        record = self.decision_records[decision_id]
        # Tenant isolation: a caller must close decisions under the same
        # source the decision was recorded for.  Without this check a caller
        # holding another tenant's decision id could close that decision and
        # mutate the shared learning aggregate under the wrong calibration
        # series.
        if source_id is not None and record.source_id != source_id:
            raise ValueError(
                f"Decision ID {decision_id} was recorded for source "
                f"{record.source_id!r}, not {source_id!r}"
            )
        source = record.source_id
        outcome_bool = self._outcome_to_bool(outcome, record.decision)
        if record.confidence is None:
            # No confidence was reported at decision time — calibration is
            # undefined, not zero.  Learning falls back to attribution only.
            calibration_error = None
        else:
            self.calibration_engine.record_prediction(source, record.confidence, outcome_bool)
            calibration_error = self.calibration_engine.calibrate(record.confidence, outcome_bool)
        attribution_report = self.causal_engine.attribute(
            record.module_outputs, record.decision, outcome, decision_fn
        )
        learning_signal = self._compute_learning_signal(calibration_error, attribution_report)
        report = FeedbackReport(
            str(uuid.uuid4()), decision_id, record.decision, outcome,
            attribution_report.contributions, calibration_error, learning_signal,
            recommendations=self._generate_recommendations(calibration_error, attribution_report),
        )
        self.feedback_reports.append(report)
        self._processed[decision_id] = report
        if self.enable_auto_learning:
            self._trigger_learning_update(report)
        return report

    @staticmethod
    def _outcome_to_bool(outcome: Any, decision: Any) -> bool:
        if isinstance(outcome, bool): return outcome
        if isinstance(outcome, (int,float)) and isinstance(decision, (int,float)):
            scale=max(1.0,abs(float(outcome)),abs(float(decision)))
            return abs(float(outcome)-float(decision))/scale < .1
        if isinstance(outcome, (int,float)): return float(outcome)>0
        if isinstance(outcome,str) and isinstance(decision,str): return outcome==decision
        return outcome == decision

    @staticmethod
    def _compute_learning_signal(calibration_error: float | None,
                                 attribution_report: AttributionReport) -> float:
        # The measured learning signal is the measured total attribution,
        # damped by the measured reliability 1 - calibration_error when the
        # decision carried a confidence. No invented 0.6/0.4 blend: every
        # factor in the product was measured. Unmeasured calibration leaves
        # the signal equal to the raw attribution (declared, not a midpoint).
        reliability = 1.0 if calibration_error is None else max(0.0, 1.0 - float(calibration_error))
        return max(-1.0, min(1.0, reliability * attribution_report.total_attribution))

    @staticmethod
    def _generate_recommendations(calibration_error: float | None,
                                  attribution_report: AttributionReport) -> list[str]:
        result=[]
        if calibration_error is None:
            result.append("No confidence reported - calibration not applicable")
        elif calibration_error>.3: result.append("High calibration error - confidence estimation needs improvement")
        elif calibration_error<.1: result.append("Well calibrated - confidence estimation is accurate")
        top=attribution_report.get_top_contributors(2)
        if top: result.append(f"Top contributing modules: {[item.module_id for item in top]}")
        negative=attribution_report.get_negative_contributors()
        if negative: result.append(f"Negative contributors: {[item.module_id for item in negative]} - consider review")
        return result

    def _trigger_learning_update(self, report: FeedbackReport) -> None:
        attribution={name:item.contribution_score for name,item in report.attribution.items()}
        # High calibration error attenuates the rotation: reliability is the
        # measured 1 - calibration_error. When calibration is unmeasured the
        # attribution rotates undamped (declared above, not a fabricated 0.5).
        reliability = 1.0 if report.calibration_score is None else max(0.0, 1.0 - report.calibration_score)
        changes: dict[str, float] = {}
        for name, score in attribution.items():
            # Negative attribution rotates toward the |1> pole (w -> -1);
            # positive attribution rotates toward |0> (w -> +1).
            angle = -float(score) * reliability * _QUARTER_TURN
            prior = self.model_parameters.get(name, 0.0)
            updated = max(-1.0, min(1.0, _rotate_weight(prior, angle)))
            changes[name] = updated - prior
            self.model_parameters[name] = updated
        self.learning_updates.append(LearningUpdate(
            str(uuid.uuid4()),report.decision_id,attribution,report.calibration_score,changes
        ))

    def update_models(self, attribution: Mapping[str,float], calibration: float) -> None:
        error=float(calibration)
        if not 0<=error<=1: raise ValueError("calibration must be in [0, 1]")
        reliability = 1.0 - error
        for name,score in attribution.items():
            value=float(score)
            if not math.isfinite(value): raise ValueError("attribution scores must be finite")
            angle = -value * reliability * _QUARTER_TURN
            prior = self.model_parameters.get(name, 0.0)
            self.model_parameters[name] = max(-1.0, min(1.0, _rotate_weight(prior, angle)))

    def get_module_performance(self) -> dict[str,float]: return self.model_parameters.copy()

    def get_learning_statistics(self) -> dict[str,Any]:
        return {"total_decisions":len(self.decision_records),
                "total_feedback_reports":len(self.feedback_reports),
                "total_learning_updates":len(self.learning_updates),
                "calibration_stats":self.calibration_engine.get_global_calibration(),
                "attribution_stats":self.causal_engine.get_attribution_statistics(),
                "module_performance":self.get_module_performance()}

    def get_feedback_history(self,n: int=10) -> list[FeedbackReport]:
        if n<0: raise ValueError("n must be nonnegative")
        return self.feedback_reports[-n:] if n else []

    def identify_underperforming_modules(self,threshold: float=0.0) -> list[str]:
        return [name for name,score in self.model_parameters.items() if score<threshold]

    def snapshot(self) -> dict[str, Any]:
        """Durable form of the learned aggregate state.

        Live decision records carry arbitrary decision/outcome objects and are
        not serialised; what persists is what future decisions actually read:
        learned model parameters, the calibration series, and cumulative
        counts.  Restoring a snapshot replays that learned state; recorded
        decision ids do not resurrect, so outcomes against pre-restart
        decisions still fail closed.
        """
        return {
            "schema": "intelligence-feedback-core/1",
            "enable_auto_learning": self.enable_auto_learning,
            "model_parameters": dict(self.model_parameters),
            "calibration": self.calibration_engine.export_state(),
            "counts": {
                "decisions": len(self.decision_records),
                "feedback_reports": len(self.feedback_reports),
                "learning_updates": len(self.learning_updates),
            },
            "processed_decision_ids": sorted(self._processed.keys()),
        }

    def restore(self, state: Mapping[str, Any]) -> dict[str, Any]:
        """Restore learned state from a snapshot; returns a restore report.

        Replaces the live (unpersisted) learning state.  Calibration series
        and model parameters are replayed exactly; historical decision ids
        stay unresolvable — a restored core rejects outcomes against them.
        """
        if dict(state or {}).get("schema") != "intelligence-feedback-core/1":
            raise ValueError("unsupported feedback-core snapshot schema")
        self.reset_learning()
        self.enable_auto_learning = bool(state.get("enable_auto_learning", True))
        self.model_parameters = {
            str(name): float(value)
            for name, value in dict(state.get("model_parameters") or {}).items()
        }
        self.calibration_engine.import_state(state.get("calibration") or {})
        return {
            "restored": True,
            "model_parameters": len(self.model_parameters),
            "calibration_sources": len(self.calibration_engine.export_state()),
            "historical_decisions_carried": dict(state.get("counts") or {}).get(
                "decisions", 0
            ),
        }

    def rollback_outcome(self, decision_id: str, prior: Mapping[str, Any]) -> None:
        """Undo a ``process()`` whose durable handoff failed.

        The learned update is transactional: when persistence of the new
        aggregate fails, in-memory state must return to exactly the last
        durable state — otherwise memory would carry an update the disk
        never accepted, and the decision would be half-consumed (marked
        processed but without its outcome surviving restart).  Live
        ``decision_records`` are untouched: the decision stays recorded and
        unprocessed, so the caller can retry ``process`` after the write
        path is repaired.  ``prior`` is the ``snapshot()`` taken before
        processing.
        """
        report = self._processed.pop(decision_id, None)
        if report is not None:
            if self.feedback_reports and self.feedback_reports[-1] is report:
                self.feedback_reports.pop()
            elif report in self.feedback_reports:
                self.feedback_reports.remove(report)
            if (
                self.learning_updates
                and self.learning_updates[-1].decision_id == decision_id
            ):
                self.learning_updates.pop()
            self.causal_engine.pop_last_report()
        self.model_parameters = {
            str(name): float(value)
            for name, value in dict(prior.get("model_parameters") or {}).items()
        }
        self.calibration_engine.import_state(prior.get("calibration") or {})

    def reset_learning(self) -> None:
        self.decision_records.clear(); self.learning_updates.clear(); self.feedback_reports.clear()
        self.model_parameters.clear(); self._processed.clear()
        self.calibration_engine.reset(); self.causal_engine.reset()


__all__=["DecisionRecord","LearningUpdate","FeedbackReport","IntelligenceFeedbackCore"]
