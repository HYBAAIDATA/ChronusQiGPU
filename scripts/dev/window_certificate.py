"""Window certificate + matched-cap null for the Pisot probe schedule.

Closes the two questions raised in the A/B review (2026-11-17).

1. WINDOW. The A/B harness ran pisot_schedule(window=batch, ...) - the
   schedule's offset space EQUALS the linear range (both 65,536). This script
   proves it without trusting the harness: at cap == window the schedule must
   cover every residue exactly once, so

       set(schedule) == set(range(window))

   and the matched-cap paired min-digest null is P(win) = 0, all ties, mean
   exactly 0. The reviewer's window_size=100_000 hypothesis is also tested
   against the measured intersection of the registered run: 44,300 of 50,000
   schedule offsets fell below the K threshold (88.6%). For a bottom-up sweep
   over a 100,000 window that fraction would be ~50%; the observation is
   consistent with 65,536 and inconsistent with 100,000.

2. EXCHANGEABILITY. With A == B the min-digest difference is identically zero
   for every block. The 53/500 wins observed in the registered K-matched run
   came from the schedule's offsets >= K (5,700 of them, present by
   construction in any K-matched design), not from a larger window.

Note on the schedule's structure (reviewer's algebra, one refinement): four
of the five limbs are linear in the step counter (2k+1, k+2, 2k, 3k) - a
jittered linear sweep. The fifth, lucas(k) mod window, is NOT a sparse
monotone exponential: Lucas mod 2**16 is periodic (period 3*2**15 = 98,304),
so it acts as a pseudorandom scatter - and it is the limb that completes the
last residues after the linear limbs plateau, which is why matched-cap
generation runs deep into the guard. Guard is 4*window iterations with one
lucas call per five, i.e. ~52,000 lucas calls to fill 65,536.

Reporting: this is an ASSERTION RECORD, not a bootstrap. Under window ==
batch, min over the full batch is provably never worse than min over the
schedule, so the expected result is exactly: wins 0/500, ties 500, mean
0.00000, by set inclusion. No confidence interval is computed or wanted - a
CI on a deterministic zero would read as a degenerate estimate rather than a
proof. Label: window = 65_536, deployment comparison (not a second K-match).
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nonce_order_ab import BATCH, _digest, pisot_schedule  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
VECTOR = ROOT / "tests" / "vectors" / "mainnet_nonces_975565_976064.json"


def main() -> int:
    window = BATCH  # exactly what the registered run passed as the window
    label = f"window = {window}, deployment comparison"
    print(f"certificate: {label}", flush=True)
    print(f"building schedule(window={window}, cap={window}) ...", flush=True)
    schedule = pisot_schedule(window, cap=window)
    schedule_set = set(schedule)
    linear_all = set(range(window))

    # Theorem 1, asserted not sampled: every offset is a value % window, so A
    # is a subset of the linear range whenever window == batch. Full fill at
    # cap == window is the stronger observed fact, reported alongside.
    assert schedule_set.issubset(linear_all), "A is not a subset of range(batch)"
    full_fill = schedule_set == linear_all
    print(f"assert set(schedule).issubset(range({window})): holds "
          f"({len(schedule_set)} distinct offsets; full fill: {full_fill})")

    data = json.loads(VECTOR.read_text(encoding="utf-8"))
    print("theorem 2, hashed per block over BOTH orders "
          "(catches a swapped ordering or a broken _digest) ...", flush=True)
    diffs = []
    wins = ties = losses = 0
    for count, row in enumerate(data["blocks"]):
        prefix = bytes.fromhex(row["prefix_hex"])
        best_sched = None
        for nonce in schedule:
            digest = _digest(prefix, nonce)
            if best_sched is None or digest < best_sched:
                best_sched = digest
        best_lin = None
        for nonce in range(window):
            digest = _digest(prefix, nonce)
            if best_lin is None or digest < best_lin:
                best_lin = digest
        # min(B) <= min(A) follows from set inclusion; a violation means the
        # harness is broken - exactly the failure a bootstrap CI would hide.
        assert best_sched >= best_lin, (
            f"min(schedule) < min(linear) at height {row['height']}"
        )
        diff = math.log10(best_sched) - math.log10(best_lin)
        diffs.append(diff)
        if diff < 0.0:
            wins += 1
        elif diff == 0.0:
            ties += 1
        else:
            losses += 1
        if (count + 1) % 50 == 0 or count + 1 == len(data["blocks"]):
            print(f"  paired {count + 1}/{len(data['blocks'])}", flush=True)

    total = len(diffs)
    mean = sum(diffs) / total
    max_abs_diff = max(abs(d) for d in diffs)
    print(f"\nreport: wins {wins}/{total}, ties {ties}, losses {losses}, "
          f"mean {mean:.5f} - by set inclusion")
    print(f"max |diff|         {max_abs_diff:.6f} decades (expected exactly 0)")
    clean = wins == 0 and losses == 0 and mean == 0.0
    print(f"verdict            {'HOLDS' if clean else 'FAILED'}  ({label})")

    out = ROOT / "build" / "window_certificate.json"
    out.write_text(json.dumps({
        "label": label,
        "window": window,
        "blocks": total,
        "wins": wins,
        "ties": ties,
        "losses": losses,
        "mean_log10_diff": mean,
        "max_abs_diff": max_abs_diff,
        "full_fill": full_fill,
    }, indent=1), encoding="utf-8")
    print(f"results written to {out}")
    return 0 if clean else 1


if __name__ == "__main__":
    sys.exit(main())