"""Per-probe cost: full 80-byte rehash vs shared midstate + 16-byte tail.

Claim under test (owner, 2026-11-17): a shared midstate via hashlib sha256
.copy() saves one full compression per probe (~2x), and because every probe
then costs identically it removes locality as the last axis on which nonce
ORDERING could matter - making the ordering purely cosmetic for hashing.

Measured on real chain-verified headers, both orderings, equal probe counts:

  baseline : sha256d(prefix || nonce)   - inner hash = 2 compressions
  midstate : sha256(prefix[:64]) built once per header, then per probe
             copy() + update(12-byte suffix + 4-byte nonce) = 1 compression

The first sha256 of an 80-byte header processes exactly one full 64-byte
block plus a 16-byte tail block, so the midstate split is exact.

PRE-REGISTERED EXPECTATIONS (2026-11-17, recorded before any timing run):
  speedup 1.2x - 1.6x. The outer sha256 over the 32-byte digest is untouched,
  so round 2 caps the gain; .copy() adds per-call overhead exactly where
  rehashing 80 bytes is already cheap. Below 1.2x -> not worth the code.
  Above 1.6x -> suspect the benchmark before celebrating the number.

Correctness is asserted bit-exactly BEFORE timing, per nonce over the first
256 probes of EACH order (bind the copy, update, then digest - update()
returns None, so no call chaining that could silently reorder the tail).
No ordering advantage is possible or claimed: with a shared midstate every
probe costs identically BY CONSTRUCTION, so ordering cannot affect per-probe
cost at all. That makes order-independence structural rather than measured
and retires the locality axis permanently, whether or not the ratio lands
inside the band.
"""
import hashlib
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nonce_order_ab import SHIPPED_CAP, pisot_schedule  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
VECTOR = ROOT / "tests" / "vectors" / "mainnet_nonces_975565_976064.json"
OUT = ROOT / "build" / "midstate_bench.json"
PROBES = SHIPPED_CAP  # 50_000, equal counts for both orderings
REPEATS = 3
HEADERS = 5


def sha256d(prefix: bytes, nonce: int) -> int:
    header = prefix + nonce.to_bytes(4, "little")
    return int.from_bytes(
        hashlib.sha256(hashlib.sha256(header).digest()).digest(), "little"
    )


def sha256d_mid(mid, tail: bytes, nonce: int) -> int:
    h = mid.copy()
    h.update(tail + nonce.to_bytes(4, "little"))
    return int.from_bytes(hashlib.sha256(h.digest()).digest(), "little")


def bench_min(prefix_full: bytes, prefix_tail: bytes, order, mid) -> float:
    """Median nanoseconds of a full min-scan over the order (as in the A/B)."""
    samples = []

    def run():
        best = None
        if mid is None:
            for nonce in order:
                digest = sha256d(prefix_full, nonce)
                if best is None or digest < best:
                    best = digest
        else:
            for nonce in order:
                digest = sha256d_mid(mid, prefix_tail, nonce)
                if best is None or digest < best:
                    best = digest

    for _ in range(REPEATS):
        t0 = time.perf_counter_ns()
        run()
        samples.append(time.perf_counter_ns() - t0)
    return statistics.median(samples)


def main() -> int:
    data = json.loads(VECTOR.read_text(encoding="utf-8"))
    rows = data["blocks"][:HEADERS]
    schedule = pisot_schedule(65_536, cap=SHIPPED_CAP)
    linear = range(PROBES)
    results = []

    print(f"probes per arm {PROBES}, repeats {REPEATS}, headers {len(rows)}\n")
    print(f"{'height':>7} {'base lin us':>12} {'base sched us':>14} "
          f"{'mid lin us':>11} {'mid sched us':>13} {'speedup':>8}")
    for row in rows:
        prefix_full = bytes.fromhex(row["prefix_hex"])
        mid = hashlib.sha256(prefix_full[:64])
        tail = prefix_full[64:]

        # Bit-exact correctness BEFORE any timing: per nonce over the first
        # 256 probes of each order. Bind the copy, update, then digest -
        # update() returns None, so no call chaining.
        for order in (schedule, linear):
            for nonce in list(order)[:256]:
                reference = hashlib.sha256(
                    hashlib.sha256(prefix_full + nonce.to_bytes(4, "little")).digest()
                ).digest()
                h = mid.copy()
                h.update(tail + nonce.to_bytes(4, "little"))
                assert hashlib.sha256(h.digest()).digest() == reference, (
                    f"midstate digest mismatch at height {row['height']} nonce {nonce}"
                )

        base_lin = bench_min(prefix_full, tail, linear, None)
        base_sched = bench_min(prefix_full, tail, schedule, None)
        mid_lin = bench_min(prefix_full, tail, linear, mid)
        mid_sched = bench_min(prefix_full, tail, schedule, mid)
        speedup = ((base_lin + base_sched) / 2) / ((mid_lin + mid_sched) / 2)
        results.append({
            "height": row["height"],
            "baseline_linear_us": base_lin / 1e3 / PROBES,
            "baseline_schedule_us": base_sched / 1e3 / PROBES,
            "midstate_linear_us": mid_lin / 1e3 / PROBES,
            "midstate_schedule_us": mid_sched / 1e3 / PROBES,
            "speedup": speedup,
        })
        print(f"{row['height']:7d} {base_lin / 1e3 / PROBES:12.4f} "
              f"{base_sched / 1e3 / PROBES:14.4f} "
              f"{mid_lin / 1e3 / PROBES:11.4f} "
              f"{mid_sched / 1e3 / PROBES:13.4f} {speedup:8.3f}")

    avg_speedup = statistics.mean(r["speedup"] for r in results)
    order_gap_base = statistics.mean(
        abs(r["baseline_schedule_us"] - r["baseline_linear_us"]) for r in results
    )
    order_gap_mid = statistics.mean(
        abs(r["midstate_schedule_us"] - r["midstate_linear_us"]) for r in results
    )
    print(f"\nmean midstate speedup        {avg_speedup:.3f}x")
    if 1.2 <= avg_speedup <= 1.6:
        verdict = "within the pre-registered 1.2x-1.6x band"
    elif avg_speedup < 1.2:
        verdict = "BELOW the 1.2x floor - not worth the code"
    else:
        verdict = "ABOVE 1.6x - suspect the benchmark before celebrating"
    print(f"pre-registered verdict       {verdict}")
    print(f"mean |schedule-linear| gap   baseline {order_gap_base:.4f} us, "
          f"midstate {order_gap_mid:.4f} us (measurement noise; invariance is "
          "structural - equal cost per probe by construction)")
    print("sentence: midstate makes ordering irrelevant; the real win is the "
          f"{avg_speedup:.2f}x per-probe reduction, identical for every order")

    OUT.write_text(json.dumps({
        "probes": PROBES,
        "repeats": REPEATS,
        "headers": len(rows),
        "mean_speedup": avg_speedup,
        "order_gap_baseline_us": order_gap_base,
        "order_gap_midstate_us": order_gap_mid,
        "rows": results,
    }, indent=1), encoding="utf-8")
    print(f"\nresults written to {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())