"""KernelSpec registry — the ops the composed substrate knows how to route.

Each spec names its oracle: the module that defines correctness. GPU and
emitted backends must agree with the oracle bit-for-bit where the spec's
precision_bound demands it; hashlib sha256d ≤ target is the sole accept
authority for every mining op.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple


@dataclass(frozen=True)
class KernelSpec:
    """One portable op: math + signature + capability demand + bound.

    - ``math``: human description of the operation's semantics.
    - ``signature``: ordered (name, element type) parameter sketch matching
      the canonical kernel/entry for the op.
    - ``required_capabilities``: keys a device must carry in its measured
      capability map before the executor may bind it.
    - ``precision_bound``: ``exact`` (integer/exact-algebra), ``f32``,
      ``f64``, or ``u64-mod`` (wraps mod 2^64 like the kernels).
    - ``lucas_dispatch``: chunking discipline — ``ladder`` (chunk snaps to a
      ladder index), ``epoch32`` (multiples of 32 whole m32 epochs),
      ``serial`` (no dispatch chunking).
    - ``entry``: canonical kernel/entry name (must match kernels/*.cl when
      one exists).
    - ``canonical_source``: path of the canonical .cl source for this op,
      relative to the repo root; None when no canonical kernel exists and
      emitters must generate one (truth_class "emitted").
    - ``oracle``: dotted "module:attr" reference checked in tests/executor.
    """

    name: str
    math: str
    signature: Tuple[Tuple[str, str], ...]
    required_capabilities: Tuple[str, ...] = ()
    precision_bound: str = "exact"
    lucas_dispatch: str = "ladder"
    entry: str = ""
    canonical_source: Optional[str] = None
    oracle: str = ""
    executor: str = "cpu"


KERNEL_SPECS: Dict[str, KernelSpec] = {
    "sha256d_scan": KernelSpec(
        name="sha256d_scan",
        math="Double-SHA256 nonce scan; winner iff sha256d(header|nonce) <= target",
        signature=(
            ("header", "uchar[76]"),
            ("base_nonce", "u32"),
            ("count", "u32"),
            ("target_hash", "uchar[32]"),
        ),
        required_capabilities=(),
        precision_bound="exact",
        lucas_dispatch="ladder",
        entry="bitcoin_sha256d_range",
        canonical_source="kernels/bitcoin_sha256d.cl",
        oracle="mining.hash_pipeline:double_sha256",
        executor="bitcoin_hasher",
    ),
    "sha256d_m32": KernelSpec(
        name="sha256d_m32",
        math="32-lane m32 grind; whole-epoch launches, Turing lane order",
        signature=(
            ("midstate", "uchar[32]"),
            ("tail", "uchar[12]"),
            ("base_nonce", "u32"),
            ("epochs", "u32"),
            ("hits", "u32[32]"),
        ),
        required_capabilities=("m32_lane_kernel",),
        precision_bound="exact",
        lucas_dispatch="epoch32",
        entry="bitcoin_sha256d_m32",
        canonical_source="kernels/bitcoin_sha256d.cl",
        oracle="mla1517.mining.solver:M32SearchSolver.candidates",
        executor="bitcoin_hasher",
    ),
    "sha256d_gold": KernelSpec(
        name="sha256d_gold",
        math=(
            "Golden-stride scan: nonce_i = (seed + i * floor(2^32/phi)) "
            "mod 2^32 — odd stride ⇒ bijective over the nonce domain; "
            "the intelligence layer orders the search via seed. "
            "Winner iff sha256d(header|nonce) <= target."
        ),
        signature=(
            ("header", "uchar[76]"),
            ("seed", "u32"),
            ("count", "u32"),
            ("target_hash", "uchar[32]"),
        ),
        required_capabilities=(),
        precision_bound="exact",
        lucas_dispatch="ladder",
        entry="bitcoin_sha256d_gold",
        canonical_source="kernels/bitcoin_sha256d.cl",
        oracle="hyba.math_ir.emit_cpu:emit_sha256d_gold",
        executor="bitcoin_hasher",
    ),
    "unified_punch": KernelSpec(
        name="unified_punch",
        math="Unified punch kernel — all 0x01..0x1C punch semantics",
        signature=(
            ("punch_ids", "u8[N]"),
            ("in_float", "f32[N*11]"),
            ("in_ulong", "u64[N*121]"),
            ("in_int", "i32[N]"),
            ("in_double", "f64[N]"),
        ),
        required_capabilities=(),
        precision_bound="f32",
        lucas_dispatch="ladder",
        entry="unified_punch_kernel",
        canonical_source="kernels/unified_punch_kernel.cl",
        oracle="Intelligence.unified_punch:UnifiedPunchHost._execute_cpu",
        executor="unified_punch_host",
    ),
    "lucas_pisot_scale": KernelSpec(
        name="lucas_pisot_scale",
        math="Exact fib/lucas/padovan value at a ladder scale index (u64)",
        signature=(("scale_index", "u32"), ("kind", "u32"), ("value", "u64")),
        required_capabilities=("lucas_ladder_kernel",),
        precision_bound="exact",
        lucas_dispatch="serial",
        entry="mla1517_lucas_pisot_scale",
        canonical_source="mla1517_platform_v3.4/kernels/mla1517_lucas_pisot_scale.cl",
        oracle="mla1517.core:fib",
        executor="ladder_executor",
    ),
    "exact_hadamard": KernelSpec(
        name="exact_hadamard",
        math="Exact H gate on a 2^n state vector (Q(sqrt2) amplitudes)",
        signature=(
            ("amplitudes", "ExactComplex[2^n]"),
            ("qubit", "u32"),
        ),
        required_capabilities=(),
        precision_bound="exact",
        lucas_dispatch="serial",
        entry="exact_hadamard_lucas_pisot_scale",
        canonical_source="mla1517_platform_v3.4/kernels/exact_quantum_kernel.cl",
        oracle="mla1517.quantum:ExactStateVector.apply_single",
        executor="exact_accelerator",
    ),
    "poincare_fold": KernelSpec(
        name="poincare_fold",
        math="x / sqrt(1 + ||x||^2) per 11-vector — fold into the ball (0x08)",
        signature=(("in_float", "f32[N*11]"), ("out_float", "f32[N*11]")),
        required_capabilities=(),
        precision_bound="f32",
        lucas_dispatch="ladder",
        entry="unified_punch_kernel",
        canonical_source="kernels/unified_punch_kernel.cl",
        oracle="Intelligence.unified_punch:UnifiedPunchHost._execute_cpu",
        executor="unified_punch_host",
    ),
    "poincare_unfold": KernelSpec(
        name="poincare_unfold",
        math="x / sqrt(1 - ||x||^2) per 11-vector — unfold from the ball (0x09)",
        signature=(("in_float", "f32[N*11]"), ("out_float", "f32[N*11]")),
        required_capabilities=(),
        precision_bound="f32",
        lucas_dispatch="ladder",
        entry="unified_punch_kernel",
        canonical_source="kernels/unified_punch_kernel.cl",
        oracle="Intelligence.unified_punch:UnifiedPunchHost._execute_cpu",
        executor="unified_punch_host",
    ),
    "geodesic": KernelSpec(
        name="geodesic",
        math="acosh(1 + 2|u-v|^2 / ((1-|u|^2)(1-|v|^2))) — Poincare distance (0x0A)",
        signature=(("in_float", "f32[N*11]"), ("out_float", "f32[N*11]")),
        required_capabilities=(),
        precision_bound="f32",
        lucas_dispatch="ladder",
        entry="unified_punch_kernel",
        canonical_source="kernels/unified_punch_kernel.cl",
        oracle="Intelligence.unified_punch:UnifiedPunchHost._execute_cpu",
        executor="unified_punch_host",
    ),
    "golden_ontology_transform": KernelSpec(
        name="golden_ontology_transform",
        math=(
            "Fibonacci butterfly y[k] = sum_n x[n] * F_{(n+k)%N} with Binet"
            " closure, Cassini identity, orthogonality bound"
        ),
        signature=(
            ("x_re", "i64[N]"),
            ("x_im", "i64[N]"),
            ("fib_basis", "i64[N]"),
            ("y_re", "i64[N]"),
            ("y_im", "i64[N]"),
        ),
        required_capabilities=(),
        precision_bound="exact",
        lucas_dispatch="ladder",
        entry="fibonacci_butterfly_kernel",
        canonical_source="kernels/golden_ontology_transform.cl",
        oracle="mla1517.core:fib",
        executor="unified_punch_host",
    ),
    "grover_iterate": KernelSpec(
        name="grover_iterate",
        math="k* = floor(pi/4 sqrt(N)) walk steps; winner = sha256d <= target",
        signature=(("header", "uchar[80]"), ("schedule", "u32[N]"), ("target", "u256")),
        required_capabilities=(),
        precision_bound="exact",
        lucas_dispatch="ladder",
        entry="",
        canonical_source=None,
        oracle="mining.search:GroverStyleSearch.search",
        executor="cpu",
    ),
    "cnormsq": KernelSpec(
        name="cnormsq",
        math="sum_j PHI^{-(j+1)} x_j^2 — PHI-weighted f32 norm squared (0x15)",
        signature=(("in_float", "f32[N*11]"), ("out_float", "f32[N*11]")),
        required_capabilities=(),
        precision_bound="f32",
        lucas_dispatch="ladder",
        entry="unified_punch_kernel",
        canonical_source="kernels/unified_punch_kernel.cl",
        oracle="Intelligence.unified_punch:UnifiedPunchHost._execute_cpu",
        executor="unified_punch_host",
    ),
    "phi_lattice_batch": KernelSpec(
        name="phi_lattice_batch",
        math="Per-vector PHI-power projection: out[k] = sum_j x[k][j] * PHI^{-(j+1)}",
        signature=(("in_float", "f32[N*11]"), ("out_float", "f32[N]")),
        required_capabilities=(),
        precision_bound="f64",
        lucas_dispatch="ladder",
        entry="",
        canonical_source=None,
        oracle="hyba.math_ir.emit_cpu:_phi_lattice_batch",
        executor="cpu",
    ),
    "t_phi_sum_u8": KernelSpec(
        name="t_phi_sum_u8",
        math="q^T x mod 256 read directly off folded bytes (no un-fold buffer)",
        signature=(
            ("folded", "u8[M]"),
            ("original_len", "u32"),
            ("weights", "u8[N]"),
        ),
        required_capabilities=(),
        precision_bound="exact",
        lucas_dispatch="serial",
        entry="",
        canonical_source=None,
        oracle="turing_core:folded_modular_dot",
        executor="cpu",
    ),
}

# Op alias → canonical spec name; routing/attestation use canonical names.
SPEC_ALIASES: Dict[str, str] = {
    "sha256d_grind": "sha256d_scan",
    "sha256d_window": "sha256d_scan",
    "unified_punch_score": "unified_punch",
    "score": "unified_punch",
    "m32_grind": "sha256d_m32",
    "search": "grover_iterate",
    "grover_search": "grover_iterate",
    "poincare_distance": "geodesic",
    "manifold_compute": "cnormsq",
}


def get_spec(name: str) -> KernelSpec:
    """Resolve an op name or alias to its KernelSpec; fail loudly on unknown."""
    canonical = SPEC_ALIASES.get(name, name)
    spec = KERNEL_SPECS.get(canonical)
    if spec is None:
        raise KeyError(f"no KernelSpec registered for {name!r}")
    return spec
