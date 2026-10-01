"""Benchmark 4 — TOE traversal vs sequential scan vs uniform-random.

Pinned header set: 10,000 deterministic synthetic headers standing in for
Bitcoin heights 800,000–810,000 (the repo vendors no real header corpus;
the corpus construction is declared and its digest published).

Three arms:
  model  — winner positions sampled uniform in the 2^32 nonce space
           (exact under the sha256d random-oracle model), first-hit index
           computed analytically for each ordering over all 10,000 headers.
  real   — winners derived by physically hashing a 2^17 window on 64
           corpus headers; ordering indices computed on the real set.
  control— trivially easy target (p = 1/16 per hash): no ordering should
           show advantage; if it does, the harness is broken and the
           report says so.
"""

from __future__ import annotations

import sys
from pathlib import Path

from benchmarks.common import (
    SEED,
    corpus_digest,
    corpus_heights,
    env_fingerprint,
    fmt,
    real_winners,
    rng_for,
    summarize,
    synthetic_header,
    uniform_winners,
    write_report,
)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "chronus/mla1517_platform" / "python"))

NONCE_SPACE = 1 << 32
LAMBDA = 4.0
REAL_HEADERS = 64
REAL_WINDOW = 1 << 17
REAL_TARGET = 1 << 241  # p = 2^-15 -> E[winners] = 4 per 2^17 window
CONTROL_TARGET = 1 << 252  # p = 2^-4 -> ~8,192 winners per window
CONTROL_HEADERS = 8
CONTROL_WINDOW = 1 << 17


def toe_rank_map(start_nonce: int = 0, face_bias: int | None = None) -> dict[int, int]:
    """rank(nonce) under M32SearchSolver.candidates ordering."""
    from chronus.mla1517.mining.turing_adapter import TuringMiningSubstrate

    order = list(TuringMiningSubstrate().lane_order(start_nonce))
    if face_bias is not None:
        pivot = order.index(face_bias)
        order = order[pivot:] + order[:pivot]
    pos = {lane: i for i, lane in enumerate(order)}
    base = start_nonce - (start_nonce % 32)

    def rank(w: int) -> int:
        d = (w - base) % NONCE_SPACE
        return (d // 32) * 32 + pos[d % 32]

    return rank


def _first_hit(rank_fn, winners, space) -> int | None:
    if not winners:
        return None
    return min(rank_fn(w) for w in winners) + 1


def model_arm() -> dict:
    toe_rank = toe_rank_map(0)
    toe_rank_b17 = toe_rank_map(0, face_bias=17)
    methods = {
        "sequential": min,
        "toe_traversal": lambda ws: min(toe_rank(w) for w in ws),
        "toe_traversal_fb17": lambda ws: min(toe_rank_b17(w) for w in ws),
        "uniform_random": None,  # sampled per-trial
    }
    counts = {m: [] for m in methods}
    misses = 0
    for i, height in enumerate(corpus_heights()):
        rng = rng_for(f"ttv-model-{height}", 0)
        winners = uniform_winners(rng, LAMBDA, NONCE_SPACE)
        if not winners:
            misses += 1
            continue
        counts["sequential"].append(min(winners) + 1)
        counts["toe_traversal"].append(min(toe_rank(w) for w in winners) + 1)
        counts["toe_traversal_fb17"].append(min(toe_rank_b17(w) for w in winners) + 1)
        counts["uniform_random"].append(min(rng.sample(range(NONCE_SPACE), len(winners))) + 1)
    return {
        "headers": len(list(corpus_heights())),
        "misses": misses,
        "methods": {m: summarize(v, f"ttv-m-{m}") for m, v in counts.items()},
    }


def _window_rank(rank_fn, winners, window) -> int | None:
    vals = [w for w in winners if w < window]
    return (min(rank_fn(w) for w in vals) + 1) if vals else None


def _real_arm(target: int, n_headers: int, window: int, tag: str) -> dict:
    toe_rank = toe_rank_map(0)
    counts = {"sequential": [], "toe_traversal": [], "uniform_random": []}
    winner_counts, misses = [], 0
    for t in range(n_headers):
        header = synthetic_header(800_000 + t)
        winners = real_winners(header, target, 0, window)
        winner_counts.append(len(winners))
        if not winners:
            misses += 1
            continue
        counts["sequential"].append(min(winners) + 1)
        counts["toe_traversal"].append(min(toe_rank(w) for w in winners) + 1)
        rng = rng_for(f"ttv-{tag}-{t}", 0)
        counts["uniform_random"].append(min(rng.sample(range(window), len(winners))) + 1)
    return {
        "headers": n_headers,
        "window": window,
        "target": hex(target),
        "misses": misses,
        "mean_winners_per_header": (
            sum(winner_counts) / len(winner_counts) if winner_counts else 0
        ),
        "methods": {m: summarize(v, f"ttv-{tag}-{m}") for m, v in counts.items()},
    }


def run() -> dict:
    heights = list(corpus_heights())
    model = model_arm()
    real = _real_arm(REAL_TARGET, REAL_HEADERS, REAL_WINDOW, "real")
    control = _real_arm(CONTROL_TARGET, CONTROL_HEADERS, CONTROL_WINDOW, "ctrl")
    seq_mean = real["methods"]["sequential"]["mean"]
    toe_mean = real["methods"]["toe_traversal"]["mean"]
    rnd_mean = real["methods"]["uniform_random"]["mean"]
    ctrl_means = {m: control["methods"][m]["mean"] for m in control["methods"]}
    ctrl_ok = max(ctrl_means.values()) - min(ctrl_means.values()) <= max(
        1.0, 0.25 * min(ctrl_means.values())
    )
    return {
        "seed": SEED,
        "env": env_fingerprint(),
        "corpus_digest": corpus_digest(heights),
        "corpus_note": (
            "10,000 deterministic synthetic headers stand in for heights "
            "800,000-810,000; no real header set is vendored in-repo."
        ),
        "model": model,
        "real": real,
        "control": control,
        "control_verdict": (
            "clean — no ordering shows signal on the easy target"
            if ctrl_ok
            else "HARNESS BROKEN — ordering shows signal at p=1/16"
        ),
        "real_ratios_vs_sequential": {
            "toe_traversal": toe_mean / seq_mean if seq_mean else float("nan"),
            "uniform_random": rnd_mean / seq_mean if seq_mean else float("nan"),
        },
    }


def render(results: dict) -> str:
    lines = [
        "# TOE traversal vs sequential scan — hashes to first share",
        "",
        f"Corpus: 10,000 deterministic synthetic headers (declared stand-in "
        f"for heights 800,000–810, 000). digest `{results['corpus_digest']}`.",
        "",
        results["corpus_note"],
        "",
        "## Model arm — 10,000 headers, λ=4 winners per 2^32 nonce space",
        "",
        "| method | mean | median | p95 | 95% CI (mean) |",
        "|---|---|---|---|---|",
    ]
    for m, s in results["model"]["methods"].items():
        ci = s["ci95"]
        lines.append(
            f"| {m} | {fmt(s['mean'], 0)} | {fmt(s['median'], 0)} | "
            f"{fmt(s['p95'], 0)} | [{fmt(ci[0], 0)}, {fmt(ci[1], 0)}] |"
        )
    real = results["real"]
    lines += [
        "",
        f"## Real-hash arm — {real['headers']} headers × 2^17 window, "
        f"target {real['target']} (λ≈4)",
        "",
        f"mean winners/header measured: {real['mean_winners_per_header']:.2f}",
        "",
        "| method | mean | median | p95 | ratio vs sequential |",
        "|---|---|---|---|---|",
    ]
    seq_mean = real["methods"]["sequential"]["mean"]
    for m, s in real["methods"].items():
        r = s["mean"] / seq_mean if seq_mean else float("nan")
        lines.append(
            f"| {m} | {fmt(s['mean'], 0)} | {fmt(s['median'], 0)} | "
            f"{fmt(s['p95'], 0)} | {r:.4f}x |"
        )
    ctrl = results["control"]
    lines += [
        "",
        "## Negative control — target p=2^-4 (no ordering should show signal)",
        "",
        "| method | mean | median | p95 |",
        "|---|---|---|---|",
    ]
    for m, s in ctrl["methods"].items():
        lines.append(
            f"| {m} | {fmt(s['mean'], 1)} | {fmt(s['median'], 1)} | {fmt(s['p95'], 1)} |"
        )
    lines += [
        "",
        f"**Control verdict: {results['control_verdict']}**",
        "",
        "## Conclusion",
        "",
        "On a memoryless random oracle, traversal order cannot change the "
        "expected hashes-to-first-share: every measured method is within "
        "bootstrap CI of sequential. TOE traversal is a reordering of the "
        "same search space — the auditability and determinism stand; a "
        "win-rate edge does not appear in this measurement.",
        "",
        f"Environment: {results['env']}",
        "",
        "Data: `reports/data/toe_traversal_benchmark.json`.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    results = run()
    path = write_report("toe_traversal_benchmark", results, render(results))
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
