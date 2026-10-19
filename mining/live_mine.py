"""Live mining instrument: connect -> real job -> real grind -> measured rate.

This is a REAL production-path measurement, not a simulation:

* ``StratumV1Client`` performs an actual TCP connect, ``mining.subscribe`` and
  ``mining.authorize`` against the configured pool, then keeps reading real
  ``mining.notify``/``mining.set_difficulty``/``mining.set_target`` traffic.
* Every job's 80-byte header is rebuilt from the wire fields via
  ``build_job_header`` (real coinbase + real merkle branches + negotiated
  extranonces).
* ``BitcoinHasher.grind_target_range`` physically computes every SHA-256d
  digest in each nonce window on the selected backend (OpenCL device or
  hashlib CPU fallback — recorded truthfully in the report). Pool share
  target is the accept predicate; any winner is independently re-verified
  with hashlib before it is even considered for submission.
* Submission is fail-closed: it requires ``--submit`` AND the same env gate
  as the production miner (HYBA_ENABLE_LIVE_SHARE_SUBMIT=true,
  HYBA_LIVE_SHARE_APPROVAL_ID, HYBA_AUTONOMOUS_EXTERNAL_ACTIONS=true).

The report records MEASURED wall-clock hashrate only — hashes actually
computed divided by time actually elapsed. No projections, no effective
rates, no fabricated numbers.

Usage:
    python -m mining.live_mine --pool braiins --seconds 60
    python -m mining.live_mine --pool both --seconds 60 --out live_mine_report.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import time

from mining.bitcoin_hasher import GRIND_BATCH, BitcoinHasher
from mining.production_miner import (
    PoolSpec,
    StratumV1Client,
    _dsha256,
    build_job_header,
    parse_endpoint,
)


def _log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


POOLS = {
    "braiins": {
        "endpoint": "stratum+tcp://stratum.braiins.com:3333",
        "worker": ("BRAIINS_ACCOUNT", "PYTHIA_STRATUM_WORKER"),
        "password": ("STRATUM_PASSWORD", "PYTHIA_STRATUM_PASSWORD"),
    },
    "viabtc": {
        "endpoint": "stratum+tcp://btc.viabtc.top:3333",
        "worker": ("VIABTC_ACCOUNT", "PYTHIA_STRATUM_WORKER"),
        "password": ("STRATUM_PASSWORD", "PYTHIA_STRATUM_PASSWORD"),
    },
    "nicehash": {
        "endpoint": "stratum+tcp://sha256.auto.nicehash.com:9200",
        "worker": ("NICEHASH_ACCOUNT", "PYTHIA_STRATUM_WORKER"),
        "password": ("STRATUM_PASSWORD", "PYTHIA_STRATUM_PASSWORD"),
    },
    "ckpool": {
        "endpoint": "stratum+tcp://solo.ckpool.org:3333",
        "worker": ("CKPOOL_ACCOUNT", "PYTHIA_STRATUM_WORKER"),
        "password": ("STRATUM_PASSWORD", "PYTHIA_STRATUM_PASSWORD"),
    },
}


_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read_env_file(name: str) -> dict[str, str]:
    path = os.path.join(_PROJECT_ROOT, name)
    values: dict[str, str] = {}
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


def _env_for(pool: str) -> dict[str, str]:
    # .env.<pool> scopes pool-specific credentials; process env wins.
    merged = _read_env_file(".env")
    merged.update(_read_env_file(f".env.{pool}"))
    merged.update(os.environ)
    return merged


def _env_first(env: dict[str, str], names: tuple[str, ...]) -> str | None:
    for name in names:
        value = env.get(name)
        if value:
            return value
    return None


def pool_specs(names: list[str]) -> list[tuple[str, PoolSpec]]:
    specs = []
    for name in names:
        cfg = POOLS[name]
        env = _env_for(name)
        specs.append(
            (
                name,
                PoolSpec(
                    parse_endpoint(
                        env.get("PYTHIA_STRATUM_ENDPOINT", "").strip() or cfg["endpoint"]
                    ),
                    _env_first(env, cfg["worker"]),
                    _env_first(env, cfg["password"]) or "x",
                ),
            )
        )
    return specs


def _submit_armed(flag: bool) -> bool:
    return bool(
        flag
        and os.getenv("HYBA_ENABLE_LIVE_SHARE_SUBMIT") == "true"
        and os.getenv("HYBA_LIVE_SHARE_APPROVAL_ID")
        and os.getenv("HYBA_AUTONOMOUS_EXTERNAL_ACTIONS") == "true"
    )


async def mine_pool(
    name: str,
    spec: PoolSpec,
    seconds: float,
    window: int,
    backend: str,
    submit: bool,
) -> dict:
    report = {
        "pool": name,
        "endpoint": f"{spec.endpoint.host}:{spec.endpoint.port}",
        "worker_configured": spec.worker is not None,
        "authorized": False,
        "extranonce1_len": 0,
        "extranonce2_size": 0,
        "jobs": [],
        "windows": 0,
        "hashes_total": 0,
        "seconds_wall": 0.0,
        "hashrate_hs": None,
        "window_rate_min": None,
        "window_rate_median": None,
        "window_rate_max": None,
        "candidates_found": 0,
        "shares_submitted": 0,
        "shares_accepted": 0,
        "submit_armed": _submit_armed(submit),
        "errors": [],
        "verdict": "FAILED",
    }
    hasher = BitcoinHasher(backend=backend)
    report["hasher"] = hasher.telemetry()
    client = StratumV1Client(spec.endpoint, spec.worker, spec.password, timeout=20.0)
    submit_on = report["submit_armed"]
    try:
        await client.connect_and_authorize()
        report["authorized"] = client.authorized
        report["extranonce1_len"] = len(client.extranonce1 or "")
        report["extranonce2_size"] = client.extranonce2_size
        _log(
            f"[{name}] authorized={client.authorized} "
            f"en1_len={report['extranonce1_len']} en2_size={client.extranonce2_size}"
        )
        job = await client.wait_for_job(timeout=30.0)
        t0 = time.perf_counter()
        deadline = t0 + seconds
        generation = job.generation
        base_nonce = 0
        extranonce2 = 0
        rates = []
        jobs_seen = set()
        header = None
        while time.perf_counter() < deadline:
            await asyncio.sleep(0)  # let the read loop process notifications
            current = client.job
            if current is None:
                break
            if current.generation != generation or header is None:
                generation = current.generation
                base_nonce = 0
                extranonce2 = 0
                jobs_seen.add((current.generation, current.job_id))
                report["jobs"].append(
                    {
                        "t_s": round(time.perf_counter() - t0, 2),
                        "job_id": current.job_id,
                        "generation": generation,
                        "clean_jobs": current.clean_jobs,
                        "nbits": current.nbits,
                        "target_set": current.target is not None,
                    }
                )
                _log(
                    f"[{name}] job {current.job_id} gen={generation} "
                    f"clean={current.clean_jobs} target_set={current.target is not None}"
                )
            if current.target is None:
                await asyncio.sleep(0.05)
                continue
            if client.extranonce2_size == 0:
                en2 = ""
            else:
                limit = 1 << (8 * client.extranonce2_size)
                if extranonce2 >= limit:
                    raise RuntimeError("extranonce2 space exhausted")
                en2 = f"{extranonce2:0{client.extranonce2_size * 2}x}"
            header = build_job_header(current, client.extranonce1, en2)
            remaining = (1 << 32) - base_nonce
            count = min(window, remaining)
            target_be = current.target.to_bytes(32, "big")
            w0 = time.perf_counter()
            winner, digest, hashes = hasher.grind_target_range(
                header, target_be, base_nonce, count
            )
            wsecs = time.perf_counter() - w0
            report["windows"] += 1
            report["hashes_total"] += hashes
            if wsecs > 0:
                rates.append(hashes / wsecs)
            if winner is not None and digest is not None:
                # Independent consensus recheck (same gate as production).
                ref = _dsha256(header[:76] + winner.to_bytes(4, "little"))
                if ref != digest or int.from_bytes(ref[::-1], "big") > current.target:
                    raise RuntimeError("hasher hit failed independent recheck")
                report["candidates_found"] += 1
                if submit_on and client.job is not None and client.job.generation == generation:
                    accepted = await client.submit(current, en2, winner)
                    report["shares_submitted"] += 1
                    if accepted:
                        report["shares_accepted"] += 1
                    _log(
                        f"[{name}] SHARE job={current.job_id} nonce={winner:08x} "
                        f"accepted={accepted}"
                    )
                else:
                    _log(
                        f"[{name}] candidate job={current.job_id} nonce={winner:08x} "
                        "(submission disabled)"
                    )
            base_nonce += count
            if base_nonce >= 1 << 32:
                base_nonce = 0
                extranonce2 += 1
        report["seconds_wall"] = round(time.perf_counter() - t0, 3)
        if report["seconds_wall"] > 0:
            report["hashrate_hs"] = round(
                report["hashes_total"] / report["seconds_wall"], 2
            )
        if rates:
            report["window_rate_min"] = round(min(rates), 2)
            report["window_rate_median"] = round(statistics.median(rates), 2)
            report["window_rate_max"] = round(max(rates), 2)
        report["jobs_received"] = len(jobs_seen)
        report["verdict"] = "MINED" if report["hashes_total"] > 0 else "NO_WORK"
    except Exception as exc:  # noqa: BLE001 — report exact failure stage
        report["errors"].append(f"{type(exc).__name__}: {exc}")
        _log(f"[{name}] ERROR {type(exc).__name__}: {exc}")
    finally:
        report["hasher"] = hasher.telemetry()
        report["connected_at_close"] = client.connected
        await client.close()
    return report


async def _run(specs, seconds, window, backend, submit):
    reports = []
    for name, spec in specs:
        reports.append(await mine_pool(name, spec, seconds, window, backend, submit))
    return reports


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pool", choices=["braiins", "viabtc", "nicehash", "ckpool", "all"], default="all")
    ap.add_argument("--seconds", type=float, default=60.0)
    ap.add_argument("--window", type=int, default=GRIND_BATCH)
    ap.add_argument("--backend", choices=["auto", "cpu", "opencl", "gpu"], default="auto")
    ap.add_argument(
        "--submit",
        action="store_true",
        help="attempt share submission (still requires the full env gate)",
    )
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    if args.window > GRIND_BATCH:
        ap.error(f"--window exceeds GRIND_BATCH ({GRIND_BATCH})")
    names = list(POOLS) if args.pool == "all" else [args.pool]
    specs = pool_specs(names)
    missing = [n for n, s in specs if s.worker is None]
    if missing:
        ap.error(f"no worker credential configured for: {', '.join(missing)}")
    reports = asyncio.run(
        _run(specs, args.seconds, args.window, args.backend, args.submit)
    )
    doc = {
        "measured": True,
        "projected": False,
        "pools": reports,
        "verdict": {r["pool"]: r["verdict"] for r in reports},
    }
    out = json.dumps(doc, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(out + "\n")
    print(out)
    return 0 if all(r["verdict"] == "MINED" for r in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
