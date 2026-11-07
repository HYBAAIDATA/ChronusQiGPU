"""Chronus Quantum iGPU REST API Service — Enterprise CIaaS Platform.

Production-ready service layer exposing the Chronus computational substrate
via REST endpoints with OpenAPI specification, authentication, rate limiting,
and comprehensive observability.
"""

__version__ = "36.0.0"
__all__ = [
    "create_app",
    "ChronusService",
    "WorkloadRequest",
    "WorkloadResponse",
    "HealthStatus",
    "VerificationResult",
]