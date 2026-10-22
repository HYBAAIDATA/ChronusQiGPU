"""Private-key local validation custody, not independent release attestation.

Commands really execute. Failed runs remain failed; credentials never enter child
processes. Source manifests, command logs and signer metadata are authenticated.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import hmac
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import uuid

_ROOT = Path(__file__).resolve().parent.parent
_SCHEMA = "euclid.validation-custody/2"
_PUBLIC_HISTORICAL_KEY = b"euclid-validation-custody-salt-20261014"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_key(key):
    if not isinstance(key, bytes) or len(key) < 32 or key == _PUBLIC_HISTORICAL_KEY:
        raise ValueError("private validation signing key of at least 32 bytes required")
    return key


def credentials():
    try:
        key = bytes.fromhex(os.environ.get("EUCLID_VALIDATION_CUSTODY_KEY_HEX", ""))
    except ValueError as exc:
        raise ValueError("invalid validation signing key encoding") from exc
    validate_key(key)
    signer = os.environ.get("EUCLID_VALIDATION_CUSTODY_SIGNER", "").strip()
    if not signer:
        raise ValueError("explicit local signer identity required")
    return key, signer


def safe_path(root, relative):
    root = Path(root)
    rel = Path(relative)
    if root.is_symlink() or rel.is_absolute() or not rel.parts or ".." in rel.parts:
        raise ValueError("unsafe custody path")
    path = root
    for part in rel.parts:
        path /= part
        if path.is_symlink():
            raise ValueError("symlink custody paths are not allowed")
    path.resolve().relative_to(root.resolve())
    return path


def source_hashes(root):
    root = Path(root)
    if root.is_symlink():
        raise ValueError("symlink source root")
    found = {}
    for folder in ("Intelligence", "chronus/agent", "tests/frontier_agent", "scripts"):
        base = safe_path(root, folder)
        if not base.exists():
            continue
        for directory, dirs, names in os.walk(base, followlinks=False):
            dirs[:] = [name for name in dirs if name not in {"__pycache__", ".pytest_cache"}]
            for name in dirs + names:
                p = Path(directory) / name
                if p.is_symlink():
                    raise ValueError("symlink in custody source inventory")
            for name in names:
                p = Path(directory) / name
                if p.suffix == ".py":
                    found[p.relative_to(root).as_posix()] = sha256_file(p)
    return dict(sorted(found.items()))


def run_command(argv, cwd, log_path, timeout=120):
    cwd = Path(cwd)
    log_path = safe_path(cwd, Path(log_path).relative_to(cwd))
    log_path.parent.mkdir(parents=True, exist_ok=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith("EUCLID_VALIDATION_CUSTODY_")}
    env["PYTHONPATH"] = str(cwd)
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    timed_out = False
    with log_path.open("xb") as log:
        try:
            process = subprocess.Popen(argv, cwd=cwd, env=env, stdout=log,
                                       stderr=subprocess.STDOUT, start_new_session=True)
        except OSError as exc:
            code = 127
            log.write(("EXECUTION_ERROR: " + type(exc).__name__ + "\n").encode())
        else:
            try:
                process.wait(timeout=timeout)
                code = process.returncode
            except subprocess.TimeoutExpired:
                timed_out = True
                if os.name == "posix":
                    os.killpg(process.pid, signal.SIGKILL)
                else:
                    process.kill()
                process.wait()
                code = 124
                log.write(b"\nTIMEOUT: command exceeded the configured bound\n")
    return {"argv": list(argv), "cwd": str(cwd), "started_at": started,
            "exit_code": code, "timed_out": timed_out,
            "log_path": log_path.relative_to(cwd).as_posix(),
            "log_sha256": sha256_file(log_path)}


def sign_artifact(payload, key, signer):
    validate_key(key)
    if not isinstance(signer, str) or not signer.strip():
        raise ValueError("signer identity required")
    custody = {"signature_scheme": "HMAC-SHA256", "signer_identity": signer,
               "signed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
               "assurance": "operator-local-self-custody-not-independent-attestation"}
    signature = hmac.new(key, canonical({"payload": payload, "custody": custody}), hashlib.sha256).hexdigest()
    return {"payload": payload, "custody": {**custody, "signature": signature}}


def verify_artifact(artifact, key, root):
    try:
        validate_key(key)
        payload = artifact["payload"]
        custody = dict(artifact["custody"])
        signature = custody.pop("signature")
        if custody["signature_scheme"] != "HMAC-SHA256" or not custody["signer_identity"]:
            return False
        expected = hmac.new(key, canonical({"payload": payload, "custody": custody}), hashlib.sha256).hexdigest()
        if not isinstance(signature, str) or not hmac.compare_digest(expected, signature):
            return False
        if payload["schema"] != _SCHEMA or payload["source_stable"] is not True:
            return False
        if not payload["sha256"] or payload["sha256"] != source_hashes(root):
            return False
        commands = payload["commands"]
        if not isinstance(commands, list):
            return False
        for command in commands:
            if type(command["exit_code"]) is not int or type(command["timed_out"]) is not bool:
                return False
            log = safe_path(root, command["log_path"])
            if sha256_file(log) != command["log_sha256"]:
                return False
        success = bool(commands) and all(c["exit_code"] == 0 and not c["timed_out"] for c in commands)
        return type(payload["all_commands_passed"]) is bool and payload["all_commands_passed"] == success
    except (ValueError, TypeError, KeyError, OSError, AttributeError):
        return False


def default_commands():
    return [
        [sys.executable, "-m", "pytest", "tests/frontier_agent", "-q", "--confcutdir=tests/frontier_agent", "-p", "no:cacheprovider"],
        [sys.executable, "-m", "black", "--check", "--line-length", "100", "chronus/agent", "tests/frontier_agent"],
        [sys.executable, "-m", "compileall", "-q", "chronus/agent", "tests/frontier_agent", "Intelligence/registry.py"],
        [sys.executable, "scripts/claim_guard_linter.py", "docs"],
        [sys.executable, "scripts/assert_production_drift_gate.py"],
    ]


def generate_custody_artifact(*, root=None, commands=None, timeout=120):
    key, signer = credentials()  # Before writes or subprocesses.
    root = Path(_ROOT if root is None else root)
    target = safe_path(root, "docs/euclid_frontier_local_validation.json")
    before = source_hashes(root)
    results = []
    run_id = uuid.uuid4().hex
    for index, command in enumerate(default_commands() if commands is None else commands):
        log = safe_path(root, f"evidence/validation-custody/{run_id}/{index}.log")
        results.append(run_command(command, root, log, timeout))
    stable = before == source_hashes(root)
    payload = {"schema": _SCHEMA, "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
               "sha256": before, "source_stable": stable, "commands": results,
               "all_commands_passed": stable and bool(results) and all(c["exit_code"] == 0 and not c["timed_out"] for c in results),
               "restrictions": ["no_merge", "no_release", "no_deployment", "no_mining", "no_provider_calls"]}
    artifact = sign_artifact(payload, key, signer)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=target.parent, prefix=".custody-", delete=False) as f:
            temp = Path(f.name)
            json.dump(artifact, f, sort_keys=True, indent=2)
            f.flush()
            os.fsync(f.fileno())
        safe_path(root, "docs/euclid_frontier_local_validation.json")
        os.replace(temp, target)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    try:
        key, _signer = credentials()
        if args.verify:
            return 0 if verify_artifact(json.loads(args.verify.read_text()), key, _ROOT) else 1
        target = generate_custody_artifact()
        return 0 if json.loads(target.read_text())["payload"]["all_commands_passed"] else 1
    except (ValueError, OSError) as exc:
        print(f"Validation custody refused: {type(exc).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
