"""Exact two-amplitude Grover search over a folded register, wired to OVID/THESEUS.

Reconstructed from the owner's final design (the verbatim text was not
available in this workspace; names, signature and behaviour follow it).

* State: Grover amplitudes over 2^D states collapse, by symmetry, to two
  classes - marked amplitude alpha, unmarked beta - starting from the
  integers (1, 1) (the 1/sqrt(N) scale is factored out).
* One canonical iterate (oracle -alpha, inversion about the mean):
      mu     = (U*beta - M*alpha) / N,  U = N - M
      alpha' = 2*mu + alpha
      beta'  = 2*mu - beta
  in ``fractions.Fraction``; total marked probability M*alpha^2 / N exactly.
* The peak is found by stepping from (1,1); the integer bound
  isqrt(N//M) + 2 caps the walk (the true peak is ~ (pi/4) sqrt(N/M)).
* Below ``verify_full_vector_below`` states the full 2^D Fraction vector is
  stepped alongside and must match the two-amplitude state exactly.
* The oracle predicate is evaluated classically on every materialised state;
  that cost is reported, not hidden.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from math import isqrt
from typing import Callable, List, Optional, Sequence, Tuple

from chronus.geodesic.scheduler import lucas_pisano_geodesic_order, schedule_parameters
from chronus.ovid.folded_custody import FoldedWorkingHandle, OvidFoldedAdapter, attest

EVENT_VERIFIED = "GROVER_TARGET_VERIFIED"
EVENT_EXHAUSTED = "GROVER_DOMAIN_EXHAUSTED"
GROVER_SCHEMA = "chronus.triad-grover-receipt/1"


def _two_amplitude_step(alpha: Fraction, beta: Fraction, N: int, M: int) -> Tuple[Fraction, Fraction]:
    U = N - M
    mu = (U * beta - M * alpha) / N
    return 2 * mu + alpha, 2 * mu - beta


def _marked_probability_exact(alpha: Fraction, N: int, M: int) -> Fraction:
    return Fraction(M) * alpha * alpha / N


def exact_grover_two_amplitude_trajectory(N: int, M: int) -> List[Tuple[int, Fraction, Fraction, Fraction]]:
    """[(t, alpha_t, beta_t, P_t)] from (1,1) up to and including the peak."""
    if isinstance(N, bool) or isinstance(M, bool) or not isinstance(N, int) or not isinstance(M, int):
        raise TypeError("N and M must be integers")
    if N < 1 or not 1 <= M <= N:
        raise ValueError("require N >= 1 and 1 <= M <= N")
    alpha, beta = Fraction(1), Fraction(1)
    traj = [(0, alpha, beta, _marked_probability_exact(alpha, N, M))]
    if M == N:
        return traj
    max_steps = isqrt(N // M) + 2
    for t in range(1, max_steps + 1):
        alpha, beta = _two_amplitude_step(alpha, beta, N, M)
        if M * alpha * alpha + (N - M) * beta * beta != N:
            raise ArithmeticError("norm conservation failed")
        p = _marked_probability_exact(alpha, N, M)
        if p <= traj[-1][3]:
            return traj
        traj.append((t, alpha, beta, p))
    raise ArithmeticError("peak not reached within isqrt(N//M)+2 steps")


def exact_lucas_pisot_iterations(N: int, M: int) -> int:
    """Grover iteration count at the exact probability peak."""
    return exact_grover_two_amplitude_trajectory(N, M)[-1][0]


def _full_vector_step(vec: List[Fraction], marked: Sequence[bool]) -> List[Fraction]:
    flipped = [-v if m else v for v, m in zip(vec, marked)]
    mean = sum(flipped, Fraction(0)) / len(flipped)
    return [2 * mean - v for v in flipped]


@dataclass
class TriadGroverResult:
    found: bool
    artifact_id: str
    active_dim: int
    states: int
    marked_count: int
    iterations: int
    total_marked_probability: Fraction
    single_target_probability: Fraction
    winner_index: Optional[int]
    winner_value: Optional[int]
    winner_schedule_position: Optional[int]
    states_materialised: int
    oracle_evaluations: int
    handle_version: int
    schedule: dict = field(default_factory=dict)
    receipts: List[str] = field(default_factory=list)
    full_vector_checked: bool = False


def _active_positions(handle: FoldedWorkingHandle) -> List[int]:
    reg = handle.register
    return [j for j in range(reg.num_generators) if not (reg.resolved_mask >> j) & 1]


def run_triad_exact_grover_search(
    *,
    adapter: OvidFoldedAdapter,
    handle: FoldedWorkingHandle,
    oracle_predicate: Callable[[int], bool],
    geodesic_order: Optional[Sequence[int]] = None,
    epoch_step: Optional[int] = None,
    verify_full_vector_below: int = 64,
) -> TriadGroverResult:
    positions = _active_positions(handle)
    D = len(positions)
    if D == 0:
        raise ValueError("active subspace is empty (all generators resolved)")
    N = 1 << D
    if epoch_step is None:
        epoch_step = handle.version
    if geodesic_order is None:
        p = schedule_parameters(D, epoch_step)
        order = lucas_pisano_geodesic_order(D, epoch_step=epoch_step)
        schedule = {"schedule_source": "lucas_pisano_geodesic", "epoch_step": epoch_step,
                    "pisano_period": p["pisano_period"], "lucas_stride_mod": p["lucas_stride_mod"],
                    "fibonacci_phase_mod": p["fibonacci_phase_mod"]}
    else:
        order = list(geodesic_order)
        if len(order) != N or sorted(order) != list(range(N)):
            raise ValueError("geodesic_order must be a permutation of range(2^active_dim)")
        schedule = {"schedule_source": "explicit", "epoch_step": epoch_step}

    # Active-subspace expansion: schedule index t -> full register index.
    offsets = []
    for t in order:
        idx = 0
        for b, j in enumerate(positions):
            if (t >> b) & 1:
                idx |= 1 << j
        offsets.append(idx)
    values = adapter.materialise_indices(handle, offsets)
    marked = [bool(oracle_predicate(v)) for v in values]     # classical: every state evaluated
    marked_pos = [i for i, m in enumerate(marked) if m]
    M = len(marked_pos)
    common = dict(artifact_id=handle.artifact_id, active_dim=D, states=N, marked_count=M,
                  states_materialised=N, oracle_evaluations=N, schedule=schedule)
    accounting = "oracle_predicate evaluated classically on every materialised state"

    if M == 0:
        rid = adapter.theseus.append_audit_receipt(EVENT_EXHAUSTED, attest({
            "schema": GROVER_SCHEMA, "event": EVENT_EXHAUSTED, "artifact_id": handle.artifact_id,
            "handle_version": handle.version, "frame_sha256": handle.sha256_digest, "states": N,
            "marked_count": 0, "total_marked_probability": "0", "oracle_evaluations": N,
            "accounting": accounting, **schedule}))
        return TriadGroverResult(found=False, iterations=0, total_marked_probability=Fraction(0),
                                 single_target_probability=Fraction(0), winner_index=None, winner_value=None,
                                 winner_schedule_position=None, handle_version=handle.version,
                                 receipts=[rid], **common)

    traj = exact_grover_two_amplitude_trajectory(N, M)
    iters, alpha, beta, total = traj[-1]
    checked = False
    if N < verify_full_vector_below:
        vec = [Fraction(1)] * N
        for t, a_t, b_t, _p in traj[1:]:
            vec = _full_vector_step(vec, marked)
            if any(v != (a_t if m else b_t) for v, m in zip(vec, marked)):
                raise ArithmeticError(f"full-vector mismatch at step {t}")
        checked = True

    win = marked_pos[0]                       # first marked state in geodesic order
    win_idx = offsets[win] | handle.register.resolved_bits   # full register index: keep pre-collapsed bits
    h = handle
    for j in positions:
        h = adapter.commit_collapse_step(h, j, (win_idx >> j) & 1)
    bits, (hi, lo) = h.register.unfold_mk().readout_winner()
    value = (hi << h.register.k) | lo
    if bits != win_idx or value != values[win]:
        raise ArithmeticError("collapsed read-out disagrees with materialised winner")
    rid = adapter.theseus.append_audit_receipt(EVENT_VERIFIED, attest({
        "schema": GROVER_SCHEMA, "event": EVENT_VERIFIED, "artifact_id": handle.artifact_id,
        "handle_version": h.version, "frame_sha256": h.sha256_digest, "states": N,
        "marked_count": M, "iterations": iters,
        "total_marked_probability": f"{total.numerator}/{total.denominator}",
        "winner_index": win_idx, "winner_value": value, "winner_schedule_position": win + 1,
        "oracle_evaluations": N, "accounting": accounting, **schedule}))
    return TriadGroverResult(found=True, iterations=iters, total_marked_probability=total,
                             single_target_probability=total / M, winner_index=win_idx, winner_value=value,
                             winner_schedule_position=win + 1, handle_version=h.version, receipts=[rid],
                             full_vector_checked=checked, **common)
