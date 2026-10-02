"""Sealed production evidence bundle for EUCLID release decisions."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Mapping

from .contracts import domain_hash
from .evidence import atomic_write


def create_evidence_bundle(
    *,
    runtime: Mapping[str, Any],
    memory: Mapping[str, Any],
    training: Mapping[str, Any],
    genetic_mining: Mapping[str, Any],
    self_healing: Mapping[str, Any],
    output: str | Path | None = None,
) -> dict[str, Any]:
    sections = {
        "runtime": dict(runtime),
        "memory": dict(memory),
        "training": dict(training),
        "genetic_mining": dict(genetic_mining),
        "self_healing": dict(self_healing),
    }
    required = {
        "runtime": (
            runtime.get("schema") == "euclid.startup/1"
            and runtime.get("network_enabled") is False
            and runtime.get("federation_enabled") is False
        ),
        "memory": bool(memory.get("valid")),
        "training": bool(training.get("passed")),
        "genetic_mining": bool(genetic_mining.get("passed")),
        "self_healing": bool(self_healing.get("passed")),
    }
    body = {
        "schema": "euclid.production-evidence/1",
        "generated_at": time.time(),
        "sections": sections,
        "required_gates": required,
        "passed": all(required.values()),
        "boundaries": {
            "local_runtime_only": True,
            "external_superiority_proven": False,
            "autonomous_repair_enabled": False,
            "network_federation_enabled": False,
        },
    }
    bundle = {**body, "seal": domain_hash("euclid.production-evidence.seal.v1", body)}
    if output is not None:
        atomic_write(Path(output), bundle)
    return bundle


__all__ = ["create_evidence_bundle"]