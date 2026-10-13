"""
03_structure — folding and measurement. Not mining.

Folding: Hilbert-space data → structured representation.
Quantum operator: structured state → candidate distribution.
These two layers must never be reported as each other.
"""
from __future__ import annotations

import math
from typing import Dict, Sequence

import numpy as np

import sys
from pathlib import Path

SYS_MATH = Path(__file__).resolve().parents[1] / "01_mathematics"
if str(SYS_MATH) not in sys.path:
    sys.path.insert(0, _repo_root)

from golden_transform import PHI, PSI, SQRT5, apply_Mn, coherence, project


def normalize_prob(p: np.ndarray) -> np.ndarray:
    p = np.asarray(p, dtype=float).reshape(-1)
    p = np.clip(p, 0.0, None)
    s = p.sum()
    if s <= 0:
        return np.ones_like(p) / max(p.size, 1)
    return p / s


def n_effective(p: np.ndarray) -> float:
    """N_eff = 1 / Σ p_i²  (participation ratio)."""
    p = normalize_prob(p)
    return float(1.0 / max(np.sum(p ** 2), 1e-30))


def shannon_entropy(p: np.ndarray) -> float:
    p = normalize_prob(p)
    p = p[p > 1e-15]
    return float(-np.sum(p * np.log(p)))


def max_prob(p: np.ndarray) -> float:
    return float(np.max(normalize_prob(p)))


def phi_overlap_pairs(p: np.ndarray) -> float:
    """Mean |a| / (|a|+|b|) over consecutive pairs — Φ-mass fraction."""
    p = normalize_prob(p)
    if p.size < 2:
        return 0.0
    fracs = []
    for i in range(0, p.size - 1, 2):
        a, b = project(p[i], p[i + 1])
        den = abs(a) + abs(b)
        fracs.append(abs(a) / den if den > 0 else 0.0)
    return float(np.mean(fracs)) if fracs else 0.0


def fold_pairs_Mn(data: Sequence[float], n: int) -> np.ndarray:
    """Hilbert folding: apply M^n to consecutive pairs, then renormalize."""
    x = np.asarray(data, dtype=float).reshape(-1)
    if x.size % 2:
        x = np.append(x, 0.0)
    out = np.zeros_like(x)
    for i in range(0, x.size, 2):
        u, v = apply_Mn(float(x[i]), float(x[i + 1]), n)
        out[i], out[i + 1] = u, v
    return out


def fold_to_distribution(data: Sequence[float], n: int) -> np.ndarray:
    folded = fold_pairs_Mn(data, n)
    return normalize_prob(np.abs(folded))


def unfold_pairs_Mn(data: Sequence[float], n: int) -> np.ndarray:
    """Inverse fold: M^{-n} on pairs. Exact because det(M^n)=(-1)^n."""
    return fold_pairs_Mn(data, -int(n))


def phi_channel_project(data: Sequence[float], n: int, psi_floor: float = 0.0) -> Dict:
    """
    Quantum-mathematical fold in the Φ/ψ eigenbasis of M.

    M^n is invertible (Cassini: det = (−1)^n). Applying it to paired amplitudes
    is a change of eigenbasis, not a classical codec.

    Full channel: keep (a Φ^n, b ψ^n) — reversible eigenbasis fold.
    Φ-channel: discard ψ-mass below psi_floor. Projection onto the growing ray.
    """
    x = np.asarray(data, dtype=float).reshape(-1)
    if x.size % 2:
        x = np.append(x, 0.0)
    n_pairs = x.size // 2
    bytes_in = int(x.nbytes)
    a_keep = np.zeros(n_pairs, dtype=float)
    b_keep = np.zeros(n_pairs, dtype=float)
    for i in range(n_pairs):
        a, b = project(float(x[2 * i]), float(x[2 * i + 1]))
        a_keep[i] = a
        b_keep[i] = b
    # After M^n in eigenbasis: (a Φ^n, b ψ^n)
    a_n = a_keep * (PHI ** n)
    b_n = b_keep * (PSI ** n)
    # Lossy: discard ψ channel
    kept_psi = np.abs(b_n) > psi_floor if psi_floor > 0 else np.zeros(n_pairs, dtype=bool)
    b_hat = np.where(kept_psi, b_n, 0.0)
    recon = np.zeros_like(x)
    for i in range(n_pairs):
        # invert M^n: divide by eigenvalues, then reconstruct
        a0 = a_n[i] / (PHI ** n)
        b0 = b_hat[i] / (PSI ** n) if abs(PSI ** n) > 1e-30 and kept_psi[i] else 0.0
        rx, ry = a0 * PHI + b0 * PSI, a0 + b0
        recon[2 * i], recon[2 * i + 1] = rx, ry
    bytes_lossy = int(a_n.nbytes + (b_n[kept_psi].nbytes if psi_floor > 0 else 0))
    err = float(np.linalg.norm(x - recon) / max(np.linalg.norm(x), 1e-15))
    return {
        "n": n,
        "pairs": n_pairs,
        "bytes_in": bytes_in,
        "bytes_lossless": bytes_in,
        "bytes_lossy": bytes_lossy,
        "compression_ratio": float(bytes_in / max(bytes_lossy, 1)),
        "psi_mass_dropped": float(np.sum(np.abs(b_n)[~kept_psi]) / max(np.sum(np.abs(a_n)) + np.sum(np.abs(b_n)), 1e-15)),
        "reconstruction_rel_error": err,
        "phi_mass_fraction": float(np.sum(np.abs(a_n)) / max(np.sum(np.abs(a_n)) + np.sum(np.abs(b_n)), 1e-15)),
        "reconstructed": recon,
        "lossless_roundtrip_error": float(
            np.linalg.norm(x - unfold_pairs_Mn(fold_pairs_Mn(x, n), n)) / max(np.linalg.norm(x), 1e-15)
        ),
    }


def metrics(p: np.ndarray, marked: Sequence[int] = ()) -> Dict[str, float]:
    p = normalize_prob(p)
    marked_p = float(sum(p[i] for i in marked if 0 <= i < p.size))
    return {
        "input_dimension": float(p.size),
        "effective_dimension": n_effective(p),
        "entropy": shannon_entropy(p),
        "max_probability": max_prob(p),
        "marked_probability": marked_p,
        "phi_overlap": phi_overlap_pairs(p),
        "mean_pair_coherence": float(
            np.mean([coherence(p[i], p[i + 1]) for i in range(0, p.size - 1, 2)])
            if p.size >= 2
            else 0.0
        ),
    }
