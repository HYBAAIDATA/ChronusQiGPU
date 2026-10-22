"""Live stratum handshake + wire-activity probe.

Connects to a configured pool through the production StratumV1Client and
reports REAL wire traffic: subscribe result, authorization, difficulty
broadcasts, and the mining.notify job stream. Nothing is simulated — every
line printed corresponds to a message that actually crossed the socket.

    python -m mining.live_handshake --pool braiins --seconds 60
    python -m mining.live_handshake --pool viabtc --seconds 60
    python -m mining.live_handshake --pool both   --seconds 60
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from typing import Any, Dict

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from mining.production_miner import (
    StratumV1Client,
    parse_endpoint,
    build_job_header,
)


def _read_env_file(name: str) -> Dict[str, str]:
    path = os.path.join(_PROJECT_ROOT, name)
    values: Dict[str, str] = {}
    if not os.path.isfile(path):
        return values
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            if key:
                values[key] = value.strip().strip('"').strip("'")
    return values


def _env_for(pool: str) -> Dict[str, str]:
    # .env.<pool> scopes pool-specific credentials; process env wins.
    merged = _read_env_file(".env")
    merged.update(_read_env_file(f".env.{pool}"))
    merged.update(os.environ)
    return merged


_POOL_CONFIG = {
    "braiins": {
        "endpoint": ("BRAIINS_ENDPOINT", "PYTHIA_STRATUM_ENDPOINT"),
        "worker": ("BRAIINS_ACCOUNT", "PYTHIA_STRATUM_WORKER"),
        "password": ("STRATUM_PASSWORD", "PYTHIA_STRATUM_PASSWORD"),
        "default_endpoint": "stratum+tcp://stratum.braiins.com:3333",
    },
    "viabtc": {
        "endpoint": ("VIABTC_ENDPOINT", "PYTHIA_STRATUM_ENDPOINT"),
        "worker": ("VIABTC_ACCOUNT", "PYTHIA_STRATUM_WORKER"),
        "password": ("STRATUM_PASSWORD", "PYTHIA_STRATUM_PASSWORD"),
        "default_endpoint": "stratum+tcp://btc.viabtc.top:3333",
    },
    "nicehash": {
        "endpoint": ("NICEHASH_ENDPOINT", "PYTHIA_STRATUM_ENDPOINT"),
        "worker": ("NICEHASH_ACCOUNT", "PYTHIA_STRATUM_WORKER"),
        "password": ("STRATUM_PASSWORD", "PYTHIA_STRATUM_PASSWORD"),
        "default_endpoint": "stratum+tcp://sha256.auto.nicehash.com:9200",
    },
    "ckpool": {
        "endpoint": ("CKPOOL_ENDPOINT", "PYTHIA_STRATUM_ENDPOINT"),
        "worker": ("CKPOOL_ACCOUNT", "PYTHIA_STRATUM_WORKER"),
        "password": ("STRATUM_PASSWORD", "PYTHIA_STRATUM_PASSWORD"),
        "default_endpoint": "stratum+tcp://solo.ckpool.org:3333",
    },
}


def _cfg(pool: str, field: str, env: Dict[str, str]) -> str:
    for key in _POOL_CONFIG[pool][field]:
        v = env.get(key, "").strip()
        if v:
            return v
    if field == "endpoint":
        return _POOL_CONFIG[pool]["default_endpoint"]
    specific = _POOL_CONFIG[pool][field][0]
    raise SystemExit(
        f"[{pool}] no {field} configured: set {specific} "
        f"in .env.{pool}, .env, or the environment"
    )


async def _probe(pool: str, seconds: float) -> Dict[str, Any]:
    """One real handshake + a window of live wire activity."""
    env = _env_for(pool)
    endpoint = parse_endpoint(_cfg(pool, "endpoint", env))
    client = StratumV1Client(
        endpoint,
        _cfg(pool, "worker", env),
        _cfg(pool, "password", env),
    )
    report: Dict[str, Any] = {
        "pool": pool,
        "endpoint": f"{endpoint.host}:{endpoint.port}",
        "handshake": {},
        "jobs": [],
        "errors": [],
    }
    t0 = time.monotonic()
    try:
        await client.connect_and_authorize()
        report["handshake"] = {
            "authorized": client.authorized,
            "extranonce1": client.extranonce1,
            "extranonce2_size": client.extranonce2_size,
        }
        print(
            f"[{pool}] CONNECTED {endpoint.host}:{endpoint.port} "
            f"authorized={client.authorized} en1={client.extranonce1} "
            f"en2_size={client.extranonce2_size}",
            file=sys.stderr,
        )
    except Exception as exc:
        report["errors"].append(f"connect/authorize failed: {exc}")
        print(f"[{pool}] HANDSHAKE FAILED: {exc}", file=sys.stderr)
        return report

    seen = set()
    try:
        while time.monotonic() - t0 < seconds:
            try:
                job = await client.wait_for_job(timeout=max(5.0, seconds))
            except Exception as exc:
                report["errors"].append(f"wait_for_job: {exc}")
                break
            if job.job_id in seen:
                await asyncio.sleep(0.25)
                continue
            seen.add(job.job_id)
            header80 = build_job_header(
                job, client.extranonce1, "00" * client.extranonce2_size
            )
            entry = {
                "t_s": round(time.monotonic() - t0, 2),
                "job_id": job.job_id,
                "clean_jobs": job.clean_jobs,
                "nbits": job.nbits,
                "ntime": job.ntime,
                "prevhash": job.prevhash[:16] + "...",
                "target_le_bits": (
                    int(client.target).bit_length() if client.target else None
                ),
                "header80_prefix": header80[:20].hex() + "...",
                "generation": job.generation,
            }
            report["jobs"].append(entry)
            print(
                f"[{pool}] notify job={job.job_id} clean={job.clean_jobs} "
                f"nbits={job.nbits} gen={job.generation}",
                file=sys.stderr,
            )
    finally:
        report["connected_at_close"] = bool(client.connected)
        await client.close()
    report["duration_s"] = round(time.monotonic() - t0, 2)
    report["jobs_received"] = len(report["jobs"])
    return report


async def _run(pools, seconds: float) -> Dict[str, Any]:
    reports = await asyncio.gather(*(_probe(p, seconds) for p in pools))
    return {
        "pools": reports,
        "verdict": {
            p["pool"]: (
                "LIVE" if p["jobs"] else
                ("CONNECTED_NO_JOBS" if p["handshake"].get("authorized") else "FAILED")
            )
            for p in reports
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pool", choices=tuple(_POOL_CONFIG) + ("all",),
                    default="all")
    ap.add_argument("--seconds", type=float, default=60.0)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    pools = list(_POOL_CONFIG) if args.pool == "all" else [args.pool]
    report = asyncio.run(_run(pools, args.seconds))
    payload = json.dumps(report, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(payload)
    print(payload)
    ok = all(v == "LIVE" for v in report["verdict"].values())
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
