"""Database configuration scaffolding for Chronus.

Configuration structures only; the active workload store is the SQLite
backend in chronus.service.workload_store. No ORM or pooling executes here.
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