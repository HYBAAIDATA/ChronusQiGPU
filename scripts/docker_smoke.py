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
import re
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
sys.path.insert(0, str(ROOT))

from al_haras.entitlements import SubscriptionAuthority, SubscriptionClaims  # noqa: E402

CONTAINER = "pythia-smoke"


# The operator key the container is started with; state-changing calls present it.
ADMIN_KEY = secrets.token_hex(32)

# The subscription boundary mediates the privileged routes: the container gets a
# smoke-only keyring and this process mints a token for tenant/actor headers.
SUBSCRIPTION_KEY = secrets.token_hex(32)
SUBSCRIPTION = SubscriptionAuthority(
    {"smoke": SUBSCRIPTION_KEY.encode()}, "hyba-subscriptions"
).issue(
    SubscriptionClaims(
        subscription_id="smoke-sub",
        tenant_id="smoke",
        issuer="hyba-subscriptions",
        key_id="smoke",
        capabilities=("hyba.security",),
        actors=("operator-1",),
        not_before=0,
        expires_at=int(time.time()) + 3600,
    )
)
MEDIATED = {
    "Authorization": f"Bearer {SUBSCRIPTION}",
    "X-HYBA-Tenant": "smoke",
    "X-HYBA-Actor": "operator-1",
}


def http(
    url: str,
    *,
    method: str = "GET",
    body: dict | None = None,
    timeout: float = 5.0,
    headers: dict | None = None,
):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        request.add_header("Content-Type", "application/json")
    for name, value in (headers or {}).items():
        request.add_header(name, value)
    if method not in ("GET", "HEAD") and "Authorization" not in (headers or {}):
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
            "AL_HARAS_SUBSCRIPTION_KEYS": json.dumps({"smoke": SUBSCRIPTION_KEY}),
            "AL_HARAS_DATA_DIR": "/var/lib/pythia/al-haras",
        }
        if self.args.execution_device:
            # Bridge-free route (e.g. the exact SHA256d CPU reference): the
            # MMIO register block is not the execution device.
            env.pop("MLA1517_MMIO_DEVICE", None)
            env["PYTHIA_EXECUTION_DEVICE"] = self.args.execution_device
        if self.args.live_submit:
            env.update(self.strict_env())
            self.provision(state, env)
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

    def strict_env(self) -> dict:
        """Strict storage/governance: THESEUS custody + OVID store + AL HARAS identity."""
        if not hasattr(self, "_strict"):
            self._strict = {
                "PYTHIA_M3_REQUIRED": "1",
                "PYTHIA_STORAGE_DB": "/var/lib/pythia/storage/ontology.db",
                "PYTHIA_STORAGE_ROOT": "/var/lib/pythia/storage/root",
                "PYTHIA_STORAGE_CUSTODY_ROOT": "/var/lib/pythia/storage/custody",
                "PYTHIA_STORAGE_INTEGRITY_KEY_HEX": secrets.token_hex(32),
                "PYTHIA_STORAGE_CUSTODY_KEY_HEX": secrets.token_hex(32),
                "PYTHIA_STORAGE_TENANT": "smoke",
                "PYTHIA_M3_TENANT": "smoke",
                "PYTHIA_M3_ACTOR": "operator-1",
                "PYTHIA_M3_AL_HARAS_TOKEN": SUBSCRIPTION,
            }
        return self._strict

    def provision(self, state: Path, env: dict) -> None:
        """One-time operator admission of the storage tenant, in the image."""
        argv = ["docker", "run", "--rm", "--network", "none", "-v", f"{state}:/var/lib/pythia"]
        for key, value in env.items():
            argv += ["-e", f"{key}={value}"]
        argv += [self.args.image, "sh", "-c",
                 "mkdir -p /var/lib/pythia/storage/root && "
                 "python scripts/provision_m3_tenant.py --tenant smoke --approve-tenant"]
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=300)
        (self.out / "provision.log").write_text(proc.stdout + proc.stderr, encoding="utf-8")
        if proc.returncode != 0:
            raise RuntimeError(f"tenant provisioning failed: {proc.stderr[-300:]}")

    def approve_live_submission(self) -> bool:
        body = {
            "pools": [{"endpoint": f"127.0.0.1:{self.args.pool_port}", "worker": "smoke.rig",
                       "password": "x", "enabled": True}],
            "live_submit": {"enabled": True},
        }
        last = ""
        until = time.monotonic() + 120
        while time.monotonic() < until:
            try:
                status, reply = http_json(f"{self.base}/api/v1/config", method="PUT",
                                          body=body, timeout=60)
            except OSError as exc:
                status, reply = 0, {"error": f"{type(exc).__name__}: {exc}"}
            last = f"PUT /api/v1/config -> {status} {json.dumps(reply)[:200]}"
            if status == 200:
                return self.stage("live submission approved (operator)", True, last)
            time.sleep(3)
        return self.stage("live submission approved (operator)", False, last)

    def teardown(self) -> None:
        with open(self.out / "container.log", "w", encoding="utf-8") as fh:
            subprocess.run(["docker", "logs", CONTAINER], stdout=fh, stderr=subprocess.STDOUT)
        subprocess.run(
            ["docker", "exec", "-u", "0", CONTAINER, "chmod", "-R", "a+rX", "/var/lib/pythia"],
            capture_output=True,
        )
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
            f"{self.base}/api/v1/mining/start",
            method="POST",
            body={"observation": {"value": 1}},
            headers=MEDIATED,
        )
        self.stage(
            "operator start",
            status == 200 and started_payload.get("ok") is True,
            f"POST /api/v1/mining/start -> {status} {json.dumps(started_payload)[:200]}",
        )
        if self.args.live_submit and not self.approve_live_submission():
            return False

        deadline = time.monotonic() + self.args.seconds
        evidence: dict = {}
        workers: dict = {}
        while time.monotonic() < deadline:
            time.sleep(5)
            _, evidence = http_json(f"{self.base}/api/v1/mining/evidence", headers=MEDIATED)
            _, status_payload = http_json(f"{self.base}/api/v1/mla1517/status")
            workers = {
                name: record.get("state")
                for name, record in (status_payload.get("workers") or {}).items()
                if isinstance(record, dict)
            }
            (self.out / "evidence.json").write_text(json.dumps(evidence, indent=2, default=str))
            (self.out / "status.json").write_text(json.dumps(status_payload, indent=2, default=str))
            if self.args.stop_on_accept:
                try:
                    if json.loads((self.out / "pool.json").read_text()).get("accepted", 0) >= 1:
                        break
                except (OSError, ValueError):
                    pass

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
        if not self.args.execution_device:
            self.stage(
                "device path (no wedge)",
                observed >= 3,
                f"{observed} vault records reached the chooser in {self.args.seconds}s",
            )
        # A read-only image must keep every writer on the state volume: any
        # component still writing beside its code shows up here.
        denied = sorted(set(re.findall(
            r"(?:Permission denied|Read-only file system): '([^']+)'",
            log_text + json.dumps(evidence, default=str),
        )))
        self.stage(
            "state stays on the volume",
            not denied,
            "no permission/read-only errors" if not denied else "denied: " + ", ".join(denied[:6]),
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
        if self.args.execution_device:
            self.stage(
                "search executed",
                int(loss.get("hashes", 0) or 0) > 0,
                f"{executions} executions, {loss.get('hashes', 0)} hashes "
                f"(PYTHIA_EXECUTION_DEVICE={self.args.execution_device})",
            )
            outcome = (evidence.get("agentic") or {}).get("last_outcome") or {}
            self.note(
                "candidates",
                f"host_verified={outcome.get('candidate_host_verified')} "
                f"pool_outcome={outcome.get('pool_outcome')} submission={evidence.get('submission')}",
            )
        if self.args.live_submit:
            self.stage("share submitted", pool.get("submits", 0) >= 1, f"submits={pool.get('submits')}")
            self.stage(
                "pool verified + accepted",
                pool.get("accepted", 0) >= 1 and not pool.get("rejected", 0),
                f"accepted={pool.get('accepted')} rejected={pool.get('rejected')} "
                f"reasons={pool.get('reject_reasons')}",
            )
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
    parser.add_argument("--execution-device", default="",
                        help="bridge-free route, e.g. cpu (default: the MMIO register bridge)")
    parser.add_argument("--live-submit", action="store_true",
                        help="strict storage/governance, tenant admission, operator approval")
    parser.add_argument("--stop-on-accept", action="store_true")
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
