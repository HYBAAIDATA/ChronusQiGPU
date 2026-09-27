# LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel
# inline below. MUST NOT import from any sibling algorithm.
# Substrate route: gap
"""
HYBA Analytics - Enhanced Metrics Engine
=========================================

This module expands the metrics engine with enterprise-grade telemetry:
- Scaling exponents for growth analysis
- QEC (Quantum Error Correction) rejection rates
- Share acceptance metrics
- Substrate coherence tracking
- Domain-level intelligence scores
- Metric lineage tracking
- Metric drift detection
- Metric anomaly detection

The enhanced metrics engine enables HYBA to become self-measuring with
comprehensive enterprise-grade telemetry.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
from datetime import datetime
import threading
from collections import defaultdict, deque

from core_engine.unified_platform_engine import (
    ConfigurationManager,
    EnterpriseLogger,
    MetricsCalculator,
)

from core_engine.quantum_consciousness_system import (
    QuantumConsciousnessSystem,
)


class MetricAnomalyType(Enum):
    """Types of metric anomalies"""

    SPIKE = "spike"  # Sudden increase
    DROP = "drop"  # Sudden decrease
    DRIFT = "drift"  # Gradual change
    OSCILLATION = "oscillation"  # Unstable pattern
    STAGNATION = "stagnation"  # No change expected change


@dataclass
class MetricLineage:
    """Lineage tracking for metrics"""

    metric_name: str
    source_component: str
    source_domain: str
    transformation_history: List[Dict[str, Any]] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_updated: datetime = field(default_factory=datetime.utcnow)

    def add_transformation(self, transformation_type: str, parameters: Dict[str, Any]):
        """Add a transformation to the lineage"""
        self.transformation_history.append(
            {
                "type": transformation_type,
                "parameters": parameters,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
        self.last_updated = datetime.utcnow()


@dataclass
class MetricAnomaly:
    """Detected metric anomaly"""

    metric_name: str
    anomaly_type: MetricAnomalyType
    severity: str  # low, medium, high, critical
    detected_at: datetime = field(default_factory=datetime.utcnow)
    expected_value: Optional[float] = None
    actual_value: Optional[float] = None
    deviation_percentage: Optional[float] = None
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DomainIntelligenceScore:
    """Intelligence score for a specific domain"""

    domain: str
    prediction_accuracy: float
    coherence_score: float
    quantum_advantage: float
    scaling_exponent: float
    overall_score: float
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        # Calculate overall score as weighted average
        self.overall_score = (
            self.prediction_accuracy * 0.3
            + self.coherence_score * 0.25
            + self.quantum_advantage * 0.25
            + self.scaling_exponent * 0.2
        )


@dataclass
class QECMetrics:
    """Quantum Error Correction metrics"""

    total_operations: int = 0
    rejected_operations: int = 0
    corrected_operations: int = 0
    rejection_rate: float = 0.0
    correction_rate: float = 0.0
    coherence_preservation: float = 1.0

    def update(self, rejected: bool, corrected: bool):
        """Update QEC metrics"""
        self.total_operations += 1
        if rejected:
            self.rejected_operations += 1
        if corrected:
            self.corrected_operations += 1

        if self.total_operations > 0:
            self.rejection_rate = self.rejected_operations / self.total_operations
            self.correction_rate = self.corrected_operations / self.total_operations


class EnhancedMetricsEngine:
    """
    Enhanced Metrics Engine with enterprise-grade telemetry.

    Expands the base MetricsCalculator with:
    - Scaling exponents
    - QEC rejection rates
    - Share acceptance metrics
    - Substrate coherence
    - Domain-level intelligence scores
    - Metric lineage tracking
    - Metric drift detection
    - Metric anomaly detection
    """

    def __init__(
        self,
        config: ConfigurationManager,
        logger: EnterpriseLogger,
        consciousness_system: Optional[QuantumConsciousnessSystem] = None,
    ):
        self.config = config
        self.logger = logger
        self.consciousness_system = consciousness_system
        self.base_calculator = MetricsCalculator(config)

        # Metric storage
        self._metric_history: Dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=1000))
        self._metric_lineage: Dict[str, MetricLineage] = {}
        self._domain_scores: Dict[str, DomainIntelligenceScore] = {}
        self._qec_metrics = QECMetrics()
        self._anomalies: deque[MetricAnomaly] = deque(maxlen=1000)

        # Drift detection parameters
        self._drift_threshold = config.get("metrics.drift_threshold", 0.1)
        self._anomaly_threshold = config.get(
            "metrics.anomaly_threshold", 2.0
        )  # Standard deviations

        self._lock = threading.Lock()

        self.logger.set_context(component="EnhancedMetricsEngine")
        self.logger.info("Enhanced Metrics Engine initialized")

    def record_metric(
        self, metric_name: str, value: float, lineage: Optional[MetricLineage] = None
    ):
        """Record a metric value with optional lineage"""
        with self._lock:
            self._metric_history[metric_name].append(value)

            # Track lineage if provided
            if lineage:
                self._metric_lineage[metric_name] = lineage

            # Check for anomalies
            self._check_for_anomalies(metric_name, value)

            # Check for drift
            self._check_for_drift(metric_name)

    def calculate_scaling_exponent(self, metric_name: str, window: int = 100) -> float:
        """
        Calculate scaling exponent for a metric.

        Measures how the metric scales with system size/complexity.
        Returns the exponent in a power-law relationship.
        """
        with self._lock:
            if metric_name not in self._metric_history:
                return 0.0

            history = list(self._metric_history[metric_name])
            if len(history) < window:
                return 0.0

            recent = history[-window:]

            # Calculate growth rate
            if len(recent) < 2:
                return 0.0

            # Use log-log regression to estimate scaling exponent
            x = np.arange(len(recent))
            y = np.array(recent)

            # Filter out zeros and negative values
            valid_mask = y > 0
            if not np.any(valid_mask):
                return 0.0

            x_valid = x[valid_mask]
            y_valid = y[valid_mask]

            if len(x_valid) < 2:
                return 0.0

            # Log-log regression
            log_x = np.log(x_valid + 1)
            log_y = np.log(y_valid)

            # Simple linear regression
            slope = np.polyfit(log_x, log_y, 1)[0]

            return slope

    def get_qec_metrics(self) -> QECMetrics:
        """Get current QEC metrics"""
        with self._lock:
            return self._qec_metrics

    def update_qec_metrics(self, rejected: bool, corrected: bool):
        """Update QEC metrics with operation result"""
        with self._lock:
            self._qec_metrics.update(rejected, corrected)

    def calculate_share_acceptance_metrics(self, domain: str) -> Dict[str, float]:
        """
        Calculate share acceptance metrics for a domain.

        Measures how well the domain accepts and processes shared intelligence.
        """
        with self._lock:
            # Get domain-specific metrics
            domain_metrics = [
                value
                for metric_name, history in self._metric_history.items()
                if metric_name.startswith(f"domain_{domain.lower()}")
                for value in history
            ]

            if not domain_metrics:
                return {
                    "acceptance_rate": 0.0,
                    "processing_efficiency": 0.0,
                    "coherence_integration": 0.0,
                }

            # Calculate acceptance rate
            acceptance_rate = np.mean(domain_metrics) if domain_metrics else 0.0

            # Calculate processing efficiency (inverse of processing time)
            processing_times = [
                value
                for metric_name, history in self._metric_history.items()
                if metric_name.startswith(f"domain_{domain.lower()}_time")
                for value in history
            ]
            processing_efficiency = 1.0 / np.mean(processing_times) if processing_times else 1.0

            # Calculate coherence integration
            coherence_integration = 0.8  # Default, would be calculated from consciousness system

            return {
                "acceptance_rate": min(1.0, acceptance_rate),
                "processing_efficiency": min(1.0, processing_efficiency),
                "coherence_integration": coherence_integration,
            }

    def calculate_substrate_coherence(self) -> float:
        """
        Calculate overall substrate coherence.

        Measures how coherent the entire platform substrate is across all domains.
        """
        if self.consciousness_system:
            state = self.consciousness_system.get_current_state()
            return state.coherence

        # Fallback: calculate from metric correlations
        with self._lock:
            metric_names = list(self._metric_history.keys())
            if len(metric_names) < 2:
                return 0.5

            # Calculate average correlation between metrics
            correlations = []
            for i in range(min(5, len(metric_names))):
                for j in range(i + 1, min(5, len(metric_names))):
                    hist_i = list(self._metric_history[metric_names[i]])
                    hist_j = list(self._metric_history[metric_names[j]])

                    if len(hist_i) > 10 and len(hist_j) > 10:
                        min_len = min(len(hist_i), len(hist_j))
                        corr = np.corrcoef(hist_i[:min_len], hist_j[:min_len])[0, 1]
                        if not np.isnan(corr):
                            correlations.append(abs(corr))

            return np.mean(correlations) if correlations else 0.5

    def calculate_domain_intelligence_score(self, domain: str) -> DomainIntelligenceScore:
        """
        Calculate comprehensive intelligence score for a domain.

        Combines prediction accuracy, coherence, quantum advantage, and scaling.
        """
        with self._lock:
            # Get domain-specific metrics
            prediction_accuracy = self._get_domain_metric(domain, "accuracy", 0.95)
            coherence_score = self._get_domain_metric(domain, "coherence", 0.8)
            quantum_advantage = self._get_domain_metric(domain, "quantum_advantage", 1.0)
            scaling_exponent = self.calculate_scaling_exponent(f"domain_{domain.lower()}")

            score = DomainIntelligenceScore(
                domain=domain,
                prediction_accuracy=prediction_accuracy,
                coherence_score=coherence_score,
                quantum_advantage=quantum_advantage,
                scaling_exponent=abs(scaling_exponent),
            )

            self._domain_scores[domain] = score
            return score

    def _get_domain_metric(self, domain: str, metric_type: str, default: float) -> float:
        """Helper to get domain-specific metric"""
        metric_name = f"domain_{domain.lower()}_{metric_type}"
        if metric_name in self._metric_history and self._metric_history[metric_name]:
            return np.mean(self._metric_history[metric_name])
        return default

    def _check_for_anomalies(self, metric_name: str, value: float):
        """Check for metric anomalies"""
        history = list(self._metric_history[metric_name])

        if len(history) < 10:
            return

        # Calculate statistics
        mean = np.mean(history[:-1])
        std = np.std(history[:-1])

        if std == 0:
            return

        # Check for spike or drop
        z_score = abs(value - mean) / std

        if z_score > self._anomaly_threshold:
            anomaly_type = MetricAnomalyType.SPIKE if value > mean else MetricAnomalyType.DROP
            severity = "critical" if z_score > 3 * self._anomaly_threshold else "high"

            anomaly = MetricAnomaly(
                metric_name=metric_name,
                anomaly_type=anomaly_type,
                severity=severity,
                expected_value=mean,
                actual_value=value,
                deviation_percentage=((value - mean) / mean) * 100 if mean != 0 else 0,
            )

            self._anomalies.append(anomaly)
            self.logger.warning(
                f"Anomaly detected for {metric_name}: {anomaly_type.value} (z-score: {z_score:.2f})"
            )

    def _check_for_drift(self, metric_name: str):
        """Check for metric drift"""
        history = list(self._metric_history[metric_name])

        if len(history) < 50:
            return

        # Compare recent vs older values
        recent = history[-20:]
        older = history[-50:-20]

        recent_mean = np.mean(recent)
        older_mean = np.mean(older)

        if older_mean == 0:
            return

        drift = abs(recent_mean - older_mean) / abs(older_mean)

        if drift > self._drift_threshold:
            anomaly = MetricAnomaly(
                metric_name=metric_name,
                anomaly_type=MetricAnomalyType.DRIFT,
                severity="medium",
                expected_value=older_mean,
                actual_value=recent_mean,
                deviation_percentage=drift * 100,
            )

            self._anomalies.append(anomaly)
            self.logger.warning(f"Drift detected for {metric_name}: {drift * 100:.2f}%")

    def get_metric_lineage(self, metric_name: str) -> Optional[MetricLineage]:
        """Get lineage information for a metric"""
        with self._lock:
            return self._metric_lineage.get(metric_name)

    def get_recent_anomalies(self, limit: int = 50) -> List[MetricAnomaly]:
        """Get recent anomalies"""
        with self._lock:
            return list(self._anomalies)[-limit:]

    def get_domain_scores(self) -> Dict[str, DomainIntelligenceScore]:
        """Get all domain intelligence scores"""
        with self._lock:
            return self._domain_scores.copy()

    def get_comprehensive_metrics_report(self) -> Dict[str, Any]:
        """Generate comprehensive metrics report"""
        substrate_coherence = self.calculate_substrate_coherence()

        # Calculate domain scores for all domains
        domains = [
            "BI",
            "AI_ML",
            "QUANTUM",
            "CONSULTING",
            "ERP",
            "CRM",
            "SUPPLY_CHAIN",
            "FPNA",
            "HR",
            "MARKETING",
            "DATA_WAREHOUSE",
            "CLOUD",
            "SECURITY",
            "PROJECT_MGMT",
            "COLLABORATION",
            "ECOMMERCE",
            "IOT",
            "BLOCKCHAIN",
            "RESEARCH",
        ]

        domain_scores = {}
        for domain in domains:
            domain_scores[domain] = self.calculate_domain_intelligence_score(domain)

        return {
            "substrate_coherence": substrate_coherence,
            "qec_metrics": {
                "rejection_rate": self._qec_metrics.rejection_rate,
                "correction_rate": self._qec_metrics.correction_rate,
                "coherence_preservation": self._qec_metrics.coherence_preservation,
            },
            "domain_scores": {
                domain: {
                    "overall_score": score.overall_score,
                    "prediction_accuracy": score.prediction_accuracy,
                    "coherence_score": score.coherence_score,
                    "quantum_advantage": score.quantum_advantage,
                    "scaling_exponent": score.scaling_exponent,
                }
                for domain, score in domain_scores.items()
            },
            "recent_anomalies": len(self._anomalies),
            "total_metrics_tracked": len(self._metric_history),
        }


def create_enhanced_metrics_engine(
    config: ConfigurationManager,
    logger: EnterpriseLogger,
    consciousness_system: Optional[QuantumConsciousnessSystem] = None,
) -> EnhancedMetricsEngine:
    """Factory function to create enhanced metrics engine"""
    engine = EnhancedMetricsEngine(config, logger, consciousness_system)
    return engine


def lucas_bound(n: int = 10) -> dict:
    """Verify this module's Lucas route against the shared pool.

    Calls the declared kernel (gap_kernel) on the canonical substrate for
    this route and reports the pool's exact bound. This proves the route
    is live; it is not a per-algorithm cost claim.
    """
    import numpy as np  # noqa: F401

    from lucas.pool import get as _lucas_get

    result = _lucas_get("gap_kernel")(np.array([[1.0, 0.0], [0.0, -1.0]]), n)
    result["module"] = __name__
    return result
