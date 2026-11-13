# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
# Chronus is a HYBA Data product.
"""Backend detection and selection, driven by the operator's option.

Every run detects the backends this machine offers (probe, then the
known-answer self-test) and selects one from an explicit option:

* ``--backend auto|igpu|metal|opencl|cuda|simd|reference``
* ``--prefer ours|host`` (default ``ours``)

``igpu`` is the Chronus iGPU: HYBA's software-defined GPU on the resident
lattice (Mode A). It is a first-class GPU route in its own right. ``metal``,
``opencl`` and ``cuda`` are the host's own GPU (Mode B). ``simd`` and
``reference`` name single Chronus engines directly, for diagnosis.

* ``auto`` with ``prefer=ours`` selects the Chronus iGPU even when the host
  has a GPU of its own.
* ``auto`` with ``prefer=host`` selects the host GPU when one is present and
  passes its self-test; otherwise the Chronus iGPU, and ``fallback_reason``
  says why the host GPU was not used.
* A named backend runs exactly there or fails closed.

Every selection records ``requested_backend``, ``detected_backends``,
``preference``, ``executed_backend`` and ``fallback_reason``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from chronus.fleet.errors import DeviceUnavailableError

BACKEND_AUTO = "auto"
BACKEND_IGPU = "igpu"
BACKEND_METAL = "metal"
BACKEND_OPENCL = "opencl"
BACKEND_CUDA = "cuda"
BACKEND_SIMD = "simd"
BACKEND_REFERENCE = "reference"
#: Internal Chronus engine (libchronus_igpu); selectable as a route, not a --backend choice.
BACKEND_CPP_SIMD = "cpp-simd"

BACKENDS = (BACKEND_IGPU, BACKEND_METAL, BACKEND_OPENCL, BACKEND_CUDA, BACKEND_SIMD, BACKEND_REFERENCE)
BACKEND_CHOICES = (BACKEND_AUTO,) + BACKENDS
HOST_GPU_BACKENDS = (BACKEND_METAL, BACKEND_CUDA, BACKEND_OPENCL)
OUR_BACKENDS = (BACKEND_IGPU, BACKEND_CPP_SIMD, BACKEND_SIMD, BACKEND_REFERENCE)
KNOWN_BACKENDS = OUR_BACKENDS + HOST_GPU_BACKENDS

PREFER_OURS = "ours"
PREFER_HOST = "host"
PREFERENCES = (PREFER_OURS, PREFER_HOST)
DEFAULT_PREFERENCE = PREFER_OURS

#: The order ``auto`` walks for each preference. The option drives the choice;
#: measured throughput never reorders it.
PREFERENCE_ORDER = {
    PREFER_OURS: OUR_BACKENDS + HOST_GPU_BACKENDS,
    PREFER_HOST: HOST_GPU_BACKENDS + OUR_BACKENDS,
}

BACKEND_LABELS = {
    BACKEND_IGPU: "Chronus iGPU (software-defined GPU, resident lattice)",
    BACKEND_CPP_SIMD: "Chronus engine: native libchronus_igpu",
    BACKEND_SIMD: "Chronus engine: NumPy SIMD",
    BACKEND_REFERENCE: "Chronus engine: exact reference",
    BACKEND_METAL: "host GPU: Apple Metal",
    BACKEND_OPENCL: "host GPU: OpenCL",
    BACKEND_CUDA: "host GPU: CUDA",
}


def check_backend(backend: str) -> str:
    if backend not in BACKEND_CHOICES and backend != BACKEND_CPP_SIMD:
        raise DeviceUnavailableError(f"unknown backend {backend!r}; choose one of {', '.join(BACKEND_CHOICES)}")
    return backend


def check_preference(prefer: str | None) -> str:
    prefer = prefer or DEFAULT_PREFERENCE
    if prefer not in PREFERENCES:
        raise DeviceUnavailableError(f"unknown preference {prefer!r}; choose ours or host")
    return prefer


@dataclass(frozen=True)
class BackendSelection:
    """What was asked for, what this machine offers and what was selected."""

    requested_backend: str
    preference: str
    detected_backends: tuple[str, ...]
    executed_backend: str | None
    fallback_reason: str | None
    statuses: Mapping[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.executed_backend is not None

    def require(self) -> "BackendSelection":
        if not self.ok:
            raise DeviceUnavailableError(f"backend {self.requested_backend} unavailable: {self.fallback_reason}")
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "requested_backend": self.requested_backend,
            "preference": self.preference,
            "detected_backends": list(self.detected_backends),
            "executed_backend": self.executed_backend,
            "fallback_reason": self.fallback_reason,
            "statuses": dict(sorted(self.statuses.items())),
        }


def detected(statuses: Mapping[str, str | None]) -> tuple[str, ...]:
    """Backends that are present and passed their self-test, in canonical order."""
    return tuple(b for b in KNOWN_BACKENDS if b in statuses and statuses[b] is None)


def select_backend(
    statuses: Mapping[str, str | None], backend: str = BACKEND_AUTO, prefer: str | None = DEFAULT_PREFERENCE
) -> BackendSelection:
    """Select one backend. ``statuses`` maps a backend to None when it is verified, else why it is not."""
    backend = check_backend(backend)
    prefer = check_preference(prefer)
    found = detected(statuses)
    shown = {b: ("verified" if s is None else s) for b, s in statuses.items()}
    if backend != BACKEND_AUTO:
        if backend in found:
            return BackendSelection(backend, prefer, found, backend, None, shown)
        why = statuses.get(backend) or "not enabled or not detected on this machine"
        return BackendSelection(backend, prefer, found, None, f"{backend}: {why}; failing closed", shown)
    passed_over = []
    for candidate in PREFERENCE_ORDER[prefer]:
        if candidate in found:
            reason = None
            if passed_over and candidate not in (PREFERENCE_ORDER[prefer][0],):
                reason = f"prefer={prefer}: " + "; ".join(passed_over) + f"; selected {candidate}"
            return BackendSelection(backend, prefer, found, candidate, reason, shown)
        if candidate in statuses:
            passed_over.append(f"{candidate} {statuses[candidate]}")
        elif prefer == PREFER_HOST and candidate in HOST_GPU_BACKENDS:
            passed_over.append(f"{candidate} not detected")
    return BackendSelection(backend, prefer, found, None, "no backend passed its self-test on this machine", shown)
