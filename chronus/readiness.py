"""Production-readiness gates for the CHRONUS heterogeneous compute stack.

Supports both:
1. The owner-approved two-mode CHRONUS product contract (``native_chronus_gpu``
   core readiness via ``CoreProductionEvidence`` + ``audit_core_surfaces``, and
   additive ``host_gpu_augmentation`` via ``AcceleratorCertification``); and
2. External hardware/deployment receipt verification via ``ProductionEvidence``
   + ``audit_software_surfaces``.
"""

from __future__ import annotations

import argparse
import importlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from chronus.provenance import ProvenanceError, validate_provenance
from chronus.virtual_igpu.abi import ExecutionPolicy, ProductMode

_SHA256 = re.compile(r"^[0-9a-f]{64}$")

NATIVE_CHRONUS_MODE = ProductMode.NATIVE_CHRONUS_GPU.value
HOST_GPU_AUGMENTATION_MODE = ProductMode.HOST_GPU_AUGMENTATION.value

CORE_MODE = NATIVE_CHRONUS_MODE
ACCELERATOR_MODE = HOST_GPU_AUGMENTATION_MODE


@dataclass(frozen=True)
class Gate:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class EvidenceReceipt:
    """Digest-bound reference to externally produced or executed release evidence."""

    kind: str
    artifact_sha256: str
    observed_at: str
    subject: str
    producer: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


EvidenceRef = EvidenceReceipt


@dataclass(frozen=True)
class ProductionEvidence:
    """Evidence inputs for the five external release gates; booleans are never evidence."""

    opencl_conformance: EvidenceReceipt | Mapping[str, Any] | None = None
    asic_protocol: EvidenceReceipt | Mapping[str, Any] | None = None
    pool_acknowledgement: EvidenceReceipt | Mapping[str, Any] | None = None
    provenance_valid: Mapping[str, Any] | None = None
    container_measured: EvidenceReceipt | Mapping[str, Any] | None = None


@dataclass(frozen=True)
class CoreProductionEvidence:
    """Evidence required to declare native CHRONUS production-ready."""

    software_execution: EvidenceRef | Mapping[str, Any] | None = None
    independent_verification: EvidenceRef | Mapping[str, Any] | None = None
    receipt_identity: EvidenceRef | Mapping[str, Any] | None = None
    custody_restart: EvidenceRef | Mapping[str, Any] | None = None
    clean_install: EvidenceRef | Mapping[str, Any] | None = None
    full_suite: EvidenceRef | Mapping[str, Any] | None = None


@dataclass(frozen=True)
class AcceleratorCertification:
    """Certification for one physical accelerator lane."""

    backend: str
    device_id: str
    artifact_sha256: str
    observed_at: str
    subject: str
    producer: str
    execution_observed: bool
    correctness_verified: bool
    metadata: Mapping[str, Any] = field(default_factory=dict)


_SOFTWARE_SURFACES: dict[str, tuple[str, tuple[str, ...]]] = {
    "tensor": (
        "hyba.hybrid.tensor_advisor",
        ("WindowRanker", "apply_tensor_advice"),
    ),
    "performance_accounting": (
        "hyba.hybrid.performance",
        ("LayerSample", "PerformanceReport"),
    ),
    "virtual_quantum_computer": (
        "turing_universal_quantum_computer",
        ("TenThousandQubitSystem", "QuantumRegister"),
    ),
    "manifold": (
        "aethel.manifold",
        ("PrimeStorageManifold", "GeodesicNavigator"),
    ),
    "sha256d": (
        "chronus.reference",
        (
            "sha256d_scan",
            "sha256d_verify",
            "sha256_midstate",
            "sha256d_merkle",
        ),
    ),
    "chronus_seam": (
        "chronus.seam.types",
        ("KernelName", "KERNEL_CLASS"),
    ),
}

_CORE_SURFACES: dict[str, tuple[str, tuple[str, ...]]] = {
    "virtual_igpu": (
        "chronus.virtual_igpu",
        ("RuntimeDaemon", "ChronusClient", "ProductMode", "ExecutionPolicy"),
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


def audit_software_surfaces() -> tuple[Gate, ...]:
    """Import every canonical software surface and verify its required public symbols."""
    gates: list[Gate] = []
    for name, (module_name, symbols) in _SOFTWARE_SURFACES.items():
        try:
            module = importlib.import_module(module_name)
            missing = [symbol for symbol in symbols if not hasattr(module, symbol)]
        except Exception as exc:
            gates.append(Gate(name, False, f"{type(exc).__name__}: {exc}"))
            continue
        if missing:
            gates.append(Gate(name, False, f"missing symbols: {', '.join(missing)}"))
        else:
            gates.append(Gate(name, True, f"{module_name}: {', '.join(symbols)}"))
    return tuple(gates)


def audit_core_surfaces() -> tuple[Gate, ...]:
    """Import the owner-approved mature capability surfaces."""
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


_REQUIRED_EXTERNAL = {
    "opencl_conformance": "opencl_conformance",
    "asic_protocol": "asic_protocol",
    "pool_acknowledgement": "pool_acknowledgement",
    "container_measured": "container_measurement",
}


def _receipt_gate(name: str, value: Any) -> Gate:
    expected_kind = _REQUIRED_EXTERNAL[name]
    if value is None:
        return Gate(name, False, "required external evidence")
    if isinstance(value, bool):
        return Gate(name, False, "boolean assertions are not evidence")
    try:
        receipt = value if isinstance(value, EvidenceReceipt) else EvidenceReceipt(**dict(value))
    except (TypeError, ValueError):
        return Gate(name, False, "invalid evidence receipt")
    problems = []
    if receipt.kind != expected_kind:
        problems.append(f"kind must be {expected_kind!r}")
    if not _SHA256.fullmatch(receipt.artifact_sha256):
        problems.append("artifact_sha256 must be a lowercase SHA-256 digest")
    if not receipt.subject.strip():
        problems.append("subject is required")
    if not receipt.producer.strip():
        problems.append("producer is required")
    try:
        stamp = datetime.fromisoformat(receipt.observed_at.replace("Z", "+00:00"))
        if stamp.tzinfo is None or stamp.utcoffset() != timezone.utc.utcoffset(stamp):
            problems.append("observed_at must be an RFC3339 UTC timestamp")
    except (AttributeError, TypeError, ValueError):
        problems.append("observed_at must be an RFC3339 UTC timestamp")
    if not isinstance(receipt.metadata, Mapping):
        problems.append("metadata must be a mapping")
    if problems:
        return Gate(name, False, "; ".join(problems))
    return Gate(name, True, f"verified receipt kind={receipt.kind} subject={receipt.subject} artifact_sha256={receipt.artifact_sha256}")


def _provenance_gate(value: Any) -> Gate:
    if value is None:
        return Gate("provenance_valid", False, "required post-merge provenance record")
    if isinstance(value, bool):
        return Gate("provenance_valid", False, "boolean assertions are not evidence")
    if not isinstance(value, Mapping):
        return Gate("provenance_valid", False, "provenance evidence must be a mapping")
    try:
        normalized = validate_provenance(value, production=True)
    except ProvenanceError as exc:
        return Gate("provenance_valid", False, f"invalid provenance: {exc}")
    return Gate("provenance_valid", True, f"validated production provenance repo_sha={normalized['repo_sha']} human_merge_sha={normalized['human_merge_sha']}")


def _coerce_evidence(evidence: ProductionEvidence | Mapping[str, Any] | None) -> ProductionEvidence:
    if evidence is None:
        return ProductionEvidence()
    if isinstance(evidence, ProductionEvidence):
        return evidence
    if not isinstance(evidence, Mapping):
        raise TypeError("evidence must be ProductionEvidence, a mapping, or None")
    return ProductionEvidence(**{name: evidence.get(name) for name in ProductionEvidence.__dataclass_fields__})


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


def _is_legacy_production_evidence(
    evidence: Any,
    accelerator_certifications: Sequence[Any],
) -> bool:
    if isinstance(evidence, ProductionEvidence):
        return True
    if isinstance(evidence, CoreProductionEvidence) or accelerator_certifications:
        return False
    if isinstance(evidence, Mapping):
        legacy_keys = set(ProductionEvidence.__dataclass_fields__)
        if any(k in legacy_keys for k in evidence):
            return True
    return False


def production_readiness(
    evidence: CoreProductionEvidence | ProductionEvidence | Mapping[str, Any] | None = None,
    *,
    accelerator_certifications: Sequence[
        AcceleratorCertification | Mapping[str, Any]
    ] = (),
) -> dict[str, Any]:
    """Return a fail-closed readiness report supporting both two-mode and receipt contracts."""
    if _is_legacy_production_evidence(evidence, accelerator_certifications):
        physical = _coerce_evidence(evidence)  # type: ignore[arg-type]
        software = audit_software_surfaces()
        physical_gates = (
            _receipt_gate("opencl_conformance", physical.opencl_conformance),
            _receipt_gate("asic_protocol", physical.asic_protocol),
            _receipt_gate("pool_acknowledgement", physical.pool_acknowledgement),
            _provenance_gate(physical.provenance_valid),
            _receipt_gate("container_measured", physical.container_measured),
        )
        all_gates = (*software, *physical_gates)
        return {
            "production_ready": all(gate.passed for gate in all_gates),
            "software_ready": all(gate.passed for gate in software),
            "gates": [asdict(gate) for gate in all_gates],
            "claim_boundary": (
                "software imports do not prove hardware execution, ASIC availability, "
                "pool acceptance, provenance, container size, or hashrate"
            ),
        }

    core_evidence = _coerce_core(evidence)  # type: ignore[arg-type]
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
            "execution_policy": ExecutionPolicy.STANDALONE_SOFTWARE.value,
            "requires_physical_gpu": False,
            "identity": (
                "Chronus is the software-defined GPU; the executing host substrate "
                "does not define the product."
            ),
            "gates": [asdict(g) for g in (*source_gates, *evidence_gates)],
        },
        ACCELERATOR_MODE: {
            "ready": core_ready and accelerator_ready,
            "execution_policy": ExecutionPolicy.PREFERRED_ACCELERATOR.value,
            "requires_physical_gpu": True,
            "lanes": accelerator_lanes,
            "identity": (
                "Chronus augments/scales a certified host GPU or accelerator; "
                "this mode is additive to native Chronus."
            ),
            "note": (
                "host-accelerator certification is additive; failure or absence "
                "of a physical lane does not demote native CHRONUS"
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
            "CHRONUS is a substrate-agnostic software-defined GPU. Native product "
            "identity/readiness does not depend on a host GPU. Host-GPU augmentation "
            "and other device-specific claims require their own device-bound "
            "execution and correctness evidence."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate native CHRONUS readiness separately from optional "
            "host-GPU/accelerator augmentation certifications."
        )
    )
    parser.add_argument(
        "--evidence",
        help="JSON file containing CoreProductionEvidence fields",
    )
    parser.add_argument(
        "--accelerators",
        help="JSON file containing a list of AcceleratorCertification records",
    )
    args = parser.parse_args()

    evidence = None
    if args.evidence:
        evidence = json.loads(Path(args.evidence).read_text(encoding="utf-8"))
    accelerator_certifications = ()
    if args.accelerators:
        raw = json.loads(Path(args.accelerators).read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise SystemExit("--accelerators must contain a JSON list")
        accelerator_certifications = raw

    report = production_readiness(
        evidence,
        accelerator_certifications=accelerator_certifications,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["production_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ACCELERATOR_MODE",
    "CORE_MODE",
    "HOST_GPU_AUGMENTATION_MODE",
    "NATIVE_CHRONUS_MODE",
    "AcceleratorCertification",
    "CoreProductionEvidence",
    "EvidenceReceipt",
    "EvidenceRef",
    "Gate",
    "ProductionEvidence",
    "audit_core_surfaces",
    "audit_software_surfaces",
    "main",
    "production_readiness",
]

