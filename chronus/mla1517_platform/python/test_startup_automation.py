"""Fresh-process startup automation for the canonical mining runtime.

The test launches ``main.py --mine`` — the production entry point — as a
child process and observes it from outside. No internal step is invoked:
the runtime must connect, subscribe, authorise, receive the pool's job,
plan, execute, host-verify the candidate, submit it, and record the pool's
literal acknowledgement — the whole closed loop — on its own.

A scripted local Stratum peer stands in for the pool over real TCP. The
share is found honestly (the peer declares a target every nonce meets),
locally verified by the miner's own SHA256d proof check, and acknowledged
by the peer, not by the miner.
"""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

PLATFORM = Path(__file__).resolve().parent
REPO = PLATFORM.parents[2]
TUQC = REPO / "turing_universal_quantum_computer"
PYTHON = sys.executable or r"C:\Python312\python.exe"

from test_agentic_voyages import EASY_TARGET, FakePool, _job, bip34_coinb1

PATIENCE_S = float(os.getenv("PYTHIA_STARTUP_TEST_TIMEOUT_S", "120"))


def _serve(pool: FakePool):
    """Host the scripted Stratum peer on its own asyncio loop thread."""
    loop = asyncio.new_event_loop()
    server = loop.run_until_complete(asyncio.start_server(pool.handle, "127.0.0.1", 0))
    port = server.sockets[0].getsockname()[1]
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    return loop, server, port


def _child_env(tmp: Path, port: int) -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(PLATFORM), str(TUQC), str(REPO)])
    env["PYTHONIOENCODING"] = "utf-8"
    env["MLA1517_LOG_LEVEL"] = "INFO"
    env["PYTHIA_EXECUTION_DEVICE"] = "cpu"
    env["PYTHIA_ALLOW_UNLISTED_POOLS"] = "1"
    env["PYTHIA_POOLS"] = "braiins"
    env["MLA1517_STRATUM_ENDPOINT"] = f"127.0.0.1:{port}"
    env["MLA1517_STRATUM_USER"] = "PYTHIA.001"
    env["MLA1517_STRATUM_PASSWORD"] = "x"
    env["PYTHIA_MINING_SESSION_PATH"] = str(tmp / "mining_session.json")
    env["PYTHIA_MINING_COOLDOWN_SECONDS"] = "0.2"
    env["PYTHIA_CAUSAL_LOG_PATH"] = str(tmp / "causal_ledger.jsonl")
    env["PYTHIA_AGENTIC_STATE_PATH"] = str(tmp / "agentic_policy.json")
    env["PYTHIA_INTELLIGENCE_DIR"] = str(tmp / "intelligence")
    env["PYTHIA_RETARGET_TELEMETRY_PATH"] = str(tmp / "retarget_windows.json")
    env["PYTHIA_WORKER_HEARTBEAT_DIR"] = str(tmp / "hb")
    # Isolate from any runtime_config.json the checkout happens to hold.
    env["PYTHIA_RUNTIME_CONFIG"] = str(tmp / "runtime_config.json")
    return env


class StartupAutomationTests(unittest.TestCase):
    def test_fresh_process_reaches_operational_mining_and_submits(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="pythia-startup-"))
        job = _job(
            "startup-job-1",
            prevhash=secrets.token_hex(32),
            coinb1=bip34_coinb1(840_000),
        )
        pool = FakePool(target=EASY_TARGET, job=job)
        loop, server, port = _serve(pool)
        log_path = tmp / "miner.log"
        proc = None
        try:
            with log_path.open("w", encoding="utf-8") as log:
                proc = subprocess.Popen(
                    [
                        PYTHON,
                        "-u",
                        str(PLATFORM / "main.py"),
                        "--mine",
                        "--submit",
                        "--log-level",
                        "INFO",
                    ],
                    cwd=REPO,
                    env=_child_env(tmp, port),
                    stdout=log,
                    stderr=subprocess.STDOUT,
                )
                deadline = time.monotonic() + PATIENCE_S
                while time.monotonic() < deadline:
                    if pool.submits:
                        break
                    if proc.poll() is not None:
                        self.fail("miner exited before submitting: " + log_path.read_text()[-4000:])
                    time.sleep(0.25)
            self.assertTrue(pool.submits, "no mining.submit reached the pool in time")
            session_path = tmp / "mining_session.json"
            deadline = time.monotonic() + 30
            outcome = None
            while time.monotonic() < deadline:
                if session_path.exists():
                    body = json.loads(session_path.read_text(encoding="utf-8"))
                    log_tail = body.get("share_log") or []
                    if log_tail:
                        outcome = log_tail[-1].get("outcome")
                        break
                time.sleep(0.25)
            self.assertTrue(outcome, f"pool acknowledgement not recorded: {outcome!r}")
            causal_path = tmp / "causal_ledger.jsonl"
            kinds = set()
            revisions = set()
            if causal_path.exists():
                for line in causal_path.read_text(encoding="utf-8").splitlines():
                    event = json.loads(line)
                    kinds.add(event.get("kind"))
                    revisions.add(event.get("software_revision"))
            self.assertIn("submission_sent", kinds)
            self.assertTrue(
                {"execution_started", "execution_finished"} & kinds,
                f"expected execution evidence in {sorted(kinds)}",
            )
            self.assertEqual(revisions - {None}, revisions, f"missing revision: {sorted(kinds)}")
            self.assertTrue(all(revisions), "causal records carry no software_revision")
        finally:
            if proc is not None:
                proc.terminate()
                try:
                    proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    proc.kill()
            loop.call_soon_threadsafe(server.close)
            loop.call_soon_threadsafe(loop.stop)

    def test_miner_refuses_unlisted_pool_without_override(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="pythia-startup-deny-"))
        job = _job("deny-job", coinb1=bip34_coinb1(840_000))
        pool = FakePool(target=EASY_TARGET, job=job)
        loop, server, port = _serve(pool)
        env = _child_env(tmp, port)
        env.pop("PYTHIA_ALLOW_UNLISTED_POOLS", None)
        try:
            result = subprocess.run(
                [PYTHON, "-u", str(PLATFORM / "main.py"), "--mine"],
                cwd=REPO,
                env=env,
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("PYTHIA_ALLOW_UNLISTED_POOLS", result.stderr + result.stdout)
        finally:
            loop.call_soon_threadsafe(server.close)
            loop.call_soon_threadsafe(loop.stop)


if __name__ == "__main__":
    unittest.main()
