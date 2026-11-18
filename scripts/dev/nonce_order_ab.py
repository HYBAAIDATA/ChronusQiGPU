"""A/B: Pisot probe schedule vs linear scan, on real mainnet headers.

Provenance of the schedule under test: ``pisot_schedule`` below is the
owner-supplied verbatim copy of ``PythiaPrecomputedSolver
.generate_pisot_probe_schedule`` from the unlanded drop-in. No module under
``src/`` defines it (searched 2026-11-17); swap to the import when it lands.
The 50,000-probe cap is a parameter of that drop-in, NOT of the current
repository: the mining entrypoint defaults to ``MINING_NONCE_BATCH=65536``
with a hard ceiling of 2**20, and no 50,000 constant exists in ``src/`` or in
the archived design narrative.

Pre-registered expectations, recorded before any run (amendments are marked *
and were made before execution, with reasons):

  coverage    schedule < linear   (cap 50_000 of a 65_536 batch -> ~76%)
  probe cost  schedule > linear   (lucas() bigint work per schedule probe)
  min digest  indistinguishable   (K iid draws have the same min law)

* Amendment 1 (pre-run): the paired min-digest test is K-MATCHED. Comparing
  50,000 schedule probes against 65,536 linear probes confounds the null:
  E[log10 min] shifts by log10(65537/50001) ~= +0.117 decades purely from the
  draw-count difference. Linear is therefore truncated to the schedule's probe
  count for the null test. The unequal-K shipped-vs-full comparison is still
  reported separately as the coverage penalty, checked against its +0.117
  analytic expectation.
* Amendment 2 (pre-run): with overlapping probe sets the "coin flip" is not
  fair. Under iid digests, P(schedule < linear) = |A\\B| / |AUB| and
  P(tie) = |A&B| / |AUB|. These are computed from the measured sets and the
  observed win/tie counts are compared against them.
* Amendment 3 (pre-run): schedule generation is timed single-shot, not
  median-of-7. The build is deterministic and bigint-heavy; repeating it seven
  times multiplies runtime without adding information. Hash probes keep the
  median-of-7 measurement.
* Amendment 4 (pre-run, before the 500-block run): the original verdict rule
  |mean| < 0.01 is tighter than one null sigma. With ~20% non-tie events of
  ~0.9 decades each over 500 paired blocks, the null mean carries sigma ~= 0.02,
  so the 0.01 rule would flag a TRUE null most of the time (a 10-block smoke
  run demonstrated exactly this artifact). The registered min-digest verdict
  is therefore: the 95% bootstrap CI includes 0, AND the observed win/tie
  counts sit within 3 sigma of their analytic expectations.

POST-RUN CLARIFICATION (2026-11-17, after the registered run; no threshold
changed, pre-registration text above is frozen):

  The window EQUALS --batch in the registered run: pisot_schedule was called
  with window = batch = 65_536, and the matched row produced all 65_536
  residues, so set(schedule) == set(range(65_536)) - proven without hashing by
  scripts/dev/window_certificate.py, which also runs the matched-cap paired
  null (P(win) = 0, all ties, mean exactly 0). The reviewer's
  window_size=100_000 hypothesis concerns the unlanded drop-in's default, not
  this harness; the measured intersection refutes it for this run as well
  (44,300 of 50,000 schedule offsets fell below the K threshold - 88.6%,
  vs ~50% expected for a bottom-up sweep over a 100,000 window). Coverage is
  now reported as count_coverage (probes / linear probes) AND range_density
  (probes / window). With window == batch the two coincide (0.763); the
  0.500-over-1.53x-range framing belonged to the 100,000 hypothesis, which
  the reviewer has since withdrawn - it is retained nowhere as a measurement.

If any of the three surprises, that IS the finding. Do not move the
thresholds after seeing the numbers.

Hash count cannot differ for equal K: the min of K iid draws has the same law
whichever K indices you choose. The real axes are coverage, per-probe cost,
and locality. The two table rows separate "the schedule is bad" (matched cap)
from "the cap is bad" (shipped cap against the repo's 65,536 batch).
"""

import argparse
import hashlib
import json
import math
import random
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_VECTOR = ROOT / "tests" / "vectors" / "mainnet_nonces_975565_976064.json"
DEFAULT_OUT = ROOT / "build" / "nonce_order_ab_results.json"
BATCH = 65_536
SHIPPED_CAP = 50_000
BOOTSTRAP = 10_000
SEED = 20_261_117
PROBE_SAMPLE = 4_096


# --- schedule under test ----------------------------------------------------
# Owner-supplied verbatim copy of PythiaPrecomputedSolver
# .generate_pisot_probe_schedule from the unlanded drop-in (see header).
def _fib_pair(n):
    if n == 0:
        return (0, 1)
    a, b = _fib_pair(n >> 1)
    c = a * (2 * b - a)
    d = a * a + b * b
    return (d, c + d) if n & 1 else (c, d)


def _fib(n):
    return _fib_pair(n)[0]


def _lucas(n):
    return _fib(n - 1) + _fib(n + 1)


def _zeckendorf(n):
    if n <= 0:
        return []
    avail, k = [], 2
    while _fib(k) <= n:
        avail.append((k, _fib(k)))
        k += 1
    out = []
    for k, v in reversed(avail):
        if v <= n:
            out.append(k)
            n -= v
    return out


def pisot_schedule(window, seed=42, cap=SHIPPED_CAP):
    """Verbatim drop-in schedule (see the provenance note in the header)."""
    schedule, seen = [], set()
    for z in _zeckendorf(seed):
        off = (z * 13) % window
        if off not in seen:
            schedule.append(off)
            seen.add(off)
    limbs = [_lucas, lambda n: 2 * n + 1, lambda n: n + 2,
             lambda n: n * 2, lambda n: n * 3]
    k, li, guard = 1, 0, 0
    while len(schedule) < cap and guard < window * 4:
        off = limbs[li % len(limbs)](k) % window
        if off not in seen:
            schedule.append(off)
            seen.add(off)
        li += 1
        if li % len(limbs) == 0:
            k += 1
        guard += 1
    return schedule


# --- hashing ----------------------------------------------------------------
def _digest(prefix: bytes, nonce: int) -> int:
    header = prefix + nonce.to_bytes(4, "little")
    return int.from_bytes(
        hashlib.sha256(hashlib.sha256(header).digest()).digest(), "little"
    )


def _min_log10(prefix: bytes, order) -> float:
    best = None
    for nonce in order:
        digest = _digest(prefix, nonce)
        if best is None or digest < best:
            best = digest
    return math.log10(best)


def _block_stats(prefix: bytes, schedule, batch: int) -> tuple[float, float, float]:
    """(log10 min over schedule, log10 min over linear[:K], log10 min over full linear).

    The full linear pass also captures the running minimum at K-1 so the
    K-matched null and the unequal-K coverage penalty come from one hash pass.
    """
    best_schedule = None
    for nonce in schedule:
        digest = _digest(prefix, nonce)
        if best_schedule is None or digest < best_schedule:
            best_schedule = digest
    best_full = None
    best_at_k = None
    k = len(schedule)
    for nonce in range(batch):
        digest = _digest(prefix, nonce)
        if best_full is None or digest < best_full:
            best_full = digest
        if nonce == k - 1:
            best_at_k = best_full
    return math.log10(best_schedule), math.log10(best_at_k), math.log10(best_full)


def _time(fn, repeats=7):
    samples = []
    for _ in range(repeats):
        t0 = time.perf_counter_ns()
        fn()
        samples.append(time.perf_counter_ns() - t0)
    return statistics.median(samples)


def _ci(diffs):
    rng = random.Random(SEED)
    means = sorted(
        sum(rng.choice(diffs) for _ in diffs) / len(diffs)
        for _ in range(BOOTSTRAP)
    )
    return means[int(0.025 * BOOTSTRAP)], means[int(0.975 * BOOTSTRAP)]


def main() -> int:
    parser = argparse.ArgumentParser(description="Pisot probe schedule vs linear scan A/B")
    parser.add_argument("--vector", type=Path, default=DEFAULT_VECTOR)
    parser.add_argument("--batch", type=int, default=BATCH)
    parser.add_argument("--limit", type=int, default=0, help="0 = all 500 blocks")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--window", type=int, default=0,
                        help="schedule offset space; 0 = window == batch")
    parser.add_argument("--skip-paired", action="store_true",
                        help="table + set analysis only (no per-block hashing)")
    args = parser.parse_args()
    window = args.window or args.batch

    data = json.loads(args.vector.read_text(encoding="utf-8"))
    rows = data["blocks"]
    if args.limit:
        rows = rows[: args.limit]

    print(f"{'variant':10} {'window':>7} {'cap':>7} {'produced':>9} "
          f"{'count_cov':>9} {'density':>8} {'gen us':>10} {'per probe us':>13}")
    count_coverage = {}
    range_density = {}
    gen_ns_by_label = {}
    probe_ns_by_label = {}
    orders = {}
    for label, cap in (("matched", args.batch), ("shipped", SHIPPED_CAP)):
        t0 = time.perf_counter_ns()
        order = pisot_schedule(window, cap=cap)  # single-shot: deterministic build
        gen_ns = time.perf_counter_ns() - t0
        distinct = len(set(order))
        orders[label] = order
        count_coverage[label] = distinct / args.batch
        range_density[label] = distinct / window
        gen_ns_by_label[label] = gen_ns
        prefix = bytes.fromhex(rows[0]["prefix_hex"])
        sample = order[:PROBE_SAMPLE]
        probe_ns_by_label[label] = _time(
            lambda o=sample: _min_log10(prefix, o)
        ) / max(1, len(sample))
        print(f"{label:10} {window:7d} {cap:7d} {distinct:9d} "
              f"{count_coverage[label]:9.3f} {range_density[label]:8.3f} "
              f"{gen_ns / 1e3:10.1f} {probe_ns_by_label[label] / 1e3:13.4f}")
    t0 = time.perf_counter_ns()
    linear_order = list(range(args.batch))
    gen_ns_linear = time.perf_counter_ns() - t0
    prefix = bytes.fromhex(rows[0]["prefix_hex"])
    probe_ns_linear = _time(
        lambda o=linear_order[:PROBE_SAMPLE]: _min_log10(prefix, o)
    ) / PROBE_SAMPLE
    print(f"{'linear':10} {window:7d} {args.batch:7d} {args.batch:9d} "
          f"{1.000:9.3f} {1.000:8.3f} "
          f"{gen_ns_linear / 1e3:10.1f} {probe_ns_linear / 1e3:13.4f}")

    schedule = orders["shipped"]
    k = len(schedule)
    set_a = set(schedule)
    set_b = set(range(k))
    inter = len(set_a & set_b)
    only_a = k - inter
    union = len(set_a | set_b)
    p_win = only_a / union if union else 0.0
    p_tie = inter / union if union else 0.0
    print(f"\nset analysis (K-matched): |A|={k} |A&B|={inter} |A only|={only_a} "
          f"-> expected wins {p_win:.3f}, ties {p_tie:.3f} (iid-digest null)")

    diffs = []
    cov_penalty = []
    wins = ties = losses = 0
    per_block = []
    if args.skip_paired:
        print("paired test SKIPPED (--skip-paired)")
    else:
        for count, row in enumerate(rows):
            prefix = bytes.fromhex(row["prefix_hex"])
            s, l_k, l_all = _block_stats(prefix, schedule, args.batch)
            diffs.append(s - l_k)
            cov_penalty.append(s - l_all)
            if s < l_k:
                wins += 1
            elif s == l_k:
                ties += 1
            else:
                losses += 1
            per_block.append({
                "height": row["height"],
                "min_sched_log10": s,
                "min_linear_k_log10": l_k,
                "min_linear_full_log10": l_all,
            })
            if (count + 1) % 50 == 0 or count + 1 == len(rows):
                print(f"  paired {count + 1}/{len(rows)}", flush=True)

    lo, hi = _ci(diffs)
    mean = sum(diffs) / len(diffs)
    mean_cov = sum(cov_penalty) / len(cov_penalty)
    expected_cov = math.log10((args.batch + 1) / (k + 1))

    if diffs:
        print(f"\npaired blocks        {len(diffs)}  (K={k} matched)")
        print(f"mean log10 diff      {mean:+.5f}  (null: 0)")
        print(f"95% bootstrap CI     [{lo:+.5f}, {hi:+.5f}]")
        print(f"schedule lower on    {wins}/{len(diffs)} ({100 * wins / len(diffs):.1f}%)  "
              f"ties {ties}  linear lower {losses}")
        sigma = math.sqrt(len(diffs) * p_win * (1 - p_win)) if 0 < p_win < 1 else 0.0
        print(f"expected wins        {p_win * len(diffs):.0f}  (sigma {sigma:.1f}), "
              f"expected ties {p_tie * len(diffs):.0f}")

    gen_probe_schedule = gen_ns_by_label["shipped"] / max(1, k)
    gen_probe_linear = gen_ns_linear / args.batch
    cost_schedule = gen_probe_schedule + probe_ns_by_label["shipped"]
    cost_linear = gen_probe_linear + probe_ns_linear
    ratio = cost_schedule / cost_linear if cost_linear else float("inf")

    print("\npre-registered verdicts:")
    print(f"  coverage   {'AS PREDICTED' if count_coverage['shipped'] < 1.0 else 'SURPRISE'}"
          f"  (count {count_coverage['shipped']:.3f}, density {range_density['shipped']:.3f}"
          f" of window {window})")
    print(f"  probe cost {'AS PREDICTED' if cost_schedule > cost_linear else 'SURPRISE'}"
          f"  (schedule/linear per-probe cost ratio {ratio:.1f}x)")
    if diffs:
        sigma_w = math.sqrt(len(diffs) * p_win * (1 - p_win)) if 0 < p_win < 1 else 0.0
        sigma_t = math.sqrt(len(diffs) * p_tie * (1 - p_tie)) if 0 < p_tie < 1 else 0.0
        wins_ok = abs(wins - p_win * len(diffs)) <= 3 * sigma_w
        ties_ok = abs(ties - p_tie * len(diffs)) <= 3 * sigma_t
        digest_ok = (lo <= 0.0 <= hi) and wins_ok and ties_ok
        print(f"  min digest {'AS PREDICTED' if digest_ok else 'SURPRISE'}"
              f"  (mean {mean:+.5f}, CI [{lo:+.5f}, {hi:+.5f}],"
              f" wins {'within 3s' if wins_ok else 'OUTSIDE 3s'},"
              f" ties {'within 3s' if ties_ok else 'OUTSIDE 3s'})")
        print(f"  coverage penalty (unequal K): mean {mean_cov:+.5f} "
              f"vs analytic {expected_cov:+.5f}")
    else:
        print("  min digest SKIPPED (--skip-paired)")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "batch": args.batch,
        "window": window,
        "schedule_k": k,
        "count_coverage": count_coverage,
        "range_density": range_density,
        "gen_ns": {**gen_ns_by_label, "linear": gen_ns_linear},
        "per_probe_hash_ns": {**probe_ns_by_label, "linear": probe_ns_linear},
        "per_probe_cost_ratio": ratio,
        "set_analysis": {"k": k, "intersection": inter, "only_a": only_a, "union": union},
        "paired": ({
            "blocks": len(diffs),
            "mean_log10_diff": mean,
            "ci95": [lo, hi],
            "wins": wins,
            "ties": ties,
            "losses": losses,
            "expected_wins": p_win * len(diffs),
            "expected_ties": p_tie * len(diffs),
        } if diffs else None),
        "coverage_penalty": ({"mean": mean_cov, "analytic": expected_cov} if diffs else None),
        "blocks": per_block,
    }, indent=1), encoding="utf-8")
    print(f"\nresults written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())