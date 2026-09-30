"""Boundary error conversion. Closes S1.

The seam surface is exception-free. The substrate below may raise.
The seam catches and returns Result[T]. The error taxonomy is closed.
"""

from __future__ import annotations

import logging
import traceback
from typing import Any, Callable, TypeVar

from . import store
from .types import Err, Ok, Result, SeamError

T = TypeVar("T")
_LOG = logging.getLogger("chronus.seam.contract")


def _map_exception(exc: BaseException) -> SeamError:
    name = type(exc).__name__
    text = str(exc).lower()
    table = {
        "BufferCorruption": SeamError.buffer_corruption,
        "KernelUnavailable": SeamError.kernel_unavailable,
        "AttestationFailure": SeamError.attestation_failure,
        "RateLimit": SeamError.rate_limited,
        "Deadline": SeamError.deadline_exceeded,
        "DeviceUnsupportedError": SeamError.capability_mismatch,
        "AttestationViolation": SeamError.attestation_failure,
    }
    if name in table:
        return table[name]
    if "buffer" in text and "corrupt" in text:
        return SeamError.buffer_corruption
    if "rate" in text and "limit" in text:
        return SeamError.rate_limited
    if "deadline" in text or "timeout" in text:
        return SeamError.deadline_exceeded
    return SeamError.unknown


def seam_guard(fn: Callable[..., T], *args: Any, **kwargs: Any) -> Result[T]:
    try:
        out = fn(*args, **kwargs)
        if isinstance(out, (Ok, Err)):
            return out
        return Ok(out)
    except Exception as exc:
        code = _map_exception(exc)
        detail = f"{type(exc).__name__}: {exc}"
        store.audit(
            "seam_unknown" if code is SeamError.unknown else "seam_error",
            detail=detail,
        )
        if code is SeamError.unknown:
            _LOG.error(
                "unknown Chronus seam exception: %s\n%s",
                detail,
                traceback.format_exc(),
            )
        return Err(code, detail)


def guarded(fn: Callable[..., T]) -> Callable[..., Result[T]]:
    def wrapped(*args: Any, **kwargs: Any) -> Result[T]:
        return seam_guard(fn, *args, **kwargs)

    wrapped.__name__ = getattr(fn, "__name__", "guarded")
    wrapped.__doc__ = getattr(fn, "__doc__", None)
    return wrapped
