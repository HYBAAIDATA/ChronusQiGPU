"""Normalized Fourier transforms of bounded explicit one-dimensional vectors."""

import numpy as np

MAX_LENGTH = 4096


def qft(values, inverse=False):
    """Return a normalized positive-sign DFT, or its inverse.

    Input must be a finite nonempty 1-D vector with power-of-two length at
    most MAX_LENGTH. Both input and output are explicit complex128 arrays.
    """
    if not isinstance(inverse, bool):
        raise ValueError("inverse must be a bool")
    try:
        vector = np.asarray(values, dtype=np.complex128)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError("values must be a finite numerical vector") from exc
    if vector.ndim != 1:
        raise ValueError("values must be one-dimensional")
    n = vector.size
    if n == 0 or n > MAX_LENGTH or n & (n - 1):
        raise ValueError("length must be a power of two between 1 and 4096")
    if not np.isfinite(vector).all():
        raise ValueError("values must be finite")
    result = np.fft.fft(vector, norm="ortho") if inverse else np.fft.ifft(vector, norm="ortho")
    if not np.isfinite(result).all():
        raise ValueError("transform overflowed")
    return result
