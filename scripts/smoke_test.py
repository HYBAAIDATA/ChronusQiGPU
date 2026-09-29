#!/usr/bin/env python3
"""Production smoke test for the PYTHIA operator app.

Runs locally against the Python control API. No real share submission
unless --live is passed and every gate is armed.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CANONICAL_PYTHON = _PROJECT_ROOT / "mla1517_platform_v3.4" / "python"
if str(_CANONICAL_PYTHON) not in sys.path:
    sys.path.insert(0, str(_CANONICAL_PYTHON))

from startup_contract import resolve_stratum_identity  # noqa: E402


def _load_dotenv() -> None:
    env_file = _PROJECT_ROOT / ".env"
    if not env_file.is_file():
        return
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        name = name.strip()
        value = value.strip()
        if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        if name.isidentifier() and name not in os.environ:
            os.environ[name] = value


_load_dotenv()


def _env(name: str, required: bool = False) -> str:
    value = os.environ.get(name, "")
    if required and not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def _api_key() -> str:
    return _env("EUCLID_ADMIN_API_KEY", required=True)


_API_PORT = int(os.environ.get("PYTHIA_SMOKE_PORT", "3001"))


def _request(method: str, path: str, data: dict | None = None) -> tuple[int, dict]:
    url = f"http://127.0.0.1:{_API_PORT}{path}"
    headers = {"Authorization": f"Bearer {_api_key()}", "Accept": "application/json"}
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8") or "{}")


def _wait_for_api(timeout_s: float = 30.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            status, _ = _request("GET", "/api/v1/healthz")
            if status == 200:
                return
        except urllib.error.URLError:
            pass
        time.sleep(0.5)
    raise SystemExit("Control API did not become ready in time")


def _check_health() -> None:
    status, body = _request("GET", "/api/v1/healthz")
    assert status == 200, f"/api/v1/healthz returned {status}: {body}"
    print("OK  /api/v1/healthz")


def _check_status() -> dict:
    status, body = _request("GET", "/api/v1/mla1517/status")
    assert status == 200, f"/api/v1/mla1517/status returned {status}: {body}"
    print("OK  /api/v1/mla1517/status")
    print(json.dumps(body, indent=2))
    return body


def _check_config() -> dict:
    status, body = _request("GET", "/api/v1/config")
    assert status == 200, f"/api/v1/config returned {status}: {body}"
    print("OK  /api/v1/config")
    print(json.dumps(body, indent=2))
    return body


def _check_ready_to_mine() -> None:
    status, body = _request("GET", "/api/v1/ready-to-mine")
    # 503 is the honest "not ready" signal.
    assert status in (200, 503), f"/api/v1/ready-to-mine returned {status}: {body}"
    print(f"OK  /api/v1/ready-to-mine ({status})")


def _check_self_repair_status() -> None:
    status, body = _request("GET", "/api/v1/intelligence/maintenance")
    assert status == 200, f"/api/v1/intelligence/maintenance returned {status}: {body}"
    print("OK  /api/v1/intelligence/maintenance")
    print(json.dumps(body, indent=2))


def _check_autonomous_supervisor() -> None:
    status, body = _request("GET", "/api/v1/intelligence/autonomous")
    assert status == 200, f"/api/v1/intelligence/autonomous returned {status}: {body}"
    print("OK  /api/v1/intelligence/autonomous")
    print(json.dumps(body, indent=2))


def _run_stratum_dry_run() -> None:
    identity = resolve_stratum_identity()
    cmd = [
        sys.executable,
        str(_PROJECT_ROOT / "mining" / "stratum_bridge.py"),
        "--pool",
        f"{identity.host}:{identity.port}",
        "--worker",
        identity.user,
        "--password",
        os.environ.get("MLA1517_STRATUM_PASSWORD", ""),
        "--dry-run",
        "--max-runtime",
        "30",
        "--max-shares",
        "0",
    ]
    print("RUN stratum bridge dry-run:", " ".join(cmd))
    result = subprocess.run(cmd, cwd=_PROJECT_ROOT, text=True, capture_output=True, timeout=60)
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        raise SystemExit(f"Stratum dry-run failed with code {result.returncode}")
    print("OK  stratum dry-run authorized and received a job without submitting shares")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-dry-run",
        action="store_true",
        help="Skip the live Stratum authorization dry-run",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Attempt to submit one real share (requires live_submit to be armed)",
    )
    args = parser.parse_args()

    _env("MLA1517_STRATUM_USER", required=True)
    _env("EUCLID_ADMIN_API_KEY", required=True)

    print(f"Waiting for control API on 127.0.0.1:{_API_PORT} ...")
    _wait_for_api()

    _check_health()
    _check_status()
    _check_config()
    _check_ready_to_mine()
    _check_self_repair_status()
    _check_autonomous_supervisor()

    if args.live:
        print("WARNING: --live requested; this will attempt real share submission.")
        print("Press Ctrl+C within 5 seconds to abort...")
        time.sleep(5)
        # The bridge's own gates must be armed; the smoke test does not bypass them.
        _run_stratum_dry_run()
    elif not args.skip_dry_run:
        _run_stratum_dry_run()

    print("\nAll smoke checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
