"""Database configuration scaffolding for Chronus.

Configuration structures only; the active workload store is the SQLite
backend in chronus.service.workload_store. No ORM or pooling executes here.
"""

from chronus import __version__ as __version__  # single source: chronus.__version__
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