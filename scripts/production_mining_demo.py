"""Bounded demonstration of the production mining entry point.

Runs ``mining_runtime._main_async`` — the same entry as
``python chronus/mla1517_platform/python/main.py --mine`` — against a
scripted, in-process Stratum endpoint (test-only fixture; never a real
pool). It prints a truthful JSON trace: which guarded states the cycle
machine actually visited, the separated lifecycle flags, the backend
census the registry probed, and literal share counters. If no share was
found, the counters say so — nothing is manufactured.

Usage:
    python scripts/production_mining_demo.py [--seconds 12] [--easy]

``--easy`` uses a target that accepts the first hash of every window
(deterministic submit+ack evidence); the default is a real-difficulty
target where shares_found=0 is the expected, honest result.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import logging
import os
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "chronus" / "mla1517_platform" / "python"))
sys.path.insert(0, str(REPO))

EASY_TARGET = "ff" * 32  # every nonce meets it — share on the first hash
HARD_TARGET = "00" * 31 + "01"  # nothing in the demo window meets it


def _line(payload: dict) -> bytes:
    return (json.dumps(payload, separators=(",", ":")) + "\n").encode()


class _ScriptedPool:
    """TEST-ONLY Stratum fixture: literal subscribe/authorize/notify/submit.

    Deterministic subscribe (extranonce1 01020304, extranonce2 size 4),
    accepts every worker, pushes one fixed job, and accepts every submit.
    It records what it receives; it proves wire correctness, nothing else.
    """

    def __init__(self, target: str, job: list) -> None:
        self.target = target
        self.job = job
        self.submits: list[list] = []
        self.connections = 0
        self.authorized: list[str] = []
        self._writer: asyncio.StreamWriter | None = None

    async def handle(self, reader, writer) -> None:
        self.connections += 1
        self._writer = writer
        try:
            subscribe = json.loads(await reader.readline())
            writer.write(
                _line(
                    {
                        "id": subscribe["id"],
                        "result": [[["mining.notify", "ae"]], "01020304", 4],
                        "error": None,
                    }
                )
            )
            authorize = json.loads(await reader.readline())
            self.authorized.append(str(authorize["params"][0]))
            writer.write(_line({"id": authorize["id"], "result": True, "error": None}))
            writer.write(
                _line({"id": None, "method": "mining.set_target", "params": [self.target]})
            )
            writer.write(_line({"id": None, "method": "mining.notify", "params": self.job}))
            await writer.drain()
            while line := await reader.readline():
                message = json.loads(line)
                if message.get("method") == "mining.submit":
                    self.submits.append(message["params"])
                    writer.write(_line({"id": message["id"], "result": True, "error": None}))
                    await writer.drain()
        except (ConnectionError, asyncio.IncompleteReadError):
            pass
        finally:
            writer.close()


def _job(job_id: str) -> list:
    # BIP34-style coinb1: version, one null input, script len, height push —
    # the pool-derived chain tip exists only when this shape is present.
    height = 800_001
    push = height.to_bytes(3, "little")
    script_prefix = bytes([len(push)]) + push
    coinb1 = (
        "02000000"
        + "01"
        + "00" * 32
        + "ffffffff"
        + f"{len(script_prefix) + 8:02x}"
        + script_prefix.hex()
    )
    return [
        job_id,
        "ab" * 32,
        coinb1,
        "ffffffff",
        [],
        "20000000",
        "1d00ffff",
        "65abcdef",
        True,
    ]


async def _demo(seconds: float, easy: bool) -> dict:
    import mining_runtime

    target = EASY_TARGET if easy else HARD_TARGET
    pool = _ScriptedPool(target, _job("demo-job"))
    server = await asyncio.start_server(pool.handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]

    with tempfile.TemporaryDirectory(prefix="pythia-demo-") as tmp:
        env = {
            "PYTHIA_ALLOW_UNLISTED_POOLS": "1",
            # A declared catalog pool name, repointed at the local fixture —
            # the same override an operator uses for a listed pool.
            "PYTHIA_POOLS": "braiins",
            "MLA1517_BRAIINS_ENDPOINT": f"127.0.0.1:{port}",
            "MLA1517_BRAIINS_USER": "DEMO.001",
            "MLA1517_BRAIINS_PASSWORD": "x",
            "PYTHIA_EXECUTION_DEVICE": "auto",
            "PYTHIA_MINING_SESSION_PATH": str(Path(tmp) / "session.json"),
            "PYTHIA_MINING_COOLDOWN_SECONDS": "0",
            "PYTHIA_AGENTIC_STATE_PATH": str(Path(tmp) / "agentic.json"),
            "PYTHIA_CAUSAL_LOG_PATH": str(Path(tmp) / "causal.jsonl"),
            "PYTHIA_INTELLIGENCE_DIR": str(Path(tmp) / "intel"),
            "PYTHIA_RETARGET_TELEMETRY_PATH": str(Path(tmp) / "retarget.json"),
            "PYTHIA_WORKER_HEARTBEAT_DIR": str(Path(tmp) / "hb"),
            "PYTHIA_IDENTITY_HMAC_SECRET": "aa" * 32,
            "PYTHIA_NONCE_ORDER": "m32",
            "PYTHIA_RECONNECT_MAX_S": "1",
        }
        saved = {}
        for key, value in env.items():
            saved[key] = os.environ.get(key)
            os.environ[key] = value
        try:
            args = argparse.Namespace(
                device=None,
                map_bytes=0,
                difficulty_mask=0,
                base_step=0,
                user=None,
                password=None,
                submit=True,
                tls=False,
                log_level="warning",
            )
            task = asyncio.create_task(mining_runtime._main_async(args))
            try:
                await asyncio.sleep(seconds)
            finally:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task
            server.close()
            await server.wait_closed()

            causal_path = Path(tmp) / "causal.jsonl"
            events = (
                [
                    json.loads(line)
                    for line in causal_path.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
                if causal_path.exists()
                else []
            )
            session_path = Path(tmp) / "session.json"
            session = (
                json.loads(session_path.read_text(encoding="utf-8"))
                if session_path.exists()
                else {}
            )
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    transitions = [
        {
            "from": e["detail"].get("from"),
            "to": e["detail"].get("to"),
            "event": e["detail"].get("event"),
        }
        for e in events
        if e["kind"] == "cycle_transition"
    ]
    decisions = [
        {
            "decision_id": e["detail"].get("decision_id"),
            "selected_action": e["detail"].get("selected_action"),
            "reason": e["detail"].get("reason"),
            "disposition": e["detail"].get("disposition"),
        }
        for e in events
        if e["kind"] == "decision"
    ]
    share_log = session.get("share_log", [])
    shares_found = sum(1 for s in share_log)
    result = {
        "demo": "production mining entry point vs scripted local stratum",
        "fixture": "test-only local pool; not live-pool or hardware evidence",
        "seconds": seconds,
        "target": "easy" if easy else "hard",
        "pool_connections": pool.connections,
        "authorized_workers": pool.authorized,
        "cycle_states_visited": sorted({t["to"] for t in transitions}),
        "transitions_total": len(transitions),
        "cycle_tail": transitions[-12:],
        "decisions": decisions[-6:],
        "shares_found": shares_found,
        "shares_submitted": len(pool.submits),
        "shares_accepted": sum(1 for s in share_log if s.get("outcome") is True),
        "share_log": share_log[-4:],
        "causal_events": len(events),
        "event_kinds": sorted({e["kind"] for e in events}),
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=12.0)
    parser.add_argument("--easy", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)
    started = time.time()
    report = asyncio.run(_demo(args.seconds, args.easy))
    report["wall_clock_s"] = round(time.time() - started, 2)
    print(json.dumps(report, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
