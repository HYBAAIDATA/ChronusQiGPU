"""Docker workload contract: manifest.json schema and the result envelope.

Each container exposes ``/workload/{manifest,input,kernel,backend,expected,
output,proof,benchmark}``. The manifest declares the mathematical model,
scale, fold family, encoding, backend, oracle, exactness mode, and seed; the
result envelope carries measured outcome fields only — no inferred speedups.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict

from .core import fib, lucas, sha256_json
from .pisot_fold import pisot_fold

__all__ = [
    "WorkloadManifest",
    "WorkloadResult",
    "WORKLOAD_DIRS",
    "BACKENDS",
    "EXACTNESS_MODES",
    "run_workload",
]

#: Directories every /workload container must expose.
WORKLOAD_DIRS = ("input", "kernel", "backend", "expected", "output", "proof")

BACKENDS = ("mla1517", "cpu", "gpu", "simulator", "quantum_device")
EXACTNESS_MODES = ("exact", "arbitrary_precision", "bounded_residual")


@dataclass(frozen=True)
class WorkloadManifest:
    """The declared workload manifest recorded in /workload/manifest.json."""

    workload: str
    mathematical_model: str  # "quantum" | "quantum_simulation" | "classical"
    scale: int
    fold_family: str
    encoding: str
    backend: str
    oracle_definition: str = "hash-or-reference"
    exactness_mode: str = "exact"
    seed: int = 31071976
    extra: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.backend not in BACKENDS:
            raise ValueError(f"backend must be one of {BACKENDS}")
        if self.exactness_mode not in EXACTNESS_MODES:
            raise ValueError(f"exactness_mode must be one of {EXACTNESS_MODES}")
        if not self.workload:
            raise ValueError("workload name is required")
        if self.scale < 1:
            raise ValueError("scale must be >= 1")

    def as_dict(self) -> Dict[str, Any]:
        body = {
            "workload": self.workload,
            "mathematical_model": self.mathematical_model,
            "scale": self.scale,
            "fold_family": self.fold_family,
            "encoding": self.encoding,
            "backend": self.backend,
            "oracle_definition": self.oracle_definition,
            "exactness_mode": self.exactness_mode,
            "seed": self.seed,
        }
        body.update(self.extra)
        return body


@dataclass(frozen=True)
class WorkloadResult:
    """The required result envelope — measured fields only."""

    workload: str
    backend: str
    scale: int
    lucas_operator: str
    pisot_fold: str
    cassini_valid: bool
    zeckendorf_valid: bool
    baseline_result: Any
    scaled_result: Any
    fidelity_or_error: float
    runtime_seconds: float
    memory_bytes: int
    bytes_moved: int
    proof_checks: int
    # Honesty pin: kept literal False by construction — a workload run is
    # measured evidence, never a proof claim.
    theorem_proven: bool = False
    interpretation: str = "measured result only"
    manifest_digest: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "workload": self.workload,
            "backend": self.backend,
            "scale": self.scale,
            "lucas_operator": self.lucas_operator,
            "pisot_fold": self.pisot_fold,
            "cassini_valid": self.cassini_valid,
            "zeckendorf_valid": self.zeckendorf_valid,
            "baseline_result": self.baseline_result,
            "scaled_result": self.scaled_result,
            "fidelity_or_error": self.fidelity_or_error,
            "runtime_seconds": self.runtime_seconds,
            "memory_bytes": self.memory_bytes,
            "bytes_moved": self.bytes_moved,
            "proof_checks": self.proof_checks,
            "theorem_proven": self.theorem_proven,
            "interpretation": self.interpretation,
            "manifest_digest": self.manifest_digest,
        }


def run_workload(manifest: WorkloadManifest) -> WorkloadResult:
    """Execute the declared workload on the exact reference path.

    The baseline is the exact recurrence evaluation; the scaled result is the
    same evaluation at the declared scale. ``theorem_proven`` is always False:
    a runtime result is measured evidence, not a theorem.
    """
    from .cassini import verify_state
    from .zeckendorf_codec import is_valid_mask, to_mask

    started = time.perf_counter()
    baseline = fib(manifest.scale)
    scaled = fib(manifest.scale + 1) + fib(manifest.scale - 1)  # L_scale
    scaled_ok = scaled == lucas(manifest.scale)
    fold = pisot_fold(manifest.scale, family=manifest.fold_family.split("_")[0])
    proofs = verify_state(manifest.scale)
    proof_checks = len(proofs)
    cassini_valid = all(p.passed for p in proofs)
    mask = to_mask(manifest.scale)
    zeckendorf_valid = is_valid_mask(mask)
    runtime = time.perf_counter() - started
    fidelity = 0.0 if (scaled_ok and cassini_valid and zeckendorf_valid) else 1.0
    return WorkloadResult(
        workload=manifest.workload,
        backend=manifest.backend,
        scale=manifest.scale,
        lucas_operator="defined",
        pisot_fold=fold.exactness_status,
        cassini_valid=cassini_valid,
        zeckendorf_valid=zeckendorf_valid,
        baseline_result=str(baseline),
        scaled_result=str(scaled),
        fidelity_or_error=fidelity,
        runtime_seconds=runtime,
        memory_bytes=0,
        bytes_moved=0,
        proof_checks=proof_checks,
        theorem_proven=False,
        interpretation="measured result only",
        manifest_digest=sha256_json(manifest.as_dict()),
    )
