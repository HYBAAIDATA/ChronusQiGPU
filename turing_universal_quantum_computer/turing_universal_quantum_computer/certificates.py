"""Run witnesses for the VQC.

Every execution can emit a witness: a small, verifiable record of *what ran,
what it produced, and what may be claimed about it*.  The witness is the
product artefact — it is what a caller can attach to a result, diff against a
re-run, or hand to a reviewer.

The invariant that matters: a witness cannot assert more than the backend
proved.  ``theorem_proven`` and ``consensus_authority`` are always False
(this package proves no theorems and holds no consensus authority), and
``measured_qpu`` is refused unless a hardware backend actually ran.  Those
checks are enforced in :func:`verify_witness`, so a tampered or over-claiming
witness fails verification instead of passing quietly.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from .backends import ExecutionClass, ExecutionResult, Program, TruthClass
from .backends.qpu import QPUJob, assert_measured_qpu

__all__ = [
    "WITNESS_SCHEMA",
    "WitnessError",
    "RunWitness",
    "issue_witness",
    "verify_witness",
]

WITNESS_SCHEMA = "turing.vqc.run_witness.v1"


class WitnessError(RuntimeError):
    """Refusal: a witness is malformed or claims more than was proven."""


@dataclass(frozen=True)
class RunWitness:
    """A verifiable record of one VQC execution."""

    schema: str
    program_digest: str
    backend: str
    execution_class: str
    truth_class: str
    n_qubits: int
    materialised: bool
    field: str
    norm_sq_exact: str | None
    support: int | None
    gate_counts: dict[str, int] = field(default_factory=dict)
    measured_qpu: bool = False
    provider_job_id: str | None = None
    #: This package proves no theorems. Always False.
    theorem_proven: bool = False
    #: SHA-256d remains the sole accept authority. Always False.
    consensus_authority: bool = False
    issued_at: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, indent=2)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RunWitness":
        if payload.get("schema") != WITNESS_SCHEMA:
            raise WitnessError(f"unsupported witness schema {payload.get('schema')!r}")
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        unknown = sorted(set(payload) - known)
        if unknown:
            raise WitnessError(f"witness has unknown field(s): {unknown}")
        return cls(**payload)

    def digest(self) -> str:
        canonical = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def issue_witness(
    program: Program,
    result: ExecutionResult,
    *,
    provider_job: QPUJob | None = None,
    notes: str = "",
) -> RunWitness:
    """Issue a witness for one execution.

    A hardware result requires its ``QPUJob`` record here, so a hardware claim
    cannot be made without evidence attached at issue time.
    """
    measured_qpu = bool(result.measured_qpu)
    if measured_qpu:
        assert_measured_qpu(result, provider_job)
    elif provider_job is not None:
        raise WitnessError(
            "a provider job record was supplied for a non-hardware result; "
            "refusing to attach hardware evidence to a simulated run"
        )
    payload = result.payload or {}
    return RunWitness(
        schema=WITNESS_SCHEMA,
        program_digest=result.program_digest,
        backend=result.backend,
        execution_class=result.execution_class.value,
        truth_class=result.truth_class.value,
        n_qubits=result.n_qubits,
        materialised=bool(result.materialised),
        field=str(payload.get("field", "n/a")),
        norm_sq_exact=payload.get("norm_sq_exact"),
        support=payload.get("support"),
        gate_counts=program.gate_counts(),
        measured_qpu=measured_qpu,
        provider_job_id=(provider_job.job_id if provider_job else None),
        issued_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        notes=notes,
    )


def verify_witness(witness: RunWitness) -> bool:
    """Fail-closed verification of a witness.  Raises on any overclaim."""
    if witness.schema != WITNESS_SCHEMA:
        raise WitnessError(f"unsupported witness schema {witness.schema!r}")
    if witness.theorem_proven:
        raise WitnessError("refused: this package proves no theorems")
    if witness.consensus_authority:
        raise WitnessError(
            "refused: the VQC holds no consensus authority; SHA-256d target "
            "comparison is the sole accept rule"
        )
    if witness.n_qubits < 1:
        raise WitnessError("refused: n_qubits must be >= 1")
    if len(witness.program_digest) != 64:
        raise WitnessError("refused: program_digest must be a SHA-256 hex digest")

    hardware = witness.execution_class == ExecutionClass.HARDWARE.value
    if witness.measured_qpu and not hardware:
        raise WitnessError(
            f"refused: measured_qpu is set but the backend is "
            f"{witness.execution_class!r}, not hardware"
        )
    if hardware and not witness.measured_qpu:
        raise WitnessError("refused: a hardware backend must carry measured_qpu")
    if witness.measured_qpu and not witness.provider_job_id:
        raise WitnessError("refused: measured_qpu requires a provider job id")

    if witness.execution_class in (
        ExecutionClass.EXACT_ALGEBRAIC.value,
        ExecutionClass.EXACT_SYMBOLIC.value,
        ExecutionClass.BOUNDED_EXACT.value,
    ) and witness.truth_class != TruthClass.EXACT.value:
        raise WitnessError(
            f"refused: an exact backend cannot report truth_class "
            f"{witness.truth_class!r}"
        )
    if (
        witness.execution_class == ExecutionClass.APPROXIMATE.value
        and witness.truth_class == TruthClass.EXACT.value
    ):
        raise WitnessError("refused: an approximate backend cannot report truth_class 'exact'")
    if witness.materialised and witness.execution_class == ExecutionClass.EXACT_SYMBOLIC.value:
        raise WitnessError("refused: a symbolic backend never materialises a state")
    return True
