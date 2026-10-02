"""Governed, local-first EUCLID runtime.

The package is intentionally fail-closed.  Importing it performs no I/O,
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

__all__ = [
    "Authority",
    "Capability",
    "Experience",
    "EuclidRuntime",
    "Health",
    "Mission",
    "MemoryDatabase",
    "MemoryScope",
    "RewardAuthority",
    "TrainingCase",
    "TrainingPipeline",
    "load_manifest",
    "validate_partitions",
    "verify_manifest",
    "write_manifest",
]
