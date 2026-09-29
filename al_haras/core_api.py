"""Declared mla1517-core public API and import-audit helper."""

from __future__ import annotations
import ast
from pathlib import Path

PUBLIC_SYMBOLS = {
    "mla1517_core.core": {
        "fib_pair",
        "fib",
        "lucas",
        "fast_doubling",
        "cassini",
        "cassini_seal",
        "cassini_verify_pair",
        "zeckendorf",
        "zeckendorf_decode",
        "verify_zeckendorf_canonical",
        "nth_prime",
        "prime_gap",
        "sha256_json",
    },
    "mla1517_core.rings": {
        "ZPhi",
        "ZRho",
        "ZPsi",
        "ZTau",
        "ring_add",
        "ring_mul",
        "ring_pow",
        "ring_norm",
    },
    "mla1517_core.math_folding": {
        "Quadratic5",
        "fibonacci_binet",
        "lucas_binet",
        "pisot_threshold",
        "truncate_pisot",
        "pulvini_fold",
        "pulvini_unfold",
        "fold_lossless",
        "unfold_lossless",
        "truncate_exact",
    },
    "mla1517_core.objects": {
        "MLAObject",
        "PRIMEObjectV2",
        "canonical_hash",
        "make_object",
        "HotDescriptor",
    },
    "mla1517_core.store": {
        "PrimeDB",
        "put",
        "get",
        "verify",
        "put_exact_tensor",
        "get_exact_tensor",
        "find_resonant_blocks",
    },
    "mla1517_core.scale": {
        "ScalePoint",
        "ScaleBudget",
        "ScaleDecision",
        "estimate",
        "authorize",
        "execute_exact",
    },
    "mla1517_core.scaling": {
        "LADDER",
        "OpenCLLadderExecutor",
        "exact_fibonacci_decomposition",
        "exact_lucas_decomposition",
        "exact_padovan_decomposition",
    },
    "mla1517_core.quantum": {
        "QuantumState",
        "hadamard",
        "pauli_x",
        "pauli_y",
        "pauli_z",
        "s_gate",
        "t_gate",
        "cnot",
        "tensor",
        "normalize_exact",
        "measure_exact",
    },
    "mla1517_core.accelerator": {
        "ExactOpenCLAccelerator",
        "AcceleratorUnavailable",
        "ExactResourceError",
    },
    "mla1517_core.host": {"HostGPUPlan", "execute_reference"},
    "mla1517_core.connectors": {"CapabilityReport", "select_backend"},
    "mla1517_core.runtime": {"MLA1517Runtime", "ExecutionEnvelope"},
    "mla1517_core.primedb_engine": {"NativePrimeDB", "VaultRecord"},
    "mla1517_core.knowledge": {"KnowledgeFabric"},
    "mla1517_core.learning": {"LearningLedger"},
    "mla1517_core.m32.geometry": {
        "M32Topology",
        "build_m32",
        "laplacian_gap",
        "build_hermitian",
        "operator_gap",
        "route",
        "polyhedral_destination",
    },
    "mla1517_core.hyba_devices": {
        "DeviceInventory",
        "VirtualGPU",
        "Attestation",
        "MathIR",
        "MultiHasher",
    },
}


class PrivateImport(ValueError):
    pass


def audit_file(path: Path) -> None:
    tree = ast.parse(path.read_text(), filename=str(path))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.ImportFrom)
            and node.module
            and node.module.startswith("mla1517_core")
        ):
            if node.module.startswith(
                ("mla1517_core._", "mla1517_core.internal", "mla1517_core.experiments")
            ):
                raise PrivateImport(f"{path}:{node.lineno}:{node.module}")
            allowed = PUBLIC_SYMBOLS.get(node.module)
            if allowed is None:
                raise PrivateImport(f"{path}:{node.lineno}:undeclared module {node.module}")
            for alias in node.names:
                if alias.name == "*" or alias.name not in allowed:
                    raise PrivateImport(f"{path}:{node.lineno}:{node.module}.{alias.name}")


def import_audit(paths):
    checked = []
    for path in paths:
        if path.is_file() and path.suffix == ".py":
            audit_file(path)
            checked.append(str(path))
    return tuple(checked)
