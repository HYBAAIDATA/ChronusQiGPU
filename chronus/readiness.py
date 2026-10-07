"""CHRONUS production-readiness contract.

Owner-approved product model:
1. standalone_software — CHRONUS is a complete software-defined execution product
   and does not require a physical GPU;
2. accelerator_enhanced — CHRONUS may bind to a certified accelerator to increase
   throughput/capacity, but accelerator certification is lane-specific and must
   never gate the standalone product.

This module keeps core-product readiness separate from per-accelerator readiness.
It consumes digest-bound evidence references; booleans alone are not accepted as
production evidence.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
import importlib
import re
from typing import Any, Mapping, Sequence

from .virtual_igpu.abi import ExecutionPolicy

_SHA256 = re.compile(r"^[0-9a-f]{64}$")

CORE_MODE = ExecutionPolicy.STANDALONE_SOFTWARE.value
ACCELERATOR_MODE = ExecutionPolicy.PREFERRED_ACCELERATOR.value


@dataclass(frozen=True)
class Gate:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class EvidenceRef:
    """Digest-bound reference to an executed artifact."""

    kind: str
    artifact_sha256: str
    observed_at: str
    subject: str
    producer: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CoreProductionEvidence:
    """Evidence required to declare standalone CHRONUS production-ready."""

    software_execution: EvidenceRef | Mapping[str, Any] | None = None
    independent_verification: EvidenceRef | Mapping[str, Any] | None = None
    receipt_identity: EvidenceRef | Mapping[str, Any] | None = None
    custody_restart: EvidenceRef | Mapping[str, Any] | None = None
    clean_install: EvidenceRef | Mapping[str, Any] | None = None
    full_suite: EvidenceRef | Mapping[str, Any] | None = None


@dataclass(frozen=True)
class AcceleratorCertification:
    """Certification for one physical accelerator lane.

    The artifact must bind the actual backend/device and demonstrate execution +
    correctness. This is deliberately independent of core product readiness.
    """

    backend: str
    device_id: str
    artifact_sha256: str
    observed_at: str
    subject: str
    producer: str
    execution_observed: bool
    correctness_verified: bool
    metadata: Mapping[str, Any] = field(default_factory=dict)


_CORE_SURFACES: dict[str, tuple[str, tuple[str, ...]]] = {
    "virtual_igpu": (
        "chronus.virtual_igpu",
        ("RuntimeDaemon", "ChronusClient", "CPUEmulatorAdapter", "ExecutionPolicy"),
    ),
    "mathematical_engine": (
        "chronus.v33",
        ("ChronosEngine", "M32Manifold", "QSDLCompiler", "HamiltonianLibrary"),
    ),
    "scale_contract": (
        "chronus.seam.scale",
        ("scale_job", "compute_effective_capacity", "memory_budget_bytes"),
    ),
    "measurement": (
        "chronus.measurement",
        ("MeasurementArtifact", "measure_chronus", "replay_artifact"),
    ),
    "delivery": (
        "chronus.delivery",
        ("probe_embedded", "probe_cloud_instance", "ChronusDelivery"),
    ),
}


_EXPECTED_EVIDENCE_KINDS = {
    "software_execution": "chronus_software_execution",
    "independent_verification": "chronus_independent_verification",
    "receipt_identity": "chronus_receipt_identity",
    "custody_restart": "chronus_custody_restart",
    "clean_install": "chronus_clean_install",
    "full_suite": "chronus_full_suite",
}


def audit_core_surfaces() -> tuple[Gate, ...]:
    """Import the owner-approved mature capability surfaces.

    This is a source/package audit only. It is intentionally not treated as
    executed production evidence.
    """

    gates: list[Gate] = []
    for name, (module_name, symbols) in _CORE_SURFACES.items():
        try:
            module = importlib.import_module(module_name)
            missing = [symbol for symbol in symbols if not hasattr(module, symbol)]
        except Exception as exc:
            gates.append(Gate(name, False, f"{type(exc).__name__}: {exc}"))
            continue
        if missing:
            gates.append(Gate(name, False, "missing symbols: " + ", ".join(missing)))
        else:
            gates.append(Gate(name, True, f"{module_name}: " + ", ".join(symbols)))
    return tuple(gates)


def _coerce_ref(value: EvidenceRef | Mapping[str, Any] | None) -> EvidenceRef | None:
    if value is None:
        return None
    if isinstance(value, EvidenceRef):
        return value
    if not isinstance(value, Mapping):
        return None
    try:
        return EvidenceRef(**dict(value))
    except (TypeError, ValueError):
        return None


def _validate_timestamp(value: str) -> bool:
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError):
        return False
    return stamp.tzinfo is not None


def _evidence_gate(name: str, value: EvidenceRef | Mapping[str, Any] | None) -> Gate:
    expected_kind = _EXPECTED_EVIDENCE_KINDS[name]
    ref = _coerce_ref(value)
    if ref is None:
        return Gate(name, False, "required executed evidence artifact")
    problems: list[str] = []
    if ref.kind != expected_kind:
        problems.append(f"kind must be {expected_kind!r}")
    if not _SHA256.fullmatch(ref.artifact_sha256):
        problems.append("artifact_sha256 must be a lowercase SHA-256 digest")
    if not _validate_timestamp(ref.observed_at):
        problems.append("observed_at must be timezone-aware ISO-8601")
    if not ref.subject.strip():
        problems.append("subject is required")
    if not ref.producer.strip():
        problems.append("producer is required")
    if not isinstance(ref.metadata, Mapping):
        problems.append("metadata must be a mapping")
    if problems:
        return Gate(name, False, "; ".join(problems))
    return Gate(
        name,
        True,
        f"{ref.subject} artifact_sha256={ref.artifact_sha256}",
    )


def _coerce_core(
    evidence: CoreProductionEvidence | Mapping[str, Any] | None,
) -> CoreProductionEvidence:
    if evidence is None:
        return CoreProductionEvidence()
    if isinstance(evidence, CoreProductionEvidence):
        return evidence
    if not isinstance(evidence, Mapping):
        raise TypeError("core evidence must be a mapping or CoreProductionEvidence")
    return CoreProductionEvidence(
        **{
            name: evidence.get(name)
            for name in CoreProductionEvidence.__dataclass_fields__
        }
    )


def _accelerator_gate(
    cert: AcceleratorCertification | Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(cert, AcceleratorCertification):
        cert = AcceleratorCertification(**dict(cert))
    problems: list[str] = []
    if not cert.backend.strip():
        problems.append("backend is required")
    if not cert.device_id.strip():
        problems.append("device_id is required")
    if not _SHA256.fullmatch(cert.artifact_sha256):
        problems.append("artifact_sha256 must be a lowercase SHA-256 digest")
    if not _validate_timestamp(cert.observed_at):
        problems.append("observed_at must be timezone-aware ISO-8601")
    if not cert.subject.strip() or not cert.producer.strip():
        problems.append("subject and producer are required")
    if not cert.execution_observed:
        problems.append("physical execution was not observed")
    if not cert.correctness_verified:
        problems.append("correctness was not independently verified")
    return {
        "backend": cert.backend,
        "device_id": cert.device_id,
        "ready": not problems,
        "detail": "; ".join(problems) if problems else "device-bound execution certified",
        "artifact_sha256": cert.artifact_sha256,
    }


def production_readiness(
    evidence: CoreProductionEvidence | Mapping[str, Any] | None = None,
    *,
    accelerator_certifications: Sequence[
        AcceleratorCertification | Mapping[str, Any]
    ] = (),
) -> dict[str, Any]:
    """Evaluate CHRONUS readiness without turning GPU evidence into a core gate.

    A standalone CHRONUS release can be production-ready with zero physical GPU
    certifications. Each accelerator lane becomes production-ready only after
    its own device-bound certification artifact satisfies the lane gate.
    """

    core_evidence = _coerce_core(evidence)
    source_gates = audit_core_surfaces()
    evidence_gates = tuple(
        _evidence_gate(name, getattr(core_evidence, name))
        for name in CoreProductionEvidence.__dataclass_fields__
    )
    core_ready = all(g.passed for g in (*source_gates, *evidence_gates))

    accelerator_lanes = [
        _accelerator_gate(cert) for cert in accelerator_certifications
    ]
    accelerator_ready = any(lane["ready"] for lane in accelerator_lanes)

    modes = {
        CORE_MODE: {
            "ready": core_ready,
            "requires_physical_gpu": False,
            "gates": [asdict(g) for g in (*source_gates, *evidence_gates)],
        },
        ACCELERATOR_MODE: {
            "ready": core_ready and accelerator_ready,
            "requires_physical_gpu": True,
            "lanes": accelerator_lanes,
            "note": (
                "accelerator certification is additive; failure or absence of a "
                "physical lane does not demote standalone CHRONUS"
            ),
        },
    }

    ready_modes = [name for name, status in modes.items() if status["ready"]]
    return {
        "product": "Chronus",
        "production_ready": core_ready,
        "core_production_ready": core_ready,
        "ready_modes": ready_modes,
        "modes": modes,
        "claim_boundary": (
            "CHRONUS product identity and standalone production readiness do not "
            "depend on a physical GPU. GPU/iGPU/accelerator claims require their "
            "own device-bound execution and correctness evidence."
        ),
    }


__all__ = [
    "ACCELERATOR_MODE",
    "CORE_MODE",
    "AcceleratorCertification",
    "CoreProductionEvidence",
    "EvidenceRef",
    "Gate",
    "audit_core_surfaces",
    "production_readiness",
]
