#!/usr/bin/env python3
"""End-to-end mining stack smoke, natively (no Docker), on the CPU route.

The same service the deploy image runs (``python main.py`` with the image's
environment), against the scripted Stratum pool, with the labelled exact
SHA256d CPU reference as the execution device. It drives the stack the way
an operator does and records every stage of the canonical path:

    boot -> operator start -> subscribe/authorize -> job received
         -> search executed (hashes) -> candidate rechecked -> submitted
         -> pool verdict (the pool verifies the share's SHA256d itself)

    python scripts/native_stack_smoke.py --seconds 120 --out native-smoke

This is the stack proof available while GitHub Actions is on a billing
hold. It is not Docker evidence and not hardware evidence: the execution
lane is reported as the CPU reference, never as a device.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import docker_smoke as ds  # noqa: E402  (shared operator auth + http helpers)


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def image_env(state: Path) -> dict[str, str]:
    """deploy/azure/Dockerfile ENV, rooted at ``state`` instead of /var/lib/pythia."""
    v = str(state)
    return {
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUNBUFFERED": "1",
        "PYTHONPATH": os.pathsep.join([str(ROOT), str(ROOT / "chronus/mla1517_platform/python")]),
        "PYTHIA_HOST": "127.0.0.1",
        "PYTHIA_WEB_ROOT": str(ROOT / "dist/public"),
        "PYTHIA_AUTOSTART_WORKERS": "0",
        "PYTHIA_RUNTIME_CONFIG": f"{v}/runtime_config.json",
        "PYTHIA_BOOT_LOCK": f"{v}/tmp/main.lock",
        "PYTHIA_BOOT_AUDIT": f"{v}/boot-audit.jsonl",
        "PYTHIA_WORKER_HEARTBEAT_DIR": f"{v}/tmp/hb",
        "PYTHIA_MINING_SESSION_PATH": f"{v}/mining_session.json",
        "PYTHIA_CAUSAL_LOG_PATH": f"{v}/causal_ledger.jsonl",
        "PYTHIA_AGENTIC_STATE_PATH": f"{v}/agentic_policy.json",
        "PYTHIA_TELEMETRY_HISTORY_PATH": f"{v}/telemetry_history.jsonl",
        "PYTHIA_RETARGET_TELEMETRY_PATH": f"{v}/retarget_windows.json",
        "PYTHIA_BACKEND_EVIDENCE_PATH": f"{v}/backend_decisions.jsonl",
        "PYTHIA_INTELLIGENCE_DIR": f"{v}/intelligence",
        "PYTHIA_STORE_DIR": f"{v}/pythia-store",
        "AL_HARAS_DATA_DIR": f"{v}/al-haras",
    }


class NativeSmoke(ds.Smoke):
    def setup(self) -> None:  # noqa: D401 - replaces the Docker container with a process
        if self.out.exists():
            shutil.rmtree(self.out)
        state = self.out / "state"
        (state / "tmp").mkdir(parents=True)
        py = sys.executable
        self.spawn(
            [py, "scripts/scripted_pool.py", "--port", str(self.args.pool_port),
             "--difficulty", str(self.args.difficulty), "--job-interval", str(self.args.job_interval),
             "--log", str(self.out / "pool.jsonl"), "--summary", str(self.out / "pool.json")],
            "pool.out",
        )
        env = {
            **{k: v for k, v in os.environ.items() if not k.startswith(("PYTHIA_", "MLA1517_", "HYBA_"))},
            **image_env(state),
            "PYTHIA_PORT": str(self.args.port),
            "MLA1517_STRATUM_USER": "smoke.rig",
            "EUCLID_ADMIN_API_KEY": ds.ADMIN_KEY,
            "MLA1517_STRATUM_ENDPOINT": f"127.0.0.1:{self.args.pool_port}",
            "PYTHIA_POOLS": "braiins",
            "PYTHIA_ALLOW_UNLISTED_POOLS": "1",
            "PYTHIA_EXECUTION_DEVICE": "cpu",
            "AL_HARAS_SUBSCRIPTION_KEYS": json.dumps({"smoke": ds.SUBSCRIPTION_KEY}),
        }
        if self.args.live_submit:
            # Strict mode: THESEUS custody + OVID ontology store for every
            # proof, and an AL HARAS identity for the guardian's admission.
            env.update({
                "PYTHIA_M3_REQUIRED": "1",
                "PYTHIA_STORAGE_DB": str(state / "storage" / "ontology.db"),
                "PYTHIA_STORAGE_ROOT": str(state / "storage" / "root"),
                "PYTHIA_STORAGE_INTEGRITY_KEY_HEX": secrets.token_hex(32),
                "PYTHIA_STORAGE_CUSTODY_KEY_HEX": secrets.token_hex(32),
                "PYTHIA_STORAGE_TENANT": "smoke",
                "PYTHIA_M3_TENANT": "smoke",
                "PYTHIA_M3_ACTOR": "operator-1",
                "PYTHIA_M3_AL_HARAS_TOKEN": ds.SUBSCRIPTION,
            })
            env["PYTHIA_STORAGE_CUSTODY_ROOT"] = str(state / "storage" / "custody")
            (state / "storage" / "root").mkdir(parents=True, exist_ok=True)
            # One-time operator admission of the storage tenant (fails closed otherwise).
            admitted = subprocess.run(
                [py, "scripts/provision_m3_tenant.py", "--tenant", "smoke", "--approve-tenant"],
                cwd=ROOT, env=env, capture_output=True, text=True, timeout=120,
            )
            (self.out / "provision.log").write_text(admitted.stdout + admitted.stderr, encoding="utf-8")
            if admitted.returncode != 0:
                raise SystemExit(f"tenant provisioning failed: {admitted.stderr[-400:]}")
        env.update(dict(item.split("=", 1) for item in self.args.env))
        handle = open(self.out / "container.log", "w", encoding="utf-8")
        self.service = subprocess.Popen(
            [py, "main.py"], cwd=ROOT, env=env, stdout=handle, stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        self.procs.append(self.service)

    def run(self) -> bool:
        started = time.monotonic()
        healthy = False
        while time.monotonic() - started < 120 and self.service.poll() is None:
            try:
                if ds.http(f"{self.base}/healthz", timeout=2)[0] == 200:
                    healthy = True
                    break
            except OSError:
                pass
            time.sleep(1)
        if not self.stage("boot", healthy, f"/healthz 200 after {time.monotonic() - started:.1f}s"
                          if healthy else f"no /healthz (service rc={self.service.poll()})"):
            return False
        status, ready = ds.http_json(f"{self.base}/api/v1/ready-to-mine")
        self.note("ready-to-mine before start", f"HTTP {status}: {ready.get('reason') or ready.get('blockers') or ''}")
        status, payload = ds.http_json(f"{self.base}/api/v1/mining/start", method="POST",
                                       body={"observation": {"value": 1}}, headers=ds.MEDIATED)
        if not self.stage("operator start", status == 200 and payload.get("ok") is True,
                          f"POST /api/v1/mining/start -> {status} {json.dumps(payload)[:200]}"):
            return False
        if self.args.live_submit:
            # The operator's approval, bound to this pool endpoint + worker. It
            # is refused until strict storage/governance (AL HARAS + THESEUS)
            # evidence is ready, so retry for a bounded time and report why.
            body = {
                "pools": [{"endpoint": f"127.0.0.1:{self.args.pool_port}", "worker": "smoke.rig",
                           "password": "x", "enabled": True}],
                "live_submit": {"enabled": True},
            }
            approved, last = False, ""
            until = time.monotonic() + 90
            while time.monotonic() < until:
                try:
                    status, reply = ds.http_json(f"{self.base}/api/v1/config", method="PUT",
                                                 body=body, timeout=60)
                except OSError as exc:  # applying config restarts arms; retry
                    status, reply = 0, {"error": f"{type(exc).__name__}: {exc}"}
                last = f"PUT /api/v1/config -> {status} {json.dumps(reply)[:220]}"
                if status == 200:
                    approved = True
                    break
                time.sleep(3)
            if not self.stage("live submission approved (operator)", approved, last):
                return False
        deadline = time.monotonic() + self.args.seconds
        evidence: dict = {}
        workers: dict = {}
        pool: dict = {}
        while time.monotonic() < deadline:
            time.sleep(5)
            _, evidence = ds.http_json(f"{self.base}/api/v1/mining/evidence", headers=ds.MEDIATED)
            _, status_payload = ds.http_json(f"{self.base}/api/v1/mla1517/status")
            workers = {n: r.get("state") for n, r in (status_payload.get("workers") or {}).items()
                       if isinstance(r, dict)}
            (self.out / "evidence.json").write_text(json.dumps(evidence, indent=2, default=str))
            (self.out / "status.json").write_text(json.dumps(status_payload, indent=2, default=str))
            if (self.out / "pool.json").exists():
                try:
                    pool = json.loads((self.out / "pool.json").read_text())
                except ValueError:
                    pass
            if self.args.stop_on_accept and pool.get("accepted", 0) >= 1:
                break
        self.stage("workers", workers.get("agentic-mining") in {"running", "ready"},
                   ", ".join(f"{k}={v}" for k, v in sorted(workers.items())) or "no workers reported")
        self.stage("subscribe + authorize", "smoke.rig" in pool.get("authorized", []),
                   f"authorized={pool.get('authorized')} methods={pool.get('methods')}")
        self.stage("job received", pool.get("jobs_sent", 0) >= 1,
                   f"jobs_sent={pool.get('jobs_sent')}")
        intelligence = evidence.get("intelligence") if isinstance(evidence, dict) else None
        loss = (intelligence or {}).get("loss", {})
        self.stage("search executed", int(loss.get("hashes", 0) or 0) > 0,
                   f"{loss.get('executions', 0)} executions, {loss.get('hashes', 0)} hashes "
                   f"(lane: CPU reference)")
        candidates = ((evidence.get("agentic") or {}).get("last_outcome") or {})
        self.note("candidates", f"last outcome: host_verified={candidates.get('candidate_host_verified')} "
                  f"pool_outcome={candidates.get('pool_outcome')} submission={evidence.get('submission')}")
        if self.args.live_submit:
            self.stage("share submitted", pool.get("submits", 0) >= 1, f"submits={pool.get('submits')}")
            self.stage("pool verified + accepted",
                       pool.get("accepted", 0) >= 1 and not pool.get("rejected", 0),
                       f"accepted={pool.get('accepted')} rejected={pool.get('rejected')} "
                       f"reasons={pool.get('reject_reasons')}")
        else:
            self.stage("shadow: nothing written to the pool", pool.get("submits", 0) == 0,
                       f"submits={pool.get('submits')} (live submission not approved)")
        self.stage("evidence", bool(evidence.get("evidence_available")) and isinstance(intelligence, dict),
                   f"schema={evidence.get('schema')} worker_live={evidence.get('worker_live')}")
        return all(ok is not False for _, ok, _ in self.stages)

    def teardown(self) -> None:
        try:
            os.killpg(self.service.pid, signal.SIGINT)
            self.service.wait(timeout=15)
        except (ProcessLookupError, subprocess.TimeoutExpired, AttributeError):
            try:
                os.killpg(self.service.pid, signal.SIGKILL)
            except (ProcessLookupError, AttributeError):
                pass
        for proc in self.procs:
            if proc.poll() is None:
                proc.send_signal(signal.SIGINT)
        for proc in self.procs:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--seconds", type=int, default=120)
    parser.add_argument("--out", default="native-smoke")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--pool-port", type=int, default=0)
    parser.add_argument("--difficulty", type=float, default=1e-5)
    parser.add_argument("--job-interval", type=float, default=15.0)
    parser.add_argument("--stop-on-accept", action="store_true")
    parser.add_argument("--live-submit", action="store_true",
                        help="PYTHIA_M3_REQUIRED=1 and approve live submission for this pool")
    parser.add_argument("--env", action="append", default=[], help="extra KEY=VALUE for the service")
    args = parser.parse_args()
    args.port = args.port or free_port()
    args.pool_port = args.pool_port or free_port()
    args.image = "native checkout (no Docker)"
    smoke = NativeSmoke(args)
    smoke.setup()
    try:
        passed = smoke.run()
    finally:
        smoke.teardown()
    report = smoke.summary(passed).replace("## Docker live smoke", "## Native stack smoke (CPU reference, no Docker)")
    (smoke.out / "summary.md").write_text(report, encoding="utf-8")
    print(report)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
