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

import hashlib
from dataclasses import dataclass, field
from fractions import Fraction
from math import isqrt
from typing import Callable, List, Optional, Sequence, Tuple

from chronus.geodesic.scheduler import lucas_pisano_geodesic_order, schedule_parameters
from chronus.ovid.folded_custody import FoldedWorkingHandle, OvidFoldedAdapter, attest, verify_attested

EVENT_VERIFIED = "GROVER_TARGET_VERIFIED"
EVENT_EXHAUSTED = "GROVER_DOMAIN_EXHAUSTED"
# Written before the first collapse commit: the full outcome of a search whose
# winner passed verification, so a crash after the final collapse can be finished
# idempotently from the restored, fully resolved handle.
EVENT_SELECTED = "GROVER_OUTCOME_SELECTED"
GROVER_SCHEMA = "chronus.triad-grover-receipt/2"
FRACTION_ENCODING = "hex-fraction/1"


def encode_exact_fraction(value: Fraction) -> dict:
    """Exact, size-independent encoding of a Fraction for receipts.

    Hexadecimal numerator/denominator: CPython caps int->decimal str conversion
    at 4300 digits (sys.int_info.str_digits_check_threshold), which the exact
    peak probability exceeds from 19 active generators (denominator 2^19331)."""
    if not isinstance(value, Fraction):
        raise TypeError("exact Fraction required")
    sign = "-" if value < 0 else ""
    return {"encoding": FRACTION_ENCODING, "numerator": f"{sign}{abs(value.numerator):x}",
            "denominator": f"{value.denominator:x}"}


def decode_exact_fraction(obj: dict) -> Fraction:
    if not isinstance(obj, dict) or obj.get("encoding") != FRACTION_ENCODING:
        raise ValueError(f"expected {FRACTION_ENCODING} object")
    return Fraction(int(obj["numerator"], 16), int(obj["denominator"], 16))


def _two_amplitude_step(alpha: Fraction, beta: Fraction, N: int, M: int) -> Tuple[Fraction, Fraction]:
    U = N - M
    mu = (U * beta - M * alpha) / N
    return 2 * mu + alpha, 2 * mu - beta


def _marked_probability_exact(alpha: Fraction, N: int, M: int) -> Fraction:
    return Fraction(M) * alpha * alpha / N


def exact_grover_two_amplitude_trajectory(N: int, M: int) -> List[Tuple[int, Fraction, Fraction, Fraction]]:
    """[(t, alpha_t, beta_t, P_t)] from (1,1) up to the first non-increase.

    Stopping rule: iterate while the marked probability strictly increases and
    stop at the first step where it does not.  For M/N <= 1/2 that first local
    maximum is the global maximum over t <= isqrt(N//M)+2; for M/N > 1/2 it can be
    step 0 even when a later step is higher (N=8, M=5: 5/8, 5/32, 125/128), so the
    result is not necessarily the highest attainable probability."""
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
    """Grover iteration count at the first non-increase of the exact marked
    probability (see ``exact_grover_two_amplitude_trajectory``)."""
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
    winner_verifier: Optional[Callable[[int], bool]] = None,
) -> TriadGroverResult:
    """``winner_verifier`` (e.g. a fresh full-header SHA-256d check) runs on the
    selected value before any collapse commit or GROVER_TARGET_VERIFIED receipt is
    written; a rejection raises and leaves no verified receipt behind."""
    positions = _active_positions(handle)
    D = len(positions)
    if D == 0:
        return _finish_selected_outcome(adapter, handle, oracle_predicate, winner_verifier)
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
        if any(isinstance(t, bool) or not isinstance(t, int) for t in order):
            raise ValueError("geodesic_order entries must be integers")
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
            "marked_count": 0, "total_marked_probability": encode_exact_fraction(Fraction(0)),
            "oracle_evaluations": N,
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
    # Dry-run the collapse in memory and check the read-out before any custody write.
    reg = handle.register
    for j in positions:
        reg = reg.collapse_generator(j, (win_idx >> j) & 1)
    bits, (hi, lo) = reg.unfold_mk().readout_winner()
    value = (hi << reg.k) | lo
    if bits != win_idx or value != values[win]:
        raise ArithmeticError("collapsed read-out disagrees with materialised winner")
    if winner_verifier is not None and not winner_verifier(value):
        raise ArithmeticError("selected winner failed independent verification")
    outcome = {
        "schema": GROVER_SCHEMA, "artifact_id": handle.artifact_id,
        "handle_version": handle.version + D, "frame_sha256": hashlib.sha256(reg.to_wire_bytes()).hexdigest(),
        "start_version": handle.version, "start_frame_sha256": handle.sha256_digest,
        "active_dim": D, "states": N, "marked_count": M, "iterations": iters,
        "total_marked_probability": encode_exact_fraction(total),
        "winner_index": win_idx, "winner_value": value, "winner_schedule_position": win + 1,
        "oracle_evaluations": N, "accounting": accounting, **schedule}
    adapter.theseus.append_audit_receipt(EVENT_SELECTED, attest({**outcome, "event": EVENT_SELECTED}))
    h = handle
    for j in positions:
        h = adapter.commit_collapse_step(h, j, (win_idx >> j) & 1)
    if h.register != reg or h.sha256_digest != outcome["frame_sha256"]:
        raise ArithmeticError("committed register disagrees with in-memory collapse")
    rid = adapter.theseus.append_audit_receipt(EVENT_VERIFIED, attest({**outcome, "event": EVENT_VERIFIED}))
    return TriadGroverResult(found=True, iterations=iters, total_marked_probability=total,
                             single_target_probability=total / M, winner_index=win_idx, winner_value=value,
                             winner_schedule_position=win + 1, handle_version=h.version, receipts=[rid],
                             full_vector_checked=checked, **common)


def _finish_selected_outcome(adapter: OvidFoldedAdapter, handle: FoldedWorkingHandle,
                             oracle_predicate: Callable[[int], bool],
                             winner_verifier: Optional[Callable[[int], bool]]) -> TriadGroverResult:
    """Fully resolved handle: finish a search whose outcome was selected (and its
    collapse committed) but whose GROVER_TARGET_VERIFIED receipt is missing, or
    return the existing verified result.  Handles with no pending outcome are
    rejected as before."""
    def ours(body: dict) -> bool:
        return (body.get("artifact_id") == handle.artifact_id and body.get("handle_version") == handle.version
                and body.get("frame_sha256") == handle.sha256_digest)

    selected = verified = None
    for event, rec in adapter.theseus.journal_receipts([EVENT_SELECTED, EVENT_VERIFIED]):
        body = verify_attested(rec)
        if ours(body):
            if event == EVENT_SELECTED and selected is None:
                selected = body
            elif event == EVENT_VERIFIED and verified is None:
                verified = (body, rec)
    if selected is None:
        raise ValueError("active subspace is empty (all generators resolved) and no search outcome is pending")
    bits, (hi, lo) = handle.register.unfold_mk().readout_winner()
    value = (hi << handle.register.k) | lo
    if bits != selected["winner_index"] or value != selected["winner_value"]:
        raise ArithmeticError("resolved register disagrees with the selected outcome")
    if not oracle_predicate(value):
        raise ArithmeticError("selected winner no longer satisfies the oracle")
    if winner_verifier is not None and not winner_verifier(value):
        raise ArithmeticError("selected winner failed independent verification")
    if verified is None:
        body = {k: v for k, v in selected.items() if k != "event"}
        rid = adapter.theseus.append_audit_receipt(EVENT_VERIFIED, attest({**body, "event": EVENT_VERIFIED}))
    else:
        rid = adapter.theseus.receipt_entry_hash(EVENT_VERIFIED, verified[1])
        if rid is None:
            raise ArithmeticError("verified receipt is not in the tenant journal")
    total = decode_exact_fraction(selected["total_marked_probability"])
    schedule = {k: selected[k] for k in ("schedule_source", "epoch_step", "pisano_period",
                                         "lucas_stride_mod", "fibonacci_phase_mod") if k in selected}
    return TriadGroverResult(
        found=True, artifact_id=handle.artifact_id, active_dim=selected["active_dim"], states=selected["states"],
        marked_count=selected["marked_count"], iterations=selected["iterations"], total_marked_probability=total,
        single_target_probability=total / selected["marked_count"], winner_index=selected["winner_index"],
        winner_value=value, winner_schedule_position=selected["winner_schedule_position"],
        states_materialised=0, oracle_evaluations=1, handle_version=handle.version,
        schedule=schedule, receipts=[rid])
