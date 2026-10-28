"""Packageable source of the EUCLID emergence predicate."""

from __future__ import annotations

from typing import Any


def compute_emergence_criterion(
    spectral_gap: float,
    betti_1: float,
    phi_resonance: float,
) -> tuple[bool, dict[str, Any]]:
    """Evaluate the three declared emergence conditions and return diagnostics."""
    cond_delta = spectral_gap > 0
    cond_betti = betti_1 >= 1
    cond_phi = phi_resonance > 0.5
    emerged = cond_delta and cond_betti and cond_phi
    return emerged, {
        "spectral_gap": spectral_gap,
        "betti_1": betti_1,
        "phi_resonance": phi_resonance,
        "delta_ok": cond_delta,
        "betti_ok": cond_betti,
        "phi_ok": cond_phi,
        "emerged": emerged,
    }
