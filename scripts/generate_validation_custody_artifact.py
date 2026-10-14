"""Generate signed validation self-custody artifact for EUCLID frontier contracts (item 6.1)."""

from __future__ import annotations

import datetime
import hashlib
import hmac
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_command(argv: list[str], cwd: Path) -> dict:
    start_time = datetime.datetime.now(datetime.timezone.utc).isoformat()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(cwd)
    proc = subprocess.run(argv, cwd=str(cwd), env=env, capture_output=True, text=True)
    out = proc.stdout + proc.stderr
    out_sha = hashlib.sha256(out.encode("utf-8")).hexdigest()
    return {
        "argv": argv,
        "cwd": str(cwd),
        "started_at": start_time,
        "exit_code": proc.returncode,
        "log_sha256": out_sha,
        "output_tail": out[-1000:] if len(out) > 1000 else out,
    }


def generate_custody_artifact() -> Path:
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    commands = [
        # 1. Pytest suite
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/frontier_agent",
            "-q",
            "--confcutdir=tests/frontier_agent",
            "--basetemp=.pytest_tmp",
            "-p",
            "no:cacheprovider",
        ],
        # 2. Black formatting check
        [
            sys.executable,
            "-m",
            "black",
            "--check",
            "--line-length",
            "100",
            "chronus/agent",
            "tests/frontier_agent",
            "scripts/claim_guard_linter.py",
            "scripts/assert_production_drift_gate.py",
            "scripts/lucas_qualification_harness.py",
        ],
        # 3. Python compileall
        [
            sys.executable,
            "-m",
            "compileall",
            "-q",
            "chronus/agent",
            "tests/frontier_agent",
            "Intelligence/registry.py",
            "scripts/claim_guard_linter.py",
            "scripts/assert_production_drift_gate.py",
            "scripts/lucas_qualification_harness.py",
        ],
        # 4. Claim-guard documentation linter
        [sys.executable, "scripts/claim_guard_linter.py", "docs"],
        # 5. Production drift gate
        [sys.executable, "scripts/assert_production_drift_gate.py"],
    ]

    command_results = [run_command(cmd, _ROOT) for cmd in commands]

    # Gather source and test file hashes
    file_hashes = {}
    for folder in ("chronus/agent", "tests/frontier_agent"):
        for path in sorted((_ROOT / folder).rglob("*.py")):
            rel = str(path.relative_to(_ROOT)).replace("\\", "/")
            file_hashes[rel] = sha256_file(path)

    for script_name in (
        "scripts/claim_guard_linter.py",
        "scripts/assert_production_drift_gate.py",
        "scripts/lucas_qualification_harness.py",
    ):
        p = _ROOT / script_name
        if p.exists():
            file_hashes[script_name] = sha256_file(p)

    # Git environment hash
    try:
        git_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(_ROOT), text=True
        ).strip()
    except Exception:
        git_sha = "unknown"

    environment_state = {
        "python": sys.version,
        "platform": platform.platform(),
        "processor": platform.processor(),
        "git_head": git_sha,
        "file_hashes_digest": hashlib.sha256(
            json.dumps(file_hashes, sort_keys=True).encode("utf-8")
        ).hexdigest(),
    }

    artifact_body = {
        "task": "EUCLID-FRONTIER-REMEDIATION-20261014",
        "generated_at": now,
        "environment": environment_state,
        "commands": command_results,
        "all_commands_passed": all(c["exit_code"] == 0 for c in command_results),
        "sha256": file_hashes,
        "restrictions": [
            "no_merge",
            "no_release",
            "no_deployment",
            "no_mining",
            "no_provider_calls",
        ],
    }

    # Canonical serialization and HMAC signature for custody verification
    canonical_body = json.dumps(artifact_body, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    signer_key = b"euclid-validation-custody-salt-20261014"
    signature = hmac.new(signer_key, canonical_body, hashlib.sha256).hexdigest()

    signed_artifact = {
        "payload": artifact_body,
        "custody": {
            "signature_scheme": "HMAC-SHA256",
            "signer_identity": "euclid-validation-custody-authority",
            "signature": signature,
            "signed_at": now,
        },
    }

    target = _ROOT / "docs" / "euclid_frontier_local_validation.json"
    target.write_text(json.dumps(signed_artifact, indent=2, sort_keys=True), encoding="utf-8")
    print(f"[SUCCESS] Validation custody artifact written and signed at {target}")
    return target


if __name__ == "__main__":
    generate_custody_artifact()
