#!/usr/bin/env python3
"""PYTHIA live Braiins soak — 600s continuous Stratum V1 mining run.

Operator-directed live commissioning run against stratum.braiins.com.
Maintains one Stratum V1 TCP session at a time (auto-reconnect <3s on
drop), grinds live jobs through the hash pipeline (11D manifold nonce
order by default, CPU-exact sha256d when OpenCL is absent), and submits
every winning share through the repo's own identity-bound live-submit
gate (runtime_config approval for the exact endpoint+worker identity).

Telemetry heartbeat every 15 seconds:
    [Elapsed/600s] | Shares Accepted: X | Moving Average Hashrate

Honesty contract (AGENTS.md): sha256d is the sole accept authority;
the hashrate printed is the measured physical rate only.
"""

from __future__ import annotations

import argparse
import asyncio
import functools
import json
import os
import sys
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parent
for _p in (str(_REPO), str(_REPO / "mla1517_platform_v3.4" / "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mining.stratum_bridge import (  # noqa: E402
    StratumBridge,
    build_coinbase,
    coinbase_hash,
    merkle_root,
    build_header80,
    difficulty_to_target,
    _lane_nonces,
)
from mining.hash_pipeline import HashPipeline  # noqa: E402


class SoakBridge(StratumBridge):
    """StratumBridge that answers mining.ping so the session stays alive."""

    def _handle_server_message(self, parsed: dict) -> None:
        method = parsed.get("method")
        if method == "mining.ping" and self._writer is not None:
            try:
                self._writer.write(
                    (json.dumps({"id": parsed.get("id"), "result": "pong"}) + "\n").encode()
                )
            except OSError:
                pass
            return
        super()._handle_server_message(parsed)


def _nonce_hex(nonce: int) -> str:
    """Stratum nonce field: uint32 as %08x (cpuminer convention; the pool
    places it in the header's little-endian slot itself)."""
    return f"{nonce & 0xFFFFFFFF:08x}"


def _grind_window(
    pipeline: HashPipeline,
    job,
    bridge: SoakBridge,
    *,
    window: int,
    base_nonce: int,
    extranonce2_int: int,
    order: str,
) -> dict:
    """Build header for the live job and grind one nonce window."""
    pad_len = bridge.extranonce2_size * 2
    extranonce2 = f"{extranonce2_int:0{pad_len}x}"[-pad_len:]
    coinbase = build_coinbase(job.coinb1, bridge.extranonce1, extranonce2, job.coinb2)
    root = merkle_root(coinbase_hash(coinbase), job.merkle_branch)
    header = build_header80(job.version, job.prev_hash, root[::-1].hex(), job.ntime, job.nbits)
    target = difficulty_to_target(job.difficulty).to_bytes(32, "big")
    nonces = _lane_nonces(base_nonce, window, header80=header, order=order)
    res = pipeline.grind(header, target, nonces)
    return {
        "job_id": job.job_id,
        "extranonce2": extranonce2,
        "ntime": job.ntime,
        "result": res,
    }


def _telemetry(
    elapsed: float,
    duration: float,
    stats: dict,
    backend: str,
    job_id: str,
    difficulty: float,
) -> None:
    total_hashes = stats["total_hashes"]
    avg = total_hashes / elapsed if elapsed > 0 else 0.0
    acc = stats["shares_accepted"]
    rej = stats["shares_rejected"]
    reconnects = stats["reconnects"]
    print(
        f"[{int(elapsed)}s/{int(duration)}s] | Shares Accepted: {acc} | "
        f"Rejected: {rej} | Moving Avg Hashrate: {avg/1e6:.2f} MH/s | "
        f"total hashes: {total_hashes:,} | job: {job_id or 'none'} | "
        f"diff: {difficulty:g} | backend: {backend} | reconnects: {reconnects}",
        flush=True,
    )


def _telem_args(stats: dict) -> tuple:
    return (
        time.perf_counter() - stats["t0"],
        stats["duration"],
        stats,
        stats["backend"],
        stats.get("job_id", ""),
        stats.get("difficulty", 0.0),
    )


async def _session(args, pipeline: HashPipeline, stats: dict, deadline: float) -> None:
    """One connected session: connect -> authorize -> listen+grind until
    the socket drops or the duration expires."""
    bridge = SoakBridge(args.host, args.port, args.worker, args.password)
    print(f"[connect] stratum+tcp://{args.host}:{args.port} as {args.worker}", flush=True)
    await bridge.connect(timeout=10.0)
    workers = [args.worker] + [w for w in args.worker_alts if w != args.worker]
    authorized = False
    for idx, w in enumerate(workers):
        bridge.worker = w
        try:
            if idx == 0:
                await bridge.handshake(suggest_diff=args.suggest_diff)
            else:
                # Session already subscribed; retry authorize only.
                auth = await bridge._rpc("mining.authorize", [w, args.password])
                bridge.authorized = auth is True
            if bridge.authorized:
                authorized = True
                bridge.worker = w
                break
        except Exception as exc:
            print(f"[auth] {w} rejected: {exc}", flush=True)
    if not authorized:
        raise RuntimeError("mining.authorize rejected for all worker names")
    stats["worker"] = bridge.worker
    print(
        f"[auth] authorized {bridge.worker} | extranonce1={bridge.extranonce1} "
        f"en2_size={bridge.extranonce2_size}",
        flush=True,
    )

    listener = asyncio.create_task(bridge.listen_forever())
    telemetry_task = asyncio.create_task(_telemetry_loop(stats, deadline))
    try:
        base_nonce = 0
        en2 = stats["extranonce2_counter"]
        current_job = None
        while time.perf_counter() < deadline:
            job = bridge.last_job
            if job is None or not job.job_id:
                job = await bridge.wait_for_job(timeout=15.0)
            if job.job_id != current_job or job.clean_jobs:
                current_job = job.job_id
                stats["job_id"] = job.job_id
                stats["difficulty"] = job.difficulty
                base_nonce = 0
                job.clean_jobs = False
                print(
                    f"[job] {job.job_id} diff={job.difficulty:g} nbits={job.nbits} "
                    f"prev={job.prev_hash[:16]}…",
                    flush=True,
                )
            out = await asyncio.get_running_loop().run_in_executor(
                None,
                functools.partial(
                    _grind_window,
                    pipeline,
                    job,
                    bridge,
                    window=args.window,
                    base_nonce=base_nonce,
                    extranonce2_int=en2,
                    order=args.order,
                ),
            )
            res = out["result"]
            stats["total_hashes"] += res.hashes_computed
            stats["batches"] += 1
            if res.mining_success:
                nonce_hex = _nonce_hex(res.winning_nonce)
                print(
                    f"[share] WINNING NONCE 0x{nonce_hex} digest={res.winning_hash[::-1].hex()[:24]}… "
                    f"submitting to pool",
                    flush=True,
                )
                submission = bridge.submit_share(
                    job.job_id, out["extranonce2"], out["ntime"], nonce_hex
                )
                if submission is None:
                    print(
                        "[share] submit GATED: live-submit not approved for this identity",
                        flush=True,
                    )
                else:
                    verdict = await submission
                    print(
                        f"[share] pool verdict: {'ACCEPTED' if verdict else 'REJECTED'}",
                        flush=True,
                    )
            base_nonce = (base_nonce + args.window) & 0xFFFFFFFF
            if base_nonce < args.window:
                en2 += 1
                stats["extranonce2_counter"] = en2
                print(f"[extranonce2] -> {en2:08x}", flush=True)
    finally:
        stats["shares_accepted"] += bridge.shares_accepted
        stats["shares_rejected"] += bridge.shares_rejected
        telemetry_task.cancel()
        listener.cancel()
        await bridge.disconnect()


async def _telemetry_loop(stats, deadline) -> None:
    while time.perf_counter() < deadline:
        await asyncio.sleep(15.0)
        _telemetry(*_telem_args(stats))


async def amain(args) -> int:
    stats = {
        "t0": time.perf_counter(),
        "total_hashes": 0,
        "batches": 0,
        "reconnects": 0,
        "extranonce2_counter": 0,
        "backend": "unknown",
        "job_id": "",
        "difficulty": 0.0,
        "worker": args.worker,
        "shares_accepted": 0,
        "shares_rejected": 0,
        "duration": args.duration,
    }
    deadline = stats["t0"] + args.duration
    print(
        f"[soak] PYTHIA live Braiins soak: {args.duration}s | window={args.window} "
        f"order={args.order} | pipeline init…",
        flush=True,
    )
    pipeline = HashPipeline(hasher_backend=args.backend)
    stats["backend"] = f"{pipeline.hasher.backend}/{pipeline.hasher.device}"
    print(f"[pipeline] backend={stats['backend']}", flush=True)
    print(
        "[soak] telemetry heartbeat every 15s; submit gate = runtime_config live_submit", flush=True
    )

    while time.perf_counter() < deadline:
        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            break
        try:
            await asyncio.wait_for(_session(args, pipeline, stats, deadline), timeout=remaining)
        except asyncio.TimeoutError:
            break
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            stats["reconnects"] += 1
            print(f"[reconnect] session dropped ({type(exc).__name__}: {exc})", flush=True)
            if time.perf_counter() >= deadline:
                break
            await asyncio.sleep(min(3.0, max(0.0, deadline - time.perf_counter())))
        else:
            break  # clean return: duration reached inside _session

    _telemetry(*_telem_args(stats))
    print(
        f"[soak] complete: {time.perf_counter()-stats['t0']:.0f}s | "
        f"worker={stats['worker']} | batches={stats['batches']} | "
        f"reconnects={stats['reconnects']}",
        flush=True,
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration", type=float, default=600.0)
    parser.add_argument("--host", default=os.getenv("BRAIINS_HOST", "stratum.braiins.com"))
    parser.add_argument("--port", type=int, default=int(os.getenv("BRAIINS_PORT", "3333")))
    parser.add_argument("--worker", default=os.getenv("BRAIINS_ACCOUNT", "PYTHAGORAS.PYTHIA"))
    parser.add_argument(
        "--worker-alts",
        nargs="*",
        default=["PYTHAGOROS.PYTHIA"],
        help="alternate worker names to try if authorize rejects the primary",
    )
    parser.add_argument("--password", default=os.getenv("BRAIINS_PASSWORD", "123"))
    parser.add_argument("--window", type=int, default=100000, help="nonces per grind window")
    parser.add_argument("--order", default=os.getenv("PYTHIA_NONCE_ORDER", "11d"))
    parser.add_argument("--suggest-diff", type=float, default=1.0)
    parser.add_argument("--backend", default="auto", choices=["auto", "gpu", "opencl", "cpu"])
    args = parser.parse_args()
    try:
        return asyncio.run(amain(args))
    except KeyboardInterrupt:
        print("\n[soak] stopped by operator", flush=True)
        return 0


if __name__ == "__main__":
    sys.exit(main())
