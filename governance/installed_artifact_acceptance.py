#!/usr/bin/env python3
"""Acceptance suite executed against the INSTALLED package only.

Run with a venv interpreter from a directory outside the checkout:

    <venv>/Scripts/python.exe governance/installed_artifact_acceptance.py

The script launches the installed ``pythia-api`` console script and voyages
the critical surface: liveness, readiness components, correlation echo,
telemetry, denied mutations, and the reserved-namespace non-masquerade.
Nothing from the repository checkout is placed on sys.path — every import
inside the server resolves from site-packages.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

CHECKS: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")


def http(port: int, method: str, path: str, headers=None, body=None, timeout=20):
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        method=method,
        headers=headers or {},
        data=json.dumps(body).encode() if body is not None else None,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return res.status, dict(res.headers), json.loads(res.read() or b"{}")
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), json.loads(exc.read() or b"{}")


def main() -> int:
    python = Path(sys.executable)
    pythia_api = python.parent / "pythia-api.exe"
    if not pythia_api.is_file():
        pythia_api = python.parent / "pythia-api"
    record("console script present", pythia_api.is_file(), str(pythia_api))
    if not pythia_api.is_file():
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        env = {
            **os.environ,
            "MLA1517_STRATUM_USER": "acceptance",
            "MLA1517_STRATUM_PASSWORD": "acceptance",
            "MLA1517_VIABTC_ENDPOINT": "btc.viabtc.io:3333",
            "PYTHIA_POOL_PROFILE": "viabtc",
            "PYTHIA_AUTOSTART_WORKERS": "0",
            "PYTHIA_BOOT_AUDIT": str(Path(tmp) / "BOOT_AUDIT.log"),
            "PYTHIA_BOOT_LOCK": str(Path(tmp) / "boot.lock"),
            "PYTHIA_WORKER_HEARTBEAT_DIR": str(Path(tmp) / "heartbeats"),
            "PYTHIA_WEB_ROOT": str(Path(tmp) / "web"),
        }
        port = 8471
        proc = subprocess.Popen(
            [str(pythia_api), "--host", "127.0.0.1", "--port", str(port)],
            cwd=tmp,  # neutral working directory — not the checkout
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            deadline = time.time() + 30
            up = False
            while time.time() < deadline:
                try:
                    status, _, _ = http(port, "GET", "/api/health", timeout=2)
                    up = status == 200
                    break
                except OSError:
                    time.sleep(0.5)
            record("installed control plane serves liveness", up)
            if not up:
                return 1

            status, headers, body = http(port, "GET", "/api/health")
            record(
                "correlation header minted",
                bool(headers.get("X-Request-Id")),
                headers.get("X-Request-Id", ""),
            )

            status, headers, body = http(
                port, "GET", "/api/health", headers={"X-Request-Id": "acc-1"}
            )
            record(
                "correlation header echoed",
                headers.get("X-Request-Id") == "acc-1",
                headers.get("X-Request-Id", ""),
            )

            status, _, body = http(port, "GET", "/api/v1/readyz")
            components = body.get("components") or {}
            record(
                "readiness reports component truth",
                status == 200 and "identity" in components,
                f"components={sorted(components)}",
            )

            status, _, body = http(port, "GET", "/api/v1/telemetry/summary")
            record("telemetry summary serves", status == 200, f"status={status}")

            status, _, body = http(port, "GET", "/api/v1/system/map")
            record("system map serves", status == 200, f"status={status}")

            status, headers, body = http(
                port, "POST", "/api/v1/mining/start", body={}
            )
            record(
                "unauthenticated privileged mutation denied",
                status in (400, 401, 403) and "evidence_id" in body,
                f"status={status} reason={body.get('reason')}",
            )

            status, _, body = http(port, "PUT", "/api/v1/config", body={})
            record(
                "unauthenticated config write denied",
                status in (400, 401, 403),
                f"status={status} body={body}",
            )

            # Reserved prefixes are denied at the AL HARAS boundary (signed
            # denial) before routing; they can never masquerade as services.
            for path in ("/api/v1/policy/status", "/api/v1/recovery/run"):
                status, _, body = http(port, "GET", path)
                denied = status == 404 or (
                    status in (400, 401, 403) and ("evidence_id" in body or "error" in body)
                )
                record(
                    f"reserved namespace fails closed: {path}",
                    denied and status != 200,
                    f"status={status} reason={body.get('reason', body.get('error'))}",
                )

            # Restart determinism: relaunch and confirm liveness returns.
            proc.terminate()
            proc.wait(timeout=15)
            proc = subprocess.Popen(
                [str(pythia_api), "--host", "127.0.0.1", "--port", str(port)],
                cwd=tmp,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            deadline = time.time() + 30
            up = False
            while time.time() < deadline:
                try:
                    status, _, _ = http(port, "GET", "/api/health", timeout=2)
                    up = status == 200
                    break
                except OSError:
                    time.sleep(0.5)
            record("installed control plane restarts and serves", up)
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()

    failed = [name for name, ok, _ in CHECKS if not ok]
    print(f"\n{len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed")
    if failed:
        print("FAILED:", ", ".join(failed))
        return 1
    print("EVIDENCE_CLASS: INSTALLED_ARTIFACT_EXECUTED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
