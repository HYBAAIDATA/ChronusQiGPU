"""Deterministic, complete nonce-ordering substrate for PYTHIA.

This module provides a permutation of a requested integer window. It does not
prune candidates, predict SHA256d outputs, change Bitcoin's proof predicate, or
claim a physical hashrate improvement. The returned order is a deterministic
search permutation only.
"""
from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Any


class TuringScheduleError(ValueError):
    """The requested or supplied schedule violates the complete-window contract."""


def _validate_window(window: int) -> int:
    if isinstance(window, bool) or not isinstance(window, int):
        raise TuringScheduleError("window must be an integer")
    if window < 0:
        raise TuringScheduleError("window must be non-negative")
    return window


def _validate_seed(seed: int) -> int:
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise TuringScheduleError("seed must be an integer")
    return seed


def _validate_cap(cap: int | None, window: int) -> int:
    if cap is None:
        return window
    if isinstance(cap, bool) or not isinstance(cap, int):
        raise TuringScheduleError("cap must be an integer or None")
    if not 0 <= cap <= window:
        raise TuringScheduleError("cap must be within the requested window")
    return cap


def iter_nonce_schedule(window: int, *, seed: int = 0, cap: int | None = None) -> Iterator[int]:
    """Yield a deterministic prefix of a complete permutation of ``[0, window)``.

    The schedule is a rotated ascending or descending traversal. Both direction
    choices are bijections modulo ``window``; therefore every full schedule is
    complete, duplicate-free, and in range. A prefix is never presented as a
    complete schedule by this function's metadata-free API, so callers that
    require coverage must request ``cap=window`` or call ``validate_schedule``.
    """
    window = _validate_window(window)
    seed = _validate_seed(seed)
    cap = _validate_cap(cap, window)
    if window == 0:
        return
    offset = seed % window
    direction = -1 if seed & 1 else 1
    for index in range(cap):
        yield (offset + direction * index) % window


def extended_nonce_schedule(window: int, *, seed: int = 0, cap: int | None = None) -> tuple[int, ...]:
    """Return a deterministic schedule prefix as an immutable tuple."""
    return tuple(iter_nonce_schedule(window, seed=seed, cap=cap))


def validate_schedule(schedule: Iterable[Any], window: int, *, require_complete: bool = True) -> tuple[int, ...]:
    """Validate nonce coverage, uniqueness, and bounds.

    ``require_complete=True`` rejects missing entries. Every element must be an
    integer in range; values that would have wrapped modulo the window are
    rejected rather than silently repaired.
    """
    window = _validate_window(window)
    values = tuple(schedule)
    if require_complete and len(values) != window:
        raise TuringScheduleError(
            f"complete schedule requires {window} entries, got {len(values)}"
        )
    if not require_complete and len(values) > window:
        raise TuringScheduleError("schedule prefix is longer than its window")
    for value in values:
        if isinstance(value, bool) or not isinstance(value, int):
            raise TuringScheduleError("schedule values must be integers")
        if not 0 <= value < window:
            raise TuringScheduleError(f"schedule value {value} is outside [0, {window})")
    if len(set(values)) != len(values):
        raise TuringScheduleError("schedule contains duplicate nonces")
    if require_complete and set(values) != set(range(window)):
        raise TuringScheduleError("schedule is missing one or more nonces")
    return values


def complete_nonce_schedule(window: int, *, seed: int = 0) -> tuple[int, ...]:
    """Return and validate the complete deterministic nonce permutation."""
    schedule = extended_nonce_schedule(window, seed=seed, cap=window)
    return validate_schedule(schedule, window, require_complete=True)
