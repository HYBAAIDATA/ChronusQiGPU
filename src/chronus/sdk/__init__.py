"""Chronus Quantum iGPU Python SDK — Enterprise Client Library.

Production-ready SDK for interacting with Chronus CIaaS services.
Supports authentication, workload submission, verification, and
post-quantum signed receipts.
"""

__version__ = "36.0.0"
__all__ = [
    "ChronusAPISDK",
    "ChronusSDKConfig",
    "WorkloadResult",
    "VerificationReceipt",
    "ChronusSDKError",
    "AuthenticationError",
    "AuthorizationError",
    "RateLimitError",
    "ServiceUnavailableError",
]