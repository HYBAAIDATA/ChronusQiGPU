"""Chronus Quantum iGPU — Thesus Database System.

Production-ready database integration with connection pooling,
ORM models, and migration support for Hyperscale Hyperscale
Computational Infrastructure & CIaaS Platform.

Thesus provides:
- Async PostgreSQL connection pooling
- ORM models for workloads, receipts, configurations, and node registry
- Database migrations and schema management
- Connection lifecycle management
"""

__version__ = "36.0.0"
__all__ = [
    "ThesusDatabase",
    "DatabaseConfig",
    "database",
    "get_database",
    "Base",
    "WorkloadRecord",
    "NodeRecord",
    "ConfigRecord",
    "ReceiptRecord",
]