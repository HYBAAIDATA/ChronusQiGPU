#!/usr/bin/env python3
"""Real-block phi-resonance test — 1000+ real nonces vs random controls.

Fetches real Bitcoin blocks from blockstream.info (cached to
artifacts/blocks_cache.json so re-runs are instant), then applies three
resonance metrics found in the project:

  1. phi15_resonance  — the harness metric: k = round(nonce/φ¹⁵),
     diff = |nonce − k·φ¹⁵|, strength = 1 − diff/(φ¹⁵/2),
     is_resonant = precision ≥ 99.9999%  (the "95% resonant" headline)

  2. phi_mod1_resonance — PhiResonanceVerifier from
     bitcoin_phi_pci.py: min circular distance of nonce/2³² to the
     φ⁻ᵏ mod-1 targets (k = 1..15), tolerance 0.05

  3. lucas_score — LucasSearchAttractor.attractor_score(nonce) from
     lucas_search_attractor.py (raw scale + rescaled mod-2³² variants)

Every metric is run on BOTH the real nonces and on matched controls:
  - uniform-random nonces (same count, seeded)
  - shuffled real nonces (permutes the real values — same marginal
    distribution, destroys any positional structure)

The question is never "is the rate high?" — it is "is the rate higher
than the same metric produces on random data?".

Usage:
    python scripts/block_resonance_test.py --blocks 1000
    python scripts/block_resonance_test.py --blocks 1000 --refresh
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Tuple

PHI = (1.0 + math.sqrt(5.0)) / 2.0
PHI_15 = PHI**15  # ≈ 1364.000733
PRECISION_THRESHOLD = 99.9999
TWO_POW_32 = 4_294_967_296

LUCAS = [
    2,
    1,
    3,
    4,
    7,
    11,
    18,
    29,
    47,
    76,
    123,
    199,
    322,
    521,
    843,
    1364,
    2207,
    3571,
    5778,
    9349,
    15127,
]

BLOCKSTREAM = "https://blockstream.info/api"
CACHE_PATH = Path(__file__).resolve().parent.parent / "artifacts" / "blocks_cache.json"


# ---------------------------------------------------------------------------
# Metrics (replicated exactly from the project code, then tested)
# ---------------------------------------------------------------------------


def phi15_resonance(nonce: int) -> Tuple[float, bool]:
    """Harness metric from nonce_structure_test_harness.py.

    strength = 1 − |nonce − round(nonce/φ¹⁵)·φ¹⁵| / (φ¹⁵/2)
    is_resonant = (1 − diff/nonce)·100 ≥ 99.9999  OR  diff < 1
    """
    if nonce <= 0:
        return 0.0, False
    k = round(nonce / PHI_15)
    diff = abs(nonce - k * PHI_15)
    precision = (1.0 - diff / nonce) * 100.0
    strength = max(0.0, 1.0 - (diff / (PHI_15 / 2.0)))
    is_res = precision >= PRECISION_THRESHOLD or diff < 1.0
    return strength, is_res


# PhiResonanceVerifier from bitcoin_phi_pci.py — verbatim logic
_MOD1_TARGETS = [(1.0 / (PHI**k)) % 1.0 for k in range(1, 16)]
_MOD1_TOL = 0.05


def phi_mod1_resonance(nonce: int) -> Tuple[float, bool]:
    norm = (nonce % TWO_POW_32) / TWO_POW_32
    d = min(abs(norm - t) for t in _MOD1_TARGETS)
    wrap = min(d, 1.0 - d)
    score = max(0.0, 1.0 - (wrap / _MOD1_TOL))
    return score, wrap <= _MOD1_TOL


def lucas_attractor_score(nonce: int, scale: str = "mod") -> float:
    """LucasSearchAttractor.attractor_score applied to a nonce.

    The attractor's max node is L20 = 15127, far below nonce scale
    (~4e9), so the raw score is always ~0. 'mod' folds the nonce into
    the attractor's range first: nonce mod (2·max_lucas).
    """
    max_lucas = LUCAS[-1]
    if scale == "raw":
        x = nonce
    elif scale == "mod":
        x = nonce % (2 * max_lucas)
    elif scale == "scaled":
        x = int((nonce / TWO_POW_32) * 2 * max_lucas)
    else:
        raise ValueError(scale)
    dist = min(abs(x - L) for L in LUCAS)
    s = max(max_lucas * 0.01, 1.0)
    return 1.0 / (1.0 + dist / s)


# ---------------------------------------------------------------------------
# Block fetching (cached)
# ---------------------------------------------------------------------------


def _fetch(url: str, timeout: int = 20) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "euclid-resonance-test/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def fetch_blocks(count: int, refresh: bool = False) -> List[Dict[str, Any]]:
    """Fetch `count` most-recent blocks. Cached to artifacts/blocks_cache.json."""
    if CACHE_PATH.exists() and not refresh:
        cached = json.loads(CACHE_PATH.read_text())
        if len(cached) >= count:
            print(f"[cache] {len(cached)} blocks on disk, using {count}")
            return cached[:count]

    print(f"[fetch] pulling {count} blocks from blockstream.info ...")
    blocks: List[Dict[str, Any]] = []
    tip = _fetch(f"{BLOCKSTREAM}/blocks/tip/height", timeout=10)
    print(f"[fetch] tip = {tip}")

    height = tip
    while len(blocks) < count and height > 0:
        try:
            batch = _fetch(f"{BLOCKSTREAM}/blocks/{height}", timeout=20)
        except Exception as e:
            print(f"[fetch] retry after error at height {height}: {e}")
            time.sleep(1.0)
            continue
        if not batch:
            break
        blocks.extend(batch)
        height = batch[-1]["height"] - 1
        done = len(blocks)
        if done % 100 == 0 or done >= count:
            print(f"[fetch] {done}/{count} ...")
        time.sleep(0.15)  # be polite to the public API

    blocks = blocks[:count]
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(blocks))
    print(f"[fetch] done — {len(blocks)} blocks, cached to {CACHE_PATH}")
    return blocks


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


def summarise(strengths: List[float], resonant: List[bool], label: str) -> Dict[str, Any]:
    n = len(strengths)
    ge05 = sum(1 for s in strengths if s >= 0.5)
    ge07 = sum(1 for s in strengths if s >= 0.7)
    ge09 = sum(1 for s in strengths if s >= 0.9)
    res_rate = sum(resonant) / n
    mean = sum(strengths) / n
    return {
        "label": label,
        "n": n,
        "mean_strength": mean,
        "rate>=0.5": ge05 / n,
        "rate>=0.7": ge07 / n,
        "rate>=0.9": ge09 / n,
        "is_resonant_rate": res_rate,
    }


def ks_statistic(a: List[float], b: List[float]) -> float:
    """Two-sample Kolmogorov–Smirnov statistic."""
    xs = sorted(a)
    ys = sorted(b)
    i = j = 0
    d = 0.0
    na, nb = len(xs), len(ys)
    while i < na and j < nb:
        if xs[i] <= ys[j]:
            i += 1
        else:
            j += 1
        d = max(d, abs(i / na - j / nb))
    return d


def ks_pvalue(d: float, n1: int, n2: int) -> float:
    """Asymptotic KS p-value (Kolmogorov distribution)."""
    en = math.sqrt(n1 * n2 / (n1 + n2))
    lam = (en + 0.12 + 0.11 / en) * d
    s = sum(((-1) ** (k - 1)) * math.exp(-2 * (k * lam) ** 2) for k in range(1, 101))
    return max(0.0, min(1.0, 2 * s))


# ---------------------------------------------------------------------------
# Main test
# ---------------------------------------------------------------------------


def run_test(n_blocks: int, refresh: bool) -> Dict[str, Any]:
    blocks = fetch_blocks(n_blocks, refresh)
    nonces = [int(b["nonce"]) for b in blocks]
    n = len(nonces)
    print(f"\n[1] Real nonces: {n} (heights {blocks[0]['height']} .. {blocks[-1]['height']})")

    rng = random.Random(2024)
    random_nonces = [rng.randrange(TWO_POW_32) for _ in range(n)]
    shuffled = nonces[:]
    rng.shuffle(shuffled)

    results: Dict[str, Any] = {"n_blocks": n, "metrics": {}}

    for metric_name, fn in [
        ("phi15_strength", lambda x: phi15_resonance(x)),
        ("phi_mod1", lambda x: phi_mod1_resonance(x)),
        ("lucas_mod", lambda x: (lucas_attractor_score(x, "mod"), False)),
        ("lucas_scaled", lambda x: (lucas_attractor_score(x, "scaled"), False)),
    ]:
        real = [fn(x) for x in nonces]
        ctrl = [fn(x) for x in random_nonces]
        shuf = [fn(x) for x in shuffled]

        real_s = [r[0] for r in real]
        ctrl_s = [r[0] for r in ctrl]
        shuf_s = [r[0] for r in shuf]

        real_r = [r[1] for r in real]
        ctrl_r = [r[1] for r in ctrl]

        row_real = summarise(real_s, real_r, "real_blocks")
        row_ctrl = summarise(ctrl_s, ctrl_r, "random_control")
        row_shuf = summarise(shuf_s, real_r, "shuffled_blocks")

        d_rc = ks_statistic(real_s, ctrl_s)
        p_rc = ks_pvalue(d_rc, n, n)

        results["metrics"][metric_name] = {
            "real": row_real,
            "random": row_ctrl,
            "shuffled": row_shuf,
            "ks_real_vs_random": {"D": d_rc, "p": p_rc},
        }

    return results


def print_report(res: Dict[str, Any]) -> None:
    n = res["n_blocks"]
    print("\n" + "=" * 78)
    print(f"PHI-RESONANCE TEST — {n} REAL MAINNET NONCES vs CONTROLS")
    print("=" * 78)
    for name, m in res["metrics"].items():
        print(f"\n--- {name} ---")
        print(f"  {'':>22} {'mean':>8} {'>=0.5':>8} {'>=0.7':>8} {'>=0.9':>8} {'resonant':>9}")
        for key in ("real", "random", "shuffled"):
            r = m[key]
            print(
                f"  {r['label']:>22} {r['mean_strength']:8.4f} "
                f"{r['rate>=0.5']:8.3f} {r['rate>=0.7']:8.3f} {r['rate>=0.9']:8.3f} "
                f"{r['is_resonant_rate']:9.4f}"
            )
        ks = m["ks_real_vs_random"]
        verdict = "DIFFERENT from random" if ks["p"] < 0.01 else "consistent with random"
        print(f"  KS real vs random: D={ks['D']:.4f}  p={ks['p']:.4g}  → {verdict}")

    print("\n" + "-" * 78)
    print("INTERPRETATION")
    print("-" * 78)
    p15 = res["metrics"]["phi15_strength"]
    print(
        f"  phi15 strength≥0.5: real {p15['real']['rate>=0.5']*100:.1f}%  vs  "
        f"random {p15['random']['rate>=0.5']*100:.1f}%"
    )
    print(
        "  NOTE: the 'is_resonant' (precision ≥ 99.9999%) flag is vacuous for "
        "typical nonces — any nonce ≫ 682 always satisfies it, since "
        "diff ∈ [0, φ¹⁵/2] by construction."
    )


def main() -> int:
    # Windows consoles default to cp1252 — the report uses φ, ≥, →, etc.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Real-block phi-resonance test")
    ap.add_argument("--blocks", type=int, default=1000)
    ap.add_argument("--refresh", action="store_true", help="re-fetch instead of using cache")
    ap.add_argument("--save", type=str, default=None, help="write JSON report to this path")
    ap.add_argument("--csv", type=str, default=None, help="write per-block CSV to this path")
    args = ap.parse_args()

    res = run_test(args.blocks, args.refresh)
    print_report(res)

    if args.save:
        Path(args.save).parent.mkdir(parents=True, exist_ok=True)
        Path(args.save).write_text(json.dumps(res, indent=2))
        print(f"\nReport saved to {args.save}")

    if args.csv:
        blocks = json.loads(CACHE_PATH.read_text())[: res["n_blocks"]]
        with open(args.csv, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(
                [
                    "height",
                    "nonce",
                    "phi15_strength",
                    "phi15_resonant",
                    "mod1_score",
                    "mod1_resonant",
                    "lucas_mod",
                    "lucas_scaled",
                ]
            )
            for b in blocks:
                s, r = phi15_resonance(int(b["nonce"]))
                ms, mr = phi_mod1_resonance(int(b["nonce"]))
                w.writerow(
                    [
                        b["height"],
                        b["nonce"],
                        f"{s:.6f}",
                        r,
                        f"{ms:.6f}",
                        mr,
                        f"{lucas_attractor_score(b['nonce'], 'mod'):.6f}",
                        f"{lucas_attractor_score(b['nonce'], 'scaled'):.6f}",
                    ]
                )
        print(f"CSV saved to {args.csv}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
