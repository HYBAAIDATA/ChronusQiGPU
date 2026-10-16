"""Production-readiness gates for the heterogeneous compute stack."""

from __future__ import annotations

import importlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping

from chronus.provenance import ProvenanceError, validate_provenance

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class Gate:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class EvidenceReceipt:
    """Digest-bound reference to externally produced release evidence."""

    kind: str
    artifact_sha256: str
    observed_at: str
    subject: str
    producer: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProductionEvidence:
    """Evidence inputs for the five release gates; booleans are never evidence."""

    opencl_conformance: EvidenceReceipt | Mapping[str, Any] | None = None
    asic_protocol: EvidenceReceipt | Mapping[str, Any] | None = None
    pool_acknowledgement: EvidenceReceipt | Mapping[str, Any] | None = None
    provenance_valid: Mapping[str, Any] | None = None
    container_measured: EvidenceReceipt | Mapping[str, Any] | None = None


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


def audit_software_surfaces() -> tuple[Gate, ...]:
    """Import every canonical surface and verify its required public symbols."""
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


def production_readiness(
    evidence: ProductionEvidence | Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a fail-closed readiness report.

    Software availability and external physical evidence are separate gates.
    Missing evidence remains visible and can never be inferred from imports.
    """
    physical = _coerce_evidence(evidence)
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


def main() -> int:
    report = production_readiness()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["production_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "EvidenceReceipt",
    "Gate",
    "ProductionEvidence",
    "audit_software_surfaces",
    "production_readiness",
]
