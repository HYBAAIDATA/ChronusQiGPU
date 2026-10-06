#!/usr/bin/env python3
"""Run the canonical mining path against a verifying loopback pool.

This is the retained-artifact counterpart of
``chronus/mla1517_platform/python/test_loopback_pool_verdict.py``. It drives
``mining_runtime._main_async`` — the same code the ``pythia-mine`` entry point
runs — against the same verifying pool implementation the test gate uses,
and keeps the run's artifacts (session file, pool verdict log, causal ledger,
backend-selection log, custody manifest) under
``evidence/loopback_pool_verdict/<head-sha12>/``.

Claim boundary: this proves the canonical submit -> pool verdict -> durable
recording path executes end-to-end on loopback. It is NOT evidence of shares
accepted by a production or testnet pool.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
PLATFORM = ROOT / "chronus" / "mla1517_platform" / "python"
sys.path.insert(0, str(PLATFORM))
sys.path.insert(0, str(ROOT))

import mining_runtime  # noqa: E402
from test_loopback_pool_verdict import (  # noqa: E402
    LOOPBACK_DIFFICULTY,
    VerifyingStratumPool,
    _job_params,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _head_sha12() -> str:
    return subprocess.run(
        ["git", "rev-parse", "--short=12", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


async def _wait(predicate, *, timeout: float, what: str) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:
            raise AssertionError(f"timed out waiting for {what}")
        await asyncio.sleep(0.05)


async def _run(out_dir: Path, *, min_accepted: int, timeout: float) -> dict:
    work = out_dir / "work"
    work.mkdir(parents=True, exist_ok=True)
    session_path = work / "mining_session.json"
    pool_log = work / "pool_verdicts.jsonl"
    run_log = out_dir / "run.log"

    handler = logging.FileHandler(run_log, encoding="utf-8")
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.INFO)

    worker = "loopback.evidence"
    env = {
        "PYTHIA_ALLOW_UNLISTED_POOLS": "1",
        "PYTHIA_POOLS": "braiins",
        "PYTHIA_EXECUTION_DEVICE": "cpu",
        "PYTHIA_MINING_SESSION_PATH": str(session_path),
        "PYTHIA_MINING_COOLDOWN_SECONDS": "0",
        "PYTHIA_CAUSAL_LOG_PATH": str(work / "causal_ledger.jsonl"),
        "PYTHIA_BACKEND_EVIDENCE_PATH": str(work / "backend_decisions.jsonl"),
        "PYTHIA_INTELLIGENCE_DIR": str(work / "intelligence"),
        "PYTHIA_TELEMETRY_HISTORY_PATH": str(work / "telemetry_history.jsonl"),
        "PYTHIA_RETARGET_TELEMETRY_PATH": str(work / "retarget_windows.json"),
        "PYTHIA_AGENTIC_STATE_PATH": str(work / "agentic.json"),
        "PYTHIA_SALAMANDER_EVIDENCE_PATH": str(work / "salamander.jsonl"),
        "PYTHIA_WORKER_HEARTBEAT_DIR": str(work / "hb"),
        "MLA1517_COORDINATOR_CONTROL_SOCKET": str(work / "control.sock"),
        "PYTHIA_IDENTITY_HMAC_SECRET": "ab" * 32,
        "PYTHIA_STORAGE_DB": str(work / "hyba.sqlite3"),
        "PYTHIA_STORAGE_ROOT": str(work / "cas"),
        "PYTHIA_STORAGE_CUSTODY_ROOT": str(work / "theseus-custody"),
        "PYTHIA_STORAGE_INTEGRITY_KEY_HEX": "11" * 32,
        "PYTHIA_STORAGE_CUSTODY_KEY_HEX": "22" * 32,
    }
    saved = {k: os.environ.get(k) for k in env}
    os.environ.update(env)
    os.environ.pop("PYTHIA_BITCOIN_RPC_URL", None)
    os.environ.pop("PYTHIA_BITCOIN_NETWORK", None)

    pool = VerifyingStratumPool(
        difficulty=LOOPBACK_DIFFICULTY, worker=worker, log_path=pool_log
    )
    pool.add_job(_job_params("job-e2e"))
    server = await asyncio.start_server(pool.handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    os.environ["MLA1517_STRATUM_ENDPOINT"] = f"127.0.0.1:{port}"
    os.environ["MLA1517_STRATUM_USER"] = worker
    saved["MLA1517_STRATUM_ENDPOINT"] = None
    saved["MLA1517_STRATUM_USER"] = None

    args = SimpleNamespace(
        device=None,
        user=worker,
        password="x",
        submit=True,
        tls=False,
        map_bytes=8192,
        difficulty_mask=0,
        base_step=0,
        log_level="INFO",
    )
    started = time.time()
    task = asyncio.create_task(mining_runtime._main_async(args))
    try:
        def accepted_shares() -> list[dict]:
            if not session_path.exists():
                return []
            try:
                data = json.loads(session_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return []
            return [
                e
                for e in data.get("share_log", [])
                if e.get("state") == "ACCEPTED"
            ]

        await _wait(
            lambda: len(accepted_shares()) >= min_accepted,
            timeout=timeout,
            what=f"{min_accepted} pool-ACCEPTED shares in durable share_log",
        )
        await asyncio.sleep(0.5)
        shares = accepted_shares()
    finally:
        task.cancel()
        try:
            await task
        except BaseException:
            pass
        server.close()
        await server.wait_closed()
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        logging.getLogger().removeHandler(handler)
        handler.close()

    verdicts = pool.verdicts
    custody_files = sorted(
        p for p in (work / "theseus-custody").rglob("*") if p.is_file()
    )
    cas_files = sorted(p for p in (work / "cas").rglob("*") if p.is_file())
    return {
        "elapsed_seconds": round(time.time() - started, 3),
        "shares": shares,
        "verdicts": verdicts,
        "work": work,
        "session_path": session_path,
        "pool_log": pool_log,
        "causal": work / "causal_ledger.jsonl",
        "backend": work / "backend_decisions.jsonl",
        "hyba_db": work / "hyba.sqlite3",
        "custody_files": custody_files,
        "cas_files": cas_files,
        "run_log": run_log,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="evidence directory (default: evidence/loopback_pool_verdict/<head-sha12>)",
    )
    parser.add_argument("--min-accepted", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=240.0)
    ns = parser.parse_args()

    head = _head_sha12()
    out_dir = ns.out or (ROOT / "evidence" / "loopback_pool_verdict" / head)
    if out_dir.exists():
        parser.error(f"output directory already exists: {out_dir}")
    out_dir.mkdir(parents=True)

    result = asyncio.run(
        _run(out_dir, min_accepted=ns.min_accepted, timeout=ns.timeout)
    )

    # Flatten the retained artifacts: the work dir files are copied to the
    # pack root so each artifact sits beside the manifest.
    import shutil

    artifacts = {}
    for name, src in (
        ("mining_session.json", result["session_path"]),
        ("pool_verdicts.jsonl", result["pool_log"]),
        ("causal_ledger.jsonl", result["causal"]),
        ("backend_decisions.jsonl", result["backend"]),
        ("hyba.sqlite3", result["hyba_db"]),
    ):
        if src.exists():
            dest = out_dir / name
            shutil.copy2(src, dest)
            artifacts[name] = _sha256(dest)
    artifacts["run.log"] = _sha256(result["run_log"])
    custody_manifest = {
        "theseus_custody": [
            {
                "path": str(p.relative_to(result["work"])),
                "sha256": _sha256(p),
                "bytes": p.stat().st_size,
            }
            for p in result["custody_files"]
        ],
        "content_addressed_store": [
            {
                "path": str(p.relative_to(result["work"])),
                "sha256": _sha256(p),
                "bytes": p.stat().st_size,
            }
            for p in result["cas_files"]
        ],
    }
    # Retain the custody journal (the chained, tamper-evident spine) and a
    # sha256 manifest of every custody/CAS file — not the mirror copies
    # themselves, which would bloat the pack with one file per event.
    custody_out = out_dir / "custody"
    custody_out.mkdir(exist_ok=True)
    for wal in sorted(
        (result["work"] / "theseus-custody").rglob("journal/wal.jsonl")
    ):
        rel = wal.relative_to(result["work"] / "theseus-custody")
        owner = rel.parent.parent.name or "root"
        dest = custody_out / "journal" / owner / "wal.jsonl"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(wal, dest)
        key = dest.relative_to(custody_out).as_posix()
        artifacts[f"custody/{key}"] = _sha256(dest)
    (custody_out / "manifest.json").write_text(
        json.dumps(custody_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    artifacts["custody/manifest.json"] = _sha256(
        custody_out / "manifest.json"
    )
    # The scratch run tree is not evidence: keep the flattened artifacts.
    # Files still held open by the cancelled runtime (e.g. the sqlite handle
    # on Windows) may survive the first pass; retry briefly.
    for _ in range(30):
        shutil.rmtree(result["work"], ignore_errors=True)
        if not result["work"].exists():
            break
        time.sleep(0.1)

    pool_hashes = {
        v["block_hash"] for v in result["verdicts"] if v["accepted"]
    }
    logged_hashes = {e["block_hash"] for e in result["shares"]}
    pack = {
        "schema": "phiminer.loopback-pool-verdict/1",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "workspace_head_sha": head,
        "command": [
            sys.executable,
            "scripts/run_loopback_evidence.py",
            f"--min-accepted {ns.min_accepted}",
        ],
        "environment": {
            "PYTHIA_EXECUTION_DEVICE": "cpu",
            "pool_difficulty": LOOPBACK_DIFFICULTY,
            "submit_armed": True,
        },
        "outcome": {
            "elapsed_seconds": result["elapsed_seconds"],
            "pool_submits": len(result["verdicts"]),
            "pool_accepts": sum(1 for v in result["verdicts"] if v["accepted"]),
            "pool_rejects": sum(
                1 for v in result["verdicts"] if not v["accepted"]
            ),
            "durable_share_log_accepted": len(result["shares"]),
            "verdict_custody_match": bool(pool_hashes & logged_hashes),
        },
        "share_log": result["shares"],
        "pool_verdicts": result["verdicts"],
        "artifacts_sha256": artifacts,
        "custody_manifest": custody_manifest,
        "claim_boundary": (
            "Executed on loopback only: proves the canonical pythia-mine path "
            "executes submit -> pool verdict -> durable recording end-to-end "
            "(verifying pool recomputes each share before answering). NOT "
            "evidence of acceptance by a production or testnet pool, and NOT "
            "evidence of physical-device hashing."
        ),
    }
    pack_path = out_dir / "pack.json"
    pack_path.write_text(
        json.dumps(pack, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out_dir / "pack.sha256").write_text(
        f"{_sha256(pack_path)}  pack.json\n", encoding="utf-8"
    )
    print(json.dumps(pack["outcome"], indent=2, sort_keys=True))
    print(f"evidence pack: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
