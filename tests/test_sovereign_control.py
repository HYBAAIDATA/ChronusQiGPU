"""AL HARAS sovereign control plane: policy, decisions, enforcement, evidence.

Anything that installs the audit hook runs in a child process: PEP 578
hooks cannot be removed, so installing one in the pytest process would
bound every later test.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from al_haras.sovereign_control import (
    SovereignBoundaryDenied,
    SovereignConfigError,
    SovereignControlPlane,
    SovereignEgressDenied,
    install_from_env,
    load_policy,
    read_audit,
    verify_attestation,
    worker_argv,
)

ROOT = Path(__file__).resolve().parents[1]
KEY_HEX = "ab" * 32


def _env(tmp_path, **extra):
    env = {
        "HYBA_SOVEREIGN_MODE": "air_gapped",
        "HYBA_SOVEREIGN_AUDIT_PATH": str(tmp_path / "audit" / "sovereign.jsonl"),
        "HYBA_SOVEREIGN_ATTESTATION_KEY": KEY_HEX,
    }
    env.update(extra)
    return env


def _plane(tmp_path, **extra):
    return SovereignControlPlane(load_policy(_env(tmp_path, **extra)), role="test")


# -- policy -----------------------------------------------------------------


def test_connected_mode_installs_nothing():
    assert load_policy({}).mode == "connected"
    assert install_from_env({}) is None
    assert worker_argv("w.py", {}) == [sys.executable, "w.py"]


@pytest.mark.parametrize(
    "overrides, match",
    [
        ({"HYBA_SOVEREIGN_MODE": "offline"}, "expected one of"),
        ({"HYBA_SOVEREIGN_AUDIT_PATH": ""}, "AUDIT_PATH is required"),
        ({"HYBA_SOVEREIGN_AUDIT_PATH": "s3://bucket/audit.jsonl"}, "must be a local path"),
        ({"HYBA_SOVEREIGN_ATTESTATION_KEY": "short"}, "at least 32 bytes"),
        ({"HYBA_SOVEREIGN_EGRESS_ALLOW": "1.1.1.1:443"}, "cannot allow a global address"),
        ({"HYBA_SOVEREIGN_EGRESS_ALLOW": "10.0.0.0/8:99999"}, "bad port"),
        ({"PYTHIA_STORAGE_ROOT": "az://container/theseus"}, "remote location"),
        ({"HYBA_SOVEREIGN_STORAGE_ROOTS": "gs://bucket"}, "not a local path"),
    ],
)
def test_invalid_sovereign_configuration_refuses(tmp_path, overrides, match):
    with pytest.raises(SovereignConfigError, match=match):
        load_policy(_env(tmp_path, **overrides))


def test_private_mode_may_allow_a_public_address(tmp_path):
    policy = load_policy(_env(tmp_path, HYBA_SOVEREIGN_MODE="private",
                              HYBA_SOVEREIGN_EGRESS_ALLOW="1.1.1.1:443"))
    assert [rule.as_text() for rule in policy.rules] == ["1.1.1.1/32:443"]


def test_policy_digest_is_stable_and_key_free(tmp_path):
    a = load_policy(_env(tmp_path, HYBA_SOVEREIGN_EGRESS_ALLOW="10.0.0.0/8:3333"))
    b = load_policy(_env(tmp_path, HYBA_SOVEREIGN_EGRESS_ALLOW="10.0.0.0/8:3333"))
    assert a.digest == b.digest
    assert KEY_HEX not in json.dumps(a.as_public_dict())


def test_worker_argv_wraps_in_sovereign_mode(tmp_path):
    argv = worker_argv("worker.py", _env(tmp_path))
    assert argv == [sys.executable, "-m", "al_haras.sovereign_exec", "worker.py"]


# -- decisions --------------------------------------------------------------


def test_address_decisions(tmp_path):
    plane = _plane(tmp_path, HYBA_SOVEREIGN_EGRESS_ALLOW="10.0.0.0/8:3333,[fd00::5]:8443")
    assert plane.decide_address("127.0.0.1", 9)[0]
    assert plane.decide_address("::1", 9)[0]
    assert plane.decide_address("localhost", 9)[0]
    assert plane.decide_address("10.20.30.40", 3333)[0]
    assert not plane.decide_address("10.20.30.40", 3334)[0]
    assert plane.decide_address("fd00::5", 8443)[0]
    assert not plane.decide_address("1.1.1.1", 443)[0]
    assert not plane.decide_address("0.0.0.0", 80)[0]
    assert not plane.decide_address("pypi.org", 443)[0]


def test_denials_are_recorded_and_coalesced(tmp_path):
    plane = _plane(tmp_path)
    for _ in range(10):
        with pytest.raises(SovereignEgressDenied):
            plane.check_connect(2, ("1.1.1.1", 443))
    denied = [r["event"] for r in plane.audit.records if r["event"]["event"] == "denied"]
    # occurrences 1, 2, 3, 4 and 8 are written; the counter keeps all ten.
    assert [d["occurrence"] for d in denied] == [1, 2, 3, 4, 8]
    assert plane.denial_counts() == {"connect": 10}


def test_locations(tmp_path):
    root = tmp_path / "theseus"
    plane = _plane(tmp_path, HYBA_SOVEREIGN_STORAGE_ROOTS=str(root))
    assert plane.check_location(str(root / "g0001"), kind="storage")
    for uri in ("s3://b/k", "az://c/b", "gs://b/o", "https://data.example.com/x.csv"):
        with pytest.raises(SovereignBoundaryDenied):
            plane.check_location(uri, kind="ingestion")
    with pytest.raises(SovereignBoundaryDenied):
        plane.check_location(str(tmp_path / "elsewhere"), kind="storage")


def test_attestation_signature_and_anchor(tmp_path):
    plane = _plane(tmp_path)
    with pytest.raises(SovereignEgressDenied):
        plane.check_connect(2, ("8.8.8.8", 53))
    document = plane.attestation()
    key = bytes.fromhex(KEY_HEX)
    records = read_audit(tmp_path / "audit" / "sovereign.jsonl")
    assert verify_attestation(document, key, records)["valid"]
    assert not verify_attestation(document, b"x" * 32, records)["valid"]
    edited = json.loads(json.dumps(records))
    edited[1]["event"]["target"] = "10.0.0.1:53"
    verdict = verify_attestation(document, key, edited)
    assert not verdict["valid"] and verdict["first_broken_record"] == 1


# -- enforcement (child processes) -----------------------------------------


def _run(code, env, timeout=120):
    return subprocess.run(
        [sys.executable, "-c", code],
        env={**os.environ, "PYTHONPATH": str(ROOT), **env},
        cwd=str(ROOT), capture_output=True, text=True, timeout=timeout,
    )


ENFORCE = """
import asyncio, socket, urllib.request
from al_haras.sovereign_control import install_from_env, SovereignEgressDenied
install_from_env(role="test-child")
results = {}
def attempt(name, fn):
    try:
        fn(); results[name] = "allowed"
    except SovereignEgressDenied:
        results[name] = "denied"
    except OSError as exc:
        results[name] = "denied" if "sovereign" in str(exc) else "os-error:" + type(exc).__name__
attempt("tcp", lambda: socket.create_connection(("1.1.1.1", 443), timeout=3))
attempt("udp", lambda: socket.socket(socket.AF_INET, socket.SOCK_DGRAM).sendto(b"x", ("8.8.8.8", 53)))
attempt("dns", lambda: socket.getaddrinfo("pypi.org", 443))
attempt("urllib", lambda: urllib.request.urlopen("https://pypi.org/simple/", timeout=3))
async def go():
    await asyncio.open_connection("1.1.1.1", 80)
attempt("asyncio", lambda: asyncio.run(go()))
srv = socket.socket(); srv.bind(("127.0.0.1", 0)); srv.listen(1)
attempt("loopback", lambda: socket.create_connection(srv.getsockname(), timeout=3).close())
print(results)
"""


def test_air_gapped_process_refuses_real_egress(tmp_path):
    proc = _run(ENFORCE, _env(tmp_path))
    assert proc.returncode == 0, proc.stderr
    results = eval(proc.stdout.strip().splitlines()[-1])  # noqa: S307 - our own child's dict
    assert results == {
        "tcp": "denied", "udp": "denied", "dns": "denied",
        "urllib": "denied", "asyncio": "denied", "loopback": "allowed",
    }
    events = [r["event"]["event"] for r in read_audit(tmp_path / "audit" / "sovereign.jsonl")]
    assert events[:2] == ["control_plane_started", "hook_installed"]
    assert events.count("denied") >= 5


def test_entrypoint_refuses_invalid_sovereign_configuration(tmp_path):
    env = _env(tmp_path, HYBA_SOVEREIGN_ATTESTATION_KEY="")
    proc = subprocess.run(
        [sys.executable, "main.py"], env={**os.environ, **env}, cwd=str(ROOT),
        capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 78
    assert "sovereign configuration error" in proc.stderr


def test_sovereign_exec_bounds_the_worker(tmp_path):
    script = tmp_path / "worker.py"
    script.write_text(
        "import socket, sys\n"
        "try:\n"
        "    socket.create_connection(('1.1.1.1', 443), timeout=3)\n"
        "    sys.exit(3)\n"
        "except PermissionError:\n"
        "    print('denied', __name__)\n",
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, "-m", "al_haras.sovereign_exec", str(script)],
        env={**os.environ, "PYTHONPATH": str(ROOT), **_env(tmp_path)},
        cwd=str(ROOT), capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "denied __main__"
    roles = {r["event"].get("role") for r in read_audit(tmp_path / "audit" / "sovereign.jsonl")}
    assert "worker:worker.py" in roles


def test_proof_pack_end_to_end(tmp_path):
    out = tmp_path / "proof"
    proc = subprocess.run(
        [sys.executable, "scripts/sovereign_proof_pack.py", "--out", str(out), "--skip-network-probe"],
        env={**os.environ, "PYTHONPATH": str(ROOT), **_env(tmp_path)},
        cwd=str(ROOT), capture_output=True, text=True, timeout=300,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    results = json.loads((out / "results.json").read_text())
    assert results["passed"] and all(results["expectations"].values())
    for name in ("attestation.json", "audit.jsonl", "denied_events.json", "verification.json",
                 "tamper_tests.json", "summary.md"):
        assert (out / name).is_file()
    tampers = json.loads((out / "tamper_tests.json").read_text())
    assert len(tampers) == 5 and all(t["detected"] for t in tampers)


def test_offline_verify_cli_needs_only_the_key(tmp_path):
    plane = _plane(tmp_path)
    with pytest.raises(SovereignEgressDenied):
        plane.check_connect(2, ("1.1.1.1", 443))
    doc = tmp_path / "attestation.json"
    doc.write_text(json.dumps(plane.attestation()), encoding="utf-8")
    audit = tmp_path / "audit" / "sovereign.jsonl"
    key_file = tmp_path / "key"
    key_file.write_text(KEY_HEX + "\n", encoding="utf-8")
    base = [sys.executable, "-m", "al_haras.sovereign_control", "verify", str(doc), "--audit", str(audit)]
    clean = {k: v for k, v in os.environ.items() if not k.startswith("HYBA_SOVEREIGN")}
    clean["PYTHONPATH"] = str(ROOT)

    def run(*extra, env=clean):
        return subprocess.run(base + list(extra), env=env, cwd=str(ROOT),
                              capture_output=True, text=True, timeout=60)

    assert run().returncode == 78
    assert run("--key-file", str(key_file)).returncode == 0
    assert run(env={**clean, "HYBA_SOVEREIGN_ATTESTATION_KEY": KEY_HEX}).returncode == 0
    lines = audit.read_text(encoding="utf-8").splitlines()
    index = next(i for i, line in enumerate(lines) if '"denied"' in line)
    record = json.loads(lines[index])
    record["event"]["target"] = "10.0.0.1:443"
    lines[index] = json.dumps(record)
    audit.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tampered = run("--key-file", str(key_file))
    assert tampered.returncode == 1
    assert json.loads(tampered.stdout)["first_broken_record"] == index
