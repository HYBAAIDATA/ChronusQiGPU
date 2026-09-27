"""
Prometheus Metrics for Enhanced AGI

Provides comprehensive monitoring and observability:
- Request metrics
- Performance metrics
- Quality metrics
- System health metrics
"""

import logging
import time
from functools import wraps

logger = logging.getLogger(__name__)

# Try to import prometheus_client, fall back to mock if not available
try:
    from prometheus_client import Counter, Gauge, Histogram, Info

    PROMETHEUS_AVAILABLE = True
except ImportError:
    logger.warning("prometheus_client not available, using mock metrics")
    PROMETHEUS_AVAILABLE = False

    # Mock classes for when Prometheus is not available
    class Counter:
        def __init__(self, *args, **kwargs):
            self.value = 0

        def inc(self, amount=1):
            self.value += amount

        def labels(self, **kwargs):
            return self

    class Histogram:
        def __init__(self, *args, **kwargs):
            self.values = []

        def observe(self, value):
            self.values.append(value)

        def labels(self, **kwargs):
            return self

        def time(self):
            return self

        def __enter__(self):
            self.start_time = time.time()
            return self

        def __exit__(self, *args):
            self.observe(time.time() - self.start_time)

    class Gauge:
        def __init__(self, *args, **kwargs):
            self.value = 0

        def set(self, value):
            self.value = value

        def inc(self, amount=1):
            self.value += amount

        def dec(self, amount=1):
            self.value -= amount

        def labels(self, **kwargs):
            return self

    class Info:
        def __init__(self, *args, **kwargs):
            self.data = {}

        def info(self, data):
            self.data = data


class AGIMetrics:
    """
    Comprehensive metrics for AGI system

    Tracks:
    - Request counts and rates
    - Response times
    - Quality metrics (confidence, satisfaction)
    - System health
    - Cache performance
    """

    def __init__(self):
        """Initialize all metrics"""

        # Request metrics
        self.requests_total = Counter(
            "agi_requests_total",
            "Total number of AGI requests",
            ["endpoint", "query_type"],
        )

        self.requests_in_progress = Gauge(
            "agi_requests_in_progress",
            "Number of requests currently being processed",
            ["endpoint"],
        )

        # Response time metrics
        self.response_time = Histogram(
            "agi_response_time_seconds",
            "Response time in seconds",
            ["endpoint", "query_type"],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
        )

        # Quality metrics
        self.confidence_score = Histogram(
            "agi_confidence_score",
            "Confidence score of responses",
            ["query_type"],
            buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
        )

        self.satisfaction_score = Histogram(
            "agi_satisfaction_score",
            "User satisfaction score",
            buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
        )

        self.phi_resonance_score = Histogram(
            "agi_phi_resonance_score",
            "Phi resonance score",
            ["component"],
            buckets=[0.0, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0],
        )

        # Conversation metrics
        self.conversations_active = Gauge(
            "agi_conversations_active", "Number of active conversations"
        )

        self.conversations_total = Counter(
            "agi_conversations_total", "Total number of conversations started"
        )

        self.messages_total = Counter(
            "agi_messages_total",
            "Total number of messages processed",
            ["direction"],  # 'inbound' or 'outbound'
        )

        # Knowledge base metrics
        self.knowledge_queries = Counter(
            "agi_knowledge_queries_total", "Total knowledge base queries", ["domain"]
        )

        self.knowledge_entries = Gauge(
            "agi_knowledge_entries", "Number of knowledge base entries", ["domain"]
        )

        # NLP metrics
        self.nlp_processing_time = Histogram(
            "agi_nlp_processing_time_seconds",
            "NLP processing time",
            buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0],
        )

        self.nlp_intents = Counter(
            "agi_nlp_intents_total", "NLP intents detected", ["intent"]
        )

        # Quantum metrics
        self.quantum_computations = Counter(
            "agi_quantum_computations_total",
            "Total quantum computations",
            ["algorithm"],
        )

        self.quantum_speedup = Histogram(
            "agi_quantum_speedup",
            "Quantum speedup factor",
            ["algorithm"],
            buckets=[1.0, 2.0, 5.0, 10.0, 50.0, 100.0],
        )

        # Cache metrics
        self.cache_hits = Counter("agi_cache_hits_total", "Cache hits", ["cache_type"])

        self.cache_misses = Counter(
            "agi_cache_misses_total", "Cache misses", ["cache_type"]
        )

        # Error metrics
        self.errors_total = Counter(
            "agi_errors_total", "Total errors", ["error_type", "component"]
        )

        # System info
        self.system_info = Info("agi_system", "AGI system information")

        self.system_info.info(
            {
                "version": "1.0.0",
                "component": "enhanced_agi",
                "prometheus_available": str(PROMETHEUS_AVAILABLE),
            }
        )

        logger.info(f"AGI metrics initialized (Prometheus: {PROMETHEUS_AVAILABLE})")

    def track_request(self, endpoint: str, query_type: str):
        """Track a request"""
        self.requests_total.labels(endpoint=endpoint, query_type=query_type).inc()
        self.requests_in_progress.labels(endpoint=endpoint).inc()

    def complete_request(self, endpoint: str):
        """Mark request as complete"""
        self.requests_in_progress.labels(endpoint=endpoint).dec()

    def record_response_time(self, endpoint: str, query_type: str, duration: float):
        """Record response time"""
        self.response_time.labels(endpoint=endpoint, query_type=query_type).observe(
            duration
        )

    def record_confidence(self, query_type: str, confidence: float):
        """Record confidence score"""
        self.confidence_score.labels(query_type=query_type).observe(confidence)

    def record_satisfaction(self, satisfaction: float):
        """Record satisfaction score"""
        self.satisfaction_score.observe(satisfaction)

    def record_phi_resonance(self, component: str, score: float):
        """Record phi resonance score"""
        self.phi_resonance_score.labels(component=component).observe(score)

    def track_conversation_start(self):
        """Track conversation start"""
        self.conversations_total.inc()
        self.conversations_active.inc()

    def track_conversation_end(self):
        """Track conversation end"""
        self.conversations_active.dec()

    def track_message(self, direction: str):
        """Track message (inbound/outbound)"""
        self.messages_total.labels(direction=direction).inc()

    def track_knowledge_query(self, domain: str):
        """Track knowledge base query"""
        self.knowledge_queries.labels(domain=domain).inc()

    def update_knowledge_count(self, domain: str, count: int):
        """Update knowledge entry count"""
        self.knowledge_entries.labels(domain=domain).set(count)

    def record_nlp_time(self, duration: float):
        """Record NLP processing time"""
        self.nlp_processing_time.observe(duration)

    def track_nlp_intent(self, intent: str):
        """Track NLP intent"""
        self.nlp_intents.labels(intent=intent).inc()

    def track_quantum_computation(self, algorithm: str, speedup: float):
        """Track quantum computation"""
        self.quantum_computations.labels(algorithm=algorithm).inc()
        self.quantum_speedup.labels(algorithm=algorithm).observe(speedup)

    def track_cache_hit(self, cache_type: str):
        """Track cache hit"""
        self.cache_hits.labels(cache_type=cache_type).inc()

    def track_cache_miss(self, cache_type: str):
        """Track cache miss"""
        self.cache_misses.labels(cache_type=cache_type).inc()

    def track_error(self, error_type: str, component: str):
        """Track error"""
        self.errors_total.labels(error_type=error_type, component=component).inc()


# Global metrics instance
_metrics: Optional[AGIMetrics] = None


def get_metrics() -> AGIMetrics:
    """Get global metrics instance"""
    global _metrics
    if _metrics is None:
        _metrics = AGIMetrics()
    return _metrics


def track_performance(endpoint: str, query_type: str = "general"):
    """Decorator to track performance metrics"""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            metrics = get_metrics()

            # Track request start
            metrics.track_request(endpoint, query_type)
            start_time = time.time()

            try:
                # Execute function
                # result = await func(*args, **kwargs)

                # Record metrics
                duration = time.time() - start_time
                metrics.record_response_time(endpoint, query_type, duration)

                # Record confidence if available
                if isinstance(result, dict) and "confidence" in result:
                    metrics.record_confidence(query_type, result["confidence"])

                return result

            except Exception as e:
                # Track error
                metrics.track_error(type(e).__name__, endpoint)
                raise

            finally:
                # Mark request complete
                metrics.complete_request(endpoint)

        return wrapper

    return decorator
