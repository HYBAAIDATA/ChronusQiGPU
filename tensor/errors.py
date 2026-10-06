"""Fail-closed error hierarchy for the ``tensor`` package.

Every error below is raised instead of silently degrading behaviour: an
invalid request, an exhausted budget, an unavailable backend, or a broken
exactness guarantee must stop execution rather than return a plausible but
wrong result.
"""

from __future__ import annotations


class TensorError(Exception):
    """Base class for all errors raised by the ``tensor`` package."""


class TensorValidationError(TensorError, ValueError):
    """A request, shape, dtype, or contract field failed validation."""


class TensorMemoryError(TensorError, MemoryError):
    """The declared or measured memory requirement exceeds its budget."""


class TensorTimeoutError(TensorError, TimeoutError):
    """An operation did not complete within its declared timeout."""


class TensorCancelledError(TensorError):
    """An operation was cancelled before completion."""


class TensorBackendUnavailableError(TensorError):
    """A required backend is not available on this host.

    Raised instead of silently substituting another backend. Automatic
    routing may catch this and fall back only when policy explicitly
    allows it (see :mod:`tensor.router`), and must record that it did so.
    """


class TensorExactnessError(TensorError):
    """An exact operation would lose information without explicit opt-in."""


class TensorVerificationError(TensorError):
    """Independent re-verification diverged from the executed result.

    Raised instead of publishing a wrong-but-well-formed output: the
    divergent result never enters custody and no receipt is issued.
    """


__all__ = [
    "TensorError",
    "TensorValidationError",
    "TensorMemoryError",
    "TensorTimeoutError",
    "TensorCancelledError",
    "TensorBackendUnavailableError",
    "TensorExactnessError",
    "TensorVerificationError",
]
