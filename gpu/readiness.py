"""Production-readiness gates for the heterogeneous compute stack."""

from __future__ import annotations

import importlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class Gate:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class ProductionEvidence:
    """External evidence that cannot be manufactured by software tests."""

    opencl_conformance: bool = False
    asic_protocol: bool = False
    pool_acknowledgement: bool = False
    provenance_valid: bool = False
    container_measured: bool = False


_SOFTWARE_SURFACES: dict[str, tuple[str, tuple[str, ...]]] = {
    "tensor": (
        "gpu.tensor",
        ("TensorMeasurement", "load_exact_tensor_module"),
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
        "gpu.reference",
        (
            "sha256d_scan",
            "sha256d_verify",
            "sha256_midstate",
            "sha256d_merkle",
        ),
    ),
    "igpu_seam": (
        "igpu.seam.types",
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


def production_readiness(
    evidence: ProductionEvidence | Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a fail-closed readiness report.

    Software availability and external physical evidence are separate gates.
    Missing evidence remains visible and can never be inferred from imports.
    """
    if evidence is None:
        physical = ProductionEvidence()
    elif isinstance(evidence, ProductionEvidence):
        physical = evidence
    else:
        physical = ProductionEvidence(
            **{
                field: bool(evidence.get(field, False))
                for field in ProductionEvidence.__dataclass_fields__
            }
        )
    software = audit_software_surfaces()
    physical_gates = tuple(
        Gate(name, passed, "provided" if passed else "required external evidence")
        for name, passed in asdict(physical).items()
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
    "Gate",
    "ProductionEvidence",
    "audit_software_surfaces",
    "production_readiness",
]