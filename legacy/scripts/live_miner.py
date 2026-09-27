#!/usr/bin/env python3
"""Consolidated live miner — wires every subsystem into one loop.

    StratumTcpClient (server.ts) → live job via /api/stratum/live/status
      → advisor /advise/predict   (Poincaré-Cassini L15 O(1) probe)
      → advisor /advise/schedule  (Zeckendorf-Lucas-Pisot window ordering)
      → HashPipeline.grind        (Stage A phi-score order → Stage C iGPU sha256d)
      → /api/stratum/share/submit (triple-gated mining.submit)
      → advisor /learn            (strategy weight feedback)
      → Database / status APIs    (provenance + counters)

SHA-256d is the sole accept authority. The advisor and phi scoring can
only order the search — the pool's result:true is the verdict.

Usage:
    python3 scripts/live_miner.py [--base http://localhost:3000]
                                  [--advisor http://127.0.0.1:3001]
                                  [--max-seconds 900] [--mode full|fast]
"""

import argparse
import hashlib
import json
import os
import struct
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402

from mining.hash_pipeline import HashPipeline  # noqa: E402

MAX_TARGET = 0x00000000FFFF0000000000000000000000000000000000000000000000000000
WINDOW = 1 << 20  # 1M nonces per window
N_WINDOWS = (1 << 32) // WINDOW  # 4096 windows cover the nonce space


def ts() -> str:
    return time.strftime("%H:%M:%S") + f".{int(time.time() * 1000) % 1000:03d}"


def sha256d(b: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(b).digest()).digest()


def get_json(path: str) -> dict:
    return json.load(urllib.request.urlopen(BASE + path, timeout=10))


def post_json(base: str, path: str, body: dict, timeout: int = 30) -> dict:
    req = urllib.request.Request(
        base + path,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        return json.load(urllib.request.urlopen(req, timeout=timeout))
    except urllib.error.HTTPError as e:
        return {"success": False, "http_status": e.code, "body": e.read().decode()[:300]}
    except Exception as e:
        return {"success": False, "error": str(e)}


def merkle_root(coinb1: str, en1: str, en2: str, coinb2: str, branch: list) -> bytes:
    h = sha256d(bytes.fromhex(coinb1 + en1 + en2 + coinb2))
    for b in branch:
        h = sha256d(h + bytes.fromhex(b))
    return h


def build_header(version: str, prevhash: str, merkle: bytes, ntime: str, nbits: str, nonce: int) -> bytes:
    hdr = bytearray(80)
    hdr[0:4] = bytes.fromhex(version)[::-1]
    ph = bytes.fromhex(prevhash)
    swapped = bytearray(32)
    for i in range(0, 32, 4):
        swapped[i:i + 4] = ph[i:i + 4][::-1]
    hdr[4:36] = swapped
    hdr[36:68] = merkle
    hdr[68:72] = bytes.fromhex(ntime)[::-1]
    hdr[72:76] = bytes.fromhex(nbits)[::-1]
    hdr[76:80] = struct.pack("<I", nonce)
    return bytes(hdr)


def share_target_be(difficulty: float) -> bytes:
    if difficulty <= 0:
        return MAX_TARGET.to_bytes(32, "big")
    scaled = int(difficulty * 1_000_000)
    return ((MAX_TARGET * 1_000_000) // scaled).to_bytes(32, "big")


def advisor_schedule(header_hex: str, target_hex: str) -> list:
    """Window ordering from the Python advisor (Zeckendorf-Lucas-Pisot
    dispersion over window indices)."""
    r = post_json(
        ADVISOR,
        "/advise/schedule",
        {
            "header_hex": header_hex,
            "target_hex": target_hex,
            "nonce_start": 0,
            "nonce_end": N_WINDOWS,
            "count": N_WINDOWS,
            "strategy": "zeckendorf_lucas_pisot",
        },
        timeout=20,
    )
    order = r.get("ordered_nonces") or list(range(N_WINDOWS))
    src = "advisor" if r.get("success") else "sequential_fallback"
    print(f"[Advisor] {ts()} schedule: {len(order)} windows ordered by {r.get('strategy', src)} k*={r.get('k_star')}")
    return order


def advisor_predict(header_hex: str, target_hex: str) -> int:
    """O(1) attractor prediction — probed first, verified by sha256d."""
    r = post_json(
        ADVISOR,
        "/advise/predict",
        {
            "header_hex": header_hex,
            "target_hex": target_hex,
            "nonce_start": 0,
            "nonce_end": 1 << 32,
        },
    )
    n = int(r.get("predicted_nonce", 1364))
    print(
        f"[Advisor] {ts()} predict: nonce={n} confidence={r.get('confidence')} "
        f"advisor_verified={r.get('meets_target')} strategy={r.get('strategy')}"
    )
    return n


def advisor_learn(header_hex: str, nonce: int, found: bool, iterations: int) -> None:
    r = post_json(
        ADVISOR,
        "/learn",
        {
            "header_hex": header_hex,
            "nonce": int(nonce),
            "found": bool(found),
            "iterations": int(iterations),
        },
        timeout=10,
    )
    if r.get("success"):
        print(f"[Advisor] {ts()} learn: found={found} weights={r.get('strategy_weights')}")


def submit_share(job_id, en2_hex, ntime, nonce, hash_hex, difficulty, worker) -> dict:
    print(f"[Share] {ts()} mining.submit sent: job={job_id} nonce={nonce} ntime={ntime}")
    resp = post_json(
        BASE,
        "/api/stratum/share/submit",
        {
            "jobId": job_id,
            "nonceHex": f"{nonce:08x}",
            "extranonce2": en2_hex,
            "nTime": ntime,
            "headerHashHex": hash_hex,
            "difficulty": difficulty,
            "worker": worker,
        },
    )
    print(f"[Share] {ts()} pool response received: {json.dumps(resp)[:400]}")
    return resp


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:3000")
    ap.add_argument("--advisor", default="http://127.0.0.1:3001")
    ap.add_argument("--max-seconds", type=float, default=900)
    ap.add_argument("--en2", default="1")
    ap.add_argument("--mode", choices=["full", "fast"], default="full",
                    help="full=pipeline score+grind every window; fast=advisor window order + raw range grind")
    args = ap.parse_args()
    global BASE, ADVISOR
    BASE, ADVISOR = args.base, args.advisor

    pipeline = HashPipeline()
    print(f"[Miner] {ts()} pipeline backend={pipeline.hasher.backend} device={pipeline.hasher.device} mode={args.mode}")

    deadline = time.time() + args.max_seconds
    total_hashes = 0
    job_state = None
    job_hdr = None
    job = None
    s = {}
    difficulty = 1.0
    en2_hex = ""
    window_order = None
    wi = 0
    learned_windows = 0

    while time.time() < deadline:
        # --- poll live job (rate-limit friendly) ---
        try:
            st = get_json("/api/stratum/live/status")
        except Exception as e:
            print(f"[Miner] {ts()} status poll failed: {e}")
            time.sleep(3)
            continue
        s = st["runtime"]["stratum"]
        job = st.get("lastJob")
        if not (s.get("connected") and s.get("authorized") and job):
            print(f"[Miner] {ts()} waiting for live job... connected={s.get('connected')}")
            time.sleep(2)
            continue

        difficulty = float(s.get("difficulty") or 1)
        en1 = s.get("extranonce1") or ""
        en2_size = int(s.get("extranonce2Size") or 8)
        en2_int = int(args.en2, 0) & ((1 << (en2_size * 8)) - 1)
        en2_hex = en2_int.to_bytes(en2_size, "big").hex()
        target = share_target_be(difficulty)

        if job_state != job["jobId"]:
            job_state = job["jobId"]
            merkle = merkle_root(job["coinb1"], en1, en2_hex, job["coinb2"], job["merkleBranch"])
            job_hdr = build_header(job["version"], job["prevHash"], merkle, job["nTime"], job["nBits"], 0)
            print(
                f"[Miner] {ts()} job={job_state} diff={difficulty} en1={en1!r} "
                f"en2={en2_hex} target={target.hex()[:20]}…"
            )
            if window_order is None:
                window_order = advisor_schedule(job_hdr[:76].hex(), target.hex())
                wi = 0
                # O(1) attractor probe — verified by sha256d like everything else.
                pn = advisor_predict(job_hdr[:76].hex(), target.hex())
                blob = job_hdr[:76] + struct.pack("<I", pn & 0xFFFFFFFF)
                h = sha256d(blob)
                total_hashes += 1
                ok = int.from_bytes(h[::-1], "big") <= int.from_bytes(target, "big")
                print(f"[Advisor] {ts()} probe nonce={pn} hash={h[::-1].hex()[:24]}… meets_target={ok}")
                if ok:
                    resp = submit_share(job_state, en2_hex, job["nTime"], pn, h[::-1].hex(), difficulty, s.get("worker"))
                    advisor_learn(job_hdr[:76].hex(), pn, True, 1)
                    if resp.get("poolResponse") or resp.get("success"):
                        return 0

        # --- grind one advisor-ordered window ---
        w = int(window_order[wi % len(window_order)])
        wi += 1
        base_nonce = (w * WINDOW) & 0xFFFFFFFF
        candidates = np.arange(base_nonce, base_nonce + WINDOW, dtype=np.uint64)

        if args.mode == "full":
            res = pipeline.grind(job_hdr, target, candidates.tolist())
            hashes = res.hashes_computed
            winner, win_hash = res.winning_nonce, res.winning_hash
        else:
            winner, win_hash, hashes = pipeline.hasher.grind_target_range(
                job_hdr, target, base_nonce, WINDOW
            )
        total_hashes += hashes
        learned_windows += 1

        if winner is not None:
            hash_hex = win_hash[::-1].hex()
            print(f"[Share] {ts()} candidate_found nonce={winner} hash={hash_hex} diff={difficulty} (window={w})")
            print(f"[Share] {ts()} meets_target=True vs pool_target (diff={difficulty})")
            resp = submit_share(job_state, en2_hex, job["nTime"], winner, hash_hex, difficulty, s.get("worker"))
            advisor_learn(job_hdr[:76].hex(), winner, True, total_hashes)
            verdict = resp.get("poolResponse") or {}
            if verdict.get("accepted") is not None or resp.get("poolResponse"):
                return 0
            continue

        # negative learning sample every ~32 windows (keeps HTTP chatter sane)
        if learned_windows % 32 == 0:
            advisor_learn(job_hdr[:76].hex(), base_nonce, False, hashes)
            rate = total_hashes / (time.time() - t_start)
            print(
                f"[Miner] {ts()} scanned={total_hashes:,} rate={rate / 1e6:.1f} MH/s "
                f"window={w} job={job_state}"
            )

    rate = total_hashes / max(time.time() - t_start, 1e-9)
    print(f"[Miner] {ts()} no share in {args.max_seconds:.0f}s — total_hashes={total_hashes:,} avg={rate / 1e6:.0f} MH/s")
    return 1


if __name__ == "__main__":
    t_start = time.time()
    sys.exit(main())
