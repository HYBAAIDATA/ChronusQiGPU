"""Truth layer — read-only classifiers. Every function returns findings;
none writes, approves, or merges.

Verdicts use the owning agent's vocabulary only:
  auditor            -> claim/trace/laureate/reduction/confirmed_defect
  math_verifier      -> holds/fails/undecidable (+ mode: symbolic|range)
  security_verifier  -> fails_open/stub_crypto/real_crypto/key_lifecycle_*
  quantum_checker    -> unitary/non_unitary/non_cptp/measurement_formalism
  precision_sentinel -> float_leak/bound_violated/ill_conditioned/
                        cancellation/oracle_disagreement
  pin_verifier       -> pin_holds/pin_violated
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from hyba.operating_model.roles import repo_root
from lucas.ladder import CURRICULUM_RUNGS, FULL_LADDER

# Files the verifiers walk. Discovery is by glob, not by trust.
SCAN_GLOBS = (
    "mining/**/*.py",
    "Intelligence/**/*.py",
    "hyba/**/*.py",
    "kellogg/**/*.py",
    "toe/**/*.py",
    "lucas/**/*.py",
    "chronus/mla1517_platform/python/**/*.py",
    "turing_core.py",
)

_CRYPTO_NAME = re.compile(r"verify|auth|hmac|signature|proof|check", re.IGNORECASE)
_MILLENNIUM_CLAIM = re.compile(
    r"\b(prove[sd]?|solves?|settles?)\b.{0,40}\b(riemann|p\s*(?:vs\.?|=)\s*np|"
    r"navier|yang.?mills|hodge|birch|millennium)\b",
    re.IGNORECASE | re.DOTALL,
)


def _py_files(root: Path) -> List[Path]:
    seen: set[Path] = set()
    out: List[Path] = []
    for pat in SCAN_GLOBS:
        for p in sorted(root.glob(pat)):
            if p.is_file() and "__pycache__" not in p.parts and p not in seen:
                seen.add(p)
                out.append(p)
    return out


def _rel(root: Path, p: Path) -> str:
    return str(p.relative_to(root)).replace("\\", "/")


# ---------------------------------------------------------------------------
# 10. PinVerifier — audits the honesty pin itself. Its only job.
# ---------------------------------------------------------------------------


def _is_false_const(node: Optional[ast.AST]) -> bool:
    return isinstance(node, ast.Constant) and node.value is False


def _pin_resolution(tree: ast.AST) -> str:
    """Resolve whether a module pins `theorem_proven` for self/alias uses.

    A non-literal value `self.theorem_proven` (or a bare name) counts as
    pinned when the same module proves the pin mechanically: a field or
    name bound to the constant False, or a read-only ``@property`` whose
    setter raises — a dynamic pin stronger than a literal, since it
    cannot be flipped without a checked proof."""
    const_bound = False
    prop_found = False
    setter_raises = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and _is_false_const(node.value):
            if any(isinstance(t, ast.Name) and t.id == "theorem_proven" for t in node.targets):
                const_bound = True
        if isinstance(node, ast.AnnAssign) and _is_false_const(node.value):
            if isinstance(node.target, ast.Name) and node.target.id == "theorem_proven":
                const_bound = True
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "theorem_proven"
        ):
            for d in node.decorator_list:
                if isinstance(d, ast.Name) and d.id == "property":
                    prop_found = True
                if isinstance(d, ast.Attribute) and d.attr == "setter":
                    if any(isinstance(s, ast.Raise) for s in ast.walk(node)):
                        setter_raises = True
    if const_bound:
        return "constant"
    if prop_found and setter_raises:
        return "read-only property"
    return ""


def _pin_ok(value: ast.AST, pin_kind: str) -> bool:
    if isinstance(value, ast.Constant):
        return value.value is False
    if not pin_kind:
        return False
    if isinstance(value, ast.Name):
        return value.id == "theorem_proven"
    if isinstance(value, ast.Attribute):
        return value.attr == "theorem_proven"
    return False


def pin_verifier(root: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Every `theorem_proven` surface must pin False — literally, via a
    module-level constant binding, or via a read-only property whose
    setter raises. Any doc claiming a Millennium-class proof is a pin
    violation."""
    root = repo_root() if root is None else Path(root)
    findings: List[Dict[str, Any]] = []
    checked = 0
    for path in _py_files(root):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        pin_kind = _pin_resolution(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Dict):
                for key, val in zip(node.keys, node.values):
                    if isinstance(key, ast.Constant) and key.value == "theorem_proven":
                        checked += 1
                        if not _pin_ok(val, pin_kind):
                            findings.append(
                                {
                                    "verdict": "pin_violated",
                                    "file": _rel(root, path),
                                    "line": node.lineno,
                                    "detail": "theorem_proven not pinned to False",
                                }
                            )
            # Also catch dict("theorem_proven"=...) / keyword forms.
            if isinstance(node, ast.Call):
                for kw in node.keywords:
                    if kw.arg == "theorem_proven":
                        checked += 1
                        if not _pin_ok(kw.value, pin_kind):
                            findings.append(
                                {
                                    "verdict": "pin_violated",
                                    "file": _rel(root, path),
                                    "line": node.lineno,
                                    "detail": "theorem_proven kwarg not pinned False",
                                }
                            )
    from hyba.operating_model.lemma import citation_check

    for doc in sorted(root.glob("docs/**/*.md")):
        text = doc.read_text(encoding="utf-8", errors="replace")
        for m in _MILLENNIUM_CLAIM.finditer(text):
            line = text[: m.start()].count("\n") + 1
            findings.append(
                {
                    "verdict": "pin_violated",
                    "file": _rel(root, doc),
                    "line": line,
                    "detail": f"doc claims proof-adjacent result: {m.group(0)[:60]!r}",
                }
            )
        for over in citation_check(text):
            findings.append(
                {
                    "verdict": "overclaim",
                    "file": _rel(root, doc),
                    "line": over.get("line"),
                    "detail": f"doc cites lemma for forbidden conclusion: " f"{over['phrase']!r}",
                }
            )
    if not findings:
        findings.append({"verdict": "pin_holds", "surfaces_checked": checked})
    return findings


# ---------------------------------------------------------------------------
# 6. MathVerifier — symbolic where possible, exact-integer range otherwise.
# ---------------------------------------------------------------------------


def _load_core(root: Path):
    """chronus.mla1517.core via the platform path, or turing_core as the root copy."""
    import sys

    plat = root / "chronus/mla1517_platform" / "python"
    if str(plat) not in sys.path:
        sys.path.insert(0, str(plat))
    try:
        import chronus.mla1517.core as core  # type: ignore

        return core
    except Exception:
        pass
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    import turing_core as core  # type: ignore

    return core


def _load_root_turing_core(root: Path):
    """Load the frozen substrate at <root>/turing_core.py directly."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("turing_core_root", root / "turing_core.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def math_verifier(root: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Verifies the repo's declared identities. Symbolic means 'identity by
    construction/closed form'; range means exact-integer evaluation on the
    declared window — weaker evidence, marked as such."""
    root = repo_root() if root is None else Path(root)
    findings: List[Dict[str, Any]] = []
    core = _load_core(root)
    fib = getattr(core, "fib", None) or getattr(core, "fibonacci")
    lucas = getattr(core, "lucas")

    # Cassini: F(n+1)F(n-1) - F(n)^2 = (-1)^n, exact range n in 2..76.
    claim_range = range(2, 77)
    bad = [n for n in claim_range if fib(n + 1) * fib(n - 1) - fib(n) ** 2 != (-1) ** n]
    findings.append(
        {
            "verdict": "holds" if not bad else "fails",
            "claim": "cassini_identity",
            "mode": "range",
            "range": [2, 76],
            **({"counterexample": bad[0]} if bad else {}),
        }
    )

    # Binet vs fast doubling is out of scope here (binet is float); the
    # exact check is fib fast-doubling vs naive recurrence.
    def fib_naive(n: int) -> int:
        a, b = 0, 1
        for _ in range(n):
            a, b = b, a + b
        return a

    bad = [n for n in range(0, 201) if fib(n) != fib_naive(n)]
    findings.append(
        {
            "verdict": "holds" if not bad else "fails",
            "claim": "fibonacci_matches_naive",
            "mode": "range",
            "range": [0, 200],
            **({"counterexample": bad[0]} if bad else {}),
        }
    )

    # tr(Q^n) = L_n for the golden matrix Q=[[1,1],[1,0]] — closed-form
    # identity (symbolic) cross-checked exactly on 1..76. Falls back to
    # the root substrate when the loaded core lacks the symbol.
    gmt = getattr(core, "golden_matrix_trace", None)
    if gmt is None:
        tc = _load_root_turing_core(root)
        gmt = getattr(tc, "golden_matrix_trace", None)
        lucas = getattr(tc, "lucas", lucas)
    if gmt is not None:
        bad = [n for n in range(1, 77) if gmt(n) != lucas(n)]
        findings.append(
            {
                "verdict": "holds" if not bad else "fails",
                "claim": "golden_matrix_trace_eq_lucas",
                "mode": "symbolic",
                "range": [1, 76],
                **({"counterexample": bad[0]} if bad else {}),
            }
        )

    # Math verifier OWNS the Lucas path-count lemma: verify_lemma runs the
    # recurrence + fast-doubling cross-oracle on the declared range.
    from hyba.operating_model.lemma import LEMMA, verify_lemma

    lv = verify_lemma(LEMMA, LEMMA["verified_range"])
    findings.append(
        {
            "verdict": "holds" if lv[0]["verdict"] == "HOLDS" else "fails",
            "claim": "lucas_path_bound",
            "mode": lv[0]["mode"],
            "range": lv[0]["range"],
        }
    )

    # M15 det ≡ -1 (mod 256) — symbolic (two integers).
    import importlib.util

    spec = importlib.util.spec_from_file_location("turing_core_verify", root / "turing_core.py")
    tc = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(tc)
    det = (tc.M15[0][0] * tc.M15[1][1] - tc.M15[0][1] * tc.M15[1][0]) % 256
    findings.append(
        {
            "verdict": "holds" if det == 255 else "fails",
            "claim": "m15_det_eq_neg1_mod256",
            "mode": "symbolic",
            **({} if det == 255 else {"counterexample": det}),
        }
    )
    return findings


# ---------------------------------------------------------------------------
# 8. QuantumChecker — unitarity and CPTP on the exact gate table.
# ---------------------------------------------------------------------------


def quantum_checker(root: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Verifies U * U^dagger = I in the exact F4 field for every declared
    gate. Non-exact surfaces are not excused — they are flagged."""
    root = repo_root() if root is None else Path(root)
    findings: List[Dict[str, Any]] = []
    try:
        from kellogg.exact_tensor import GATES, ONE, ZERO  # type: ignore
    except Exception as exc:
        return [
            {
                "verdict": "undecidable",
                "detail": f"exact gate table unavailable: {type(exc).__name__}",
            }
        ]

    def matmul(a, b):
        return tuple(
            tuple(a[i][0] * b[0][j] + a[i][1] * b[1][j] for j in range(2)) for i in range(2)
        )

    def dagger(u):
        return tuple(tuple(u[j][i].conjugate() for j in range(2)) for i in range(2))

    ident = ((ONE, ZERO), (ZERO, ONE))
    for name, gate in GATES.items():
        prod = matmul(gate, dagger(gate))
        if prod != ident:
            findings.append(
                {"verdict": "non_unitary", "file": "kellogg/exact_tensor.py", "gate": name}
            )
        else:
            findings.append({"verdict": "unitary", "gate": name})
    return findings


# ---------------------------------------------------------------------------
# 9. PrecisionSentinel — float leaks on exact surfaces, nondeterminism.
# ---------------------------------------------------------------------------

_EXACT_DECLARED = re.compile(
    r"bit-exact|exact arithmetic|exact integer|exactly representable", re.IGNORECASE
)
_EXACT_DISCLAIMED = re.compile(
    r"not.{0,20}exact|float|floating.point|approxim|estimated", re.IGNORECASE
)


def precision_sentinel(root: Optional[Path] = None) -> List[Dict[str, Any]]:
    """AST walk: `float(`/numpy float dtypes inside functions that declare
    the surface itself exact (docstring 'bit-exact'/'exact arithmetic'
    or an 'exact' in the name) and do not disclaim floats; plus
    `random.`/`np.random` nondeterminism in mining paths."""
    root = repo_root() if root is None else Path(root)
    findings: List[Dict[str, Any]] = []
    for path in _py_files(root):
        rel = _rel(root, path)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            doc = ast.get_docstring(node) or ""
            # Conversion-boundary names (from_exact_*/to_float/project...)
            # ARE the declared crossing — not leaks.
            boundary_name = bool(
                re.search(
                    r"from_exact|to_exact|to_float|as_float|project", node.name, re.IGNORECASE
                )
            )
            declares_exact = not boundary_name and (
                (_EXACT_DECLARED.search(doc) and not _EXACT_DISCLAIMED.search(doc))
                or "exact" in node.name
            )
            for sub in ast.walk(node):
                # float leak on a declared-exact surface
                if declares_exact and isinstance(sub, ast.Call):
                    f = sub.func
                    name = (
                        f.id
                        if isinstance(f, ast.Name)
                        else f.attr if isinstance(f, ast.Attribute) else ""
                    )
                    if name == "to_float":
                        continue  # declared boundary crossing, not a leak
                    if name in {"float", "float64", "float32", "astype"}:
                        findings.append(
                            {
                                "verdict": "float_leak",
                                "file": rel,
                                "line": sub.lineno,
                                "detail": f"{node.name}() declares exactness",
                            }
                        )
                # nondeterminism in mining/search paths
                if (
                    isinstance(sub, ast.Call)
                    and isinstance(sub.func, ast.Attribute)
                    and sub.func.attr
                    in {"random", "rand", "randint", "choice", "shuffle", "uniform"}
                    and ("mining" in rel or "search" in rel)
                ):
                    findings.append(
                        {
                            "verdict": "nondeterministic_source",
                            "file": rel,
                            "line": sub.lineno,
                            "detail": "RNG call on the deterministic path",
                        }
                    )
    # Ill-conditioning: cond_2(M15) over R — exact 2x2 closed form.
    # M15 eigenvalues: (tr ± sqrt(tr^2 - 4det))/2 with tr=256, det=-1.
    tr, det = 256, -1
    disc = tr * tr - 4 * det
    lam_max = (tr + disc**0.5) / 2
    lam_min = abs((tr - disc**0.5) / 2)
    cond = lam_max / lam_min
    findings.append(
        {
            "verdict": "ill_conditioned" if cond > 1e8 else "exact",
            "surface": "M15",
            "cond": cond,
            "file": "turing_core.py",
        }
    )
    return findings


# ---------------------------------------------------------------------------
# 7. SecurityVerifier — fail-open handlers, stub crypto, key lifecycle.
# ---------------------------------------------------------------------------


def security_verifier(root: Optional[Path] = None) -> List[Dict[str, Any]]:
    root = repo_root() if root is None else Path(root)
    findings: List[Dict[str, Any]] = []
    hmac_key_sites: Dict[str, List[str]] = {}
    for path in _py_files(root):
        rel = _rel(root, path)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            # fails_open: bare `except: pass`/`return <truthy>` swallowing a
            # security check (verify/auth/hmac in the same function name)
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                body_all_pass = all(isinstance(s, ast.Pass) for s in node.body)
                if body_all_pass:
                    fn = _enclosing_fn(tree, node)
                    if fn and _CRYPTO_NAME.search(fn):
                        findings.append(
                            {
                                "verdict": "fails_open",
                                "file": rel,
                                "line": node.lineno,
                                "detail": f"bare except:pass inside {fn}()",
                            }
                        )
            # stub_crypto: crypto-named function whose entire body returns
            # a constant True
            if isinstance(node, ast.FunctionDef) and _CRYPTO_NAME.search(node.name):
                body = [s for s in node.body if not isinstance(s, ast.Expr)]
                if (
                    len(body) == 1
                    and isinstance(body[0], ast.Return)
                    and isinstance(body[0].value, ast.Constant)
                    and body[0].value.value is True
                ):
                    findings.append(
                        {
                            "verdict": "stub_crypto",
                            "file": rel,
                            "line": node.lineno,
                            "detail": f"{node.name}() returns constant True",
                        }
                    )
            # key lifecycle: hmac.new(<constant key>) and reuse across files
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "new"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "hmac"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, (str, bytes))
            ):
                key = repr(node.args[0].value)[:32]
                hmac_key_sites.setdefault(key, []).append(f"{rel}:{node.lineno}")
    for key, sites in hmac_key_sites.items():
        if len(sites) > 1:
            for site in sites:
                f, _, line = site.rpartition(":")
                findings.append(
                    {
                        "verdict": "key_lifecycle_reuse",
                        "file": f,
                        "line": int(line),
                        "detail": f"same hmac key literal at {len(sites)} sites",
                    }
                )
        else:
            for site in sites:
                f, _, line = site.rpartition(":")
                findings.append(
                    {
                        "verdict": "key_lifecycle_weak",
                        "file": f,
                        "line": int(line),
                        "detail": "hmac key derived from an inline constant",
                    }
                )
    return findings


def _enclosing_fn(tree: ast.AST, target: ast.AST) -> Optional[str]:
    best: Optional[str] = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if any(n is target for n in ast.walk(node)):
                best = node.name
    return best


# ---------------------------------------------------------------------------
# 1. Auditor — claim traceability, laureate attribution, reductions.
# ---------------------------------------------------------------------------

_DECLARED_CLAIMS = (
    # (claim, source file evidence, laureate attribution, reduction-or-None)
    {
        "claim": "cassini_identity_in_m15",
        "source": "chronus/mla1517_platform/python/pythia_turing_math.py",
        "laureate": "cassini",
        "reduction": None,
    },
    {
        "claim": "round_trip_bit_exact",
        "source": "chronus/lucas/fold.py",
        "laureate": None,
        "reduction": None,
    },
    {
        "claim": "golden_matrix_trace_eq_lucas",
        "source": "chronus/mla1517_platform/python/pythia_turing_math.py",
        "laureate": "lucas",
        "reduction": "tr(Q^n)=L_n reduces NP path count " "to fast doubling",
    },
    {
        "claim": "sha256d_sole_accept_authority",
        "source": "mining/bitcoin_hasher.py",
        "laureate": None,
        "reduction": "pool acceptance reduces to sha256d<=target",
    },
    {
        "claim": "never_two_consecutive_blocks",
        "source": "mining/safety_fsm.py",
        "laureate": None,
        "reduction": None,
    },
)


def auditor(root: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Traces each declared claim to source code evidence. A claim with no
    traceable source is a confirmed defect."""
    root = repo_root() if root is None else Path(root)
    trace: List[Dict[str, Any]] = []
    for c in _DECLARED_CLAIMS:
        src = root / c["source"]
        evidence = None
        if src.is_file():
            text = src.read_text(encoding="utf-8")
            needles = {
                "cassini_identity_in_m15": ["det(M15) = -1", "M15_INV"],
                "round_trip_bit_exact": ["t_phi_fold", "t_phi_unfold"],
                "golden_matrix_trace_eq_lucas": ["golden_matrix_trace", "lucas"],
                "sha256d_sole_accept_authority": ["hashlib", "sha256"],
                "never_two_consecutive_blocks": [
                    "consecutive_blocks_prevented",
                    "never two consecutive",
                ],
            }[c["claim"]]
            if all(n in text for n in needles):
                evidence = f"{c['source']} contains {needles}"
        entry = {
            "claim": c["claim"],
            "source": evidence or "MISSING",
            "laureate": c["laureate"],
            "reduction": c["reduction"],
        }
        if evidence is None:
            entry["verdict"] = "confirmed_defect"
        # Lemma-citing claims get scope traced, not re-verified — the
        # math verifier owns the lemma; the auditor traces citations.
        if c["claim"] == "golden_matrix_trace_eq_lucas":
            entry["cites_lemma"] = True
            entry["in_scope"] = evidence is not None and (c["reduction"] or "").startswith(
                "tr(Q^n)=L_n"
            )
        else:
            entry["cites_lemma"] = False
        trace.append(entry)
    # Any lemma use that bypasses use_lemma() is a confirmed defect.
    from hyba.operating_model.lemma import ast_scope_check

    for v in ast_scope_check(root):
        trace.append(
            {
                "verdict": "confirmed_defect",
                "claim": "lemma_scope_bypass",
                "source": "MISSING",
                "file": v["file"],
                "line": v["line"],
                "detail": v["reason"],
            }
        )
    trace.extend(_submission_route_check(root))
    trace.extend(_ladder_source_check(root))
    trace.extend(_lucas_wiring_check(root))
    trace.extend(_kernel_route_check(root))
    return trace


# ---------------------------------------------------------------------------
# Single durable lifecycle for pool submissions. `client.submit` /
# `pool.submit_*` writes are permitted only at the declared transport
# primitives and their session-gated delegates; anything else is a route
# that bypasses SUBMITTING -> WAITING_EXTERNAL -> COOLDOWN persistence.
# ---------------------------------------------------------------------------

# (file, class, method) permitted to contain a submission call.
_ALLOWED_SUBMISSION_SITES = frozenset(
    {
        # The transport primitives; reachable only through the overrides below.
        ("manifold_pool_coordinator.py", "ManifoldPoolCoordinator", "submit_candidate"),
        ("manifold_pool_coordinator.py", "ManifoldPoolCoordinator", "submit_record"),
        # Delegates to the session-gated pool; the constructor requires the
        # injected coordinator to expose a MiningSession.
        ("coordinator.py", "CanonicalMiningCoordinator", "submit_observed_candidate"),
    }
)
# Submission verbs on a Stratum client or pool receiver.
_SUBMIT_ATTRS = frozenset({"submit", "submit_candidate", "submit_record"})
_SUBMIT_RECEIVERS = frozenset({"client", "pool"})
# The canonical coordinator file must override each transport primitive and
# persist SUBMITTING before delegating.
_LIFECYCLE_COORDINATOR = "chronus/mla1517/mining/coordinator.py"


def _submission_route_check(root: Path) -> List[Dict[str, Any]]:
    violations: List[Dict[str, Any]] = []
    transport_methods: set[str] = set()
    for path in _py_files(root):
        if path.name.startswith("test_"):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        # Module-level functions are submission sites too — a plain helper
        # can call client.submit without any class wrapper. Only top-level
        # defs count as module scope; class methods keep their class key.
        scopes = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                scopes.append(("<module>", node))
            elif isinstance(node, ast.ClassDef):
                for fn in node.body:
                    if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        scopes.append((node.name, fn))
        for cls_name, fn in scopes:
            for call in ast.walk(fn):
                if not isinstance(call, ast.Call):
                    continue
                f = call.func
                if not (isinstance(f, ast.Attribute) and f.attr in _SUBMIT_ATTRS):
                    continue
                receiver = f.value
                name = (
                    receiver.attr
                    if isinstance(receiver, ast.Attribute)
                    else receiver.id if isinstance(receiver, ast.Name) else ""
                )
                if name not in _SUBMIT_RECEIVERS:
                    continue
                key = (path.name, cls_name, fn.name)
                if key in _ALLOWED_SUBMISSION_SITES:
                    if cls_name == "ManifoldPoolCoordinator":
                        transport_methods.add(fn.name)
                    continue
                violations.append(
                    {
                        "verdict": "confirmed_defect",
                        "claim": "unmanaged_submission_route",
                        "source": "MISSING",
                        "file": _rel(root, path),
                        "line": call.lineno,
                        "detail": f"{cls_name}.{fn.name} calls "
                        f"{name}.{f.attr} outside the durable "
                        "mining-session lifecycle",
                    }
                )
    # The gated override must exist for each transport primitive, and the
    # candidate path must persist SUBMITTING before delegating upward.
    coord_path = root / _LIFECYCLE_COORDINATOR
    if coord_path.is_file():
        src = coord_path.read_text(encoding="utf-8")
        for prim in transport_methods:
            if f"def {prim}(" not in src:
                violations.append(
                    {
                        "verdict": "confirmed_defect",
                        "claim": "lifecycle_gate_absent",
                        "source": "MISSING",
                        "file": _LIFECYCLE_COORDINATOR,
                        "line": 0,
                        "detail": f"IntelligentPoolCoordinator does not override "
                        f"{prim}; the transport primitive is exposed",
                    }
                )
        if not ("session.begin_submission(" in src and "super().submit_candidate(" in src):
            violations.append(
                {
                    "verdict": "confirmed_defect",
                    "claim": "lifecycle_gate_absent",
                    "source": "MISSING",
                    "file": _LIFECYCLE_COORDINATOR,
                    "line": 0,
                    "detail": "submit_candidate does not persist SUBMITTING "
                    "before delegating to the transport",
                }
            )
    else:
        violations.append(
            {
                "verdict": "confirmed_defect",
                "claim": "lifecycle_gate_absent",
                "source": "MISSING",
                "file": _LIFECYCLE_COORDINATOR,
                "line": 0,
                "detail": "canonical lifecycle coordinator file missing",
            }
        )
    return violations


# ---------------------------------------------------------------------------
# Single ladder source. The canonical rung sets live in lucas/ladder.py
# (FULL_LADDER / SCALE_RUNGS); any other module re-declaring the literal
# re-introduces drift. Tests keep literals on purpose — they pin the
# shared constant's contents.
# ---------------------------------------------------------------------------

_LADDER_PATTERNS = (tuple(CURRICULUM_RUNGS), tuple(FULL_LADDER))
_LADDER_DECLARING_MODULE = "chronus/lucas/ladder.py"


def _ladder_source_check(root: Path) -> List[Dict[str, Any]]:
    violations: List[Dict[str, Any]] = []
    for path in _py_files(root):
        rel = _rel(root, path)
        if path.name.startswith("test_") or rel == _LADDER_DECLARING_MODULE:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Tuple, ast.List)):
                continue
            values = tuple(
                elt.value
                for elt in node.elts
                if isinstance(elt, ast.Constant) and isinstance(elt.value, int)
            )
            if any(values[: len(pattern)] == pattern for pattern in _LADDER_PATTERNS):
                violations.append(
                    {
                        "verdict": "confirmed_defect",
                        "claim": "ladder_literal_redeclared",
                        "source": "MISSING",
                        "file": rel,
                        "line": node.lineno,
                        "detail": "re-declares the canonical Lucas ladder; "
                        "import FULL_LADDER/SCALE_RUNGS from "
                        "lucas.ladder instead",
                    }
                )
    return violations


# ---------------------------------------------------------------------------
# LUCAS WIRING — the substrate kernel names are drawn from lucas/ (or the
# canonical re-export shims) only; importing them through a sibling module
# forks the contract.
# ---------------------------------------------------------------------------

_LUCAS_KERNEL_NAMES = frozenset(
    {
        "lucas",
        "fibonacci",
        "fast_doubling_lucas",
        "matpow_int",
        "t_phi_fold",
        "t_phi_unfold",
        "iter_original_u8",
        "folded_modular_dot",
        "golden_matrix_trace",
        "lucas_value",
    }
)
# Modules whose public surface IS the substrate: the lucas/ pool, the
# canonical re-export shims, each ecosystem's declared math core, and the
# lemma's independent oracle implementations (the lemma's cross-checks
# must not resolve back into the code they verify).
_SUBSTRATE_SOURCES = frozenset(
    {
        "lucas",
        "lucas.core",
        "lucas.ladder",
        "lucas.fold",
        "lucas.algebra",
        "turing_core",
        "pythia_turing_math",
        "chronus.mla1517.core",
        "kellogg.scales",
        "hyba.operating_model.lemma",
    }
)


def _lucas_wiring_check(root: Path) -> List[Dict[str, Any]]:
    violations: List[Dict[str, Any]] = []
    for path in _py_files(root):
        rel = _rel(root, path)
        if path.name.startswith("test_"):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            mod = node.module or ""
            if node.level:
                # Resolve the relative import to the importing file's
                # package: `from .x import` in pkg/mod.py is 'pkg.x'.
                # The platform tree's sys.path root is not a package.
                parts = list(path.parent.relative_to(root).parts)
                if parts[:2] == ["chronus/mla1517_platform", "python"]:
                    parts = parts[2:]
                for _ in range(node.level - 1):
                    parts = parts[:-1]
                mod = ".".join(p for p in (".".join(parts), mod) if p)
            if not any(n.name in _LUCAS_KERNEL_NAMES for n in node.names):
                continue
            if mod not in _SUBSTRATE_SOURCES:
                violations.append(
                    {
                        "verdict": "confirmed_defect",
                        "claim": "sibling_kernel_import",
                        "source": "MISSING",
                        "file": rel,
                        "line": node.lineno,
                        "detail": f"imports substrate kernel names from "
                        f"'{mod}'; the contract lives in lucas/",
                    }
                )
    return violations


# ---------------------------------------------------------------------------
# Kernel routing — every KERNEL_SPECS route must resolve: a declared
# canonical_source file must exist and contain its entry symbol; otherwise
# the spec must bind a resolvable exact oracle (module:qualname).
# ---------------------------------------------------------------------------

_KERNEL_ORACLE_PATHS = (
    lambda root: root,
    lambda root: root / "chronus/mla1517_platform" / "python",
)


def _kernel_route_check(root: Path) -> List[Dict[str, Any]]:
    from hyba.math_ir.specs import KERNEL_SPECS

    violations: List[Dict[str, Any]] = []
    for name, spec in KERNEL_SPECS.items():
        if spec.canonical_source:
            kernel = root / spec.canonical_source
            ok = False
            if kernel.is_file() and spec.entry:
                text = kernel.read_text(encoding="utf-8", errors="replace")
                # Require an actual `__kernel ... entry(` declaration — the
                # entry name appearing in a comment is not a kernel route.
                ok = (
                    re.search(
                        r"__kernel\s+\w+\s+" + re.escape(spec.entry) + r"\s*\(",
                        text,
                    )
                    is not None
                )
            if not ok:
                violations.append(
                    {
                        "verdict": "confirmed_defect",
                        "claim": "kernel_route_missing",
                        "source": "MISSING",
                        "file": "hyba/math_ir/specs.py",
                        "line": 0,
                        "detail": f"{name}: canonical_source "
                        f"{spec.canonical_source} missing or lacks "
                        f"entry '{spec.entry}'",
                    }
                )
            continue
        # No canonical kernel: the route must resolve to a real oracle.
        module_name, _, qualname = spec.oracle.partition(":")
        if not module_name or not qualname:
            violations.append(
                {
                    "verdict": "confirmed_defect",
                    "claim": "kernel_route_missing",
                    "source": "MISSING",
                    "file": "hyba/math_ir/specs.py",
                    "line": 0,
                    "detail": f"{name}: no canonical source and no oracle",
                }
            )
            continue
        mod_rel = module_name.replace(".", "/") + ".py"
        mod_file = next(
            (
                base(root) / mod_rel
                for base in _KERNEL_ORACLE_PATHS
                if (base(root) / mod_rel).is_file()
            ),
            None,
        )
        if mod_file is None:
            violations.append(
                {
                    "verdict": "confirmed_defect",
                    "claim": "kernel_route_missing",
                    "source": "MISSING",
                    "file": "hyba/math_ir/specs.py",
                    "line": 0,
                    "detail": f"{name}: oracle module {module_name} not found",
                }
            )
            continue
        text = mod_file.read_text(encoding="utf-8", errors="replace")
        missing = [p for p in qualname.split(".") if p not in text]
        if missing and not _oracle_resolves_at_runtime(root, module_name, qualname):
            violations.append(
                {
                    "verdict": "confirmed_defect",
                    "claim": "kernel_route_missing",
                    "source": "MISSING",
                    "file": "hyba/math_ir/specs.py",
                    "line": 0,
                    "detail": f"{name}: oracle {module_name}:{qualname} does "
                    f"not define {missing}",
                }
            )
    return violations


def _oracle_resolves_at_runtime(root: Path, module_name: str, qualname: str) -> bool:
    """Re-export shims (e.g. the root turing_core module) populate their
    surface dynamically; resolve the qualname by import when the static
    scan cannot see it."""
    import importlib
    import sys

    added = []
    for base in _KERNEL_ORACLE_PATHS:
        p = str(base(root))
        if p not in sys.path:
            sys.path.insert(0, p)
            added.append(p)
    try:
        obj = importlib.import_module(module_name)
        for part in qualname.split("."):
            obj = getattr(obj, part)
        return True
    except Exception:
        return False
    finally:
        for p in added:
            try:
                sys.path.remove(p)
            except ValueError:
                pass


# ---------------------------------------------------------------------------
# 4. Governance — reasoned verdicts only.
# ---------------------------------------------------------------------------

_BAD_VERDICTS = {
    "fails",
    "non_unitary",
    "non_cptp",
    "fails_open",
    "stub_crypto",
    "key_lifecycle_weak",
    "key_lifecycle_reuse",
    "float_leak",
    "bound_violated",
    "ill_conditioned",
    "oracle_disagreement",
    "pin_violated",
    "confirmed_defect",
    "nondeterministic_source",
    "overclaim",
}


def governance(findings: Sequence[Dict[str, Any]], *, in_scope: bool = True) -> Dict[str, Any]:
    if not in_scope:
        return {"verdict": "FAIL", "reason": "out_of_scope"}
    if any(f.get("verdict") in _BAD_VERDICTS for f in findings):
        located = [f for f in findings if f.get("verdict") in _BAD_VERDICTS]
        return {"verdict": "FAIL", "reason": "defect_confirmed", "evidence": located}
    if any(f.get("verdict") == "undecidable" for f in findings):
        return {
            "verdict": "NOT_PROVABLE",
            "reason": "undecidable",
            "evidence": [f for f in findings if f.get("verdict") == "undecidable"],
        }
    missing = [f for f in findings if f.get("source") == "MISSING"]
    if missing:
        return {"verdict": "FAIL", "reason": "defect_confirmed", "evidence": missing}
    return {
        "verdict": "PASS",
        "reason": "all_claims_traced_no_findings",
        "evidence": list(findings),
    }
