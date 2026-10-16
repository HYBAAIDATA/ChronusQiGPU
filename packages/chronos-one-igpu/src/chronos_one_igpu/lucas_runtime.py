"""Backend-neutral Lucas execution runtime.

The reference backend is exact Python integer arithmetic. Hardware backends
must implement the same evaluate(indices) contract and preserve record.verify().
No GPU is claimed unless a backend is actually present and benchmarked.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol, Sequence

from .lucas_engine import InvariantViolation, LucasRecord, make_record


@dataclass(frozen=True)
class BackendCapabilities:
    name: str
    exact_integer_arithmetic: bool
    hardware_accelerated: bool
    supports_batching: bool
    measured: bool


class LucasBackend(Protocol):
    capabilities: BackendCapabilities

    def evaluate(self, indices: Sequence[int]) -> list[LucasRecord]:
        """Evaluate and return verified Lucas records in input order."""


class ReferenceLucasBackend:
    capabilities = BackendCapabilities(
        name="python-exact-reference",
        exact_integer_arithmetic=True,
        hardware_accelerated=False,
        supports_batching=True,
        measured=True,
    )

    def evaluate(self, indices: Sequence[int]) -> list[LucasRecord]:
        records = [make_record(index) for index in indices]
        for record in records:
            record.verify()
        return records


class UnavailableBackend:
    """Explicit placeholder for a backend that is not installed or detected."""

    def __init__(self, name: str):
        self.capabilities = BackendCapabilities(name, False, True, True, False)

    def evaluate(self, indices: Sequence[int]) -> list[LucasRecord]:
        raise RuntimeError(
            f"{self.capabilities.name} backend is unavailable; refusing to fake GPU execution"
        )


class LucasRuntime:
    """Execute the exact Lucas contract through a replaceable backend."""

    def __init__(self, backend: LucasBackend | None = None):
        self.backend = backend or ReferenceLucasBackend()

    @property
    def capabilities(self) -> BackendCapabilities:
        return self.backend.capabilities

    def evaluate(self, indices: Iterable[int]) -> list[LucasRecord]:
        requested = list(indices)
        records = self.backend.evaluate(requested)
        if len(records) != len(requested):
            raise InvariantViolation("backend returned the wrong record count")
        for requested_index, record in zip(requested, records):
            if record.index != requested_index:
                raise InvariantViolation("backend changed record ordering")
            record.verify()
        return records
