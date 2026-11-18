"""Vendor-side lease tooling: key-path refusal, schema checks and verifiable output."""

import base64
import contextlib
import hashlib
import io
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "licensing"))

import issue_lease  # noqa: E402
import issue_revocations  # noqa: E402
from chronus.licensing import fingerprint, verify_lease, verify_revocations  # noqa: E402
import pytest

pytestmark = pytest.mark.real

KID = "hyba-tooling-test"
FP = fingerprint("test-id", b"tooling")


def _write_key(directory, mode=0o600):
    private_key = Ed25519PrivateKey.generate()
    path = Path(directory, "signing-key.pem")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with open(descriptor, "wb") as handle:
        handle.write(private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()))
    os.chmod(path, mode)
    raw = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return path, {KID: base64.b64encode(raw).decode("ascii")}


def _lease_file(directory, **changes):
    lease = {
        "schema": "hyba.lease/1",
        "lease_id": "lease-tooling-1",
        "serial": 3,
        "licensee": {"id": "participant-01", "name": "Evaluation participant"},
        "product": "chronus",
        "capabilities": ["capability.alpha"],
        "not_before": "2026-01-01T00:00:00Z",
        "not_after": "2027-01-01T00:00:00Z",
        "issued_at": "2025-12-20T00:00:00Z",
        "binding": {"policy": "any", "fingerprints": [FP]},
    }
    lease.update(changes)
    path = Path(directory, "lease.json")
    path.write_text(json.dumps(lease, indent=2), encoding="utf-8")
    return path


def _run(main, argv):
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        status = main(argv)
    return status, stdout.getvalue(), stderr.getvalue()


def test_private_key_inside_the_repository_is_refused():
    with tempfile.TemporaryDirectory() as directory:
        out = Path(directory, "signed.json")
        argv = ["--lease", str(_lease_file(directory)), "--key", str(ROOT / "scripts" / "licensing" / "signing-key.pem")]
        status, _, stderr = _run(issue_lease.main, argv + ["--kid", KID, "--out", str(out)])
        assert status == 2
        assert "inside the repository" in stderr
        assert not out.exists()
        status, _, stderr = _run(
            issue_revocations.main,
            ["--lease-id", "lease-1", "--key", str(ROOT / "key.pem"), "--kid", KID, "--out", str(out)],
        )
        assert status == 2 and "inside the repository" in stderr


def test_issued_lease_verifies_and_its_digest_is_printed():
    with tempfile.TemporaryDirectory() as directory:
        key, trust = _write_key(directory)
        out = Path(directory, "participant-01.lease.json")
        argv = ["--lease", str(_lease_file(directory)), "--key", str(key), "--kid", KID, "--out", str(out)]
        status, stdout, stderr = _run(issue_lease.main, argv)
        assert status == 0, stderr
        assert stdout.strip() == f"sha256 {hashlib.sha256(out.read_bytes()).hexdigest()}  {out}"
        lease = verify_lease(
            out.read_bytes(), trust_store=trust, fingerprints=[FP], now=datetime(2026, 3, 1, tzinfo=timezone.utc)
        )
        assert lease.serial == 3 and lease.kid == KID
        status, _, stderr = _run(issue_lease.main, argv)
        assert status == 2 and "already exists" in stderr
        assert _run(issue_lease.main, argv + ["--force"])[0] == 0


def test_invalid_leases_and_unsafe_keys_are_refused():
    with tempfile.TemporaryDirectory() as directory:
        key, _ = _write_key(directory)
        out = Path(directory, "signed.json")
        for changes in ({"serial": 1.5}, {"capabilities": []}, {"issued_at": "2027-01-01T00:00:00Z"}):
            argv = ["--lease", str(_lease_file(directory, **changes)), "--key", str(key), "--kid", KID, "--out", str(out)]
            assert _run(issue_lease.main, argv)[0] == 2
            assert not out.exists()
        bad_kid = ["--lease", str(_lease_file(directory)), "--key", str(key), "--kid", "bad kid", "--out", str(out)]
        assert _run(issue_lease.main, bad_kid)[0] == 2
        if os.name == "posix":
            os.chmod(key, 0o644)
            argv = ["--lease", str(_lease_file(directory)), "--key", str(key), "--kid", KID, "--out", str(out)]
            status, _, stderr = _run(issue_lease.main, argv)
            assert status == 2 and "chmod 600" in stderr


def test_issued_revocation_list_verifies():
    with tempfile.TemporaryDirectory() as directory:
        key, trust = _write_key(directory)
        ids_file = Path(directory, "revoked.txt")
        ids_file.write_text("# revoked so far\nlease-0002\n\nlease-0001  # replaced\n", encoding="utf-8")
        out = Path(directory, "revocations.json")
        argv = [
            "--lease-id", "lease-0003", "--ids-file", str(ids_file), "--issued-at", "2026-05-01T00:00:00Z",
            "--key", str(key), "--kid", KID, "--out", str(out),
        ]
        status, stdout, stderr = _run(issue_revocations.main, argv)
        assert status == 0, stderr
        assert stdout.strip() == f"sha256 {hashlib.sha256(out.read_bytes()).hexdigest()}  {out}"
        listed = verify_revocations(out.read_bytes(), trust_store=trust)
        assert listed.lease_ids == frozenset({"lease-0001", "lease-0002", "lease-0003"})
        assert json.loads(out.read_bytes())["revocations"]["lease_ids"] == ["lease-0001", "lease-0002", "lease-0003"]
