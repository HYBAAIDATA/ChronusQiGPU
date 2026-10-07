"""Intelligence feedback core integrating calibration and causal credit assignment."""
from __future__ import annotations

import math
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from .causal_attribution import AttributionReport, CausalAttributionEngine, ModuleContribution
from .truth_calibration import TruthCalibrationEngine


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
        self.learning_rate = 0.001
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
        source = source_id or record.source_id
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
        if calibration_error is None:
            return max(-1.0, min(1.0, attribution_report.total_attribution))
        value=.6*(1-float(calibration_error))+.4*attribution_report.total_attribution
        return max(-1.0,min(1.0,value))

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
        # High calibration error attenuates updates rather than reinforcing an unreliable signal.
        reliability=0.5 if report.calibration_score is None else max(0.0,1-report.calibration_score)
        changes={name:self.learning_rate*score*reliability for name,score in attribution.items()}
        self.learning_updates.append(LearningUpdate(
            str(uuid.uuid4()),report.decision_id,attribution,report.calibration_score,changes
        ))
        for name,change in changes.items():
            self.model_parameters[name]=max(-1.0,min(1.0,self.model_parameters.get(name,0.0)+change))

    def update_models(self, attribution: Mapping[str,float], calibration: float) -> None:
        error=float(calibration)
        if not 0<=error<=1: raise ValueError("calibration must be in [0, 1]")
        for name,score in attribution.items():
            value=float(score)
            if not math.isfinite(value): raise ValueError("attribution scores must be finite")
            delta=self.learning_rate*value*(1-error)
            self.model_parameters[name]=max(-1.0,min(1.0,self.model_parameters.get(name,0.0)+delta))

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

    def reset_learning(self) -> None:
        self.decision_records.clear(); self.learning_updates.clear(); self.feedback_reports.clear()
        self.model_parameters.clear(); self._processed.clear()
        self.calibration_engine.reset(); self.causal_engine.reset()

    def set_learning_rate(self,rate: float) -> None:
        value=float(rate)
        if not math.isfinite(value) or not 0<value<=1:
            raise ValueError("learning rate must be finite and in (0, 1]")
        self.learning_rate=value


__all__=["DecisionRecord","LearningUpdate","FeedbackReport","IntelligenceFeedbackCore"]
