"""Bounded live Stratum V1 pool smoke test.

Handshake phase: subscribe, authorize, first mining.notify, negotiated
difficulty. Grind phase (optional, bounded): CPU double-SHA256 grind against
the pool-set target; on a genuine hit, mining.submit is sent and the pool's
response is reported verbatim. No fabricated shares, ever — the pool's
result is the only accept authority.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

_PY = Path(__file__).resolve().parents[1] / "python"
if str(_PY) not in sys.path:
    sys.path.insert(0, str(_PY))

from manifold_pool_coordinator import PoolEndpoint, StratumClient  # noqa: E402
from mla1517.mining.stratum_adapter import DIFF1_TARGET, sha256d  # noqa: E402

POOLS = {
    "braiins": PoolEndpoint("stratum.braiins.com", 3333, "braiins"),
    "viabtc": PoolEndpoint("btc.viabtc.top", 3333, "viabtc"),
}


def log(msg: str) -> None:
    print(f"[SMOKE] {msg}", flush=True)


async def smoke(args: argparse.Namespace) -> int:
    endpoint = POOLS[args.pool]
    client = StratumClient(
        endpoint, username=args.worker, password=args.password, request_timeout=20
    )
    adapter = client.proof_adapter
    started = time.perf_counter()

    await client.connect()
    log(f"authorized on {endpoint.name} as {args.worker}")
    sub = adapter.subscription
    log(f"subscribe: extranonce1={sub.extranonce1} extranonce2_size={sub.extranonce2_size}")

    job_wait_deadline = time.perf_counter() + args.wait_seconds
    while adapter.current_job is None and time.perf_counter() < job_wait_deadline:
        await asyncio.sleep(0.25)
    job = adapter.current_job
    if job is None:
        log(f"FAIL: no mining.notify within {args.wait_seconds}s")
        await client.close()
        return 2
    difficulty = DIFF1_TARGET / adapter.target if adapter.target else 0
    log(
        f"job {job.job_id} received: nbits={job.nbits} ntime={job.ntime} "
        f"merkle_branches={len(job.merkle_branch)} difficulty={difficulty}"
    )
    log(f"handshake OK in {time.perf_counter() - started:.2f}s")

    if args.grind_seconds <= 0:
        await client.close()
        return 0

    extranonce2 = adapter.next_extranonce2()
    deadline = time.perf_counter() + args.grind_seconds
    hashes = 0
    hit: int | None = None
    while time.perf_counter() < deadline:
        for nonce in range(0, 1 << 32, 4096):
            for n in range(nonce, nonce + 4096):
                digest = sha256d(
                    adapter.build_header(job.job_id, extranonce2, job.ntime, n)
                )
                hashes += 1
                if int.from_bytes(digest, "little") <= adapter.target:
                    hit = n
                    break
            if hit is not None or time.perf_counter() >= deadline:
                break
        if hit is not None:
            break
    rate = hashes / max(time.perf_counter() - (deadline - args.grind_seconds), 1e-9)
    if hit is None:
        log(
            f"no share in {args.grind_seconds}s (difficulty={difficulty}, "
            f"measured {rate / 1e6:.2f} MH/s CPU). Handshake smoke = PASS; "
            f"share submission remains unexercised."
        )
        await client.close()
        return 0

    log(f"candidate nonce {hit:08x} meets target; submitting…")
    params = adapter.submission_params(
        worker_name=args.worker,
        job_id=job.job_id,
        extranonce2=extranonce2,
        ntime=job.ntime,
        nonce=hit,
    )
    response = await client.submit(params)
    log(f"pool verdict: {response!r}")
    await client.close()
    return 0 if response is True else 3


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool", choices=sorted(POOLS), required=True)
    parser.add_argument("--worker", required=True, help="full authorize username")
    parser.add_argument("--password", required=True)
    parser.add_argument("--wait-seconds", type=float, default=45.0)
    parser.add_argument("--grind-seconds", type=float, default=90.0)
    args = parser.parse_args()
    try:
        raise SystemExit(asyncio.run(smoke(args)))
    except Exception as exc:  # noqa: BLE001 - smoke test reports, never crashes silently
        log(f"FAIL: {type(exc).__name__}: {exc}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
