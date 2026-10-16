"""Bounded local validation custody; not independent certification or release authority.

Set EUCLID_VALIDATION_CUSTODY_KEY_HEX to a private random key of at least 32 bytes
and EUCLID_VALIDATION_CUSTODY_SIGNER to the local custodian identifier. Keep the
key outside the repository. A shared-key holder can forge an HMAC: verification
establishes local shared-key custody only, never independent execution truth.
The historical public-key/salt artifact is not accepted by this v2 verifier.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import hmac
import json
import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
SCHEMA = "euclid-local-validation-custody-v2"
SCOPE = "local-shared-key-custody-only"
SOURCE_DIRS = ("chronus/agent", "tests/frontier_agent", "tests/validation_custody", "Intelligence", "euclid")
SOURCE_FILES = (
    "scripts/generate_validation_custody_artifact.py",
    "scripts/claim_guard_linter.py",
    "scripts/assert_production_drift_gate.py",
    "scripts/lucas_qualification_harness.py",
    "pyproject.toml", "pytest.ini", "setup.cfg", "requirements.txt",
)


def canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_key(key: bytes) -> None:
    if not isinstance(key, bytes) or len(key) < 32:
        raise ValueError("private custody key must contain at least 32 bytes")
    if key == b"euclid-validation-custody-salt-20261014":
        raise ValueError("historical public custody key is forbidden")


def credentials() -> tuple[bytes, str]:
    try:
        key = bytes.fromhex(os.environ["EUCLID_VALIDATION_CUSTODY_KEY_HEX"])
        signer = os.environ["EUCLID_VALIDATION_CUSTODY_SIGNER"].strip()
    except (KeyError, ValueError) as exc:
        raise ValueError("private custody key and signer environment variables are required") from exc
    validate_key(key)
    if not signer:
        raise ValueError("local custodian identifier is required")
    return key, signer


def safe_file(root: Path, rel: str) -> Path:
    path = Path(rel)
    if path.is_absolute() or ".." in path.parts or "\\" in rel or not path.parts:
        raise ValueError("invalid custody path")
    current = root
    for part in path.parts:
        current /= part
        if current.is_symlink():
            raise ValueError("symlink custody paths are not supported")
    if not current.is_file():
        raise ValueError("custody file is missing")
    return current


def source_hashes(root: Path) -> dict[str, str]:
    paths = set()
    for folder in SOURCE_DIRS:
        base = root / folder
        if base.is_symlink():
            raise ValueError("symlink source directories are not supported")
        if base.exists():
            paths.update(p.relative_to(root).as_posix() for p in base.rglob("*.py"))
    paths.update(name for name in SOURCE_FILES if (root / name).exists())
    return {rel: sha256_file(safe_file(root, rel)) for rel in sorted(paths)}


def git_state(root: Path) -> dict:
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=root, text=True, timeout=10).strip()
    return {"head": git("rev-parse", "HEAD"), "status": git("status", "--porcelain=v1")}


def run_command(argv: list[str], cwd: Path, log_path: Path, timeout: float = 300) -> dict:
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    env = os.environ.copy()
    # Validation subprocesses must not inherit custody signing authority.
    env.pop("EUCLID_VALIDATION_CUSTODY_KEY_HEX", None)
    env.pop("EUCLID_VALIDATION_CUSTODY_SIGNER", None)
    env.pop("CUSTODY_SCRIPT_UNDER_TEST", None)
    env["PYTHONPATH"] = str(cwd)
    try:
        proc = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, timeout=timeout)
        output, code, timed_out = proc.stdout + proc.stderr, proc.returncode, False
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or b"") + (exc.stderr or b"") + b"\nVALIDATION TIMEOUT\n"
        code, timed_out = 124, True
    except OSError as exc:
        output, code, timed_out = str(exc).encode(), 127, False
    log_path.write_bytes(output)
    return {"argv": argv, "cwd": str(cwd), "started_at": started, "exit_code": code,
            "timed_out": timed_out, "timeout_seconds": timeout,
            "log_path": log_path.relative_to(cwd).as_posix(),
            "log_sha256": sha256_file(log_path),
            "output_tail": output[-1000:].decode("utf-8", errors="replace")}


def sign_artifact(payload: dict, key: bytes, signer: str) -> dict:
    validate_key(key)
    if not isinstance(signer, str) or not signer.strip():
        raise ValueError("local custodian identifier is required")
    artifact = {"payload": payload, "custody": {"schema": SCHEMA,
                "signature_scheme": "HMAC-SHA256", "signer_identity": signer,
                "key_fingerprint": hashlib.sha256(key).hexdigest(), "scope": SCOPE}}
    artifact["custody"]["signature"] = hmac.new(key, canonical(artifact), hashlib.sha256).hexdigest()
    return artifact


def verify_artifact(artifact: dict, key: bytes, root: Path) -> bool:
    """Verify HMAC AND present source/log bytes; passing checks remain a separate claim."""
    try:
        validate_key(key)
        custody = dict(artifact["custody"])
        signature = custody.pop("signature")
        if custody.get("schema") != SCHEMA or custody.get("scope") != SCOPE:
            return False
        if custody.get("signature_scheme") != "HMAC-SHA256" or not custody.get("signer_identity"):
            return False
        if custody.get("key_fingerprint") != hashlib.sha256(key).hexdigest():
            return False
        unsigned = {"payload": artifact["payload"], "custody": custody}
        expected = hmac.new(key, canonical(unsigned), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return False
        payload = artifact["payload"]
        if payload["sha256"] != source_hashes(root):
            return False
        for cmd in payload["commands"]:
            if sha256_file(safe_file(root, cmd["log_path"])) != cmd["log_sha256"]:
                return False
        passed = bool(payload["commands"]) and payload["source_stable"] is True and all(
            type(c["exit_code"]) is int and c["exit_code"] == 0 and c["timed_out"] is False
            for c in payload["commands"]
        )
        return payload["all_commands_passed"] is passed
    except (ValueError, TypeError, KeyError, OSError):
        return False


def default_commands() -> list[list[str]]:
    return [
        [sys.executable, "-m", "pytest", "tests/frontier_agent", "-q",
         "--confcutdir=tests/frontier_agent", "--basetemp=.pytest_tmp", "-p", "no:cacheprovider"],
        [sys.executable, "-m", "unittest", "discover", "-s", "tests/validation_custody", "-v"],
        [sys.executable, "-m", "black", "--check", "--line-length", "100",
         "chronus/agent", "tests/frontier_agent", "tests/validation_custody",
         *[p for p in SOURCE_FILES if p.endswith(".py")]],
        [sys.executable, "-m", "compileall", "-q", "chronus/agent", "tests/frontier_agent",
         "tests/validation_custody", "Intelligence/registry.py",
         *[p for p in SOURCE_FILES if p.endswith(".py")]],
        [sys.executable, "scripts/claim_guard_linter.py", "docs"],
        [sys.executable, "scripts/assert_production_drift_gate.py"],
    ]


def generate_custody_artifact(*, root: Path = _ROOT, commands=None, timeout: float = 300) -> Path:
    key, signer = credentials()  # Refuse before commands or artifact mutation.
    root = root.resolve()
    before, hashes = git_state(root), source_hashes(root)
    target = root / "docs" / "euclid_frontier_local_validation.json"
    if target.is_symlink() or target.parent.is_symlink():
        raise ValueError("symlink publication is refused")
    target.parent.mkdir(exist_ok=True)
    log_base = root / "evidence" / "validation_custody"
    if log_base.is_symlink() or log_base.parent.is_symlink():
        raise ValueError("symlink logs are refused")
    log_base.mkdir(parents=True, exist_ok=True)
    log_dir = Path(tempfile.mkdtemp(prefix="run-", dir=log_base))
    results = [run_command(cmd, root, log_dir / f"{i:03d}.log", timeout)
               for i, cmd in enumerate(default_commands() if commands is None else commands)]
    after_hashes, after = source_hashes(root), git_state(root)
    stable = hashes == after_hashes and before["head"] == after["head"]
    payload = {"task": "EUCLID-FRONTIER-REMEDIATION-20261014",
               "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
               "environment": {"python": sys.version, "platform": platform.platform(),
                               "git_before": before, "git_after": after},
               "source_stable": stable, "commands": results, "sha256": hashes,
               "all_commands_passed": bool(results) and stable and all(r["exit_code"] == 0 for r in results),
               "limits": ["local shared-key custody, not independent assurance",
                          "source coverage is explicit; no whole-repository coverage claim",
                          "timeout bounds direct child only; not OS/process isolation",
                          "commands execute locally; no automatic merge/release authority"]}
    signed = sign_artifact(payload, key, signer)
    fd, temp = tempfile.mkstemp(prefix=".custody-", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(signed, stream, indent=2, sort_keys=True)
            stream.write("\n")
        os.replace(temp, target)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", type=Path)
    parser.add_argument("--timeout", type=float, default=300)
    args = parser.parse_args()
    try:
        if args.verify:
            key, _ = credentials()
            artifact = json.loads(args.verify.read_text(encoding="utf-8"))
            ok = verify_artifact(artifact, key, _ROOT)
            print("Local custody verified" if ok else "Local custody verification FAILED")
            return 0 if ok else 1
        target = generate_custody_artifact(timeout=args.timeout)
        artifact = json.loads(target.read_text())
        passed = artifact["payload"]["all_commands_passed"]
        print(f"Local custody recorded: {target}; validation {'PASS' if passed else 'FAIL'}")
        return 0 if passed else 1
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print(f"Custody refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
