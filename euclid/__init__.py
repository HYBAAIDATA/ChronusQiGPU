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
from .subsystem_registry import (
    HealthLevel,
    HealthStatus,
    SubsystemDescriptor,
    SubsystemKind,
    SubsystemRegistry,
    build_default_registry,
    salamander_descriptor,
)

# These subsystems sit behind optional internal substrates (hyba_substrate,
# toe, kellogg) that are not part of the standalone wheel surface. They are
# resolved lazily so `import euclid` stays fail-closed-free on minimal
# installs; accessing them without the substrates raises the honest
# ModuleNotFoundError for the missing package.
_LAZY = {
    "EuclidEngineAdapter": "euclid.adapter",
    "ProgramSearchEngine": "euclid.adapter",
    "TrainingCase": "euclid.training_pipeline",
    "TrainingPipeline": "euclid.training_pipeline",
    "validate_partitions": "euclid.training_pipeline",
    "load_manifest": "euclid.checkpoint_manifest",
    "verify_manifest": "euclid.checkpoint_manifest",
    "write_manifest": "euclid.checkpoint_manifest",
    "StartupOrchestrator": "euclid.startup_orchestrator",
    "StartupVerdict": "euclid.startup_orchestrator",
}


def __getattr__(name):
    module = _LAZY.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    value = getattr(importlib.import_module(module), name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(__all__)

__version__ = "17.0.0"

__all__ = [
    "Authority",
    "Capability",
    "Experience",
    "EuclidEngineAdapter",
    "ProgramSearchEngine",
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
    "load_manifest",
    "build_default_registry",
    "salamander_descriptor",
    "validate_partitions",
    "verify_manifest",
    "write_manifest",
]
