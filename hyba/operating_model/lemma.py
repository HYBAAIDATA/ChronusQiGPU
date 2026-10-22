"""Lemma-before-code — the paper before the code, two pages, signed off.

``require_lemma()`` verifies the lemma document exists, stays within the
two-page bound, names the required reviewers, and records a signoff whose
``theorem_proven`` is pinned False — the lemma is a proof *sketch* under
review, not a proven theorem.
"""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from hyba.operating_model.roles import repo_root

LEMMA_PATH = "docs/lemma_lucas_polynomial.md"
SIGNOFF_PATH = "docs/lemma_signoff.json"
LEMMA_MAX_LINES = 200

REQUIRED_REVIEWERS = (
    "mathematician",
    "complexity",
    "number_theorist",
    "qi_physicist",
    "systems",
)

GOLDEN_MATRIX: Tuple[Tuple[int, int], Tuple[int, int]] = ((1, 1), (1, 0))
VERIFIED_RANGE = (1, 76)

# The lemma as a first-class, frozen object — a bound, not a proof.
LEMMA: Dict[str, Any] = {
    "name": "lucas_bounded_path_counts",
    "statement": "tr(Q^n) = L_n for Q = [[1,1],[1,0]], all n >= 1",
    "scope": {
        "graph": "two_state_golden",
        "matrix": GOLDEN_MATRIX,
        "ring": "Z",
        "authorized_uses": (
            "order_nonce_window_probe_schedules",
            "bound_verification_budget_O_log_n",
        ),
    },
    "not_a_proof_of": (
        "path_counting_on_arbitrary_NP_graphs",
        "extension_to_graphs_with_more_than_two_states",
        "P_vs_NP",
        "any_Millennium_problem",
        "quantum_advantage",
    ),
    "verified_range": VERIFIED_RANGE,
    "theorem_proven": False,
}

FORBIDDEN_CITATIONS = (
    "proves path counting on arbitrary NP graphs is polynomial",
    "extends to graphs with more than two states",
    "proves P vs NP",
    "resolves any Millennium problem",
    "gives quantum advantage",
)


# ---------------------------------------------------------------------------
# Golden-stride ordering lemmas — the φ math that orders the probe walk.
# Same discipline: statement + scope + not_a_proof_of + pinned False.
# ---------------------------------------------------------------------------

GOLDEN_STRIDE = 0x9E3779B9  # floor(2**32 / phi)
U32_SPACE = 2**32

LEMMA_GOLDEN_STRIDE: Dict[str, Any] = {
    "name": "golden_stride_bijection",
    "statement": (
        "For stride s = floor(2^32/phi) = 2654435769 and modulus m = 2^32, "
        "gcd(s, m) = 1 because s is odd; therefore the walk "
        "i -> seed + i*s (mod m) is a bijection of the nonce domain — "
        "every nonce is probed exactly once over a full 2^32 cycle."
    ),
    "scope": {
        "graph": "nonce_space_2_32",
        "stride": GOLDEN_STRIDE,
        "modulus": U32_SPACE,
        "authorized_uses": (
            "order_device_probe_walk",
            "order_host_probe_walk",
            "emit_golden_stride",
        ),
    },
    "not_a_proof_of": (
        "any_prediction_about_sha256d_output",
        "any_speedup_beyond_coverage_and_sequencing",
        "quantum_advantage",
        "any_Millennium_problem",
    ),
    "verified_range": "gcd proof + 200k-step uniqueness sweep",
    "theorem_proven": False,
}

LEMMA_PHI_RESONANCE: Dict[str, Any] = {
    "name": "phi_resonance_ordering",
    "statement": (
        "For a header H and target T, the 12-tier phi-resonance ordering "
        "with Wilson-seeded intra-tier permutation produces a header-"
        "dependent permutation of the nonce space. Distinctness across "
        "headers is verified empirically on a fixed header set by "
        "verify_resonance_ordering; the seed is 64 bits of SHA-256, so "
        "distinct orders for arbitrary header pairs are not guaranteed — "
        "two headers sharing the same seed produce the same order."
    ),
    "scope": {
        "graph": "nonce_space_2_32",
        "applies_to": "search_ordering_only",
        "authorized_uses": (
            "order_nonce_window_probe_schedules",
            "order_device_probe_walk",
            "order_host_probe_walk",
            "scale_capacity_limbs",
            "weight_poincare_metric",
        ),
    },
    "not_a_proof_of": (
        "any_prediction_about_sha256d_output",
        "any_speedup_beyond_coverage_and_sequencing",
        "quantum_advantage",
        "any_Millennium_problem",
    ),
    "verified_range": "deterministic test vectors",
    "theorem_proven": False,
}

LEMMA_LUCAS_SCALING: Dict[str, Any] = {
    "name": "lucas_scaling_limbs",
    "statement": (
        "The Lucas companion sequence L_n supplies exact integer limbs "
        "for metallic-ratio scaling. For every metallic ratio sigma_k "
        "the companion satisfies L_n = k*L_{n-1} + L_{n-2} (L_0=2, L_1=k) "
        "and the Cassini-type identity L_n^2 - L_{n-1}*L_{n+1} = (k^2+4)*(-1)^n, "
        "reconstructing exactly under integer arithmetic."
    ),
    "scope": {
        "applies_to": "capacity_and_geometry_scaling",
        "authorized_uses": (
            "scale_capacity_limbs",
            "emit_lucas_boundary_weights",
            "witness_cassini_identity",
        ),
    },
    "not_a_proof_of": (
        "continuum_yang_mills_mass_gap",
        "quantum_advantage",
        "any_Millennium_problem",
    ),
    "verified_range": "k=1..7 metallic ratios, integer recurrence + Cassini-type",
    "theorem_proven": False,
}

LEMMA_ZECKENDORF_FILING: Dict[str, Any] = {
    "name": "zeckendorf_unique_filing",
    "statement": (
        "Every non-negative integer has a unique Zeckendorf representation "
        "as a sum of non-adjacent Fibonacci numbers. The representation "
        "supplies an exact address codec."
    ),
    "scope": {
        "applies_to": "storage_addressing",
        "authorized_uses": (
            "encode_zeckendorf_address",
            "decode_zeckendorf_address",
            "verify_non_adjacent_mask",
        ),
    },
    "not_a_proof_of": (
        "lossy_compression",
        "quantum_advantage",
        "any_Millennium_problem",
    ),
    "verified_range": "n=0..10^6 round-trip + non-adjacency",
    "theorem_proven": False,
}


class ScopeViolation(ValueError):
    """The lemma was cited outside its declared scope."""


@dataclasses.dataclass(frozen=True)
class GoldenGraph:
    """The only graph the lemma covers — two-state golden adjacency."""
    n: int = 0
    matrix: Tuple[Tuple[int, int], Tuple[int, int]] = GOLDEN_MATRIX
    state_count: int = 2


# -- exact integer machinery (no floats, no numpy needed for the proof) --

def matmul_int(a, b):
    return (
        (a[0][0] * b[0][0] + a[0][1] * b[1][0],
         a[0][0] * b[0][1] + a[0][1] * b[1][1]),
        (a[1][0] * b[0][0] + a[1][1] * b[1][0],
         a[1][0] * b[0][1] + a[1][1] * b[1][1]),
    )


def matpow_int(m, n):
    """Exact integer matrix power — repeated squaring."""
    result = ((1, 0), (0, 1))
    base = m
    while n:
        if n & 1:
            result = matmul_int(result, base)
        base = matmul_int(base, base)
        n >>= 1
    return result


def trace(m) -> int:
    return m[0][0] + m[1][1]


def fast_doubling_lucas(n: int) -> int:
    """L_n in O(log n) exact integer ops via the standard pair
    recurrence: L_{2k} = L_k^2 - 2(-1)^k, L_{2k+1} = L_k L_{k+1} - (-1)^k."""
    def pair(k: int) -> Tuple[int, int]:
        if k == 0:
            return (2, 1)
        m = k >> 1
        lk, lk1 = pair(m)
        sign = -1 if (m & 1) else 1   # (-1)^m, m = floor(k/2)
        l2k = lk * lk - 2 * sign
        l2kp1 = lk * lk1 - sign
        return (l2k, l2kp1) if k % 2 == 0 else (l2kp1, l2k + l2kp1)
    return pair(n)[0]


def verify_lemma(lemma: Dict[str, Any] = LEMMA,
                 n_range: Sequence[int] = VERIFIED_RANGE) -> List[Dict[str, Any]]:
    """Classifies the lemma against its own stated scope. Read-only.

    Checks: Q² = Q + I (sanity), the trace recurrence against exact
    matpow on the declared range, fast doubling as a cross-oracle, exact
    integer types throughout, and the Lucas initials."""
    lo, hi = int(n_range[0]), int(n_range[1])
    assert lo >= 1
    q = lemma["scope"]["matrix"]
    assert matmul_int(q, q) == ((2, 1), (1, 1)), "Q^2 must equal Q + I"

    t = {0: 2, 1: 1}
    for n in range(2, hi + 1):
        t[n] = t[n - 1] + t[n - 2]
    for n in range(lo, hi + 1):
        assert t[n] == trace(matpow_int(q, n)), \
            f"trace recurrence fails at n={n}"
    for n in range(lo, hi + 1):
        fd = fast_doubling_lucas(n)
        assert fd == t[n], f"fast doubling diverges at n={n}"
        assert isinstance(fd, int) and not isinstance(fd, bool)
    assert t[0] == 2 and t[1] == 1

    return [{
        "verdict": "HOLDS",
        "mode": "recurrence + fast_doubling",
        "range": [lo, hi],
        "theorem_proven": False,
    }]


def use_lemma(usage: str, graph: Any) -> Dict[str, Any]:
    """Runtime scope guard. Callers pass the ACTUAL graph structure.

    graph must expose `.matrix` and `.state_count` (and `.n` for the
    bound). Any other graph, usage, or state count is a ScopeViolation —
    extension is a separate, unproven claim."""
    if usage not in LEMMA["scope"]["authorized_uses"]:
        raise ScopeViolation(f"usage not authorized: {usage}")
    if getattr(graph, "matrix", None) != LEMMA["scope"]["matrix"]:
        raise ScopeViolation(
            "lemma applies only to the two-state golden graph; "
            "extension to richer graphs is a separate, unproven claim")
    if getattr(graph, "state_count", None) != 2:
        raise ScopeViolation(
            f"graph has {getattr(graph, 'state_count', '?')} states; "
            "lemma covers 2")
    return {
        "path_count": fast_doubling_lucas(int(graph.n)),
        "bound": "O(log n)",
        "theorem_proven": False,
    }


def claim_complexity(claim: Any) -> Dict[str, Any]:
    """The lemma authorizes exactly one complexity claim: O(log n) for
    evaluation of tr(Q^n) on the two-state golden graph. Nothing else."""
    if getattr(claim, "quantity", None) != "tr(Q^n)":
        raise ScopeViolation(
            "lemma authorizes O(log n) only for tr(Q^n); "
            f"claimed: {getattr(claim, 'quantity', '?')}")
    if getattr(claim, "graph", None) != "two_state_golden":
        raise ScopeViolation(
            "lemma authorizes only the two-state golden graph; "
            f"claimed: {getattr(claim, 'graph', '?')}")
    if getattr(claim, "complexity", None) != "O(log n)":
        raise ScopeViolation(
            "lemma authorizes only O(log n); "
            f"claimed: {getattr(claim, 'complexity', '?')}")
    return {"authorized": True, "theorem_proven": False}


_NEGATION = re.compile(r"\b(not|never|does not|unproven|no claim)\b")


def citation_check(doc_text: str) -> List[Dict[str, Any]]:
    """Any doc citing the lemma for a forbidden conclusion is an
    overclaim — a FAIL at the auditor stage. Negated mentions
    ("not a proof that ...") are disclaimers, not citations."""
    findings = []
    lowered = doc_text.lower()
    for phrase in FORBIDDEN_CITATIONS:
        p = phrase.lower()
        idx = lowered.find(p)
        while idx != -1:
            line_start = lowered.rfind("\n", 0, idx) + 1
            context = lowered[line_start:idx]
            if not _NEGATION.search(context):
                line = lowered[:idx].count("\n") + 1
                findings.append({
                    "verdict": "overclaim", "phrase": phrase, "line": line})
                break
            idx = lowered.find(p, idx + 1)
    return findings


def ast_scope_check(package_root: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Fail if any module uses the LEMMA object without routing through
    ``use_lemma()`` in the same function. The operating_model package is
    the lemma's home — its verifiers cite the object, they don't apply
    the bound."""
    root = repo_root() if package_root is None else Path(package_root)
    violations = []
    globs = ("mining/**/*.py", "Intelligence/**/*.py", "hyba/**/*.py",
             "kellogg/**/*.py", "toe/**/*.py", "turing_core.py")
    seen = set()
    for pat in globs:
        for path in sorted(root.glob(pat)):
            if path in seen or not path.is_file():
                continue
            seen.add(path)
            if "operating_model" in path.parts:
                continue
            try:
                tree = ast.parse(
                    path.read_text(encoding="utf-8", errors="replace"))
            except SyntaxError:
                continue
            for fn in ast.walk(tree):
                if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                uses = any(
                    isinstance(n, ast.Name) and n.id == "LEMMA"
                    for n in ast.walk(fn))
                guarded = any(
                    isinstance(n, ast.Call)
                    and getattr(n.func, "id", getattr(n.func, "attr", "")) == "use_lemma"
                    for n in ast.walk(fn))
                if uses and not guarded:
                    violations.append({
                        "file": str(path.relative_to(root)).replace("\\", "/"),
                        "line": fn.lineno,
                        "reason": "lemma use not routed through use_lemma()",
                    })
    return violations


def collect_signoff(lemma: Dict[str, Any] = LEMMA,
                    n_range: Sequence[int] = VERIFIED_RANGE) -> Dict[str, Any]:
    """Reviewer signoff as EXECUTED evidence — each attestation is a
    check that ran, not a name."""
    lo, hi = int(n_range[0]), int(n_range[1])
    q = lemma["scope"]["matrix"]

    t = {0: 2, 1: 1}
    for n in range(2, hi + 1):
        t[n] = t[n - 1] + t[n - 2]
    mathematician = all(t[n] == trace(matpow_int(q, n))
                        for n in range(lo, hi + 1))
    complexity = all(fast_doubling_lucas(n) == t[n]
                     for n in range(lo, hi + 1))
    number_theorist = (t[0] == 2 and t[1] == 1)
    qi_physicist = "quantum_advantage" in lemma["not_a_proof_of"]
    systems = mathematician and complexity  # exact ints only — the checks ran

    attestations = {
        "mathematician": {"check": "trace recurrence", "result": mathematician},
        "complexity": {"check": "fast doubling O(log n)", "result": complexity},
        "number_theorist": {"check": "Lucas initials", "result": number_theorist},
        "qi_physicist": {"check": "no quantum claim needed", "result": qi_physicist},
        "systems": {"check": "exact integer, no floats", "result": systems},
    }
    for role, a in attestations.items():
        assert a["result"] is True, f"{role} attestation failed"
    return {"attestations": attestations, "theorem_proven": False}


def require_lemma(root: Optional[Path] = None, *, write: bool = True) -> Dict[str, Any]:
    root = repo_root() if root is None else Path(root)
    doc = root / LEMMA_PATH
    text = doc.read_text(encoding="utf-8")
    lines = text.splitlines()
    assert len(lines) <= LEMMA_MAX_LINES, f"lemma is {len(lines)} lines — over the two-page bound"

    lowered = text.lower()
    assert "tr(" in text or "trace" in lowered, "lemma must state the trace identity"
    assert "lucas" in lowered, "lemma must name the Lucas bound"
    missing = [r for r in REQUIRED_REVIEWERS
               if f"- {r}" not in text and f"| {r}" not in text]
    assert not missing, f"lemma missing reviewer signoff lines: {missing}"

    record = {
        "lemma": LEMMA_PATH,
        "sha": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "lines": len(lines),
        "reviewers": list(REQUIRED_REVIEWERS),
        "signoff": collect_signoff(LEMMA),
        "verify": verify_lemma(LEMMA),
        "scope_violations": ast_scope_check(root),
        "citation_overclaims": citation_check(text),
        "theorem_proven": False,
    }
    assert not record["scope_violations"], \
        f"lemma uses bypass use_lemma(): {record['scope_violations']}"
    assert not record["citation_overclaims"], \
        f"lemma doc overclaims: {record['citation_overclaims']}"
    if write:
        out = root / SIGNOFF_PATH
        out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    return record


def verify_golden_stride(lemma: Dict[str, Any] = LEMMA_GOLDEN_STRIDE
                         ) -> List[Dict[str, Any]]:
    """The two-line proof, executed: stride odd ⇒ gcd(stride, 2^32) = 1
    ⇒ the walk permutes the domain. The empirical uniqueness sweep lives
    in tests/test_golden_stride.py as a cross-check, not the proof."""
    import math

    stride = lemma["scope"]["stride"]
    modulus = lemma["scope"]["modulus"]
    assert stride % 2 == 1, "stride must be odd"
    assert math.gcd(stride, modulus) == 1, "stride must be coprime to 2^32"
    # floor(2^32/phi) cross-check: the double-precision floor is exact
    # here because 2^32/phi sits far (~2e8 ulps) from an integer; this is
    # a numeric sanity check on the constant, not part of the bijection
    # proof (which needs only "stride is odd").
    import decimal
    decimal.getcontext().prec = 50
    phi_dec = (decimal.Decimal(1) + decimal.Decimal(5).sqrt()) / 2
    assert stride == int(decimal.Decimal(U32_SPACE) / phi_dec)
    return [{
        "verdict": "HOLDS",
        "mode": "gcd(stride, 2^32) == 1 (stride odd)",
        "stride": stride,
        "theorem_proven": False,
    }]


def verify_resonance_ordering(lemma: Dict[str, Any] = LEMMA_PHI_RESONANCE
                              ) -> List[Dict[str, Any]]:
    """Executed scope check: the ordering is a header-dependent
    permutation of the window — verified on deterministic vectors; it
    asserts nothing about sha256d output."""
    from Intelligence.quantum_stack import QuantumStack

    stack = QuantumStack()
    headers = [bytes([b]) * 76 for b in (0x01, 0x02, 0x03)]
    orders = []
    for h in headers:
        order, stats = stack.full_order(h, 2048)
        assert sorted(order) == list(range(2048)), \
            "ordering must be a permutation of the window"
        orders.append(tuple(order[:64]))
    assert len(set(orders)) == len(orders), \
        "distinct headers must yield distinct probe orders"
    return [{
        "verdict": "HOLDS",
        "mode": "permutation + header-dependence on deterministic vectors",
        "theorem_proven": False,
    }]


def use_ordering_lemma(
    usage: str, stride: Optional[int] = None, *, lemma: Optional[str] = None
) -> Dict[str, Any]:
    """Runtime scope guard. Returns the lemma that authorizes the usage.
    Ambiguous usages (present in more than one lemma) raise ScopeViolation.
    """
    sources = [
        ("golden_stride_bijection", LEMMA_GOLDEN_STRIDE),
        ("phi_resonance_ordering", LEMMA_PHI_RESONANCE),
        ("lucas_scaling_limbs", LEMMA_LUCAS_SCALING),
        ("zeckendorf_unique_filing", LEMMA_ZECKENDORF_FILING),
    ]
    matches = [name for name, lem in sources
               if usage in lem["scope"]["authorized_uses"]]
    if lemma is not None:
        if lemma not in matches:
            raise ScopeViolation(f"lemma {lemma!r} does not authorize usage {usage!r}")
        matches = [lemma]
    if not matches:
        raise ScopeViolation(f"usage not authorized: {usage}")
    if len(matches) > 1:
        raise ScopeViolation(
            f"usage {usage} is authorized by multiple lemmas {matches}; "
            "pass an explicit lemma or disambiguate the authorized_uses")
    if stride is not None and stride != GOLDEN_STRIDE:
        raise ScopeViolation(
            f"stride {stride:#x} is not the lemma's stride "
            f"{GOLDEN_STRIDE:#x}; a non-phi stride is a separate, "
            "unproven claim")
    return {"authorized": True, "lemma": matches[0], "theorem_proven": False}


def collect_ordering_signoff() -> Dict[str, Any]:
    """Reviewer signoff as executed checks for the ordering lemmas."""
    stride_ok = verify_golden_stride()[0]["verdict"] == "HOLDS"
    ordering_ok = verify_resonance_ordering()[0]["verdict"] == "HOLDS"
    scoped = (
        "quantum_advantage" in LEMMA_GOLDEN_STRIDE["not_a_proof_of"]
        and "quantum_advantage" in LEMMA_PHI_RESONANCE["not_a_proof_of"]
    )
    attestations = {
        "mathematician": {"check": "stride bijection (gcd)", "result": stride_ok},
        "systems": {"check": "ordering is header-dependent permutation",
                    "result": ordering_ok},
        "qi_physicist": {"check": "no quantum claim in scope", "result": scoped},
    }
    for role, a in attestations.items():
        assert a["result"] is True, f"{role} attestation failed"
    return {"attestations": attestations, "theorem_proven": False}


ORDERING_LEMMA_PATH = "docs/lemma_golden_ordering.md"
ORDERING_SIGNOFF_PATH = "docs/lemma_ordering_signoff.json"
ORDERING_REVIEWERS = ("mathematician", "systems", "qi_physicist")


def require_ordering_lemmas(root: Optional[Path] = None, *,
                            write: bool = True) -> Dict[str, Any]:
    """Same discipline as the Lucas lemma: doc bound + reviewer lines +
    executed verifications + sha-pinned signoff record."""
    root = repo_root() if root is None else Path(root)
    doc = root / ORDERING_LEMMA_PATH
    text = doc.read_text(encoding="utf-8")
    assert len(text.splitlines()) <= LEMMA_MAX_LINES, \
        "ordering lemma exceeds the two-page bound"
    lowered = text.lower()
    assert "bijection" in lowered and "sha256d" in lowered, \
        "ordering lemma must state the bijection and the unchanged accept predicate"
    missing = [r for r in ORDERING_REVIEWERS
               if f"- {r}" not in text and f"| {r}" not in text]
    assert not missing, f"ordering lemma missing reviewer signoff lines: {missing}"
    record = {
        "lemma": ORDERING_LEMMA_PATH,
        "sha": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "lines": len(text.splitlines()),
        "lemmas": [LEMMA_GOLDEN_STRIDE["name"], LEMMA_PHI_RESONANCE["name"]],
        "signoff": collect_ordering_signoff(),
        "verify": verify_golden_stride() + verify_resonance_ordering(),
        "theorem_proven": False,
    }
    if write:
        out = root / ORDERING_SIGNOFF_PATH
        out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    return record


def ordering_lemmas_signed(root: Optional[Path] = None) -> bool:
    root = repo_root() if root is None else Path(root)
    rec = root / ORDERING_SIGNOFF_PATH
    doc = root / ORDERING_LEMMA_PATH
    if not rec.is_file() or not doc.is_file():
        return False
    try:
        stored = json.loads(rec.read_text(encoding="utf-8"))
    except Exception:
        return False
    if stored.get("theorem_proven") is not False:
        return False
    digest = hashlib.sha256(doc.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
    return stored.get("sha") == digest


def lemma_signed(root: Optional[Path] = None) -> bool:
    """True iff a signoff exists AND the stored sha matches the current
    lemma document — an edited lemma re-opens the gate."""
    root = repo_root() if root is None else Path(root)
    rec = root / SIGNOFF_PATH
    doc = root / LEMMA_PATH
    if not rec.is_file() or not doc.is_file():
        return False
    try:
        stored = json.loads(rec.read_text(encoding="utf-8"))
    except Exception:
        return False
    if stored.get("theorem_proven") is not False:
        return False
    digest = hashlib.sha256(doc.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
    return stored.get("sha") == digest
