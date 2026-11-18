"""Offline end-to-end benchmark: exact triad Grover at k=32 on verified mainnet headers.

Runs ProductionTriad.exact_grover_search (real OvidTransformService + SQLite WAL
DurableTheseusService) per header and window, and the linear scan with the same
SHA-256d oracle.  Integer counters only; wall times are measured, never used in
any decision.  No network, no pool, no mining.

The pinned 500-header fixture lives on its own data branch (sha256 in
benchmarks/triad_grover_k32/RESULTS.md); fetch it first, then run each window
size with a fresh --state directory (fresh state => zero shard reuse):

  git fetch origin data/mainnet-headers-975565-976064
  git show FETCH_HEAD:tests/vectors/mainnet_975565_976064.json > /tmp/mainnet_975565_976064.json
  python scripts/benchmarks/triad_grover_k32.py --headers /tmp/mainnet_975565_976064.json \
      --window-bits 12 --state /tmp/state12 --out out12.json

--headers accepts that vector file (blocks[].header_hex, height, block_hash_be) or a
list of rows with header_hex/height; optional integer bits must equal the header's
nBits, and an optional id must equal the header's own block hash.
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
    """Linear scan with the same oracle; a hit is confirmed by the same fresh full
    SHA-256d check the triad performs, inside the timed region, and only then are
    its 3 compressions counted."""
    o = Sha256dTargetOracle(prefix, target)
    t0 = time.perf_counter_ns()
    hit, confirm = None, 0
    for i in range(w):
        v = (o.ntime << 32) | ((base + i) & 0xFFFFFFFF)
        if o(v):
            ok, _digest = o.verify(v)
            confirm = 3
            if not ok:
                raise ArithmeticError("linear hit failed fresh SHA-256d confirmation")
            hit = v & 0xFFFFFFFF
            break
    return hit, o.evaluations, o.compressions + confirm, time.perf_counter_ns() - t0


def block_id(header: bytes) -> str:
    return hashlib.sha256(hashlib.sha256(header).digest()).digest()[::-1].hex()


def run_chunk(job):
    idx, rows, d, root = job
    w = 1 << d
    tri = open_production_triad(root, name=f"chunk{idx}")
    out = []
    for r in rows:
        hdr = bytes.fromhex(r["header_hex"])
        header_bits = struct.unpack("<I", hdr[72:76])[0]          # nBits from the serialized header
        if "bits" in r:
            if isinstance(r["bits"], bool) or not isinstance(r["bits"], int):
                raise ValueError(f"row bits must be an integer at height {r['height']}")
            if r["bits"] != header_bits:
                raise ValueError(f"row bits disagree with header nBits at height {r['height']}")
        expected_id = block_id(hdr)                                # from the full input header
        if "id" in r and r["id"] != expected_id:
            raise ValueError(f"row id disagrees with the header's block hash at height {r['height']}")
        prefix, target = hdr[:76], target_from_bits(header_bits)
        nonce = struct.unpack("<I", hdr[76:80])[0]
        tenant = f"h{r['height']}"
        rec = {"height": r["height"], "true_nonce": nonce, "chunk": idx}
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
                "digest": res["digest"], "correct": res["nonce"] == nonce and res["digest"] == expected_id,
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
    # restart pass: fresh service on the same SQLite file; restore both staged artifacts
    # per header (in-window and overfit): a hit must restore fully collapsed, an
    # exhausted window must restore its uncollapsed stage.
    t0 = time.perf_counter_ns()
    tri2 = open_production_triad(root, name=f"chunk{idx}")
    reopen_ns = time.perf_counter_ns() - t0
    restored = 0
    t1 = time.perf_counter_ns()
    for rec in out:
        st = TheseusAdapter(tri2.theseus, f"h{rec['height']}")
        ad = OvidFoldedAdapter(OvidAdapter(tri2.ovid), st)
        for side in ("in", "overfit"):
            h = ad.restore_from_theseus(rec[side]["artifact_id"])
            if rec[side]["found"]:
                if h.register.active_dimension != 0 or h.register.readout_winner()[1][1] != rec[side]["nonce"]:
                    raise AssertionError("restored winner handle is not the fully collapsed winner")
            elif h.version != 0 or h.register.active_dimension != d:
                raise AssertionError("restored exhausted handle is not the uncollapsed stage")
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
