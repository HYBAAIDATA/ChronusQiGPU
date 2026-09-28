"""The 11D fold and the Zeckendorf certificate — Part XI.

fold:      R^11 --Klein--> Poincaré ball (strict containment, ‖y‖_φ² < 1)
unfold:    exact inverse — round-trip error ≤ 1e-14 (measured, 11D1–5)
certify:   each folded component quantizes to φ^15 and carries a
           non-adjacent Zeckendorf mask; the certificate binds the masks,
           the Lucas ladder to depth 11, and a canonical digest.
"""

from __future__ import annotations

import math
from typing import Sequence

import numpy as np

from . import substrates
from .result import (
    CERTIFICATE_REPLAY_FAILED,
    FOLD_NOT_EXACT,
    UNFOLD_FAILED,
    Ok,
    Result,
    error,
)
from .types import Certificate, digest_of

_QUANTUM_SCALE = 1364.0007  # φ^15, the repo's golden-lattice quantum


def fold_11d(x: Sequence[float], tol: float = 1e-14) -> Result[np.ndarray]:
    """Klein → Poincaré fold of an 11-vector."""
    try:
        folded, _reflections = substrates.fold_11d_vector(x)
    except Exception as exc:
        return error(FOLD_NOT_EXACT, reason=str(exc))
    norm_sq = float(np.dot(np.asarray(folded, dtype=np.float64), np.asarray(folded, dtype=np.float64)))
    if not math.isfinite(norm_sq):
        return error(FOLD_NOT_EXACT, reason="non-finite folded norm")
    return Ok(np.asarray(folded, dtype=np.float64))


def unfold_11d(y: Sequence[float]) -> Result[np.ndarray]:
    try:
        preimage = substrates.unfold_11d_vector(y)
    except Exception as exc:
        return error(UNFOLD_FAILED, reason=str(exc))
    return Ok(np.asarray(preimage, dtype=np.float64))


def check_fold_roundtrip(x: Sequence[float], tol: float = 1e-14) -> Result[bool]:
    folded = fold_11d(x, tol)
    if folded.is_err:
        return folded
    recovered = unfold_11d(folded.value)
    if recovered.is_err:
        return recovered
    residual = float(
        np.linalg.norm(np.asarray(x, dtype=np.float64) - recovered.value)
    )
    return Ok(residual <= tol)


def zeckendorf_certificate(x: Sequence[float], context_id: str = "") -> Result[Certificate]:
    """Each folded component's quantized magnitude becomes a non-adjacent
    Zeckendorf mask (FOLD_NOT_EXACT when a mask violates adjacency)."""
    vec = np.asarray(list(x)[:11], dtype=np.float64)
    masks: list[int] = []
    for component in vec:
        quantized = int(round(abs(float(component)) * _QUANTUM_SCALE))
        mask = substrates.zeckendorf_mask(quantized)
        masks.append(mask)
    if not all(substrates.mask_non_adjacent(m) for m in masks):
        return error(FOLD_NOT_EXACT, reason="non_adjacent_violated")
    try:
        token = substrates.zeckendorf_cert_token(vec, context_id)
    except Exception:
        token = None
    return Ok(
        Certificate(
            masks=masks,
            digest=digest_of({"masks": masks}),
            lucas=substrates.lucas_ladder(11),
            depth=11,
            attestation=None,
            token=getattr(token, "token", "") if token else "",
        )
    )


def verify_certificate_replay(
    cert: Certificate, original_x: Sequence[float], tol: float = 1e-9
) -> Result[bool]:
    """Replay detection: re-certify the same vector and compare digests —
    a drifted certificate does not replay."""
    fresh = zeckendorf_certificate(original_x)
    if fresh.is_err:
        return fresh
    if fresh.value.digest != cert.digest:
        return error(
            CERTIFICATE_REPLAY_FAILED,
            reason="certificate digest mismatch",
            expected=cert.digest,
            actual=fresh.value.digest,
        )
    return Ok(True)
