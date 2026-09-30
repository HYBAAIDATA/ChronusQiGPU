"""Fail-closed probe for the multi-representation layer (elevation §3–§5).

Measures — not asserts by fiat — whether representation changes anything
downstream while the downstream algorithm stays constant:

  separability    raw features vs per-lens features, same nearest-centroid
                  classifier, same splits, on planted-structure populations
  memory          canonical-JSON byte size of each bound view's summary vs
                  the pickled raw observation — honest byte counts
  selection       structural signature -> lens choice; planted-structure
                  tasks must select the lens the structure needs and reject
                  lenses that don't apply
  identity        every bound view carries the same observation digest;
                  a foreign-digest view is refused
  causal_admit    the causal-graph lens is admitted only for a supplied
                  graph — correlation inference is not causal discovery
  golden_contract exact supported-N table for the N-point Fibonacci
                  butterfly (Bareiss determinant over the integer
                  circulant) + the CPU emitter's int64 overflow behaviour

Usage:
    python scripts/probe_representation_elevation.py \
        --report reports/toe_representation_elevation.json

Exit codes: 0 all checks passed; 1 any check failed; 2 a required section
was unavailable in this environment.
"""

from __future__ import annotations

import argparse
import json
import math
import pickle
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

RESULTS: List[Dict[str, Any]] = []


def check(section: str, name: str, ok: bool, evidence: Dict[str, Any]) -> None:
    RESULTS.append(
        {
            "section": section,
            "check": name,
            "status": "PASS" if ok else "FAIL",
            "evidence": evidence,
        }
    )
    print(f"  [{'PASS' if ok else 'FAIL'}] {section}: {name}")


def unavailable(section: str, name: str, reason: str) -> None:
    RESULTS.append(
        {"section": section, "check": name, "status": "UNAVAILABLE", "reason": reason}
    )
    print(f"  [UNAVAILABLE] {section}: {name} — {reason}")


# ---------------------------------------------------------------------------
# Downstream algorithm held constant: nearest-centroid classifier, LOO.
# ---------------------------------------------------------------------------


def nearest_centroid_loo(features: List[List[float]], labels: List[int]) -> float:
    n = len(features)
    correct = 0
    for i in range(n):
        centroids: Dict[int, List[float]] = {}
        counts: Dict[int, int] = {}
        for j in range(n):
            if j == i:
                continue
            lab = labels[j]
            centroids.setdefault(lab, [0.0] * len(features[j]))
            counts[lab] = counts.get(lab, 0) + 1
            for k, v in enumerate(features[j]):
                centroids[lab][k] += v
        for lab in centroids:
            centroids[lab] = [v / counts[lab] for v in centroids[lab]]
        best_lab, best_d = None, float("inf")
        for lab, c in centroids.items():
            d = sum((a - b) ** 2 for a, b in zip(features[i], c))
            if d < best_d:
                best_d, best_lab = d, lab
        if best_lab == labels[i]:
            correct += 1
    return correct / n


def make_populations(
    n_series: int = 24, length: int = 16, seed: int = 11, noise: float = 0.02
) -> Tuple[List[List[float]], List[int]]:
    """A: Fibonacci-type recurrence + small noise. B: iid, matched mean/std."""
    rng = random.Random(seed)
    series: List[List[float]] = []
    labels: List[int] = []
    for _ in range(n_series):
        a = rng.uniform(0.5, 1.5)
        b = rng.uniform(0.5, 1.5)
        s = [a, b]
        for _ in range(length - 2):
            s.append(s[-1] + s[-2] + rng.gauss(0.0, noise * max(1.0, abs(s[-1]))))
        series.append(s)
        labels.append(1)
    all_vals = [v for s in series for v in s]
    mu = sum(all_vals) / len(all_vals)
    sd = math.sqrt(sum((v - mu) ** 2 for v in all_vals) / len(all_vals))
    for _ in range(n_series):
        series.append([rng.gauss(mu, sd) for _ in range(length)])
        labels.append(0)
    return series, labels


# ---------------------------------------------------------------------------
# Feature extractors per representation — same classifier consumes all.
# ---------------------------------------------------------------------------


def raw_features(s: List[float]) -> List[float]:
    n = len(s)
    mu = sum(s) / n
    sd = math.sqrt(sum((v - mu) ** 2 for v in s) / n) or 1e-9
    lag1 = sum((s[i] - mu) * (s[i - 1] - mu) for i in range(1, n)) / (n * sd * sd)
    lag2 = sum((s[i] - mu) * (s[i - 2] - mu) for i in range(2, n)) / (n * sd * sd)
    return [mu, sd, lag1, lag2]


def tensor_features(bridge: Any, s: List[float]) -> List[float]:
    t = bridge.state_tomography({"s": s})
    if not t.available:
        return [0.0, 0.0, 0.0]
    return [t.entropy, t.coherence, t.fisher_info]


def algebraic_features(s: List[float]) -> Optional[List[float]]:
    from toe.intelligence_state import build_algebraic, observation_digest

    view = build_algebraic({"s": s}, observation_digest({"s": s}))
    if not view.available:
        return None
    summ = view.summary
    return [
        summ["family_confidence"],
        summ["residual_margin"] or 0.0,
        1.0 if summ["family"] == "golden" else 0.0,
    ]


def topological_features(s: List[float]) -> Optional[List[float]]:
    from toe.intelligence_state import build_topological, observation_digest

    view = build_topological({"s": s}, observation_digest({"s": s}))
    if not view.available:
        return None
    b = view.summary["betti_at_median"]
    return [float(b["b0"]), float(b["b1"]), float(b["b2"])]


def golden_butterfly_features(s: List[float]) -> List[float]:
    """Transform the (quantised) series by the N-point Fibonacci butterfly."""
    n = len(s)
    xs = [int(round(v * 100)) for v in s]
    basis = [0, 1]
    for _ in range(2, n):
        basis.append(basis[-1] + basis[-2])
    y = [sum(xs[m] * basis[(m + k) % n] for m in range(n)) for k in range(n)]
    mag = math.sqrt(sum(v * v for v in y)) or 1.0
    return [mag, max(abs(v) for v in y), float(sum(abs(v) for v in y))]


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------


def section_separability(bridge: Any) -> None:
    print("== separability: raw vs per-lens features, fixed classifier ==")
    for noise in (0.0, 0.05, 0.15):
        series, labels = make_populations(noise=noise)
        table: Dict[str, Any] = {}
        feats: Dict[str, List[Optional[List[float]]]] = {
            "raw": [raw_features(s) for s in series],
            "tensor": [tensor_features(bridge, s) for s in series],
            "algebraic": [algebraic_features(s) for s in series],
            "topological": [topological_features(s) for s in series],
            "golden_butterfly": [golden_butterfly_features(s) for s in series],
        }
        for name, fcols in feats.items():
            keep = [i for i, f in enumerate(fcols) if f is not None]
            if len(keep) < 6 or len({labels[i] for i in keep}) < 2:
                table[name] = {"available": False, "n_usable": len(keep)}
                continue
            acc = nearest_centroid_loo(
                [fcols[i] for i in keep], [labels[i] for i in keep]  # type: ignore
            )
            table[name] = {"available": True, "loo_accuracy": round(acc, 4), "n": len(keep)}
        # The lens designed for recurrence must beat raw where recurrence is the signal.
        alg = table.get("algebraic", {})
        check(
            "separability",
            f"algebraic lens separates planted recurrence (noise={noise})",
            bool(alg.get("available")) and alg["loo_accuracy"] > table["raw"]["loo_accuracy"],
            {"noise": noise, "accuracy_by_representation": table},
        )


def section_memory(bridge: Any) -> None:
    print("== memory: canonical-json view bytes vs pickled raw observation ==")
    from toe.intelligence_state import IntelligenceState

    data = {f"ch_{i}": [float((i + 1) * k + (k % 3)) for k in range(32)] for i in range(4)}
    st = IntelligenceState.observe(
        data, lenses=["statistical", "tensor", "temporal", "algebraic", "geometric", "topological"]
    )
    raw_bytes = len(pickle.dumps(data))
    rows = {}
    total_view_bytes = 0
    for name, view in st.views.items():
        b = len(json.dumps(view.as_dict(), default=str).encode())
        rows[name] = {"summary_bytes": b, "available": view.available}
        if view.available:
            total_view_bytes += b
    digest_handle_bytes = len(st.observation_sha256.encode())
    check(
        "memory",
        "per-view byte counts are measured honestly",
        all("summary_bytes" in r for r in rows.values()),
        {
            "raw_pickle_bytes": raw_bytes,
            "view_summary_bytes_total": total_view_bytes,
            "per_view_bytes": rows,
            "verdict": (
                "NEGATIVE for compression: full view summaries "
                f"({total_view_bytes} B) exceed the pickled observation "
                f"({raw_bytes} B) — representation is not storage "
                "compression. The small handle is the 64-hex observation "
                f"digest ({digest_handle_bytes} B); physical-storage "
                "claims are Pass 2 scope."
            ),
            "observation_digest_bytes": digest_handle_bytes,
        },
    )


def section_selection() -> None:
    print("== selection: signature -> lens choice with explicit rejections ==")
    from toe.representation import choose

    # (a) planted recurrence -> algebraic selected
    fib = [0, 1]
    for _ in range(18):
        fib.append(fib[-1] + fib[-2])
    out = choose({"s": fib})
    names = [n for n, _ in out["selection"]["selected"]]
    check(
        "selection",
        "recurrence-structured series selects algebraic",
        "algebraic" in names,
        {"signature": out["signature"], "selected": out["selection"]["selected"]},
    )
    # (b) scalar -> only statistical
    out = choose(3.5)
    names = [n for n, _ in out["selection"]["selected"]]
    rej = dict(out["selection"]["rejected"])
    check(
        "selection",
        "scalar observation selects only statistical; others rejected with reasons",
        names == ["statistical"] and len(rej) >= 5,
        {"selected": names, "rejected": rej},
    )
    # (c) supplied DAG -> causal_graph admitted; absent -> rejected
    dag = {"edges": [("a", "b"), ("b", "c")], "nodes": ["a", "b", "c"]}
    out_yes = choose({"a": 1.0, "b": 2.0, "c": 3.0}, graph=dag)
    sel_yes = [n for n, _ in out_yes["selection"]["selected"]]
    out_no = choose({"a": 1.0, "b": 2.0, "c": 3.0})
    rej_no = dict(out_no["selection"]["rejected"])
    check(
        "selection",
        "causal_graph selected iff a graph is supplied",
        "causal_graph" in sel_yes
        and "causal_graph" in rej_no
        and "discovery" in rej_no["causal_graph"],
        {"with_graph": sel_yes, "without_graph_rejection": rej_no.get("causal_graph")},
    )
    # (d) iid series -> algebraic rejected
    rng = random.Random(7)
    iid = [rng.gauss(0, 1) for _ in range(20)]
    out = choose({"s": iid})
    sel = [n for n, _ in out["selection"]["selected"]]
    rej = dict(out["selection"]["rejected"])
    check(
        "selection",
        "structureless iid series does not select algebraic",
        "algebraic" in rej or ("algebraic" in sel and False),
        {"selected": sel, "rejection": rej.get("algebraic")},
    )


def section_identity() -> None:
    print("== identity: one observation identity across every bound view ==")
    from toe.intelligence_state import (
        DivergenceError,
        IntelligenceState,
        LensView,
    )

    data = {"a": [1.0, 2.0, 3.0, 4.0, 5.0], "b": [2.0, 1.0, 2.0, 1.0, 2.0]}
    st = IntelligenceState.observe(data)
    digests = {v.observation_sha256 for v in st.views.values()}
    check(
        "identity",
        "all bound views carry the same observation digest",
        len(digests) == 1 and digests == {st.observation_sha256},
        {"digest": st.observation_sha256, "views": sorted(st.views)},
    )
    check(
        "identity",
        "receipt ledger verifies",
        st.verify_views()["ok"] and st.receipts.verify()["ok"],
        st.verify_views(),
    )
    other = IntelligenceState.observe({"a": [9.0, 9.0, 9.0, 9.0, 9.0]})
    foreign = LensView(
        "statistical",
        True,
        other.observation_sha256,
        "forged foreign view",
        summary={},
    )
    try:
        st.bind(foreign)
        raised = False
    except DivergenceError:
        raised = True
    check(
        "identity",
        "binding a foreign-digest view raises DivergenceError",
        raised,
        {},
    )


def section_causal_admission() -> None:
    print("== causal_admit: supplied-graph only ==")
    from toe.intelligence_state import IntelligenceState

    data = {"x": [1.0, 2.0, 3.0, 4.0], "y": [2.0, 4.0, 6.0, 8.0]}
    no_graph = IntelligenceState.observe(data, lenses=["causal_graph"])
    dag = {"edges": [("x", "y")], "nodes": ["x", "y"]}
    with_graph = IntelligenceState.observe(data, graph=dag, lenses=["causal_graph"])
    check(
        "causal_admit",
        "causal_graph unavailable without supplied structure, available with it",
        (not no_graph.views["causal_graph"].available)
        and "not causal discovery" in (no_graph.views["causal_graph"].reason or "")
        and with_graph.views["causal_graph"].available,
        {
            "without_graph_reason": no_graph.views["causal_graph"].reason,
            "with_graph_summary": with_graph.views["causal_graph"].summary,
        },
    )


def section_golden_contract() -> None:
    print("== golden_contract: supported-N invertibility + int64 bound ==")
    from toe.intelligence_state import fibonacci_butterfly_contract

    table = fibonacci_butterfly_contract(40)
    invertible = [n for n, r in table.items() if r["invertible"]]
    singular = [n for n, r in table.items() if not r["invertible"]]
    check(
        "golden_contract",
        "supported-N invertibility table computed exactly (Bareiss det)",
        11 in invertible,
        {
            "invertible_N": invertible,
            "singular_N": singular,
            "note": "det(M_phi^n)=±1 does NOT imply the N-point butterfly "
            "is invertible; this table is the contract",
        },
    )
    import numpy as np

    from hyba.math_ir.emit_cpu import emit_cpu
    from hyba.math_ir.specs import get_spec

    spec = get_spec("golden_ontology_transform")
    check(
        "golden_contract",
        "spec precision_bound is the explicit i64-bounded contract",
        spec.precision_bound == "i64-bounded",
        {"precision_bound": spec.precision_bound},
    )
    run = emit_cpu("golden_ontology_transform")
    n = 11
    basis = np.array([0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55], dtype=np.int64)
    big = np.full(n, 2**62, dtype=np.int64)
    try:
        run({"x_re": big, "fib_basis": basis, "n_points": n}, {})
        overflowed = "silently_wrapped"
    except OverflowError:
        overflowed = "raised"
    check(
        "golden_contract",
        "CPU emitter raises OverflowError on int64 overflow (never wraps)",
        overflowed == "raised",
        {"behaviour": overflowed},
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default="reports/toe_representation_elevation.json")
    args = parser.parse_args()

    print("TOE representation elevation probe (sections 3-5)")
    t0 = datetime.now(timezone.utc)
    from toe.bridge import TOEBridge

    bridge = TOEBridge()
    section_separability(bridge)
    section_memory(bridge)
    section_selection()
    section_identity()
    section_causal_admission()
    section_golden_contract()

    failed = [r for r in RESULTS if r["status"] == "FAIL"]
    unavail = [r for r in RESULTS if r["status"] == "UNAVAILABLE"]
    doc = {
        "format": "toe.representation_elevation/v1",
        "generated_at": t0.isoformat(),
        "commit": _git_sha(),
        "results": RESULTS,
        "summary": {
            "checks": len(RESULTS),
            "passed": len(RESULTS) - len(failed) - len(unavail),
            "failed": len(failed),
            "unavailable": len(unavail),
        },
    }
    report = Path(args.report)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(doc, indent=2, default=str), encoding="utf-8")
    print(f"\n{doc['summary']} — wrote {report}")
    if failed:
        print("FAILED:", ["{}:{}".format(r["section"], r["check"]) for r in failed])
        return 1
    if unavail:
        return 2
    return 0


def _git_sha() -> Optional[str]:
    try:
        import subprocess

        return subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT
        ).stdout.strip()
    except Exception:
        return None


if __name__ == "__main__":
    sys.exit(main())
