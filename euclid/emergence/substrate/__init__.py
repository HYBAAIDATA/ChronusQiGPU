"""Substrate package initialization."""

from .isolation import SubstrateIndependenceVerifier
from .executors import (
    BaseExecutor,
    RealSubstrateExecutor,
    StandardSyncExecutor,
    AsyncIsolatedExecutor,
    ReproductionEvidence,
)
from .harness import RunHarness, TIER_1, TIER_5, TIER_15, TIER_20
from .registry import SubstrateRegistry, compare_capability_profiles

__all__ = [
    "SubstrateIndependenceVerifier",
    "BaseExecutor",
    "RealSubstrateExecutor",
    "StandardSyncExecutor",
    "AsyncIsolatedExecutor",
    "ReproductionEvidence",
    "RunHarness",
    "TIER_1",
    "TIER_5",
    "TIER_15",
    "TIER_20",
    "SubstrateRegistry",
    "compare_capability_profiles",
]
