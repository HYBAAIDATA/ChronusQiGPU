"""Nonce resonance probe — empirical check of the phi-resonance mining claim.

The recovered HYBA_Mining doc claims: "~70% of nonce space exhibits
phi-resonance patterns" and that scoring nonces by
``score = 1 - |frac(n * phi^-1) - 0.5| * 2`` enables "O(1) complexity for
search problems".

This probe pulls N nonces through the repo's real NonceScheduler (the
Zeckendorf/golden-limb ordering that replaced phi-scrambling), scores each
with the doc's formula, runs the real sha256d PoW predicate
(``mla1517.mining.pow.check_pow``) against a fixed target, and reports
whether high-resonance nonces actually win more often than low-resonance
ones. A uniform-random control group gives the baseline.

SHA256d is a random oracle, so the honest expectation is no correlation —
this script measures that rather than asserting it.

Usage:  python -m scripts.nonce_resonance_probe [--n 100] [--win-rate 0.10]
"""

from __future__ import annotations

import argparse
import random
import statistics
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "mla1517_platform_v3.4" / "python")
)

from mla1517.mining.pow import build_header, check_pow  # noqa: E402
from mining.nonce_scheduler import NonceScheduler  # noqa: E402

PHI_INV = (5.0**0.5 - 1.0) / 2.0  # 1/phi = 0.6180339887498949


def phi_resonance(nonce: int) -> float:
    """Doc's formula: score = 1 - |frac(n * phi^-1) - 0.5| * 2, in [0,1]."""
    frac = (nonce * PHI_INV) % 1.0
    return 1.0 - abs(frac - 0.5) * 2.0


def nonce_from_entry(entry: int | dict) -> int:
    """Extract a uint32 nonce from a schedule entry."""
    if isinstance(entry, dict):
        for key in ("nonce", "index", "value"):
            if key in entry:
                return int(entry[key]) & 0xFFFFFFFF
        return int(next(iter(entry.values()))) & 0xFFFFFFFF
    return int(entry) & 0xFFFFFFFF


def run_group(nonces: list[int], header_base: bytes, target: int) -> list[dict]:
    rows = []
    for n in nonces:
        header = header_base + struct.pack("<I", n)
        rows.append(
            {
                "nonce": n,
                "score": phi_resonance(n),
                "won": check_pow(header, target),
            }
        )
    return rows


def quartile_stats(rows: list[dict]) -> list[tuple[float, float, int, int]]:
    """Split rows into score quartiles; return (lo, hi, wins, count)."""
    ordered = sorted(rows, key=lambda r: r["score"])
    q = len(ordered) // 4
    out = []
    for i in range(4):
        chunk = ordered[i * q : (i + 1) * q if i < 3 else len(ordered)]
        if not chunk:
            continue
        wins = sum(1 for r in chunk if r["won"])
        out.append((chunk[0]["score"], chunk[-1]["score"], wins, len(chunk)))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--n", type=int, default=100, help="nonces per group")
    ap.add_argument(
        "--win-rate",
        type=float,
        default=0.10,
        help="expected per-nonce win probability (sets the target)",
    )
    ap.add_argument("--seed", type=int, default=1517)
    args = ap.parse_args()

    # Deterministic header base (version | prevhash | merkle | ntime | nbits).
    header = build_header(
        version=0x20000000,
        previous_hash="00" * 32,
        merkle_root="11" * 32,
        timestamp=0x69000000,
        bits="207fffff",
        nonce=0,
    )
    header_base = header[:76]

    # Target giving each nonce a ~win_rate chance: target = 2^256 * win_rate.
    target = int(2**256 * args.win_rate)

    sched = NonceScheduler(nonce_window=0xFFFFFFFF, cap=max(args.n * 4, 4096))
    scheduled = [nonce_from_entry(e) for e in sched.schedule(header)][: args.n]

    rng = random.Random(args.seed)
    random_nonces = [rng.randrange(2**32) for _ in range(args.n)]

    sched_rows = run_group(scheduled, header_base, target)
    rand_rows = run_group(random_nonces, header_base, target)

    def report(name: str, rows: list[dict]) -> None:
        scores = [r["score"] for r in rows]
        wins = sum(1 for r in rows if r["won"])
        mean = statistics.mean(scores)
        above = sum(1 for s in scores if s >= 0.5)
        print(f"\n== {name} (n={len(rows)}, expected win rate {args.win_rate:.0%}) ==")
        print(f"winners: {wins}/{len(rows)}  ({wins / len(rows):.1%})")
        print(
            f"phi-resonance score: mean {mean:.3f}, "
            f">=0.5 ('resonant'): {above}/{len(rows)} ({above / len(rows):.0%})"
        )
        print("score quartile -> wins:")
        for lo, hi, w, c in quartile_stats(rows):
            print(f"  [{lo:.3f}, {hi:.3f}]: {w}/{c} wins ({w / c:.0%})")

    print(f"target = 2^256 * {args.win_rate}  |  PoW predicate: sha256d <= target")
    report("Scheduled nonces (NonceScheduler)", sched_rows)
    report("Uniform-random control", rand_rows)

    # Verdict: does high resonance predict wins? Compare top-half vs bottom-half.
    def top_bottom(rows: list[dict]) -> tuple[float, float]:
        ordered = sorted(rows, key=lambda r: r["score"])
        mid = len(ordered) // 2
        lo = ordered[:mid]
        hi = ordered[mid:]
        lw = sum(r["won"] for r in lo) / max(len(lo), 1)
        hw = sum(r["won"] for r in hi) / max(len(hi), 1)
        return lw, hw

    sl, sh = top_bottom(sched_rows)
    rl, rh = top_bottom(rand_rows)
    print("\n== Verdict ==")
    print(f"scheduled: low-resonance win rate {sl:.1%}, high-resonance {sh:.1%}")
    print(f"random:    low-resonance win rate {rl:.1%}, high-resonance {rh:.1%}")
    print(
        "Note: frac(n/phi) is equidistributed, so ~'70% resonant' claims are "
        "a property of the score threshold, not of the nonce space; sha256d "
        "is a random oracle, so no ordering heuristic can raise the win rate."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
