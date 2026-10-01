"""CPU emitters — the reference backend for every spec.

Each ``emit_<spec>()`` returns a callable ``(inputs: dict, dispatch: dict) ->
dict``. These are the oracles: sha256d ops recompute via hashlib; punch
family ops delegate to ``UnifiedPunchHost._execute_cpu`` (the exact numpy
mirror of the kernel); algebraic ops use the exact-int mla1517 core. A spec
with ``canonical_source=None`` is *defined* by its CPU emitter.
"""

from __future__ import annotations

import hashlib
import struct
from typing import Any, Callable, Dict, List

import numpy as np

DIM = 11
MASK64 = 0xFFFFFFFFFFFFFFFF
PHI = (1.0 + 5.0**0.5) / 2.0
PHI_INV = PHI - 1.0


def _double_sha256(data: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def _hash_meets_target(digest: bytes, target: int) -> bool:
    return int.from_bytes(digest, "little") <= target


def emit_sha256d_scan() -> Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]:
    """nonce = (base + gid) mod 2^32; winner iff sha256d(header|nonce) <= target."""

    def run(inputs: Dict[str, Any], dispatch: Dict[str, Any]) -> Dict[str, Any]:
        header = bytes(inputs["header"])
        if len(header) != 76:
            raise ValueError("sha256d_scan expects the 76-byte nonce-less header")
        base = int(inputs["base_nonce"]) & 0xFFFFFFFF
        count = int(inputs.get("count", dispatch.get("work_items", 1)))
        target = int(inputs["target"])
        hits: List[int] = []
        winner = None
        blob = bytearray(header) + bytearray(4)
        for gid in range(count):
            nonce = (base + gid) & 0xFFFFFFFF
            struct.pack_into("<I", blob, 76, nonce)
            digest = _double_sha256(bytes(blob))
            if _hash_meets_target(digest, target):
                hits.append(nonce)
                if winner is None:
                    winner = nonce
        return {"winning_nonce": winner, "hits": hits, "hashes": count}

    return run


def emit_sha256d_m32() -> Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]:
    """Turing lane-order m32 candidate stream — M32SearchSolver is the oracle."""

    def run(inputs: Dict[str, Any], dispatch: Dict[str, Any]) -> Dict[str, Any]:
        from chronus.mla1517.mining.solver import M32SearchSolver

        solver = M32SearchSolver()
        budget = int(inputs.get("budget", dispatch.get("work_items", 32)))
        cands = list(
            solver.candidates(
                start_nonce=int(inputs.get("start_nonce", 0)),
                budget=budget,
                lane_order=inputs.get("lane_order"),
            )
        )
        return {"candidates": cands, "budget": budget}

    return run


_GOLDEN_STRIDE = 0x9E3779B9


def emit_sha256d_gold() -> Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]:
    """Golden-stride oracle: nonce_i = (seed + i·⌊2³²/φ⌋) mod 2³².

    Identical walk to the device kernel — the stride is odd so the
    sequence permutes the whole nonce domain; hashlib sha256d decides.
    """

    def run(inputs: Dict[str, Any], dispatch: Dict[str, Any]) -> Dict[str, Any]:
        header = bytes(inputs["header"])
        if len(header) != 76:
            raise ValueError("sha256d_gold expects the 76-byte nonce-less header")
        seed = int(inputs.get("seed", 0)) & 0xFFFFFFFF
        count = int(inputs.get("count", dispatch.get("work_items", 1)))
        target = int(inputs["target"])
        hits: List[int] = []
        winner = None
        blob = bytearray(header) + bytearray(4)
        for i in range(count):
            nonce = (seed + i * _GOLDEN_STRIDE) & 0xFFFFFFFF
            struct.pack_into("<I", blob, 76, nonce)
            digest = _double_sha256(bytes(blob))
            if _hash_meets_target(digest, target):
                if len(hits) < 8:
                    hits.append(nonce)
                if winner is None:
                    winner = nonce
        return {"winning_nonce": winner, "hits": hits, "hashes": count}

    return run


def _cpu_punch_host():
    """A UnifiedPunchHost pinned to its CPU path (never touches OpenCL)."""
    from Intelligence.unified_punch import UnifiedPunchHost

    host = UnifiedPunchHost()
    host.use_opencl = False
    return host


def _run_punch_ids(punch_ids: List[int], inputs: Dict[str, Any]) -> Dict[str, Any]:
    def _arr(key: str, size: int, dtype: Any) -> np.ndarray:
        v = inputs.get(key)
        if v is None:
            return np.zeros(size, dtype=dtype)
        return np.asarray(v, dtype=dtype)

    host = _cpu_punch_host()
    total = len(punch_ids)
    N = int(inputs.get("n", total))
    in_float = _arr("in_float", total * DIM, np.float32)
    in_ulong = _arr("in_ulong", total * DIM * DIM, np.uint64)
    in_int = _arr("in_int", total, np.int32)
    in_double = _arr("in_double", total, np.float64)
    out_float = np.zeros(total * DIM, dtype=np.float32)
    out_ulong = np.zeros(total * DIM * DIM, dtype=np.uint64)
    out_int = np.zeros(total, dtype=np.int32)
    out_long = np.zeros(total, dtype=np.int64)
    out_double = np.zeros(total * DIM, dtype=np.float64)
    ids = np.asarray([int(p) for p in punch_ids], dtype=np.uint8)
    return host._execute_cpu(
        ids,
        in_float,
        in_ulong,
        in_int,
        in_double,
        out_float,
        out_ulong,
        out_int,
        out_long,
        out_double,
        total,
        N,
    )


def _emit_punch(punch_id: int) -> Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]:
    def run(inputs: Dict[str, Any], dispatch: Dict[str, Any]) -> Dict[str, Any]:
        ids = inputs.get("punch_ids") or [punch_id] * max(1, int(inputs.get("total", 1)))
        outs = _run_punch_ids(ids, inputs)
        return {
            "float": outs["float"],
            "ulong": outs["ulong"],
            "int": outs["int"],
            "long": outs["long"],
            "double": outs["double"],
        }

    return run


def emit_unified_punch() -> Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]:
    """General dispatch: inputs['punch_ids'] selects the per-gid semantics."""

    def run(inputs: Dict[str, Any], dispatch: Dict[str, Any]) -> Dict[str, Any]:
        ids = inputs.get("punch_ids")
        if not ids:
            raise ValueError("unified_punch inputs require 'punch_ids'")
        return _run_punch_ids(list(ids), inputs)

    return run


def emit_lucas_pisot_scale() -> Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]:
    """Exact fib/lucas/padovan at scale_index — uint64 like the ladder kernel."""

    def padovan(n: int) -> int:
        if n < 3:
            return 1
        a, b, c = 1, 1, 1
        for _ in range(n - 2):
            a, b, c = b, c, a + b
        return c

    def run(inputs: Dict[str, Any], dispatch: Dict[str, Any]) -> Dict[str, Any]:
        from lucas.core import fibonacci as fib, lucas

        scale = int(inputs["scale_index"])
        kind = str(inputs.get("kind", "fib"))
        if kind == "fib":
            value = fib(scale)
        elif kind == "lucas":
            value = lucas(scale)
        elif kind == "padovan":
            value = padovan(scale)
        else:
            raise ValueError(f"unknown ladder kind {kind!r}")
        return {"value": value & MASK64, "exact_value": value, "scale_index": scale}

    return run


def emit_exact_hadamard() -> Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]:
    """Exact H on the named qubit — amplitudes stay in Q(sqrt2)."""

    def run(inputs: Dict[str, Any], dispatch: Dict[str, Any]) -> Dict[str, Any]:
        from chronus.mla1517.quantum import H, ExactStateVector

        state = inputs["state"]
        if isinstance(state, int):  # qubit count → basis state 0
            state = ExactStateVector.basis(state, int(inputs.get("basis_index", 0)))
        qubit = int(inputs.get("qubit", 0))
        out = state.apply_single(qubit, H)
        return {"state": out, "normalized": out.normalized_exact()}

    return run


def emit_golden_ontology_transform() -> Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]:
    """fibonacci_butterfly_kernel — exact-int butterfly + invariant checks."""

    def run(inputs: Dict[str, Any], dispatch: Dict[str, Any]) -> Dict[str, Any]:
        x_re = np.asarray(inputs["x_re"], dtype=np.int64)
        x_im = (
            np.asarray(inputs.get("x_im"), dtype=np.int64)
            if inputs.get("x_im") is not None
            else None
        )
        basis = np.asarray(inputs["fib_basis"], dtype=np.int64)
        n = int(inputs.get("n_points", len(x_re)))
        y_re = np.zeros(n, dtype=np.int64)
        y_im = np.zeros(n, dtype=np.int64) if x_im is not None else None
        for k in range(n):
            acc_re = 0
            acc_im = 0
            for m in range(n):
                b = int(basis[(m + k) % n])
                acc_re += int(x_re[m]) * b
                if x_im is not None:
                    acc_im += int(x_im[m]) * b
            y_re[k] = acc_re
            if y_im is not None:
                y_im[k] = acc_im
        # invariants (the kernels' result flags)
        binet = all(int(basis[j]) == int(basis[j - 1]) + int(basis[j - 2]) for j in range(2, n))
        cassini = all(
            int(basis[m + 1]) * int(basis[m - 1]) - int(basis[m]) ** 2 == (-1 if m % 2 == 1 else 1)
            for m in range(1, n - 1)
        )
        out = {"y_re": y_re, "binet_closure": binet, "cassini_identity": cassini}
        if y_im is not None:
            out["y_im"] = y_im
        return out

    return run


def emit_grover_iterate() -> Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]:
    """GroverStyleSearch is the oracle — real sha256d accept, Grover order.

    The Lucas scale rung (10/12/15/18/20) flows through the dispatch — a
    workload ``scale_index`` or the route's ``lucas_dispatch.scale_index`` —
    and scales the search space by L_n.
    """

    def run(inputs: Dict[str, Any], dispatch: Dict[str, Any]) -> Dict[str, Any]:
        from mining.search import GroverStyleSearch

        scale_index = dispatch.get("scale_index")
        if scale_index is None:
            scale_index = dispatch.get("lucas_dispatch", {}).get("scale_index")
        return GroverStyleSearch().search(
            header=bytes(inputs["header"]),
            schedule=list(inputs["schedule"]),
            target=inputs["target"],
            scale_index=scale_index,
        )

    return run


def _phi_weights_f32() -> np.ndarray:
    return np.array(
        [np.float32(PHI) ** np.float32(-(j + 1)) for j in range(DIM)],
        dtype=np.float32,
    )


def emit_cnormsq() -> Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]:
    """PHI-weighted f32 norm squared — identical serial order to 0x15."""

    def run(inputs: Dict[str, Any], dispatch: Dict[str, Any]) -> Dict[str, Any]:
        x = np.asarray(inputs["in_float"], dtype=np.float32)
        total = x.size // DIM
        w32 = _phi_weights_f32()
        out = np.zeros(total, dtype=np.float32)
        for i in range(total):
            s = np.float32(0)
            for j in range(DIM):
                c = np.float32(x[i * DIM + j])
                s = np.float32(s + np.float32(w32[j] * c * c))
            out[i] = s
        return {"cnormsq": out}

    return run


def _phi_lattice_batch(inputs: Dict[str, Any]) -> np.ndarray:
    """Definition oracle: per-vector PHI-power projection in float64."""
    x = np.asarray(inputs["in_float"], dtype=np.float64)
    dim = int(inputs.get("dim", DIM))
    total = x.size // dim
    powers = np.array([PHI ** -(j + 1) for j in range(dim)], dtype=np.float64)
    return np.array(
        [float(np.dot(x[i * dim : (i + 1) * dim], powers)) for i in range(total)],
        dtype=np.float64,
    )


def emit_phi_lattice_batch() -> Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]:
    def run(inputs: Dict[str, Any], dispatch: Dict[str, Any]) -> Dict[str, Any]:
        return {"projection": _phi_lattice_batch(inputs)}

    return run


def emit_t_phi_sum_u8() -> Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]:
    """q^T x mod 256 on folded bytes — turing_core is the oracle."""

    def run(inputs: Dict[str, Any], dispatch: Dict[str, Any]) -> Dict[str, Any]:
        import turing_core

        folded = bytes(inputs["folded"])
        original_len = int(inputs["original_len"])
        weights = list(inputs["weights"])
        return {
            "dot": turing_core.folded_modular_dot(folded, original_len, weights),
            "streamed": list(turing_core.iter_original_u8(folded, original_len)),
        }

    return run


_CPU_EMITTERS: Dict[str, Callable[[], Callable]] = {
    "sha256d_scan": emit_sha256d_scan,
    "sha256d_m32": emit_sha256d_m32,
    "sha256d_gold": emit_sha256d_gold,
    "unified_punch": emit_unified_punch,
    "lucas_pisot_scale": emit_lucas_pisot_scale,
    "exact_hadamard": emit_exact_hadamard,
    "poincare_fold": lambda: _emit_punch(0x08),
    "poincare_unfold": lambda: _emit_punch(0x09),
    "geodesic": lambda: _emit_punch(0x0A),
    "golden_ontology_transform": emit_golden_ontology_transform,
    "grover_iterate": emit_grover_iterate,
    "cnormsq": emit_cnormsq,
    "phi_lattice_batch": emit_phi_lattice_batch,
    "t_phi_sum_u8": emit_t_phi_sum_u8,
}


def emit_cpu(spec_name: str) -> Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]:
    """Return the CPU reference callable for ``spec_name`` (alias-aware)."""
    from hyba.math_ir.specs import get_spec

    spec = get_spec(spec_name)
    factory = _CPU_EMITTERS.get(spec.name)
    if factory is None:
        raise KeyError(f"no CPU emitter for spec {spec.name!r}")
    return factory()


__all__ = ["emit_cpu", "emit_sha256d_scan", "emit_unified_punch"]
