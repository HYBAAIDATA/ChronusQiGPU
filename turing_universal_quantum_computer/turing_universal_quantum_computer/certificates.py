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
import math
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping

from .backends import ExecutionClass, ExecutionResult, Program, TruthClass
from .backends.qpu import QPUJob, assert_measured_qpu

__all__ = [
    "WITNESS_SCHEMA",
    "WITNESS_SCHEMA_V1",
    "WITNESS_SCHEMA_V2",
    "WitnessError",
    "RunWitness",
    "VQCComputationCertificate",
    "canonicalize_certificate_value",
    "issue_witness",
    "issue_computation_certificate",
    "replay_computation_certificate",
    "validate_certificate_inputs",
    "verify_computation_certificate",
    "verify_witness",
]

WITNESS_SCHEMA_V1 = "turing.vqc.run_witness.v1"
WITNESS_SCHEMA_V2 = "turing.vqc.run_witness.v2"
WITNESS_SCHEMA = WITNESS_SCHEMA_V2
COMPUTATION_CERTIFICATE_SCHEMA = "turing.vqc.computation_certificate.v1"


class WitnessError(RuntimeError):
    """Refusal: a witness is malformed or claims more than was proven."""


#: Bit length below which an integer can never hit the decimal
#: conversion cap, whatever ``sys.get_int_max_str_digits()`` reports.  A
#: B-bit integer has at most ``ceil(B * log10(2))`` decimal digits, so
#: ``bit_length <= 3 * limit`` is always safe.
_INT_ALWAYS_SAFE_BITS = int(
    getattr(sys, "get_int_max_str_digits", lambda: 4300)() * 3.0
)


def _jsonable(value: Any) -> Any:
    """Canonical value encoding with deterministic IEEE-754 handling."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (str, bool)) or value is None:
        return value
    if isinstance(value, int):
        # CPython caps int<->str decimal conversions (default 4300 digits).
        # Stabilizer results carry ``state_dimension = 1 << n_qubits``, which
        # exceeds the cap for large legal registers.  Values that cannot
        # round-trip are tagged in hex — uncapped and still exact.
        if value.bit_length() > _INT_ALWAYS_SAFE_BITS:
            try:
                str(value)
            except ValueError:
                return {"$bigint": hex(value)}
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise WitnessError("NaN and infinity cannot be certified")
        return {"$float_hex": value.hex()}
    if isinstance(value, dict):
        # String keys keep the plain object form.  Anything else is tagged
        # pairwise: ``{1: "x"}`` and ``{"1": "x"}`` must not collapse into
        # the same committed bytes.  A dict that already contains "$map"
        # is tagged as well so the two forms can never alias.
        if all(isinstance(key, str) for key in value) and "$map" not in value:
            return {key: _jsonable(item) for key, item in sorted(value.items())}
        return {
            "$map": [
                [_jsonable(key), _jsonable(item)]
                for key, item in sorted(
                    value.items(), key=lambda pair: _canonical(pair[0])
                )
            ]
        }
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (set, frozenset)):
        raise WitnessError(
            "unordered set values cannot be certified; supply a sorted sequence"
        )
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return _jsonable(to_dict())
    # Exact algebraic values in this package define a stable mathematical
    # string form.  Tagging the type prevents cross-type aliasing.
    rendered = str(value)
    if " at 0x" in rendered:
        raise WitnessError(f"non-canonical object cannot be certified: {type(value).__name__}")
    return {
        "$type": f"{type(value).__module__}.{type(value).__qualname__}",
        "$value": rendered,
    }


def _canonical(value: Any) -> bytes:
    return json.dumps(
        _jsonable(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def canonicalize_certificate_value(value: Any) -> Any:
    """Return the exact JSON-safe value form used by certificate hashing.

    Persisted execution evidence must use this representation if it is expected
    to reproduce a computation certificate after custody/restart.
    """
    return _jsonable(value)


def _digest(domain: str, value: Any) -> str:
    prefix = b"turing-vqc-certificate-v1\0" + domain.encode("ascii") + b"\0"
    return hashlib.sha256(prefix + _canonical(value)).hexdigest()


def _merkle_root(leaves: tuple[dict[str, Any], ...]) -> str:
    if not leaves:
        return hashlib.sha256(b"turing-vqc-merkle-empty-v1").hexdigest()
    level = [
        hashlib.sha256(b"turing-vqc-merkle-leaf-v1\0" + _canonical(leaf)).digest()
        for leaf in leaves
    ]
    while len(level) > 1:
        if len(level) & 1:
            level.append(level[-1])
        level = [
            hashlib.sha256(
                b"turing-vqc-merkle-node-v1\0" + level[index] + level[index + 1]
            ).digest()
            for index in range(0, len(level), 2)
        ]
    return level[0].hex()


def _field_name(result: ExecutionResult) -> str:
    raw = str((result.payload or {}).get("field", "missing"))
    lowered = raw.lower().replace(" ", "")
    if "gf(2)" in lowered or lowered == "gf2":
        return "GF2"
    if "sqrt(2)" in lowered and ("i" in lowered or "complex" in lowered):
        return "Q_zeta8"
    if lowered in {"q(i)", "q_i"}:
        return "Q_i"
    if lowered in {"q", "rational"}:
        return "Q"
    if result.truth_class is TruthClass.APPROXIMATE:
        return "float"
    return raw


def _machine_type(result: ExecutionResult) -> str:
    if result.execution_class is ExecutionClass.HARDWARE:
        return "hybrid"
    if _field_name(result) == "GF2":
        return "quantum_folded"
    if result.execution_class in (
        ExecutionClass.EXACT_ALGEBRAIC,
        ExecutionClass.EXACT_SYMBOLIC,
        ExecutionClass.BOUNDED_EXACT,
    ):
        return "quantum_unitary"
    return "hybrid"


@dataclass(frozen=True)
class VQCComputationCertificate:
    """Content-addressed proof envelope for one public VQC execution."""

    schema: str
    input: str
    machine: str
    trace: tuple[dict[str, Any], ...]
    output: str
    halted: bool
    steps: int
    certificate_digest: str
    attestation: str
    replayable: bool
    machine_type: str
    field: str
    backend: str
    execution_class: str
    truth_class: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["trace"] = [dict(item) for item in self.trace]
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "VQCComputationCertificate":
        if payload.get("schema") != COMPUTATION_CERTIFICATE_SCHEMA:
            raise WitnessError(
                f"unsupported computation certificate schema {payload.get('schema')!r}"
            )
        known = set(cls.__dataclass_fields__)  # type: ignore[attr-defined]
        unknown = sorted(set(payload) - known)
        if unknown:
            raise WitnessError(f"certificate has unknown field(s): {unknown}")
        converted = dict(payload)
        converted["trace"] = tuple(dict(item) for item in payload.get("trace", ()))
        return cls(**converted)

    def unsigned_payload(self) -> dict[str, Any]:
        payload = self.to_dict()
        payload.pop("certificate_digest")
        return payload

    def verify_integrity(self) -> bool:
        if not self.halted:
            raise WitnessError("finite VQC program certificate must be halted")
        if self.steps != max(len(self.trace) - 2, 0):
            raise WitnessError("certificate step count does not match operation trace")
        if self.attestation != _merkle_root(self.trace):
            raise WitnessError("certificate Merkle attestation mismatch")
        if self.certificate_digest != _digest(
            "computation-certificate", self.unsigned_payload()
        ):
            raise WitnessError("computation certificate digest mismatch")
        for name in ("input", "machine", "output", "certificate_digest", "attestation"):
            value = getattr(self, name)
            if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
                raise WitnessError(f"{name} is not a lowercase SHA-256 digest")
        return True


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
    computation_certificate_digest: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, indent=2)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RunWitness":
        if payload.get("schema") not in (WITNESS_SCHEMA_V1, WITNESS_SCHEMA_V2):
            raise WitnessError(f"unsupported witness schema {payload.get('schema')!r}")
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        unknown = sorted(set(payload) - known)
        if unknown:
            raise WitnessError(f"witness has unknown field(s): {unknown}")
        return cls(**payload)

    def digest(self) -> str:
        payload = self.to_dict()
        if self.schema == WITNESS_SCHEMA_V1:
            if payload.get("computation_certificate_digest") is None:
                payload.pop("computation_certificate_digest")
            canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        # Wall-clock metadata is useful operationally but is not part of the
        # reproducible content identity.
        payload.pop("issued_at")
        return _digest("run-witness", payload)


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
        computation_certificate_digest=(
            result.certificate.get("certificate_digest")
            if result.certificate is not None
            else None
        ),
    )


def verify_witness(witness: RunWitness) -> bool:
    """Fail-closed verification of a witness.  Raises on any overclaim."""
    if witness.schema not in (WITNESS_SCHEMA_V1, WITNESS_SCHEMA_V2):
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
    if witness.computation_certificate_digest is not None:
        digest = witness.computation_certificate_digest
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise WitnessError("refused: malformed computation certificate digest")

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


def issue_computation_certificate(
    program: Program,
    result: ExecutionResult,
    *,
    options: dict[str, Any] | None = None,
) -> VQCComputationCertificate:
    """Bind a program, backend identity, operation trace, and exact result."""
    if result.program_digest != program.digest():
        raise WitnessError("result is bound to a different program")
    execution_options = dict(options or {})
    replayable = not result.measured_qpu
    if execution_options.get("shots") is not None and execution_options.get("seed") is None:
        replayable = False

    trace: list[dict[str, Any]] = [
        {
            "kind": "input",
            "program": program.to_dict(),
            "options": _jsonable(execution_options),
        }
    ]
    for index, operation in enumerate(program.operations):
        trace.append(
            {
                "kind": "operation",
                "index": index,
                "gate": operation.gate,
                "qubits": list(operation.qubits),
            }
        )
    result_payload = result.as_dict()
    result_payload["certificate"] = None
    trace.append(
        {
            "kind": "output",
            "backend": result.backend,
            "truth_class": result.truth_class.value,
            "output_digest": _digest("output", result_payload),
        }
    )
    field_name = _field_name(result)
    machine_type = _machine_type(result)
    unsigned = {
        "schema": COMPUTATION_CERTIFICATE_SCHEMA,
        "input": _digest(
            "input",
            {"program": program.to_dict(), "options": execution_options},
        ),
        "machine": _digest(
            "machine",
            {
                "backend": result.backend,
                "execution_class": result.execution_class.value,
                "truth_class": result.truth_class.value,
                "machine_type": machine_type,
                "field": field_name,
            },
        ),
        "trace": tuple(trace),
        "output": _digest("output", result_payload),
        "halted": True,
        "steps": len(program.operations),
        "attestation": _merkle_root(tuple(trace)),
        "replayable": replayable,
        "machine_type": machine_type,
        "field": field_name,
        "backend": result.backend,
        "execution_class": result.execution_class.value,
        "truth_class": result.truth_class.value,
    }
    certificate = VQCComputationCertificate(
        **unsigned,
        certificate_digest=_digest("computation-certificate", unsigned),
    )
    certificate.verify_integrity()
    return certificate


def validate_certificate_inputs(
    program: Program,
    options: dict[str, Any] | None = None,
) -> None:
    """Prove program + options canonicalize *before* any backend executes.

    The public boundary is certificate-first: a caller must not be able to
    cause an execution — in particular an irreversible, provider-billable
    QPU submission — that could never be certified.  This computes the same
    ``input`` digest payload the certificate will embed, so a value that
    would fail certification fails here first, ahead of the side effect.
    """
    if not isinstance(program, Program):
        raise WitnessError("certificate inputs require a Program")
    try:
        program_payload = program.to_dict()
    except Exception as exc:
        raise WitnessError(
            f"program cannot be canonicalized for certification: {exc}"
        ) from exc
    _digest(
        "input",
        {"program": program_payload, "options": dict(options or {})},
    )


def verify_computation_certificate(
    program: Program,
    result: ExecutionResult,
    certificate: VQCComputationCertificate,
    *,
    options: dict[str, Any] | None = None,
) -> bool:
    certificate.verify_integrity()
    expected = issue_computation_certificate(program, result, options=options)
    if expected != certificate:
        raise WitnessError("computation certificate does not match program and result")
    return True


def verify_serialized_computation_certificate(
    program: Program,
    result_payload: Mapping[str, Any],
    certificate: VQCComputationCertificate,
    *,
    options: Mapping[str, Any] | None = None,
) -> bool:
    """Verify a custody-safe serialized result against its certificate.

    result_payload must be the certificate-canonical form of
    ExecutionResult.as_dict(). Tagged values are intentionally left tagged:
    feeding them through the certificate canonicalizer again is idempotent and
    reproduces the digest that was committed at execution time.
    """
    if not isinstance(result_payload, Mapping):
        raise WitnessError("serialized execution result must be a mapping")
    backend_payload = result_payload.get("payload", {})
    if not isinstance(backend_payload, Mapping):
        raise WitnessError("serialized backend payload must be a mapping")
    embedded = result_payload.get("certificate")
    if embedded is not None and not isinstance(embedded, Mapping):
        raise WitnessError("serialized certificate must be a mapping")

    try:
        result = ExecutionResult(
            backend=str(result_payload["backend"]),
            execution_class=ExecutionClass(str(result_payload["execution_class"])),
            truth_class=TruthClass(str(result_payload["truth_class"])),
            n_qubits=int(result_payload["n_qubits"]),
            program_digest=str(result_payload["program_digest"]),
            materialised=bool(result_payload["materialised"]),
            payload=dict(backend_payload),
            refusals=tuple(
                str(item) for item in result_payload.get("refusals", ())
            ),
            measured_qpu=bool(result_payload.get("measured_qpu", False)),
            certificate=dict(embedded) if isinstance(embedded, Mapping) else None,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise WitnessError(
            f"serialized execution result is malformed: {exc}"
        ) from exc

    return verify_computation_certificate(
        program,
        result,
        certificate,
        options=dict(options or {}),
    )


def replay_computation_certificate(
    program: Program,
    certificate: VQCComputationCertificate,
    executor: Any,
    *,
    options: dict[str, Any] | None = None,
) -> ExecutionResult:
    """Re-execute with the bound backend and require an identical certificate."""
    certificate.verify_integrity()
    if not certificate.replayable:
        raise WitnessError("certificate is not replayable; stochastic execution lacked a seed")
    execution_options = dict(options or {})
    result = executor(program, prefer=certificate.backend, **execution_options)
    if result.certificate is None:
        replayed = issue_computation_certificate(
            program,
            result,
            options=execution_options,
        )
    else:
        replayed = VQCComputationCertificate.from_dict(result.certificate)
    if replayed != certificate:
        raise WitnessError("certificate replay diverged")
    return result
