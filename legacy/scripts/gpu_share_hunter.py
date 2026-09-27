#!/usr/bin/env python3
"""GPU share hunter — wires the live Stratum feed to the iGPU grind pipeline.

    live pool notify (server.ts liveClient)
        -> GET /api/stratum/live/status      (jobId, coinb1/2, branch, nBits, nTime)
        -> merkle root + 80-byte header      (exact bitcoin_header.ts semantics)
        -> mining/bitcoin_hasher.py grind    (Apple M5 Max OpenCL, ~250 MH/s)
        -> POST /api/stratum/share/submit    (triple-gated live mining.submit)

SHA-256d against the pool-assigned share target is the sole accept
authority — geometry decides nothing here, the pool does.

Usage:
    python3 scripts/gpu_share_hunter.py [--base http://localhost:3000]
                                        [--max-seconds 600] [--en2 1]
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

from mining.bitcoin_hasher import BitcoinHasher  # noqa: E402

MAX_TARGET = 0x00000000FFFF0000000000000000000000000000000000000000000000000000
WINDOW = 1 << 20  # 1M nonces per GPU launch (kernel GRIND_BATCH ceiling)


def ts() -> str:
    return time.strftime("%H:%M:%S") + f".{int(time.time() * 1000) % 1000:03d}"


def sha256d(b: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(b).digest()).digest()


def get_json(path: str) -> dict:
    req = urllib.request.Request(BASE + path)
    admin_key = os.environ.get("EUCLID_ADMIN_API_KEY", "")
    if admin_key:
        req.add_header("x-euclid-admin-key", admin_key)
    return json.load(urllib.request.urlopen(req, timeout=10))


def post_json(path: str, body: dict) -> dict:
    headers = {"Content-Type": "application/json"}
    admin_key = os.environ.get("EUCLID_ADMIN_API_KEY", "")
    if admin_key:
        headers["x-euclid-admin-key"] = admin_key
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode(),
        headers=headers,
    )
    try:
        return json.load(urllib.request.urlopen(req, timeout=30))
    except urllib.error.HTTPError as e:
        return {"success": False, "http_status": e.code, "body": e.read().decode()[:500]}


def merkle_root(coinb1: str, en1: str, en2: str, coinb2: str, branch: list) -> bytes:
    cb = bytes.fromhex(coinb1 + en1 + en2 + coinb2)
    h = sha256d(cb)
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
    t = (MAX_TARGET * 1_000_000) // scaled
    return t.to_bytes(32, "big")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:3000")
    ap.add_argument("--max-seconds", type=float, default=600)
    ap.add_argument("--en2", default="1", help="extranonce2 integer (sized to pool extranonce2Size)")
    args = ap.parse_args()
    global BASE
    BASE = args.base

    hasher = BitcoinHasher(backend="gpu")
    print(f"[Hunter] {ts()} backend={hasher.backend} device={hasher.device}")

    deadline = time.time() + args.max_seconds
    total_hashes = 0
    best = None  # (hash_int, nonce)
    window_base = int.from_bytes(os.urandom(4), "little")
    job_state = None
    en1 = ""
    en2_size = 8
    en2_hex = ""

    last_poll = 0.0
    job = None
    s = {}
    difficulty = 1.0
    job_hdr = None

    while time.time() < deadline:
        # Poll the live job at most ~1/sec — status endpoint is rate limited.
        if time.time() - last_poll >= 1.0 or job is None:
            try:
                st = get_json("/api/stratum/live/status")
            except Exception as e:
                print(f"[Hunter] {ts()} status poll failed: {e}")
                st = None
            last_poll = time.time()
            if st is None:
                if job is None:
                    time.sleep(5)  # rate-limited and no job yet — wait out the window
                continue
            if st:
                s = st["runtime"]["stratum"]
                job = st.get("lastJob")
                if not (s.get("connected") and s.get("authorized") and job):
                    print(f"[Hunter] {ts()} waiting for live job... connected={s.get('connected')}")
                    time.sleep(2)
                    continue

                en1 = s.get("extranonce1") or ""
                en2_size = int(s.get("extranonce2Size") or 8)
                en2_int = int(args.en2, 0) & ((1 << (en2_size * 8)) - 1)
                en2_hex = en2_int.to_bytes(en2_size, "big").hex()
                difficulty = float(s.get("difficulty") or 1)

                if job_state != job["jobId"]:
                    job_state = job["jobId"]
                    merkle = merkle_root(job["coinb1"], en1, en2_hex, job["coinb2"], job["merkleBranch"])
                    job_hdr = build_header(job["version"], job["prevHash"], merkle, job["nTime"], job["nBits"], 0)
                    print(
                        f"[Hunter] {ts()} new job={job_state} diff={difficulty} "
                        f"en1={en1!r} en2={en2_hex} target={share_target_be(difficulty).hex()[:20]}…"
                    )

        target = share_target_be(difficulty)
        base = window_base & 0xFFFFFFFF
        window_base = (window_base + WINDOW) & 0xFFFFFFFF

        win, dig, n = hasher.grind_target_range(job_hdr, target, base, WINDOW)
        total_hashes += n

        if dig is not None:
            h_int = int.from_bytes(dig[::-1], "big")
            if best is None or h_int < best[0]:
                best = (h_int, win)

        if win is not None:
            nonce_hex = f"{win:08x}"
            hash_hex = dig[::-1].hex()
            print(f"[Share] {ts()} candidate_found nonce={win} hash={hash_hex} diff={difficulty}")
            print(f"[Share] {ts()} meets_target=True vs pool_target (diff={difficulty})")
            resp = post_json(
                "/api/stratum/share/submit",
                {
                    "jobId": job_state,
                    "nonceHex": nonce_hex,
                    "extranonce2": en2_hex,
                    "nTime": job["nTime"],
                    "headerHashHex": hash_hex,
                    "difficulty": difficulty,
                    "worker": s.get("worker"),
                },
            )
            print(f"[Share] {ts()} submit endpoint response: {json.dumps(resp)[:400]}")
            verdict = (resp.get("poolResponse") or {})
            if resp.get("success") is False and "stale" in json.dumps(resp).lower():
                print(f"[Share] {ts()} stale job — re-fetching and continuing")
                continue
            if verdict.get("accepted") is not None or resp.get("poolResponse"):
                return 0

        if total_hashes % (WINDOW * 512) == 0:
            rate = total_hashes / (time.time() - t_start)
            best_hex = f"{best[0]:064x}" if best else "-"
            print(
                f"[Hunter] {ts()} scanned={total_hashes:,} rate={rate / 1e6:.0f} MH/s "
                f"best={best_hex[:20]}… job={job_state}"
            )

    rate = total_hashes / max(time.time() - t_start, 1e-9)
    print(f"[Hunter] {ts()} no share found in {args.max_seconds:.0f}s")
    print(f"[Hunter] total_hashes={total_hashes:,} avg_rate={rate / 1e6:.0f} MH/s")
    if best:
        print(f"[Hunter] best candidate hash={best[0]:064x} nonce={best[1]}")
    return 1


if __name__ == "__main__":
    t_start = time.time()
    sys.exit(main())
