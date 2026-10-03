"""Fail-closed boundary to real quantum hardware.

This module exists to make one thing impossible: reporting ``measured_qpu``
when no physical device ran the circuit.

The consolidated package is an exact *classical* substrate.  It can be
mathematically exact and still have run nothing on a QPU, and those two facts
must never be conflated in a claim.  So this backend:

* refuses to execute at all unless a provider adapter is both registered and
  configured;
* returns no fabricated, cached or simulated result in place of a job;
* exposes :func:`assert_measured_qpu` — the *only* sanctioned way to set the
  ``measured_qpu`` flag, and it requires a completed provider job record
  carrying a provider job id, a completion timestamp, and a result digest.

Absent a provider, every entry point here raises.  That is the intended
behaviour, not a missing feature.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .base import Admission, Capability, ExecutionClass, ExecutionResult, Program, TruthClass

__all__ = [
    "QPUUnavailableError",
    "QPUClaimError",
    "QPUJob",
    "QPUProvider",
    "QPUBackend",
    "register_provider",
    "available_providers",
    "assert_measured_qpu",
    "reset_providers",
]


class QPUUnavailableError(RuntimeError):
    """Refusal: no physical, provider-backed quantum device is reachable."""


class QPUClaimError(RuntimeError):
    """Refusal: a ``measured_qpu`` claim was not backed by a completed job."""


@dataclass(frozen=True)
class QPUJob:
    """Evidence that a real provider job completed.

    All three fields are mandatory.  A result with no provider job id, no
    completion timestamp, or no digest is not evidence of anything.
    """

    provider: str
    job_id: str
    completed_at: str
    result_digest: str

    def __post_init__(self) -> None:
        for field_name in ("provider", "job_id", "completed_at", "result_digest"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise QPUClaimError(
                    f"a QPU job record requires a non-empty {field_name!r}; "
                    "a simulated or assumed run is not a measured run"
                )


@dataclass(frozen=True)
class QPUProvider:
    """A registered provider adapter.

    ``submit`` must perform a real remote submission and return a
    :class:`QPUJob`.  An adapter that fabricates a job is a correctness bug in
    the adapter, and the boundary cannot detect it — which is exactly why the
    adapter is explicit, named, and off by default.
    """

    name: str
    submit: Callable[[Program, dict[str, Any]], QPUJob] | None
    configured: bool
    detail: str = ""


_REGISTRY: dict[str, QPUProvider] = {}


def register_provider(provider: QPUProvider) -> None:
    if not provider.name:
        raise ValueError("provider requires a name")
    _REGISTRY[provider.name] = provider


def available_providers() -> dict[str, QPUProvider]:
    return dict(_REGISTRY)


def reset_providers() -> None:
    _REGISTRY.clear()


class QPUBackend:
    """The hardware backend.  Refuses unless a provider is registered and configured."""

    name = "qpu"

    def capability(self) -> Capability:
        return Capability(
            name=self.name,
            execution_class=ExecutionClass.HARDWARE,
            materialises_state=True,
            gate_set="provider-native",
            state_classes=("physical",),
            max_qubits=None,
            requires=("provider_adapter", "credentials", "network"),
            notes=(
                "Physical quantum device. No provider is bundled with this "
                "package: until a provider adapter is registered and "
                "configured, this backend refuses every program and reports "
                "measured_qpu = False."
            ),
        )

    def available(self) -> tuple[bool, str]:
        ready = [p for p in _REGISTRY.values() if p.configured and p.submit is not None]
        if ready:
            return True, f"configured provider(s): {', '.join(sorted(p.name for p in ready))}"
        if _REGISTRY:
            names = ", ".join(sorted(_REGISTRY))
            return False, f"provider(s) registered but not configured: {names}"
        return False, (
            "no QPU provider adapter is registered — this package ships none, "
            "and will not simulate one"
        )

    def admit(self, program: Program) -> Admission:
        ok, reason = self.available()
        if not ok:
            return Admission(False, self.name, reason, ExecutionClass.HARDWARE)
        return Admission(
            True,
            self.name,
            "a configured provider adapter is registered; submission is attempted on execute",
            ExecutionClass.HARDWARE,
        )

    def execute(self, program: Program, **options: Any) -> ExecutionResult:
        """Submit to a real provider, or refuse.  Never returns a simulated result."""
        ok, reason = self.available()
        if not ok:
            raise QPUUnavailableError(
                f"refused: {reason}. The VQC's exact backends are classical "
                "simulations and cannot substitute for a hardware run; use one "
                "of them explicitly if a simulated result is what you want."
            )
        provider = next(
            (p for p in sorted(_REGISTRY.values(), key=lambda p: p.name) if p.configured and p.submit)
        )
        assert provider.submit is not None  # guarded by available()
        job = provider.submit(program, dict(options))
        return ExecutionResult(
            backend=f"qpu:{provider.name}",
            execution_class=ExecutionClass.HARDWARE,
            truth_class=TruthClass.EXACT,
            n_qubits=program.n_qubits,
            program_digest=program.digest(),
            materialised=True,
            payload={
                "provider": job.provider,
                "job_id": job.job_id,
                "completed_at": job.completed_at,
                "result_digest": job.result_digest,
            },
            measured_qpu=True,
        )


def assert_measured_qpu(result: ExecutionResult, job: QPUJob | None) -> bool:
    """The only sanctioned path to a ``measured_qpu`` claim.

    Returns True when the result is genuinely hardware-backed, and raises
    otherwise.  A caller holding an exact classical result cannot reach a
    hardware claim through this function.
    """
    if job is None:
        raise QPUClaimError(
            "refused: measured_qpu requires a completed QPUJob record; an exact "
            "classical result is not a measured quantum result"
        )
    if result.execution_class is not ExecutionClass.HARDWARE:
        raise QPUClaimError(
            f"refused: backend {result.backend!r} is {result.execution_class.value}, "
            "not hardware"
        )
    if not result.measured_qpu:
        raise QPUClaimError("refused: the result is not flagged as a measured QPU run")
    if result.payload.get("job_id") != job.job_id:
        raise QPUClaimError("refused: the job record does not match the result's job id")
    if result.payload.get("result_digest") != job.result_digest:
        raise QPUClaimError("refused: the job record does not match the result digest")
    return True
