"""D4 — the fold -> Zeckendorf certificate as an honest quantized map.

The consortium demand: prove the 11D fold is *bijective* and *metric-
preserving* into a discrete Fibonacci lattice — or admit the
distortion. The mathematics is honest once stated plainly:

* The fold itself — Klein map ``x -> x / sqrt(1 + ||x||_phi^2)`` into the
  Poincare ball — **is** a diffeomorphism ``R^11 -> B^11``: bijective and
  smooth, with a measured float64 round-trip error (``check_fold_
  roundtrip``, ~1e-14). It is emphatically **not an isometry**: its
  Jacobian condition number at ``x`` grows with ``||x||`` — the map
  radially compresses (``||f(x)||_phi^2 = ||x||_phi^2/(1+||x||_phi^2)``),
  so hyperbolic distances are never preserved. ``fold_condition_number``
  measures that distortion directly.

* The certificate step — ``q_i = round(|folded_i| * phi^15)`` then
  Zeckendorf-encode — is **many-to-one and non-invertible**: every
  component in a bin of width ``1/phi^15`` maps to the same integer.
  ``component_error_bound`` is the per-component quantization bound
  ``1/(2*phi^15)``; ``preimage_width`` is the full bin width. No
  injectivity, isometry, or error-freedom claim survives contact with
  this function, and none is made.

* The certificate is a **commitment, not an encoding**: it binds a
  quantized lattice point to a digest/context for replay detection
  (``l_hras.fold.verify_certificate_replay``); it does not claim the
  continuous state can be reconstructed.

Everything returned here is measured or declared — including the
fields ``is_bijective: false`` and ``is_isometry: false``.
"""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np

from .. import substrates

_COMPONENTS = 11


def quantum_scale() -> float:
    """The certificate's quantization scale: phi^15 (Lucas-15 ~ 1364)."""
    return substrates.golden() ** 15


def quantize_component(value: float) -> int:
    """round(|value| * phi^15) — the certificate's per-component map."""
    return int(round(abs(float(value)) * quantum_scale()))


def component_error_bound() -> float:
    """Max |folded - folded_recovered| per component: 1/(2*phi^15)."""
    return 1.0 / (2.0 * quantum_scale())


def preimage_width() -> float:
    """Bin width of the per-component quantization: 1/phi^15.

    Any two components inside a bin of this width collide to the same
    integer — the certificate map is many-to-one by construction.
    """
    return 1.0 / quantum_scale()


def fold_roundtrip_error(x: Sequence[float], num_passes: int = 3) -> float:
    """Measured sup-norm round-trip error of the Klein fold at ``x``."""
    vec = np.asarray(x, dtype=np.float64).reshape(_COMPONENTS)
    folded, _ = substrates.fold_11d_vector(vec)
    unfolded = substrates.unfold_11d_vector(folded)
    return float(np.max(np.abs(unfolded - vec)))


def fold_jacobian(x: Sequence[float], h: float = 1e-6) -> np.ndarray:
    """Central-difference Jacobian of the fold at ``x`` (11x11)."""
    vec = np.asarray(x, dtype=np.float64).reshape(_COMPONENTS)
    jac = np.zeros((_COMPONENTS, _COMPONENTS))
    for j in range(_COMPONENTS):
        step = np.zeros(_COMPONENTS)
        step[j] = h
        fwd, _ = substrates.fold_11d_vector(vec + step)
        bwd, _ = substrates.fold_11d_vector(vec - step)
        jac[:, j] = (fwd - bwd) / (2.0 * h)
    return jac


def fold_condition_number(x: Sequence[float]) -> float:
    """kappa(J) = sigma_max / sigma_min of the fold Jacobian at ``x``.

    A genuine local metric-distortion measure: 1.0 would be locally
    isometric; the Klein map's radial compression makes it >> 1 for
    large ||x||. Measured, not asserted.
    """
    svals = np.linalg.svd(fold_jacobian(x), compute_uv=False)
    if svals[-1] == 0:
        return float("inf")
    return float(svals[0] / svals[-1])


def quantization_report(x: Sequence[float], context_id: str = "") -> dict[str, Any]:
    """The honest characterization of the fold->certificate pipeline."""
    vec = np.asarray(x, dtype=np.float64).reshape(_COMPONENTS)
    folded, passes = substrates.fold_11d_vector(vec)
    quantized = [quantize_component(c) for c in folded]
    masks = [substrates.zeckendorf_mask(q) for q in quantized]
    certificate = substrates.zeckendorf_cert_token(vec, context_id)
    return {
        "fold": {
            "map": "Klein map x -> x / sqrt(1 + ||x||_phi^2), B^11-valued",
            "bijective": True,
            "bijective_up_to": ("float64 round-trip; measured sup-norm error below"),
            "roundtrip_error_measured": fold_roundtrip_error(vec),
            "is_isometry": False,
            "jacobian_condition_number": fold_condition_number(vec),
            "metric_note": (
                "radial compression ||f(x)||_phi^2 = ||x||_phi^2/(1+||x||_phi^2); "
                "hyperbolic distances are never preserved"
            ),
            "passes": passes,
        },
        "quantize": {
            "scale": "phi^15",
            "scale_value": quantum_scale(),
            "component_error_bound": component_error_bound(),
            "preimage_width": preimage_width(),
            "is_bijective": False,
            "many_to_one": True,
        },
        "zeckendorf": {
            "quantized_components": quantized,
            "masks": masks,
            "all_masks_non_adjacent": all(substrates.mask_non_adjacent(m) for m in masks),
        },
        "certificate": {
            "token": certificate,
            "semantics": (
                "commitment to the quantized lattice point + context; "
                "replay-detectable, NOT a decodable encoding"
            ),
        },
        "verdict": (
            "the pipeline is a diffeomorphic fold followed by a declared "
            "many-to-one quantization; it does not preserve the hyperbolic "
            "metric and no isometric or error-free claim is made"
        ),
    }


__all__ = [
    "quantum_scale",
    "quantize_component",
    "component_error_bound",
    "preimage_width",
    "fold_roundtrip_error",
    "fold_jacobian",
    "fold_condition_number",
    "quantization_report",
]
