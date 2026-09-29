"""Exact algebra certificate for every nonce window the coordinator dispatches.

A plan's window is sized on the Lucas ladder and ordered by the M32 lane
geometry. Before the plan reaches a hasher this module re-derives that sizing
in exact integer arithmetic and materialises the first candidate nonces in
the order the M32 kernel visits them:

* Q[sqrt5]: phi^k = F_(k-1) + F_k*phi in Z[phi] (``lucas.algebra``), and its
  trace equals L_k from the independent fast-doubling ``lucas.core``;
* unit norm: N(phi^k) = (-1)^k;
* Cassini (Lucas-Fibonacci form): L_k^2 - 5*F_k^2 = 4*(-1)^k;
* Pisot rounding: |psi^k| < 1/2, so L_k is the nearest integer to phi^k;
* the L15 = 1364 ladder anchor;
* cross-checks against the MLA1517 Phase 1 reference runtime: its Cassini
  verifier, Q-matrix trace, lossless Pisot fold and 32-site M32 fabric must
  agree with the values above, derived independently;
* Hendrix order (when it is the executed order): the Lucas/Pisot scale
  value matches L_index, and gcd(stride, window) = 1, so the order is a
  bijection of the leased range.

A failed certificate refuses the dispatch. The certificate constrains which
work is dispatched; it does not make any nonce more likely to meet the
target. SHA-256d is unchanged and every candidate is still hashed and
checked against the pool target.
"""

from __future__ import annotations

from functools import lru_cache
from math import gcd
from typing import Any, Sequence

from lucas import algebra as ring
from lucas.core import fibonacci, lucas
from lucas.ladder import FULL_LADDER

SCHEMA = "pythia.dispatch_algebra/1"
ORDER_M32 = "m32_turing_complete"
ORDER_HENDRIX = "hendrix_coprime_stride"
LANES = 32
L15 = 1364
NONCE_SPACE = 1 << 32
PREVIEW_NONCES = 8
CLAIM = (
    "Sizes and orders the dispatched window. SHA-256d success probability per " "hash is unchanged."
)


def lucas_floor_index(value: int) -> int:
    """Largest k >= 1 with L_k <= value (the ladder is increasing from L_1)."""
    if value < 1:
        raise ValueError("value must be a positive integer")
    k = 1
    while lucas(k + 1) <= value:
        k += 1
    return k


def lucas_basis(window: int) -> tuple[int, str]:
    """The Lucas index a window was cut from.

    ``lucas_epoch``: the window is L_k rounded down to whole M32 epochs (how
    the operating policy and launch cap size it). ``lucas_floor``: otherwise,
    L_k <= window < L_(k+1).
    """
    k = lucas_floor_index(window)
    for candidate in (k, k + 1):
        value = lucas(candidate)
        if value - value % LANES == window:
            return candidate, "lucas_epoch"
    return k, "lucas_floor"


def _pisot_rounds(l_k: int, f_k: int) -> bool:
    """Exact test of |L_k - F_k*sqrt5| < 1, i.e. |psi^k| < 1/2.

    Cassini gives (L - F*sqrt5)(L + F*sqrt5) = 4*(-1)^k, so the bound holds
    iff L + F*sqrt5 > 4, decided here without irrational arithmetic.
    """
    if f_k < 0 or l_k < 0:
        return False
    if l_k >= 4:
        return f_k > 0 or l_k > 4
    return 5 * f_k * f_k > (4 - l_k) ** 2


@lru_cache(maxsize=1)
def _m32_fabric() -> tuple[bool, str | None]:
    try:
        from ..m32_geometry import build_topology
    except ImportError as exc:
        return False, f"{type(exc).__name__}: {exc}"
    topology = build_topology()
    return topology.nodes == LANES and topology.connected, None


def phase1_crosschecks(k: int, l_k: int, f_k: int) -> dict[str, Any]:
    """The Phase 1 reference runtime, asked the same questions independently."""
    try:
        from ..cassini import cassini_lucas_form, q_matrix_trace
        from ..pisot_fold import pisot_fold, pisot_unfold
    except ImportError as exc:
        return {"available": False, "reason": f"{type(exc).__name__}: {exc}", "checks": {}}
    cassini = cassini_lucas_form(k)
    fold = pisot_fold(k, family="fibonacci", lossless=True)
    fabric, fabric_error = _m32_fabric()
    checks = {
        "phase1_cassini": cassini.passed and cassini.observed == l_k * l_k - 5 * f_k * f_k,
        "phase1_q_matrix_trace": q_matrix_trace(k) == l_k,
        "phase1_pisot_fold_lossless": fold.folded.exact_value == f_k
        and pisot_unfold(fold.folded) == f_k,
        "phase1_m32_fabric": fabric,
    }
    return {"available": fabric_error is None, "reason": fabric_error, "checks": checks}


def exact_identities(k: int) -> dict[str, Any]:
    """Every identity the ALGEBRA tab shows, evaluated for Lucas index k."""
    power = ring.phi_power(k)
    l_k = lucas(k)
    f_k = fibonacci(k)
    sign = -1 if k % 2 else 1
    checks = {
        "q_sqrt5_trace": power.trace() == l_k,
        "q_sqrt5_phi_coefficient": power.b == f_k,
        "unit_norm": power.norm() == sign,
        "cassini": l_k * l_k - 5 * f_k * f_k == 4 * sign,
        "pisot_rounding": k >= 2 and _pisot_rounds(l_k, f_k),
        "l15_anchor": lucas(15) == L15 and 15 in FULL_LADDER,
    }
    phase1 = phase1_crosschecks(k, l_k, f_k)
    if phase1["available"]:
        checks.update(phase1["checks"])
    return {
        "k": k,
        "L_k": l_k,
        "F_k": f_k,
        "L_k_next": lucas(k + 1),
        "phi_power": {"a": power.a, "b": power.b},
        "checks": checks,
        "phase1_reference": {"available": phase1["available"], "reason": phase1["reason"]},
    }


def m32_first_nonces(base_step: int, lane_order: Sequence[int], count: int) -> list[int]:
    """The first ``count`` nonces of the M32 order the kernel executes.

    Same closed form as ``M32SearchSolver.candidates`` and the OpenCL kernel:
    base + lane[step % 32] + 32 * (step // 32).
    """
    base = base_step - base_step % LANES
    return [
        (base + int(lane_order[step % LANES]) + LANES * (step // LANES)) & 0xFFFFFFFF
        for step in range(count)
    ]


def _header_fields(header: bytes) -> dict[str, Any]:
    return {
        "version": int.from_bytes(header[0:4], "little"),
        "prev_hash": header[4:36][::-1].hex(),
        "merkle_root": header[36:68][::-1].hex(),
        "ntime": header[68:72][::-1].hex(),
        "nbits": header[72:76][::-1].hex(),
    }


def certify_dispatch(
    *,
    plan_id: str,
    job_id: str | None,
    base_step: int,
    window: int,
    lane_order: Sequence[int],
    header: bytes,
    target_le: bytes,
    ceiling: int,
    nonce_order: str,
    route: str,
    hendrix: Any = None,
) -> dict[str, Any]:
    """Certify one dispatch; ``ok`` is False with a refusal reason on failure.

    ``nonce_order`` is the order the router will execute. For Hendrix,
    ``hendrix`` is the schedule it will use (``hendrix_order.hendrix_schedule``).
    """
    failures: list[str] = []
    if len(header) != 80:
        failures.append(f"header_length:{len(header)}")
    elif header[76:80] != b"\x00\x00\x00\x00":
        failures.append("header_nonce_not_zeroed")
    if len(target_le) != 32 or not any(target_le):
        failures.append("share_target_invalid")
    lanes = [int(lane) for lane in lane_order]
    if sorted(lanes) != list(range(LANES)):
        failures.append("lane_order_not_m32_permutation")
    if window <= 0 or window % LANES:
        failures.append(f"window_not_whole_m32_epochs:{window}")
    if not (0 <= base_step and base_step + max(window, 0) <= NONCE_SPACE):
        failures.append("nonce_range_outside_uint32")
    if window > ceiling:
        failures.append(f"window_exceeds_lucas_ceiling:{window}>{ceiling}")

    identities: dict[str, Any] | None = None
    if window >= 1:
        basis_k, basis = lucas_basis(window)
        identities = {**exact_identities(basis_k), "basis": basis}
        failed = [name for name, held in identities["checks"].items() if not held]
        failures.extend(f"identity:{name}" for name in failed)

    hendrix_facts: dict[str, Any] | None = None
    if nonce_order == ORDER_HENDRIX:
        if hendrix is None:
            failures.append("hendrix_schedule_missing")
        else:
            scale = hendrix.scale
            hendrix_facts = {
                "stride": hendrix.stride,
                "coprime": gcd(hendrix.stride, window) == 1 if window > 0 else False,
                "scale_index": scale.index,
                "scale_lucas_value": scale.lucas_value,
                "scale_matches_lucas": scale.lucas_value == lucas(scale.index),
            }
            if hendrix.nonce_count != window:
                failures.append(f"hendrix_window_mismatch:{hendrix.nonce_count}!={window}")
            if not hendrix_facts["coprime"]:
                failures.append("hendrix_stride_not_coprime")
            if not hendrix_facts["scale_matches_lucas"]:
                failures.append("hendrix_scale_not_lucas")
    ceiling_k = lucas_floor_index(ceiling) if ceiling >= 1 else None
    preview = None
    if not failures and nonce_order in (ORDER_M32, ORDER_HENDRIX):
        count = min(PREVIEW_NONCES, window)
        if nonce_order == ORDER_HENDRIX:
            preview = [(base_step + hendrix.nonce_at(p)) & 0xFFFFFFFF for p in range(count)]
        else:
            preview = m32_first_nonces(base_step, lanes, count)
    return {
        "schema": SCHEMA,
        "ok": not failures,
        "refusal": ";".join(failures) or None,
        "claim": CLAIM,
        "plan_id": plan_id,
        "job_id": job_id,
        "route": route,
        "nonce_order": nonce_order,
        "window": window,
        "nonce_range": [base_step, base_step + window],
        "ceiling": {
            "value": ceiling,
            "on_lucas_ladder": ceiling_k is not None and lucas(ceiling_k) == ceiling,
        },
        "lucas": identities,
        "m32": {
            "epochs": window // LANES if window > 0 else 0,
            "lane_order": lanes,
        },
        "hendrix": hendrix_facts,
        "first_nonces": preview,
        "header": _header_fields(header) if len(header) == 80 else None,
        "share_target_be": target_le[::-1].hex() if len(target_le) == 32 else None,
    }
