"""Offline end-to-end benchmark: exact triad Grover at k=32 on verified mainnet headers.

Runs ProductionTriad.exact_grover_search (real OvidTransformService + SQLite WAL
DurableTheseusService) per header and window, and the linear scan with the same
SHA-256d oracle.  Integer counters only; wall times are measured, never used in
any decision.  No network, no pool, no mining.

  python scripts/benchmarks/triad_grover_k32.py --headers tests/vectors/mainnet_975565_976064.json \
      --window-bits 12 --state /tmp/state12 --out out.json

--headers accepts that vector file (blocks[].header_hex, height) or a list of rows
with header_hex/height (optional bits, which must equal the header's nBits).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import sys
import time
from multiprocessing import Pool

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from chronus.ovid.folded_custody import OvidAdapter, OvidFoldedAdapter, TheseusAdapter  # noqa: E402
from chronus.execution.sha256d_oracle import Sha256dTargetOracle, target_from_bits  # noqa: E402
from chronus.quantum.triad_grover import encode_exact_fraction, exact_grover_two_amplitude_trajectory  # noqa: E402
from chronus.triad import open_production_triad  # noqa: E402


def window_base(prefix: bytes, nonce: int, w: int, overfit: bool) -> int:
    if overfit:
        return (nonce + w) & 0xFFFFFFFF                    # window [nonce+W, nonce+2W): excludes nonce
    off = int.from_bytes(hashlib.sha256(prefix).digest()[:4], "big") % w   # from header[:76] only
    return (nonce - off) & 0xFFFFFFFF


def linear_scan(prefix: bytes, target: int, base: int, w: int):
    o = Sha256dTargetOracle(prefix, target)
    t0 = time.perf_counter_ns()
    hit = None
    for i in range(w):
        v = (o.ntime << 32) | ((base + i) & 0xFFFFFFFF)
        if o(v):
            hit = v & 0xFFFFFFFF
            break
    return hit, o.evaluations, o.compressions + (3 if hit is not None else 0), time.perf_counter_ns() - t0


def run_chunk(job):
    idx, rows, d, root = job
    w = 1 << d
    tri = open_production_triad(root, name=f"chunk{idx}")
    out = []
    for r in rows:
        hdr = bytes.fromhex(r["header_hex"])
        header_bits = struct.unpack("<I", hdr[72:76])[0]          # nBits from the serialized header
        if "bits" in r and int(r["bits"]) != header_bits:
            raise ValueError(f"row bits disagree with header nBits at height {r['height']}")
        prefix, target = hdr[:76], target_from_bits(header_bits)
        nonce = struct.unpack("<I", hdr[76:80])[0]
        tenant = f"h{r['height']}"
        rec = {"height": r["height"], "true_nonce": nonce}
        for overfit in (False, True):
            base = window_base(prefix, nonce, w, overfit)
            t0 = time.perf_counter_ns()
            res = tri.exact_grover_search(tenant, prefix, target, base, num_generators=d)
            full_ns = time.perf_counter_ns() - t0
            g = res["result"]
            t1 = time.perf_counter_ns()
            loop_iters = exact_grover_two_amplitude_trajectory(w, g.marked_count)[-1][0] if g.marked_count else 0
            loop_ns = time.perf_counter_ns() - t1 if g.marked_count else 0
            hit, lin_eval, lin_comp, lin_ns = linear_scan(prefix, target, base, w)
            c = res["custody"]
            rec["overfit" if overfit else "in"] = {
                "base": base, "found": g.found, "nonce": res["nonce"], "verified": res["verified"],
                "digest": res["digest"], "correct": res["nonce"] == nonce and res["digest"] == r["id"],
                "marked": g.marked_count, "iterations": g.iterations, "loop_iterations_recheck": loop_iters,
                "p_marked": encode_exact_fraction(g.total_marked_probability),
                "winner_schedule_position": g.winner_schedule_position,
                "linear_position": ((nonce - base) & 0xFFFFFFFF) + 1 if not overfit else None,
                "triad_evaluations": res["oracle_evaluations"],
                "triad_compressions": res["oracle_compressions"] + res["confirm_compressions"],
                "linear_hit": hit, "linear_evaluations": lin_eval, "linear_compressions": lin_comp,
                "full_pipeline_ns": full_ns, "pure_loop_ns": loop_ns, "linear_ns": lin_ns,
                "shards_persisted": c.shards_persisted, "shards_reused": c.shards_reused,
                "receipts_appended": c.receipts_appended, "shard_bytes": c.shard_bytes,
                "receipt_entry_hashes": g.receipts, "schedule": g.schedule, "artifact_id": g.artifact_id,
            }
        rec["journal_continuity"] = tri.theseus.verify_journal_continuity(tenant)
        out.append(rec)
    # restart pass: fresh service on the same SQLite file; restore every staged artifact
    t0 = time.perf_counter_ns()
    tri2 = open_production_triad(root, name=f"chunk{idx}")
    reopen_ns = time.perf_counter_ns() - t0
    restored = 0
    t1 = time.perf_counter_ns()
    for rec in out:
        st = TheseusAdapter(tri2.theseus, f"h{rec['height']}")
        ad = OvidFoldedAdapter(OvidAdapter(tri2.ovid), st)
        h = ad.restore_from_theseus(rec["in"]["artifact_id"])
        if h.register.active_dimension != 0 or h.register.readout_winner()[0] is None:
            raise AssertionError("restored handle is not fully collapsed")
        restored += 1
    return out, {"chunk": idx, "reopen_verify_ns": reopen_ns, "restore_ns": time.perf_counter_ns() - t1,
                 "restored": restored, "db": os.path.join(root, f"chunk{idx}.sqlite3")}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--headers", required=True)
    ap.add_argument("--window-bits", type=int, required=True)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--state", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    with open(a.headers, encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict) and "blocks" in data:
        # tests/vectors/mainnet_975565_976064.json (branch data/mainnet-headers-975565-976064)
        data = [{"height": b["height"], "header_hex": b["header_hex"], "id": b["block_hash_be"]}
                for b in data["blocks"]]
    rows = data[: a.limit]
    k = a.workers
    chunks = [(i, rows[i::k], a.window_bits, a.state) for i in range(k)]
    t0 = time.perf_counter_ns()
    with Pool(k) as pool:
        parts = pool.map(run_chunk, chunks)
    wall = time.perf_counter_ns() - t0
    recs = sorted((r for p, _ in parts for r in p), key=lambda r: -r["height"])
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump({"window_bits": a.window_bits, "workers": k, "wall_ns": wall,
                   "restart": [m for _, m in parts], "rows": recs}, fh, indent=1)


if __name__ == "__main__":
    main()
