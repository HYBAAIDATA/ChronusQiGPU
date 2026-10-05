"""Deterministic golden-ratio math primitives — multi-use substrate.

Elevate-to-documentation lock (19 July 2026):
  Research sources:
    - docs/phi_scaling/01_scaling_method.md
    - docs/phi_scaling/02_use_cases.md
    - euclid_morning/phi_universal_applications.py
    - HYBA Data sealed claims: capacity(d)=φ^d, reduction(d)=1−φ^{−d}

  φ is an *instruction* across HYBA, not a single codec trick:
    memory fold · GPU/resource scaling · Beatty scheduling · RL discount ·
    malloc free-lists · filter banks · federated weights · FEC parity spacing ·
    hierarchical exponents {10,12,15,18,20,25} · Lucas almost-integer ladder.

  This module is the shared mathematical core. Product surfaces (PULVINI,
  HERMES, EUCLID) import from here rather than re-deriving constants.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Canonical constants
# ---------------------------------------------------------------------------

PHI: float = (1.0 + math.sqrt(5.0)) / 2.0
PSI: float = (1.0 - math.sqrt(5.0)) / 2.0  # algebraic conjugate |ψ|<1
PHI_INV: float = PHI - 1.0  # = 1/φ
PHI_INV_2: float = PHI**-2
PHI_INV_3: float = PHI**-3
PHI_INV_4: float = PHI**-4
PHI_SQ: float = PHI + 1.0  # = φ²
PHI_WEIGHT_NORM: float = PHI_INV_2 + PHI_INV_3 + PHI_INV_4
SQRT5: float = math.sqrt(5.0)
LOG_PHI: float = math.log(PHI)
LOG10_PHI: float = math.log10(PHI)  # ≈ 0.20899 — +5 exponents ≈ 1 decade

# Research ladder (docs/phi_scaling + core.constants hierarchical exponents)
GREAT_SCALER_EXPONENTS: tuple[int, ...] = (10, 12, 15, 18, 20)
HIERARCHICAL_EXPONENTS: tuple[int, ...] = (10, 12, 15, 18, 20, 25)

# Fibonacci F_1=1, F_2=1, … (1-indexed style common in product code starts at 1,2,3…)
FIBONACCI: tuple[int, ...] = (
    1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610, 987,
    1597, 2584, 4181, 6765, 10946, 17711, 28657, 46368, 75025,
    121393, 196418, 317811, 514229, 832040, 1346269,
)

# Lucas L_0=2, L_1=1, L_2=3, … — almost-integers of φ^n
LUCAS: tuple[int, ...] = (
    2, 1, 3, 4, 7, 11, 18, 29, 47, 76, 123, 199, 322, 521, 843,
    1364, 2207, 3571, 5778, 9349, 15127, 24476, 39603, 64079,
    103682, 167761, 271443, 439204, 710647, 1149851,
)

CONTROL_CONSTANTS: tuple[float, ...] = (PHI, math.pi, math.e, math.sqrt(2.0), 1.0)

# Phyllotaxis golden angle (radians / degrees)
GOLDEN_ANGLE_RAD: float = 2.0 * math.pi * PHI_INV_2  # 2π/φ²
GOLDEN_ANGLE_DEG: float = 360.0 * PHI_INV_2  # ≈ 137.507764…


# ---------------------------------------------------------------------------
# Serialization / seals
# ---------------------------------------------------------------------------

def canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def normalize(values: Iterable[float]) -> List[float]:
    raw = [max(0.0, float(value)) for value in values]
    total = sum(raw)
    if total <= 0.0:
        raise ValueError("cannot normalize an all-zero vector")
    return [value / total for value in raw]


def inverse_phi_distribution(size: int) -> List[float]:
    """φ^{-k} weights, normalized — federated / staleness / priority decay."""
    if size <= 0:
        raise ValueError("size must be positive")
    return normalize(PHI**-idx for idx in range(size))


def lucas_ratio_tail(length: int = 10) -> List[float]:
    if length <= 0 or length >= len(LUCAS):
        raise ValueError("length must be between 1 and len(LUCAS)-1")
    start = len(LUCAS) - length - 1
    return [LUCAS[i + 1] / LUCAS[i] for i in range(start, len(LUCAS) - 1)]


# ---------------------------------------------------------------------------
# Core number-theoretic primitives
# ---------------------------------------------------------------------------

def fibonacci(n: int) -> int:
    """F_n with F_0=0, F_1=1."""
    if n < 0:
        raise ValueError("n must be non-negative")
    if n == 0:
        return 0
    if n == 1:
        return 1
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b


def lucas(n: int) -> int:
    """L_n with L_0=2, L_1=1. Exact integer; φ^n ≈ L_n with residual ψ^n."""
    if n < 0:
        raise ValueError("n must be non-negative")
    if n == 0:
        return 2
    if n == 1:
        return 1
    a, b = 2, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b


def phi_power(n: float) -> float:
    return PHI**float(n)


def psi_power(n: float) -> float:
    return PSI**float(n)


def binet_fibonacci(n: int) -> float:
    """Binet form F_n ≈ (φ^n − ψ^n)/√5."""
    return (phi_power(n) - psi_power(n)) / SQRT5


def binet_lucas(n: int) -> float:
    """Binet–Lucas: L_n = φ^n + ψ^n."""
    return phi_power(n) + psi_power(n)


@dataclass(frozen=True)
class PhiScalerResult:
    """Result of the four-step φ-power scaling method (docs/phi_scaling/01)."""

    n: int
    base: float
    scaled: float
    lucas_integer: int
    residual: float  # φ^n − L_n = −ψ^n  (since L_n = φ^n + ψ^n)
    relative_error: float
    domain_hint: str

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


DOMAIN_HINTS: Dict[int, str] = {
    10: "biology_branching_cell_counts",
    12: "finance_retracement_s_curves",
    15: "astronomy_orbital_resonance",
    18: "acoustics_solar_temperature",
    20: "information_theory_compression",
    25: "sovereign_governance_scale",
}


def great_scaler(n: int, base: float = 1.0) -> PhiScalerResult:
    """Apply the research ladder scaler: y = base · φ^n ≈ base · L_n."""
    if n < 0:
        raise ValueError("n must be non-negative")
    ln = lucas(n)
    exact = float(base) * phi_power(n)
    residual = phi_power(n) - float(ln)
    rel = abs(residual) / phi_power(n) if n > 0 else 0.0
    return PhiScalerResult(
        n=n,
        base=float(base),
        scaled=exact,
        lucas_integer=ln,
        residual=residual,
        relative_error=rel,
        domain_hint=DOMAIN_HINTS.get(n, "general_phi_power"),
    )


def pick_scaler_exponent(target_ratio: float) -> int:
    """Step 1 of scaling method: n = round(log(M/x) / log φ)."""
    if target_ratio <= 0:
        raise ValueError("target_ratio must be positive")
    n = int(round(math.log(float(target_ratio)) / LOG_PHI))
    return max(0, n)


def scale_to_magnitude(base: float, target: float) -> PhiScalerResult:
    """Full four-step method for scaling base toward target magnitude."""
    ratio = float(target) / float(base) if base != 0 else float(target)
    n = pick_scaler_exponent(abs(ratio))
    # Snap to nearest great-scaler exponent when close
    if GREAT_SCALER_EXPONENTS:
        nearest = min(GREAT_SCALER_EXPONENTS, key=lambda e: abs(e - n))
        if abs(nearest - n) <= 1:
            n = nearest
    return great_scaler(n, base=base)


# ---------------------------------------------------------------------------
# PULVINI working-set law (sealed claims)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class WorkingSetLaw:
    """capacity(d)=φ^d, reduction(d)=1−φ^{−d}. Fold depth is the φ power d."""

    d: int
    capacity: float
    reduction: float
    reduction_pct: float
    metric_row: str  # M1 / M2 / higher

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def working_set_law(d: int) -> WorkingSetLaw:
    if int(d) < 0:
        raise ValueError("d must be non-negative")
    d = int(d)
    cap = PHI**d
    red = 1.0 - (PHI**-d if d > 0 else 0.0)
    if d == 2:
        row = "M1"
    elif d == 4:
        row = "M2"
    elif d > 4:
        row = "M3+"
    else:
        row = f"d={d}"
    return WorkingSetLaw(
        d=d,
        capacity=cap,
        reduction=red,
        reduction_pct=red * 100.0,
        metric_row=row,
    )


def fold_weight_pair(scheme: str = "powers") -> Tuple[float, float]:
    """Production weight schemes for the 2×2 φ-fold matrix."""
    s = (scheme or "powers").lower()
    if s in ("powers", "a", "default", "production"):
        return PHI_INV, PHI_INV_2  # w1=1/φ, w2=1/φ²
    if s in ("trigonometric", "b", "unitary", "trig"):
        # Scheme B: cos(π/φ), sin(π/φ) — det = −1
        w1 = math.cos(math.pi / PHI)
        w2 = math.sin(math.pi / PHI)
        return w1, w2
    raise ValueError(f"unknown weight scheme: {scheme!r}")


def fold_matrix_det(scheme: str = "powers") -> float:
    w1, w2 = fold_weight_pair(scheme)
    return -(w1 * w1 + w2 * w2)


# ---------------------------------------------------------------------------
# Beatty sequences — zero-collision partition (φ-Scheduler)
# ---------------------------------------------------------------------------

def beatty_sequence(n_terms: int, r: float = PHI) -> List[int]:
    """⌊k·r⌋ for k=1..n_terms."""
    if n_terms < 0:
        raise ValueError("n_terms must be non-negative")
    return [int(math.floor(k * float(r))) for k in range(1, n_terms + 1)]


def beatty_partition(n_terms: int) -> Dict[str, List[int]]:
    """⌊kφ⌋ and ⌊kφ²⌋ partition the positive integers (Beatty theorem)."""
    a = beatty_sequence(n_terms, PHI)
    b = beatty_sequence(n_terms, PHI_SQ)
    return {"floor_k_phi": a, "floor_k_phi_sq": b, "disjoint": True, "cover_N": True}


def beatty_assign(item_index: int, n_workers: int = 2) -> int:
    """Assign work item to a worker via Beatty partition (n_workers=2 canonical)."""
    if item_index < 1:
        raise ValueError("item_index must be >= 1 (1-based Beatty)")
    if n_workers < 2:
        return 0
    if n_workers == 2:
        # Membership test: item in A iff exists k: floor(kφ)=item
        # Equivalent: floor(ceil(item*φ)/φ) style — use inverse
        k = int(math.ceil(item_index * PHI_INV))
        if int(math.floor(k * PHI)) == item_index:
            return 0
        return 1
    # General: φ-weighted round-robin among n_workers
    return int(math.floor(item_index * PHI)) % n_workers


# ---------------------------------------------------------------------------
# HIGH-feasibility application primitives (universal discovery)
# ---------------------------------------------------------------------------

def rl_discount_gamma() -> float:
    """Optimal infinite-horizon discount γ = φ⁻¹ ≈ 0.618."""
    return PHI_INV


def federated_staleness_weights(n_clients: int) -> List[float]:
    """φ-FedAvg: most recent φ⁻¹, next φ⁻², …"""
    return inverse_phi_distribution(n_clients)


def mutation_rate(generation: int, floor: float = 1e-4) -> float:
    """φ-EA: mutation = max(floor, φ^{−(generation+1)})."""
    if generation < 0:
        raise ValueError("generation must be non-negative")
    return max(float(floor), PHI ** (-(generation + 1)))


def fibonacci_block_sizes(n_sizes: int, base_bytes: int = 1024) -> List[int]:
    """φ-Malloc free-list sizes: base · F_k for F = 2,3,5,8,… (skip 0/1)."""
    if n_sizes <= 0:
        raise ValueError("n_sizes must be positive")
    if base_bytes <= 0:
        raise ValueError("base_bytes must be positive")
    sizes = []
    # F_3=2, F_4=3, F_5=5, … — practical buddy sizes above 1×base
    for i in range(n_sizes):
        sizes.append(int(base_bytes) * fibonacci(i + 3))
    return sizes


def nearest_fibonacci(value: int) -> int:
    if value <= 0:
        return 1
    best = 1
    n = 1
    while True:
        f = fibonacci(n)
        if f >= value:
            # pick closer of f and previous
            prev = fibonacci(n - 1) if n > 1 else 1
            return f if abs(f - value) <= abs(prev - value) else prev
        best = f
        n += 1
        if n > 80:
            return best


def phi_net_widths(n_layers: int, base: int = 34) -> List[int]:
    """Layer widths along Fibonacci / φ^k ladder."""
    if n_layers <= 0:
        raise ValueError("n_layers must be positive")
    # Find Fibonacci index near base
    widths = []
    # start at nearest fib to base
    start = nearest_fibonacci(base)
    # locate index
    idx = 1
    while fibonacci(idx) < start and idx < 40:
        idx += 1
    for i in range(n_layers):
        widths.append(fibonacci(idx + i))
    return widths


def filter_bank_centers(f0: float, n_bands: int) -> List[float]:
    """φ-Filter: center frequencies f0 · φ^k."""
    if f0 <= 0 or n_bands <= 0:
        raise ValueError("f0 and n_bands must be positive")
    return [float(f0) * phi_power(k) for k in range(n_bands)]


def fec_parity_positions(block_len: int, n_parity: int) -> List[int]:
    """φ-FEC: parity bit indices via Beatty spacing inside [0, block_len)."""
    if block_len <= 0 or n_parity <= 0:
        raise ValueError("block_len and n_parity must be positive")
    if n_parity >= block_len:
        return list(range(block_len))
    positions = []
    for k in range(1, n_parity + 1):
        # map Beatty into block
        pos = int(math.floor(k * PHI * block_len / (n_parity * PHI + 1))) % block_len
        positions.append(pos)
    # unique stable order
    return sorted(set(positions))


def btree_fanout(preferred: int = 89) -> int:
    """φ-Index: snap B-Tree fanout to nearest Fibonacci."""
    return nearest_fibonacci(preferred)


def mixed_strategy_weights() -> Tuple[float, float]:
    """φ-Strategy: (φ⁻¹, φ⁻²) normalized to sum 1 (= already φ⁻¹+φ⁻²=1)."""
    return PHI_INV, PHI_INV_2


def load_shed_fractions(n_steps: int) -> List[float]:
    """φ-Grid: successive shed fractions φ^{-k}, normalized to sum≤1."""
    raw = [PHI**(-(k + 1)) for k in range(n_steps)]
    s = sum(raw)
    if s > 1.0:
        raw = [x / s for x in raw]
    return raw


def finance_retracement_levels() -> Dict[str, float]:
    """Classic Fibonacci retracement levels from powers of 1/φ."""
    return {
        "0.236": PHI_INV_3,
        "0.382": PHI_INV_2,
        "0.500": 0.5,
        "0.618": PHI_INV,
        "0.786": math.sqrt(PHI_INV),  # common extension ≈0.786
        "1.000": 1.0,
        "1.618": PHI,
        "2.618": PHI_SQ,
    }


def hierarchical_gap(exponent: int, delta0: Optional[float] = None) -> float:
    """Δ_n = (3−φ) · φ^k — hierarchical gap family."""
    d0 = (3.0 - PHI) if delta0 is None else float(delta0)
    return d0 * phi_power(int(exponent))


def verify_identities(tol: float = 1e-12) -> Dict[str, Any]:
    """Algebraic identity battery — must pass before any external claim."""
    checks = {}
    checks["phi_quadratic"] = abs(PHI * PHI - (PHI + 1.0)) < tol
    checks["phi_inv"] = abs(PHI_INV - (PHI - 1.0)) < tol and abs(PHI_INV - 1.0 / PHI) < tol
    checks["phi_inv_sum"] = abs(PHI_INV + PHI_INV_2 - 1.0) < tol
    checks["psi_conjugate"] = abs(PHI + PSI - 1.0) < tol and abs(PHI * PSI + 1.0) < tol
    # Lucas identity: L_n = φ^n + ψ^n  ⇒  residual φ^n − L_n = −ψ^n
    for n in GREAT_SCALER_EXPONENTS:
        r = great_scaler(n)
        checks[f"lucas_residual_n{n}"] = abs(r.residual + psi_power(n)) < 1e-9
        checks[f"lucas_rel_err_n{n}"] = r.relative_error < 0.01
    # Working-set law M1/M2
    m1 = working_set_law(2)
    m2 = working_set_law(4)
    checks["m1_capacity"] = abs(m1.capacity - PHI**2) < tol
    checks["m1_reduction"] = abs(m1.reduction - (1.0 - PHI**-2)) < tol
    checks["m2_capacity"] = abs(m2.capacity - PHI**4) < tol
    checks["m2_reduction"] = abs(m2.reduction - (1.0 - PHI**-4)) < tol
    # Beatty partition disjointness sample
    part = beatty_partition(50)
    a, b = set(part["floor_k_phi"]), set(part["floor_k_phi_sq"])
    checks["beatty_disjoint_sample"] = len(a & b) == 0
    # Fold matrix invertible
    checks["fold_det_powers_nonzero"] = abs(fold_matrix_det("powers")) > 0.1
    checks["fold_det_trig_unit"] = abs(abs(fold_matrix_det("trigonometric")) - 1.0) < 1e-9
    checks["all_pass"] = all(checks.values())
    checks["seal"] = canonical_sha256({k: bool(v) for k, v in checks.items() if k != "seal"})
    return checks


def multi_use_manifest() -> Dict[str, Any]:
    """Machine-readable map: documented use → primitive."""
    return {
        "phi": PHI,
        "psi": PSI,
        "doctrine": "φ is an instruction across HYBA — not a single codec trick",
        "sealed_working_set_law": {
            "capacity": "phi^d",
            "reduction": "1 - phi^{-d}",
            "M1_d": 2,
            "M2_d": 4,
        },
        "great_scaler_exponents": list(GREAT_SCALER_EXPONENTS),
        "uses": {
            "pulvini_memory_fold": ["working_set_law", "fold_weight_pair", "fold_matrix_det"],
            "hermes_gpu_scaling": ["great_scaler", "fibonacci", "GoldenRatioScaler"],
            "beatty_scheduler": ["beatty_sequence", "beatty_partition", "beatty_assign"],
            "rl_discount": ["rl_discount_gamma"],
            "phi_malloc": ["fibonacci_block_sizes", "nearest_fibonacci"],
            "phi_net_widths": ["phi_net_widths"],
            "phi_fedavg": ["federated_staleness_weights", "inverse_phi_distribution"],
            "phi_filter_bank": ["filter_bank_centers"],
            "phi_fec": ["fec_parity_positions"],
            "phi_index": ["btree_fanout"],
            "phi_ea_mutation": ["mutation_rate"],
            "phi_grid_shed": ["load_shed_fractions"],
            "finance_retracement": ["finance_retracement_levels"],
            "hierarchical_gaps": ["hierarchical_gap", "HIERARCHICAL_EXPONENTS"],
            "mixed_strategy": ["mixed_strategy_weights"],
            "phyllotaxis_angle": ["GOLDEN_ANGLE_DEG", "GOLDEN_ANGLE_RAD"],
        },
        "identity_battery": "verify_identities",
        "research_paths": [
            "docs/phi_scaling/01_scaling_method.md",
            "docs/phi_scaling/02_use_cases.md",
            "euclid_morning/phi_universal_applications.py",
        ],
    }


__all__ = [
    "PHI",
    "PSI",
    "PHI_INV",
    "PHI_INV_2",
    "PHI_INV_3",
    "PHI_INV_4",
    "PHI_SQ",
    "PHI_WEIGHT_NORM",
    "SQRT5",
    "LOG_PHI",
    "LOG10_PHI",
    "GREAT_SCALER_EXPONENTS",
    "HIERARCHICAL_EXPONENTS",
    "FIBONACCI",
    "LUCAS",
    "CONTROL_CONSTANTS",
    "GOLDEN_ANGLE_RAD",
    "GOLDEN_ANGLE_DEG",
    "canonical_json",
    "canonical_sha256",
    "normalize",
    "inverse_phi_distribution",
    "lucas_ratio_tail",
    "fibonacci",
    "lucas",
    "phi_power",
    "psi_power",
    "binet_fibonacci",
    "binet_lucas",
    "PhiScalerResult",
    "great_scaler",
    "pick_scaler_exponent",
    "scale_to_magnitude",
    "WorkingSetLaw",
    "working_set_law",
    "fold_weight_pair",
    "fold_matrix_det",
    "beatty_sequence",
    "beatty_partition",
    "beatty_assign",
    "rl_discount_gamma",
    "federated_staleness_weights",
    "mutation_rate",
    "fibonacci_block_sizes",
    "nearest_fibonacci",
    "phi_net_widths",
    "filter_bank_centers",
    "fec_parity_positions",
    "btree_fanout",
    "mixed_strategy_weights",
    "load_shed_fractions",
    "finance_retracement_levels",
    "hierarchical_gap",
    "verify_identities",
    "multi_use_manifest",
]
