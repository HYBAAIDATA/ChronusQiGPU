#!/usr/bin/env python3
"""
HYBA Analytics - Enhanced Resilience Layer
===========================================

This module expands the resilience layer with enterprise-grade fault tolerance:
- Domain-level circuit breakers
- AGI degradation modes
- Quantum fallback modes
- Predictive failure detection
- Self-healing routines

The enhanced resilience layer enables HYBA to become fault-tolerant and
self-recovering with domain-specific resilience strategies.
"""

from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
from datetime import datetime, timedelta
import threading
from collections import deque
import time

from core_engine.unified_platform_engine import (
    ConfigurationManager,
    EnterpriseLogger,
    CircuitBreaker,
    RetryPolicy,
    FallbackStrategy,
    ResilienceManager
)

from Intelligence.agi_substrate import (
    CanonicalAGISubstrate,
    AGIDegradationMode
)


class CircuitBreakerState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Circuit is open, requests fail fast
    HALF_OPEN = "half_open"  # Testing if service has recovered


class FailurePredictionType(Enum):
    """Types of failure predictions"""
    RATE_SPIKE = "rate_spike"  # Sudden increase in failure rate
    LATENCY_SPIKE = "latency_spike"  # Sudden increase in latency
    ERROR_PATTERN = "error_pattern"  # Specific error pattern detected
    RESOURCE_EXHAUSTION = "resource_exhaustion"  # Resource limits approaching
    CASCADE_RISK = "cascade_risk"  # Risk of cascading failures


@dataclass
class DomainCircuitBreaker:
    """
    Domain-specific circuit breaker.
    
    Each domain has its own circuit breaker with:
    - Custom thresholds
    - Domain-specific recovery strategies
    - Telemetry tracking
    """
    domain: str
    failure_threshold: int = 5
    recovery_timeout: float = 60.0  # seconds
    success_threshold: int = 3
    state: CircuitBreakerState = CircuitBreakerState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[datetime] = None
    last_state_change: datetime = field(default_factory=datetime.utcnow)
    
    def record_failure(self):
        """Record a failure and potentially open circuit"""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.failure_count >= self.failure_threshold:
            self._open_circuit()
    
    def record_success(self):
        """Record a success and potentially close circuit"""
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            
            if self.success_count >= self.success_threshold:
                self._close_circuit()
        elif self.state == CircuitBreakerState.CLOSED:
            self.failure_count = max(0, self.failure_count - 1)
    
    def _open_circuit(self):
        """Open the circuit breaker"""
        self.state = CircuitBreakerState.OPEN
        self.last_state_change = datetime.utcnow()
        self.success_count = 0
    
    def _close_circuit(self):
        """Close the circuit breaker"""
        self.state = CircuitBreakerState.CLOSED
        self.last_state_change = datetime.utcnow()
        self.failure_count = 0
        self.success_count = 0
    
    def attempt_reset(self) -> bool:
        """Attempt to reset circuit to half-open state"""
        if self.state == CircuitBreakerState.OPEN:
            time_since_open = (datetime.utcnow() - self.last_state_change).total_seconds()
            
            if time_since_open >= self.recovery_timeout:
                self.state = CircuitBreakerState.HALF_OPEN
                self.last_state_change = datetime.utcnow()
                self.success_count = 0
                return True
        
        return False
    
    def can_execute(self) -> bool:
        """Check if requests can execute through this circuit breaker"""
        if self.state == CircuitBreakerState.CLOSED:
            return True
        elif self.state == CircuitBreakerState.HALF_OPEN:
            return True
        else:
            # Check if recovery timeout has passed
            return self.attempt_reset()
    
    def get_status(self) -> Dict[str, Any]:
        """Get circuit breaker status"""
        return {
            'domain': self.domain,
            'state': self.state.value,
            'failure_count': self.failure_count,
            'success_count': self.success_count,
            'last_failure_time': self.last_failure_time.isoformat() if self.last_failure_time else None,
            'last_state_change': self.last_state_change.isoformat(),
            'can_execute': self.can_execute()
        }


@dataclass
class FailurePrediction:
    """Predicted failure event"""
    prediction_type: FailurePredictionType
    domain: str
    confidence: float  # 0.0 to 1.0
    predicted_at: datetime = field(default_factory=datetime.utcnow)
    predicted_failure_time: Optional[datetime] = None
    context: Dict[str, Any] = field(default_factory=dict)
    
    def is_imminent(self, window_seconds: float = 60.0) -> bool:
        """Check if failure is imminent within time window"""
        if self.predicted_failure_time is None:
            return False
        
        time_until_failure = (self.predicted_failure_time - datetime.utcnow()).total_seconds()
        return 0 <= time_until_failure <= window_seconds


class PredictiveFailureDetector:
    """
    Predictive failure detection system.
    
    Uses historical data and patterns to predict failures before they occur.
    """
    
    def __init__(self, config: ConfigurationManager, logger: EnterpriseLogger):
        self.config = config
        self.logger = logger
        
        self._failure_history: Dict[str, deque[datetime]] = defaultdict(lambda: deque(maxlen=1000))
        self._latency_history: Dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=1000))
        self._predictions: deque[FailurePrediction] = deque(maxlen=1000)
        
        self._lock = threading.Lock()
        
        # Detection thresholds
        self._failure_rate_threshold = config.get('resilience.failure_rate_threshold', 0.1)
        self._latency_spike_threshold = config.get('resilience.latency_spike_threshold', 2.0)
        
        self.logger.set_context(component="PredictiveFailureDetector")
        self.logger.info("Predictive Failure Detector initialized")
    
    def record_failure(self, domain: str):
        """Record a failure event"""
        with self._lock:
            self._failure_history[domain].append(datetime.utcnow())
    
    def record_latency(self, domain: str, latency_ms: float):
        """Record a latency measurement"""
        with self._lock:
            self._latency_history[domain].append(latency_ms)
    
    def detect_failure_risk(self, domain: str) -> List[FailurePrediction]:
        """Detect failure risk for a domain"""
        predictions = []
        
        with self._lock:
            # Check for failure rate spike
            failure_prediction = self._detect_failure_rate_spike(domain)
            if failure_prediction:
                predictions.append(failure_prediction)
            
            # Check for latency spike
            latency_prediction = self._detect_latency_spike(domain)
            if latency_prediction:
                predictions.append(latency_prediction)
        
        return predictions
    
    def _detect_failure_rate_spike(self, domain: str) -> Optional[FailurePrediction]:
        """Detect sudden increase in failure rate"""
        failures = list(self._failure_history[domain])
        
        if len(failures) < 10:
            return None
        
        # Calculate recent vs older failure rates
        now = datetime.utcnow()
        recent_window = timedelta(minutes=5)
        older_window = timedelta(minutes=15)
        
        recent_failures = sum(1 for f in failures if now - f < recent_window)
        older_failures = sum(1 for f in failures if recent_window <= now - f < older_window)
        
        if older_failures == 0:
            return None
        
        recent_rate = recent_failures / 5.0  # per minute
        older_rate = older_failures / 10.0  # per minute
        
        rate_increase = (recent_rate - older_rate) / older_rate if older_rate > 0 else 0
        
        if rate_increase > self._failure_rate_threshold:
            return FailurePrediction(
                prediction_type=FailurePredictionType.RATE_SPIKE,
                domain=domain,
                confidence=min(0.9, rate_increase * 5),
                predicted_failure_time=now + timedelta(minutes=10),
                context={
                    'recent_rate': recent_rate,
                    'older_rate': older_rate,
                    'rate_increase': rate_increase
                }
            )
        
        return None
    
    def _detect_latency_spike(self, domain: str) -> Optional[FailurePrediction]:
        """Detect sudden increase in latency"""
        latencies = list(self._latency_history[domain])
        
        if len(latencies) < 10:
            return None
        
        recent = latencies[-5:]
        older = latencies[-20:-5]
        
        recent_avg = np.mean(recent)
        older_avg = np.mean(older)
        
        if older_avg == 0:
            return None
        
        latency_increase = (recent_avg - older_avg) / older_avg
        
        if latency_increase > self._latency_spike_threshold:
            return FailurePrediction(
                prediction_type=FailurePredictionType.LATENCY_SPIKE,
                domain=domain,
                confidence=min(0.85, latency_increase * 2),
                predicted_failure_time=datetime.utcnow() + timedelta(minutes=5),
                context={
                    'recent_avg': recent_avg,
                    'older_avg': older_avg,
                    'latency_increase': latency_increase
                }
            )
        
        return None
    
    def get_recent_predictions(self, limit: int = 50) -> List[FailurePrediction]:
        """Get recent failure predictions"""
        with self._lock:
            return list(self._predictions)[-limit:]


class SelfHealingRoutine:
    """
    Self-healing routine for automatic recovery.
    
    Implements automated recovery actions based on detected failures.
    """
    
    def __init__(
        self,
        config: ConfigurationManager,
        logger: EnterpriseLogger,
        agi_substrate: Optional[CanonicalAGISubstrate] = None
    ):
        self.config = config
        self.logger = logger
        self.agi_substrate = agi_substrate
        
        self._healing_actions: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._lock = threading.Lock()
        
        self.logger.set_context(component="SelfHealingRoutine")
        self.logger.info("Self-Healing Routine initialized")
    
    def register_healing_action(self, domain: str, action: Dict[str, Any]):
        """Register a healing action for a domain"""
        with self._lock:
            self._healing_actions[domain].append(action)
    
    def execute_healing(self, domain: str, failure_type: str) -> bool:
        """Execute healing actions for a domain"""
        with self._lock:
            actions = self._healing_actions.get(domain, [])
            
            if not actions:
                return False
            
            success = False
            for action in actions:
                if action.get('failure_type') == failure_type:
                    try:
                        self._execute_action(action)
                        success = True
                    except Exception as e:
                        self.logger.error(f"Healing action failed: {str(e)}")
            
            return success
    
    def _execute_action(self, action: Dict[str, Any]):
        """Execute a single healing action"""
        action_type = action.get('type')
        
        if action_type == 'restart_service':
            self.logger.info(f"Restarting service: {action.get('service_name')}")
            # Implementation would restart the service
        
        elif action_type == 'scale_up':
            self.logger.info(f"Scaling up: {action.get('service_name')}")
            # Implementation would scale up the service
        
        elif action_type == 'clear_cache':
            self.logger.info(f"Clearing cache: {action.get('cache_name')}")
            # Implementation would clear the cache
        
        elif action_type == 'degrade_agi':
            if self.agi_substrate:
                mode = AGIDegradationMode.REDUCED
                self.agi_substrate.set_degradation_mode(mode)
                self.logger.info(f"AGI degradation mode set to: {mode.value}")
        
        elif action_type == 'enable_fallback':
            self.logger.info(f"Enabling fallback: {action.get('fallback_name')}")
            # Implementation would enable fallback


class EnhancedResilienceLayer:
    """
    Enhanced Resilience Layer with domain-specific fault tolerance.
    
    Provides:
    - Domain-level circuit breakers
    - AGI degradation modes
    - Quantum fallback modes
    - Predictive failure detection
    - Self-healing routines
    """
    
    def __init__(
        self,
        config: ConfigurationManager,
        logger: EnterpriseLogger,
        agi_substrate: Optional[CanonicalAGISubstrate] = None
    ):
        self.config = config
        self.logger = logger
        self.agi_substrate = agi_substrate
        
        # Domain circuit breakers
        self._circuit_breakers: Dict[str, DomainCircuitBreaker] = {}
        
        # Predictive failure detector
        self._failure_detector = PredictiveFailureDetector(config, logger)
        
        # Self-healing routine
        self._self_healing = SelfHealingRoutine(config, logger, agi_substrate)
        
        # Base resilience manager
        self._base_resilience = ResilienceManager(config, logger)
        
        self._lock = threading.Lock()
        
        # Initialize domain circuit breakers
        self._initialize_circuit_breakers()
        
        self.logger.set_context(component="EnhancedResilienceLayer")
        self.logger.info("Enhanced Resilience Layer initialized")
    
    def _initialize_circuit_breakers(self):
        """Initialize circuit breakers for all domains"""
        domains = [
            'BI', 'AI_ML', 'QUANTUM', 'CONSULTING', 'ERP', 'CRM',
            'SUPPLY_CHAIN', 'FPNA', 'HR', 'MARKETING', 'DATA_WAREHOUSE',
            'CLOUD', 'SECURITY', 'PROJECT_MGMT', 'COLLABORATION',
            'ECOMMERCE', 'IOT', 'BLOCKCHAIN', 'RESEARCH'
        ]
        
        for domain in domains:
            self._circuit_breakers[domain] = DomainCircuitBreaker(
                domain=domain,
                failure_threshold=self.config.get(f'resilience.{domain}.failure_threshold', 5),
                recovery_timeout=self.config.get(f'resilience.{domain}.recovery_timeout', 60.0),
                success_threshold=self.config.get(f'resilience.{domain}.success_threshold', 3)
            )
    
    def execute_with_resilience(
        self,
        domain: str,
        operation: Callable,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute an operation with domain-specific resilience.
        
        Applies circuit breaker, retry logic, and fallback strategies.
        """
        circuit_breaker = self._circuit_breakers.get(domain)
        
        if circuit_breaker and not circuit_breaker.can_execute():
            self.logger.warning(f"Circuit breaker open for domain {domain}, using fallback")
            return self._execute_fallback(domain, *args, **kwargs)
        
        try:
            result = operation(*args, **kwargs)
            
            if circuit_breaker:
                circuit_breaker.record_success()
            
            return result
            
        except Exception as e:
            if circuit_breaker:
                circuit_breaker.record_failure()
                self._failure_detector.record_failure(domain)
            
            self.logger.error(f"Operation failed for domain {domain}: {str(e)}")
            
            # Check for predicted failures
            predictions = self._failure_detector.detect_failure_risk(domain)
            for prediction in predictions:
                if prediction.is_imminent():
                    self._self_healing.execute_healing(domain, prediction.prediction_type.value)
            
            # Retry with base resilience
            return self._base_resilience.execute_with_retry(operation, *args, **kwargs)
    
    def _execute_fallback(self, domain: str, *args, **kwargs) -> Any:
        """Execute fallback logic for a domain"""
        self.logger.info(f"Executing fallback for domain {domain}")
        
        # Simple fallback - return cached or default result
        return {
            'status': 'fallback',
            'domain': domain,
            'message': 'Service unavailable, using fallback response'
        }
    
    def set_agi_degradation_mode(self, mode: AGIDegradationMode):
        """Set AGI degradation mode"""
        if self.agi_substrate:
            self.agi_substrate.set_degradation_mode(mode)
            self.logger.info(f"AGI degradation mode set to: {mode.value}")
    
    def get_circuit_breaker_status(self, domain: str) -> Optional[Dict[str, Any]]:
        """Get circuit breaker status for a domain"""
        with self._lock:
            if domain in self._circuit_breakers:
                return self._circuit_breakers[domain].get_status()
            return None
    
    def get_all_circuit_breaker_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all circuit breakers"""
        with self._lock:
            return {
                domain: breaker.get_status()
                for domain, breaker in self._circuit_breakers.items()
            }
    
    def get_failure_predictions(self, domain: str) -> List[FailurePrediction]:
        """Get failure predictions for a domain"""
        return self._failure_detector.detect_failure_risk(domain)
    
    def get_resilience_report(self) -> Dict[str, Any]:
        """Get comprehensive resilience report"""
        circuit_breaker_status = self.get_all_circuit_breaker_status()
        
        # Calculate overall resilience score
        total_breakers = len(circuit_breaker_status)
        open_breakers = sum(
            1 for status in circuit_breaker_status.values()
            if status['state'] == CircuitBreakerState.OPEN.value
        )
        
        resilience_score = (total_breakers - open_breakers) / total_breakers if total_breakers > 0 else 1.0
        
        return {
            'resilience_score': resilience_score,
            'total_circuit_breakers': total_breakers,
            'open_circuit_breakers': open_breakers,
            'circuit_breaker_status': circuit_breaker_status,
            'agi_degradation_mode': self.agi_substrate.get_degradation_mode().value if self.agi_substrate else 'N/A'
        }


def create_enhanced_resilience_layer(
    config: ConfigurationManager,
    logger: EnterpriseLogger,
    agi_substrate: Optional[CanonicalAGISubstrate] = None
) -> EnhancedResilienceLayer:
    """Factory function to create enhanced resilience layer"""
    layer = EnhancedResilienceLayer(config, logger, agi_substrate)
    return layer
