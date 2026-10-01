"""Kellogg golden renormalization (phi-RG) — Wall 14.

Standard block-spin renormalization decimates by a factor of 2 and discards
the odd samples; the golden renormalization decimates by ``phi`` using the
bit-exact lifting step, pushing the removed detail into a scale register
instead of erasing it.  On integer input the fold is lossless —
:func:`phi_reconstruct_deep` restores the micro-state exactly.

``generate_ising_chain`` samples the exact 1-D Ising Boltzmann measure:
in zero field the chain is a two-state Markov chain with domain-wall
probability ``(1 - tanh(beta*J)) / 2``.  A 1-D Ising model has no finite-T
critical point; "critical" here means the coupling is set so the
correlation length ``xi = -1/ln(tanh(beta*J))`` is comparable to the chain
length — the declared regime for the benchmark, not a thermodynamic claim.

``chrysalis_decode`` is the transcript's "decode in chaos" probe: bits are
embedded in the scale-register band of a correlated field, the field is
flooded with Gaussian noise, and recovery is measured as bit accuracy.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Sequence, Tuple

import numpy as np

from .dphi_transform import (
    _lift_level,
    _unlift_level,
)


class RenormalizationError(ValueError):
    """A renormalization contract was violated."""


def generate_ising_chain(
    n: int, beta_j: float, seed: int = 0
) -> np.ndarray:
    """Exact sample of the zero-field 1-D Ising measure at coupling beta*J.

    Domain walls appear with probability ``(1 - tanh(beta*J))/2``; spins are
    int8 +-1.  For "critical-like" chains pass
    ``beta_j = atanh(1 - 2/n)`` so ``xi ~ n/2``.
    """
    rng = np.random.default_rng(seed)
    stay = 0.5 * (1.0 + math.tanh(beta_j))
    spins = np.empty(int(n), dtype=np.int64)
    spins[0] = rng.choice([-1, 1])
    flips = rng.random(int(n) - 1) < (1.0 - stay)
    for i in range(1, int(n)):
        spins[i] = -spins[i - 1] if flips[i - 1] else spins[i - 1]
    return spins


def critical_ising_chain(n: int, seed: int = 0) -> np.ndarray:
    """Ising chain tuned so the correlation length is ~n/2."""
    if n < 3:
        raise RenormalizationError(f"chain length must be >= 3, got {n}")
    beta_j = math.atanh(1.0 - 2.0 / n)
    return generate_ising_chain(n, beta_j, seed)


def phi_rg_step(
    state: np.ndarray, auxiliary_register: List[np.ndarray]
) -> np.ndarray:
    """One golden RG level: lift, keep coarse, push detail to the register."""
    flat = np.asarray(state).ravel()
    if flat.size < 2:
        raise RenormalizationError("cannot renormalize fewer than 2 samples")
    coarse, detail = _lift_level(flat, exact=True)
    auxiliary_register.append(detail)
    return coarse


def phi_renormalize_deep(
    state: np.ndarray, depth: int
) -> Tuple[np.ndarray, List[np.ndarray]]:
    """Fold ``state`` ``depth`` levels; return ``(macro, scale_register)``."""
    register: List[np.ndarray] = []
    current = np.asarray(state).ravel()
    if current.dtype != np.int64:
        if np.issubdtype(current.dtype, np.integer):
            current = current.astype(np.int64)
        else:
            raise RenormalizationError(
                "phi renormalization is bit-exact on integer input only"
            )
    for _ in range(depth):
        if current.size < 2:
            break
        current = phi_rg_step(current, register)
    return current, register


def phi_reconstruct_deep(
    macro_state: np.ndarray, scale_register: Sequence[np.ndarray]
) -> np.ndarray:
    """Inverse of :func:`phi_renormalize_deep` — bit-exact on int64."""
    current = np.asarray(macro_state).ravel()
    if current.dtype != np.int64:
        current = current.astype(np.int64)
    for detail in reversed(list(scale_register)):
        current = _unlift_level(current, detail, exact=True)
    return current


def block_spin_decimate(state: np.ndarray, factor: int = 2) -> np.ndarray:
    """Standard linear RG: majority-vote decimation by ``factor``."""
    flat = np.asarray(state).ravel()
    n = flat.size - (flat.size % factor)
    grouped = flat[:n].reshape(-1, factor)
    sums = grouped.sum(axis=1)
    out = np.sign(sums).astype(np.int64)
    out[out == 0] = 1
    return out


def mutual_information(x: np.ndarray, y: np.ndarray, bins: int = 8) -> float:
    """Binned Shannon mutual information of two equal-length samples (bits)."""
    fx = np.asarray(x).ravel().astype(float)
    fy = np.asarray(y).ravel().astype(float)
    if fx.size != fy.size or fx.size == 0:
        raise RenormalizationError(
            "mutual_information requires equal non-empty samples"
        )
    joint, xedges, yedges = np.histogram2d(fx, fy, bins=bins)
    pxy = joint / joint.sum()
    px = pxy.sum(axis=1, keepdims=True)
    py = pxy.sum(axis=0, keepdims=True)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(pxy > 0, pxy / (px * py), 1.0)
        mi = float(np.sum(pxy * np.log2(ratio)))
    return max(mi, 0.0)


def scale_information_retained(
    micro_state: np.ndarray, macro_alone: np.ndarray
) -> float:
    """Measured bits the macro register alone retains about the micro-state.

    Compares the sign of the micro-state (restricted to the macro's own
    extent) against the sign of the reconstructed-from-coarse view.
    """
    micro = np.asarray(micro_state).ravel()
    n = int(macro_alone.size)
    return mutual_information(
        np.sign(micro[:n]).astype(float), np.sign(macro_alone).astype(float)
    )


@dataclass(frozen=True)
class RGEfficiencyResult:
    """Measured outcome of the linear-vs-golden RG duel."""

    chain_length: int
    depth: int
    linear_macro_size: int
    golden_macro_size: int
    linear_retained_bits: float
    golden_retained_bits: float
    golden_bit_exact: bool


def benchmark_rg_efficiency(
    n: int = 2584, depth: int = 4, seed: int = 0
) -> RGEfficiencyResult:
    """Linear block-spin vs golden lifting on a correlated Ising field.

    Retention is measured by zeroing the discarded register: linear RG
    repeats its macro vote across each block; golden RG unlifts with an
    all-zero detail (the coarse view alone).  The golden number therefore
    includes only what the macro register carries — the lifted averages —
    not the detail it correctly refuses to fake.
    """
    micro = critical_ising_chain(n, seed=seed)

    # Linear RG
    lin_macro = micro
    for _ in range(depth):
        lin_macro = block_spin_decimate(lin_macro, factor=2)
    upsampled = np.repeat(lin_macro, 2 ** depth)[: micro.size]
    linear_retained = mutual_information(
        micro[: upsampled.size].astype(float), upsampled.astype(float)
    )

    # Golden RG: macro alone vs the coarse view reconstructed with zero detail
    macro, register = phi_renormalize_deep(micro, depth)
    coarse_only = np.asarray(macro).copy()
    zero_register = [np.zeros_like(part) for part in register]
    coarse_view = phi_reconstruct_deep(coarse_only, zero_register)
    golden_retained = mutual_information(
        micro[: coarse_view.size].astype(float),
        np.sign(coarse_view).astype(float),
    )

    reconstructed = phi_reconstruct_deep(macro, register)
    bit_exact = bool(np.array_equal(micro[: reconstructed.size], reconstructed))

    return RGEfficiencyResult(
        chain_length=int(micro.size),
        depth=depth,
        linear_macro_size=int(lin_macro.size),
        golden_macro_size=int(macro.size),
        linear_retained_bits=float(linear_retained),
        golden_retained_bits=float(golden_retained),
        golden_bit_exact=bit_exact,
    )


# ---------------------------------------------------------------------------
# "Project Chrysalis" — decoding bits embedded in the scale register.


@dataclass(frozen=True)
class ChrysalisResult:
    """Measured recovery of a message embedded in a noisy correlated field."""

    message_bits: int
    payload_amplitude: int
    noise_sigma: float
    golden_bit_accuracy: float
    linear_bit_accuracy: float


def _detail_positions(length: int) -> np.ndarray:
    """Lattice positions of the short children (the level-1 detail band)."""
    from .dphi_transform import phi_lattice_mask

    return np.flatnonzero(phi_lattice_mask(length))


def chrysalis_benchmark(
    n: int = 2584,
    message_bits: int = 48,
    payload_amplitude: int = 16,
    noise_sigma: float = 2.0,
    seed: int = 0,
) -> ChrysalisResult:
    """Embed bits in the detail band of a critical Ising field and recover.

    Payload ``+A``/``-A`` rides the short-lattice positions.  After one
    golden RG level the detail is ``S' = S - round(phi*L)``; the Ising
    contribution stays in ``{0,+-1,+-2}`` while the payload swings ``+-A``,
    so a sign threshold recovers the message where linear decimation smears
    the +-1 spins across pair boundaries.  Accuracy is measured.
    """
    rng = np.random.default_rng(seed)
    field = critical_ising_chain(n, seed=seed + 1)
    bits = rng.integers(0, 2, size=message_bits)

    detail_idx = _detail_positions(n)
    if message_bits > detail_idx.size:
        raise RenormalizationError(
            f"message of {message_bits} bits exceeds detail band "
            f"{detail_idx.size}"
        )
    payload = np.zeros(n, dtype=np.int64)
    payload[detail_idx[:message_bits]] = (2 * bits - 1) * payload_amplitude

    noise = np.rint(rng.normal(0.0, noise_sigma, n)).astype(np.int64)
    received = field + payload + noise

    # Golden receiver: one RG level, threshold the detail band.
    _, received_register = phi_renormalize_deep(received, 1)
    detail = received_register[0]
    golden_bits = (detail[:message_bits] > 0).astype(int)
    golden_accuracy = float(np.mean(golden_bits == bits))

    # Linear receiver: pair-average and threshold (decimation smears the
    # short-child payload into its long-child neighbours).
    linear = block_spin_decimate(received, factor=2)
    lin_idx = np.minimum(detail_idx[:message_bits] // 2, linear.size - 1)
    linear_bits = (linear[lin_idx] > 0).astype(int)
    linear_accuracy = float(np.mean(linear_bits == bits))

    return ChrysalisResult(
        message_bits=message_bits,
        payload_amplitude=payload_amplitude,
        noise_sigma=noise_sigma,
        golden_bit_accuracy=golden_accuracy,
        linear_bit_accuracy=linear_accuracy,
    )


__all__ = [
    "ChrysalisResult",
    "RGEfficiencyResult",
    "RenormalizationError",
    "block_spin_decimate",
    "benchmark_rg_efficiency",
    "chrysalis_benchmark",
    "critical_ising_chain",
    "generate_ising_chain",
    "mutual_information",
    "phi_reconstruct_deep",
    "phi_renormalize_deep",
    "phi_rg_step",
    "scale_information_retained",
]
