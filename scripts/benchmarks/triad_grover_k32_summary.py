"""Summarise one triad_grover_k32.py run into the committed raw file and the
qualification numbers, re-verifying custody from the run's SQLite files.

  python scripts/benchmarks/triad_grover_k32_summary.py --run out12.json --input /tmp/mainnet_975565_976064.json \
      --input-commit 0ef3443a7736fa7f2ce7aebc4560d318d765fd5c --code-sha <full sha> \
      --raw-out benchmarks/triad_grover_k32/raw_w4096.json --summary-out /tmp/summary12.json

Checks per header, all from SQLite: the tenant journal hash chain recomputes
(DurableTheseusService.verify_journal_continuity), the GROVER_TARGET_VERIFIED receipt
named by the run is in that chain, and its CRC-32C + SHA-256 attestation verifies.
Means are exact Fractions rendered with 3 decimals by integer arithmetic.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from fractions import Fraction

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from chronus.ovid.folded_custody import verify_attested  # noqa: E402
from chronus.quantum.triad_grover import EVENT_VERIFIED, encode_exact_fraction, exact_grover_two_amplitude_trajectory  # noqa: E402
from chronus.storage.durable import DurableTheseusService  # noqa: E402


def dec3(q: Fraction) -> str:
    """Round-half-up to 3 decimals using integers only."""
    sign = "-" if q < 0 else ""
    q = abs(q)
    m = (q.numerator * 1000 * 2 + q.denominator) // (2 * q.denominator)
    return f"{sign}{m // 1000}.{m % 1000:03d}"


def mean(vals) -> Fraction:
    vals = list(vals)
    return Fraction(sum(vals), len(vals))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--input", required=True)
    ap.add_argument("--input-commit", required=True)
    ap.add_argument("--code-sha", required=True)
    ap.add_argument("--raw-out", required=True)
    ap.add_argument("--summary-out", required=True)
    a = ap.parse_args(argv)
    with open(a.run, "rb") as fh:
        run_bytes = fh.read()
    run = json.loads(run_bytes)
    with open(a.input, "rb") as fh:
        input_sha = hashlib.sha256(fh.read()).hexdigest()
    rows, w = run["rows"], 1 << run["window_bits"]
    n = len(rows)

    chains_ok = in_chain = attested = 0
    samples = []
    by_db = {m["chunk"]: m["db"] for m in run["restart"]}
    services = {c: DurableTheseusService(p) for c, p in by_db.items()}
    workers = run["workers"]
    for r in sorted(rows, key=lambda r: -r["height"]):
        svc = services[r["chunk"]]
        tenant = f"h{r['height']}"
        if svc.verify_journal_continuity(tenant):
            chains_ok += 1
        rid = r["in"]["receipt_entry_hashes"][0]
        entries = {e.entry_hash: e for e in svc.get_journal(tenant)}
        e = entries.get(rid)
        if e is not None and e.event_type == EVENT_VERIFIED:
            in_chain += 1
            rec = json.loads(svc.reconstruct(tenant, e.object_id))
            body = verify_attested(rec)
            if body["winner_value"] & 0xFFFFFFFF == r["true_nonce"]:
                attested += 1
            if len(samples) < 3:
                samples.append({"height": r["height"], "nonce": r["in"]["nonce"], "digest": r["in"]["digest"],
                                "journal_entry_hash": rid, "receipt_body_crc32c": rec["body_crc32c"],
                                "receipt_body_sha256": rec["body_sha256"]})

    ins = [r["in"] for r in rows]
    ovs = [r["overfit"] for r in rows]
    p_marked = exact_grover_two_amplitude_trajectory(w, 1)[-1][3]
    summary = {
        "W": w, "k": 32, "headers": n, "workers": workers,
        "correct": sum(1 for x in ins if x["correct"]), "verified": sum(1 for x in ins if x["verified"]),
        "overfit_found": sum(1 for x in ovs if x["found"]),
        "iterations": sorted({x["iterations"] for x in ins}),
        "triad_evals_per_header": str(mean(x["triad_evaluations"] for x in ins)),
        "triad_compressions_per_header": str(mean(x["triad_compressions"] for x in ins)),
        "linear_evals_per_header": str(mean(x["linear_evaluations"] for x in ins)),
        "linear_compressions_per_header": str(mean(x["linear_compressions"] for x in ins)),
        "winner_schedule_position_mean": dec3(mean(x["winner_schedule_position"] for x in ins)),
        "linear_position_mean": dec3(mean(x["linear_position"] for x in ins)),
        "geodesic_before_linear": sum(1 for x in ins if x["winner_schedule_position"] < x["linear_position"]),
        "pure_o1_grover_ms": dec3(mean(x["pure_loop_ns"] for x in ins) / 10**6),
        "end_to_end_triad_pipeline_ms": dec3(mean(x["full_pipeline_ns"] for x in ins) / 10**6),
        "linear_scan_ms": dec3(mean(x["linear_ns"] for x in ins) / 10**6),
        "overfit_pipeline_ms": dec3(mean(x["full_pipeline_ns"] for x in ovs) / 10**6),
        "overfit_linear_ms": dec3(mean(x["linear_ns"] for x in ovs) / 10**6),
        "total_wall_s": dec3(Fraction(run["wall_ns"], 10**9)),
        "shards_persisted_per_header": str(mean(x["shards_persisted"] for x in ins)),
        "receipts_per_header": str(mean(x["receipts_appended"] for x in ins)),
        "custodied_frame_bytes_per_header": dec3(mean(x["shard_bytes"] for x in ins)),
        "journal_chains_recomputed_ok": f"{chains_ok}/{n}",
        "target_verified_receipts_in_chain": f"{in_chain}/{n}",
        "receipt_bodies_crc32c_sha256_verified": f"{attested}/{n}",
        "restart_restored": sum(m["restored"] for m in run["restart"]),
        "p_marked": encode_exact_fraction(p_marked),
        "verified_grover_target_receipts_sample": samples,
    }
    raw = {"schema": "chronus-triad-grover-benchmark-raw/1", "code_sha": a.code_sha,
           "input": {"branch": "data/mainnet-headers-975565-976064", "commit": a.input_commit,
                     "path": "tests/vectors/mainnet_975565_976064.json", "sha256": input_sha},
           "full_output_sha256": hashlib.sha256(run_bytes).hexdigest(),
           "window_bits": run["window_bits"], "workers": workers, "wall_ns": run["wall_ns"],
           "p_marked_in_window_all_headers": encode_exact_fraction(p_marked),
           "restart": [{k: v for k, v in m.items() if k != "db"} for m in run["restart"]], "rows": rows}
    with open(a.raw_out, "w", encoding="utf-8") as fh:
        json.dump(raw, fh, indent=1, sort_keys=True)
        fh.write("\n")
    with open(a.summary_out, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=1, sort_keys=True)
        fh.write("\n")


if __name__ == "__main__":
    main()
