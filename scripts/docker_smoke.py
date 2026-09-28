"""Observable live smoke of the deploy image against a scripted pool.

Runs the image exactly as deployed, plus a device register block on a bind
mount, a scripted Stratum pool and the vault feeder, then drives it the way
an operator does and records what happened at every stage:

1. boot: /healthz, the operator UI, the durable volume writable as uid 10001
2. operator: POST /api/v1/mining/start spawns the supervised workers
3. pool: the worker in the container subscribes, authorizes and binds jobs
4. device path: vault records are observed continuously (no wedge), and the
   Salamander recovery lifecycle is recorded in the causal ledger
5. evidence: /api/v1/mining/evidence carries the intelligence snapshot

Hashing needs genuine MLA1517 hot states; the feeder's fixtures are
quarantined or throttled by the host's own integrity checks, which the
summary reports rather than hides. Everything lands in ``--out`` (container
log, pool log, feeder log, evidence and status JSON, causal ledger) and, on
GitHub Actions, in the job summary.

    python scripts/docker_smoke.py --image pythia-control:ci --seconds 60
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import secrets
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTAINER = "pythia-smoke"


# The operator key the container is started with; state-changing calls present it.
ADMIN_KEY = secrets.token_hex(32)


def http(url: str, *, method: str = "GET", body: dict | None = None, timeout: float = 5.0):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        request.add_header("Content-Type", "application/json")
    if method not in ("GET", "HEAD"):
        request.add_header("Authorization", f"Bearer {ADMIN_KEY}")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def http_json(url: str, **kwargs):
    status, raw = http(url, **kwargs)
    try:
        return status, json.loads(raw)
    except ValueError:
        return status, {"raw": raw[:500].decode(errors="replace")}


class Smoke:
    def __init__(self, args) -> None:
        self.args = args
        self.out = Path(args.out).resolve()
        self.base = f"http://127.0.0.1:{args.port}"
        self.stages: list[tuple[str, bool, str]] = []
        self.procs: list[subprocess.Popen] = []

    def stage(self, name: str, ok: bool, detail: str) -> bool:
        self.stages.append((name, ok, detail))
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}", flush=True)
        return ok

    def note(self, name: str, detail: str) -> None:
        self.stages.append((name, None, detail))
        print(f"[INFO] {name}: {detail}", flush=True)

    def spawn(self, argv: list[str], log: str) -> subprocess.Popen:
        handle = open(self.out / log, "w", encoding="utf-8")
        proc = subprocess.Popen(argv, stdout=handle, stderr=subprocess.STDOUT, cwd=ROOT)
        self.procs.append(proc)
        return proc

    def setup(self) -> None:
        if self.out.exists():
            shutil.rmtree(self.out)
        state = self.out / "state"
        state.mkdir(parents=True)
        (state / "mmio.regs").touch()
        # The image runs as uid 10001; the bind-mounted volume must be writable.
        for path in (state, state / "mmio.regs"):
            os.chmod(path, 0o777 if path.is_dir() else 0o666)
        py = sys.executable
        self.spawn(
            [
                py,
                "scripts/scripted_pool.py",
                "--port",
                str(self.args.pool_port),
                "--job-interval",
                "10",
                "--log",
                str(self.out / "pool.jsonl"),
                "--summary",
                str(self.out / "pool.json"),
            ],
            "pool.out",
        )
        self.spawn(
            [
                py,
                "scripts/smoke_vault_feeder.py",
                "--device",
                str(state / "mmio.regs"),
                "--interval",
                "0.5",
            ],
            "feeder.jsonl",
        )
        subprocess.run(["docker", "rm", "-f", CONTAINER], capture_output=True)
        env = {
            "PYTHIA_PORT": str(self.args.port),
            "MLA1517_STRATUM_USER": "smoke.rig",
            "EUCLID_ADMIN_API_KEY": ADMIN_KEY,
            "MLA1517_STRATUM_ENDPOINT": f"127.0.0.1:{self.args.pool_port}",
            "PYTHIA_POOLS": "braiins",
            "PYTHIA_ALLOW_UNLISTED_POOLS": "1",
            "MLA1517_MMIO_DEVICE": "/var/lib/pythia/mmio.regs",
        }
        argv = [
            "docker",
            "run",
            "-d",
            "--name",
            CONTAINER,
            "--network",
            "host",
            "-v",
            f"{state}:/var/lib/pythia",
        ]
        for key, value in env.items():
            argv += ["-e", f"{key}={value}"]
        subprocess.run(argv + [self.args.image], check=True, capture_output=True)

    def teardown(self) -> None:
        with open(self.out / "container.log", "w", encoding="utf-8") as fh:
            subprocess.run(["docker", "logs", CONTAINER], stdout=fh, stderr=subprocess.STDOUT)
        subprocess.run(["docker", "rm", "-f", CONTAINER], capture_output=True)
        for proc in self.procs:
            proc.send_signal(signal.SIGINT)
        for proc in self.procs:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    def run(self) -> bool:
        started = time.monotonic()
        healthy = False
        while time.monotonic() - started < 90:
            try:
                status, _ = http(f"{self.base}/healthz", timeout=2)
                if status == 200:
                    healthy = True
                    break
            except OSError:
                pass
            time.sleep(1)
        boot_s = time.monotonic() - started
        if not self.stage(
            "boot",
            healthy,
            f"/healthz 200 after {boot_s:.1f}s" if healthy else "no /healthz in 90s",
        ):
            return False
        status, index = http(f"{self.base}/")
        self.stage(
            "operator UI",
            status == 200 and b"<html" in index.lower(),
            f"GET / -> {status}, {len(index)} bytes",
        )
        writable = subprocess.run(
            [
                "docker",
                "exec",
                CONTAINER,
                "sh",
                "-c",
                'for p in "$PYTHIA_MINING_SESSION_PATH" "$PYTHIA_CAUSAL_LOG_PATH" '
                '"$PYTHIA_AGENTIC_STATE_PATH" "$PYTHIA_INTELLIGENCE_DIR/x"; do d=$(dirname "$p"); '
                'mkdir -p "$d" && test -w "$d" || { echo "not writable: $d"; exit 1; }; done; id -u',
            ],
            capture_output=True,
            text=True,
        )
        self.stage(
            "durable volume",
            writable.returncode == 0 and writable.stdout.strip().endswith("10001"),
            f"session, causal ledger, agentic state and Aethel memory writable as uid {writable.stdout.strip()}",
        )
        status, ready = http_json(f"{self.base}/api/v1/ready-to-mine")
        self.note(
            "ready-to-mine before start",
            f"HTTP {status}: {ready.get('reason') or ready.get('blockers') or ready}",
        )

        status, started_payload = http_json(
            f"{self.base}/api/v1/mining/start", method="POST", body={}
        )
        self.stage(
            "operator start",
            status == 200 and started_payload.get("ok") is True,
            f"POST /api/v1/mining/start -> {status} {json.dumps(started_payload)[:200]}",
        )

        deadline = time.monotonic() + self.args.seconds
        evidence: dict = {}
        workers: dict = {}
        while time.monotonic() < deadline:
            time.sleep(5)
            _, evidence = http_json(f"{self.base}/api/v1/mining/evidence")
            _, status_payload = http_json(f"{self.base}/api/v1/mla1517/status")
            workers = {
                name: record.get("state")
                for name, record in (status_payload.get("workers") or {}).items()
                if isinstance(record, dict)
            }
            (self.out / "evidence.json").write_text(json.dumps(evidence, indent=2, default=str))
            (self.out / "status.json").write_text(json.dumps(status_payload, indent=2, default=str))

        self.stage(
            "workers",
            workers.get("agentic-mining") in {"running", "ready"},
            ", ".join(f"{k}={v}" for k, v in sorted(workers.items())) or "no workers reported",
        )
        status, ready = http_json(f"{self.base}/api/v1/ready-to-mine")
        self.note(
            "ready-to-mine after start",
            f"HTTP {status}: {ready.get('reason') or ready.get('blockers') or ready}",
        )
        pool = (
            json.loads((self.out / "pool.json").read_text())
            if (self.out / "pool.json").exists()
            else {}
        )
        self.stage(
            "pool session",
            "smoke.rig" in pool.get("authorized", []) and pool.get("jobs_sent", 0) >= 2,
            f"authorized={pool.get('authorized')} jobs_sent={pool.get('jobs_sent')} "
            f"methods={pool.get('methods')} submits={pool.get('submits')}",
        )
        ledger = self.out / "state" / "causal_ledger.jsonl"
        kinds: collections.Counter = collections.Counter()
        if ledger.exists():
            for line in ledger.read_text(encoding="utf-8").splitlines():
                try:
                    kinds[json.loads(line).get("kind")] += 1
                except ValueError:
                    continue
        (self.out / "causal_ledger.jsonl").write_text(ledger.read_text() if ledger.exists() else "")
        container_log = subprocess.run(
            ["docker", "logs", CONTAINER], capture_output=True, text=True
        )
        log_text = container_log.stdout + container_log.stderr
        observed = log_text.count("selected lane=")
        self.stage(
            "device path (no wedge)",
            observed >= 3,
            f"{observed} vault records reached the chooser in {self.args.seconds}s",
        )
        recoveries = {k: v for k, v in kinds.items() if k and k.startswith("recovery_")}
        self.note(
            "self-healing", json.dumps(recoveries) if recoveries else "no recoveries recorded"
        )
        intelligence = evidence.get("intelligence") if isinstance(evidence, dict) else None
        self.stage(
            "evidence",
            bool(evidence.get("evidence_available")) and isinstance(intelligence, dict),
            f"schema={evidence.get('schema')} worker_live={evidence.get('worker_live')} "
            f"intelligence={'present' if isinstance(intelligence, dict) else 'absent'}",
        )
        loss = (intelligence or {}).get("loss", {})
        executions = loss.get("executions", 0)
        self.note(
            "hashing",
            f"{executions} executions, {loss.get('hashes', 0)} hashes"
            + (
                ""
                if executions
                else " — needs genuine MLA1517 hot states; the fixtures are gated by design"
            ),
        )
        return all(ok is not False for _, ok, _ in self.stages)

    def summary(self, passed: bool) -> str:
        lines = [
            "## Docker live smoke",
            "",
            f"Image `{self.args.image}` against a scripted pool, {self.args.seconds}s — **{'PASS' if passed else 'FAIL'}**",
            "",
            "| | Stage | Observed |",
            "|---|---|---|",
        ]
        for name, ok, detail in self.stages:
            mark = "ℹ️" if ok is None else ("✅" if ok else "❌")
            lines.append(f"| {mark} | {name} | {detail.replace('|', '/')} |")
        lines += [
            "",
            "Artifacts: container log, pool and feeder logs, evidence, status and causal ledger.",
        ]
        return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--image", default="pythia-control:smoke")
    parser.add_argument("--seconds", type=int, default=60)
    parser.add_argument("--port", type=int, default=3000)
    parser.add_argument("--pool-port", type=int, default=3334)
    parser.add_argument("--out", default="smoke-artifacts")
    args = parser.parse_args()
    smoke = Smoke(args)
    passed = False
    try:
        smoke.setup()
        passed = smoke.run()
    except Exception as exc:
        smoke.stage("harness", False, f"{type(exc).__name__}: {exc}")
    finally:
        smoke.teardown()
    report = smoke.summary(passed)
    (smoke.out / "summary.md").write_text(report)
    step_summary = os.getenv("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a", encoding="utf-8") as fh:
            fh.write(report)
    print(report)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
