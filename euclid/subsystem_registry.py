"""Declarative registry for governed EUCLID boot-time health checks."""

from __future__ import annotations
import importlib
import math
import time
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Callable, Mapping


class HealthLevel(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"


class SubsystemKind(str, Enum):
    INTELLIGENCE = "intelligence"
    LEARNING = "learning"
    MODEL = "model"
    GOVERNANCE = "governance"
    RECOVERY_SUBSTRATE = "recovery_substrate"
    INTERFACE = "interface"


@dataclass(frozen=True)
class HealthStatus:
    status: HealthLevel
    confidence: float
    details: Mapping[str, Any] = field(default_factory=dict)
    suggested_fallback: str | None = None
    error_code: str | None = None
    checked_at: float = field(default_factory=time.time)

    def __post_init__(self):
        object.__setattr__(self, "status", HealthLevel(self.status))
        value = float(self.confidence)
        if not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError("confidence must be finite in [0,1]")
        object.__setattr__(self, "confidence", value)
        object.__setattr__(self, "details", MappingProxyType(dict(self.details)))


@dataclass(frozen=True)
class SubsystemDescriptor:
    name: str
    kind: SubsystemKind
    responsibility: str
    health_check: Callable[[], HealthStatus]
    fallback_mode: str | None = None
    governance_constraints: tuple[str, ...] = ()
    audit_channel: str = "startup"
    confidence_bounds: tuple[float, float] = (0.0, 1.0)
    shutdown_rules: tuple[str, ...] = ()
    critical: bool = False

    def __post_init__(self):
        if (
            not self.name.strip()
            or not self.responsibility.strip()
            or not callable(self.health_check)
        ):
            raise ValueError("name, responsibility, and health check required")
        object.__setattr__(self, "kind", SubsystemKind(self.kind))
        low, high = self.confidence_bounds
        if not 0 <= low <= high <= 1:
            raise ValueError("invalid confidence bounds")


class SubsystemRegistry:
    def __init__(self):
        self._items: dict[str, SubsystemDescriptor] = {}

    def register(self, descriptor: SubsystemDescriptor):
        if descriptor.name in self._items:
            raise ValueError("subsystem already registered")
        self._items[descriptor.name] = descriptor
        return descriptor

    def descriptors(self):
        return tuple(self._items[name] for name in sorted(self._items))

    def run_health_checks(self):
        results = {}
        for item in self.descriptors():
            start = time.perf_counter()
            try:
                status = item.health_check()
                if not isinstance(status, HealthStatus):
                    raise TypeError("health check must return HealthStatus")
                if not item.confidence_bounds[0] <= status.confidence <= item.confidence_bounds[1]:
                    status = HealthStatus(
                        HealthLevel.FAILED,
                        0,
                        {"reason": "confidence outside registered bounds"},
                        item.fallback_mode,
                        "CONFIDENCE_BOUNDS",
                    )
            except Exception as exc:
                status = HealthStatus(
                    HealthLevel.FAILED,
                    0,
                    {"error_type": type(exc).__name__},
                    item.fallback_mode,
                    "HEALTH_CHECK_EXCEPTION",
                )
            results[item.name] = {
                "descriptor": item,
                "status": status,
                "latency_ms": (time.perf_counter() - start) * 1000,
            }
        return results

    def __len__(self):
        return len(self._items)


# Salamander belongs here only as RECOVERY_SUBSTRATE, not as a specialised AI.
def salamander_descriptor(health_check: Callable[[], HealthStatus]) -> SubsystemDescriptor:
    return SubsystemDescriptor(
        "salamander",
        SubsystemKind.RECOVERY_SUBSTRATE,
        "bounded regeneration and recovery substrate",
        health_check,
        "degraded",
        ("no autonomous permission expansion", "no live share submission"),
        "startup.recovery",
        (0, 1),
        ("isolate on failed recovery invariant",),
        False,
    )


def _import_probe(module: str) -> Callable[[], HealthStatus]:
    # Boot-time liveness probe: verifies the subsystem module imports. The check
    # measures import health only — details record exactly what was probed.
    def check() -> HealthStatus:
        importlib.import_module(module)
        return HealthStatus(HealthLevel.HEALTHY, 0.9, {"probe": "import", "module": module})

    return check


# The concrete default registry wires one descriptor per canonical euclid
# surface declared "equivalent" in euclid/recovery_manifest.json, plus
# salamander as the recovery substrate.
def build_default_registry() -> SubsystemRegistry:
    registry = SubsystemRegistry()
    canonical = (
        ("contracts", SubsystemKind.GOVERNANCE, "capability and reward contracts"),
        ("evidence", SubsystemKind.MODEL, "execution evidence records"),
        ("evidence_bundle", SubsystemKind.MODEL, "bundled evidence custody"),
        ("adapters", SubsystemKind.INTERFACE, "engine adapter surface"),
        ("governance", SubsystemKind.GOVERNANCE, "authority and policy enforcement"),
        ("kairos_runtime", SubsystemKind.INTELLIGENCE, "kairos runtime cognition"),
        ("learning_service", SubsystemKind.LEARNING, "learning service surface"),
        ("memory_database", SubsystemKind.MODEL, "memory persistence"),
        ("training_pipeline", SubsystemKind.LEARNING, "training data pipeline"),
        (
            "self_healing_evidence",
            SubsystemKind.RECOVERY_SUBSTRATE,
            "self-healing evidence custody",
        ),
        ("production_harness", SubsystemKind.INTERFACE, "production harness surface"),
        ("rights", SubsystemKind.GOVERNANCE, "rights and permission model"),
        ("runtime", SubsystemKind.INTELLIGENCE, "EUCLID runtime engine"),
    )
    for name, kind, responsibility in canonical:
        registry.register(
            SubsystemDescriptor(name, kind, responsibility, _import_probe("euclid." + name))
        )
    registry.register(salamander_descriptor(_import_probe("Intelligence.salamander")))
    return registry


__all__ = [
    "HealthLevel",
    "SubsystemKind",
    "HealthStatus",
    "SubsystemDescriptor",
    "SubsystemRegistry",
    "salamander_descriptor",
    "build_default_registry",
]
