"""Governed, local-first EUCLID runtime and intelligence engine.

The package is intentionally fail-closed. Importing it performs no I/O,
network access, dynamic discovery, or self-modification.
"""

from .contracts import (
    Authority,
    Capability,
    Experience,
    Health,
    Mission,
    RewardAuthority,
)
from .runtime import EuclidRuntime
from .memory_database import MemoryDatabase, MemoryScope
from .training_pipeline import (
    TrainingCase,
    TrainingPipeline,
    validate_partitions,
)
from .checkpoint_manifest import (
    load_manifest,
    verify_manifest,
    write_manifest,
)
from .adapter import EuclidEngineAdapter
from .subsystem_registry import (
    HealthLevel,
    HealthStatus,
    SubsystemDescriptor,
    SubsystemKind,
    SubsystemRegistry,
    build_default_registry,
    salamander_descriptor,
)
from .startup_orchestrator import StartupOrchestrator, StartupVerdict

__version__ = "16.0.0"

__all__ = [
    "Authority",
    "Capability",
    "Experience",
    "EuclidEngineAdapter",
    "EuclidRuntime",
    "Health",
    "HealthLevel",
    "HealthStatus",
    "Mission",
    "MemoryDatabase",
    "MemoryScope",
    "RewardAuthority",
    "StartupOrchestrator",
    "StartupVerdict",
    "SubsystemDescriptor",
    "SubsystemKind",
    "SubsystemRegistry",
    "TrainingCase",
    "TrainingPipeline",
    "build_default_registry",
    "load_manifest",
    "salamander_descriptor",
    "validate_partitions",
    "verify_manifest",
    "write_manifest",
]
