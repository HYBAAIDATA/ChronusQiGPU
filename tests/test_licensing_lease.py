"""Offline Ed25519 lease verifier: format, failure modes and absence of network access.

Self-contained on purpose: the partner build workflow copies this file out of
the source tree and runs it against the installed (compiled) wheel.
"""

import ast
import base64
import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import textwrap
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

import chronus.licensing as licensing
from chronus.licensing import (
    CapabilityNotLicensed,
    ClockRollback,
    DmiProductUuidProvider,
    FileProvider,
    HardwareMismatch,
    LeaseError,
    LeaseExpired,
    LeaseNotYetValid,
    LeaseRevoked,
    LeaseRollback,
    MachineIdProvider,
    MalformedLease,
    SignatureInvalid,
    TrustStore,
    UnknownKey,
    canonical_bytes,
    collect_fingerprints,
    fingerprint,
    load_trust_store,
    loads_strict,
    verify_lease,
    verify_revocations,
)
import pytest

pytestmark = pytest.mark.real

NOW = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
KID = "hyba-test-2026"
FP_A = fingerprint("test-id", b"value-a")
FP_B = fingerprint("test-id", b"value-b")
FP_C = fingerprint("test-id", b"value-c")
FORBIDDEN_IMPORTS = {"socket", "ssl", "urllib", "http", "requests", "httpx"}


def _raises(expected, func, *args, **kwargs):
    try:
        func(*args, **kwargs)
    except expected as exc:
        return exc
    raise AssertionError(f"{expected.__name__} was not raised")


def _keypair():
    private_key = Ed25519PrivateKey.generate()
    raw = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return private_key, base64.b64encode(raw).decode("ascii")


PRIVATE_KEY, PUBLIC_KEY = _keypair()
TRUST = {KID: PUBLIC_KEY}


def _lease(**changes):
    lease = {
        "schema": "hyba.lease/1",
        "lease_id": "lease-0001",
        "serial": 1,
        "licensee": {"id": "participant-01", "name": "Evaluation participant"},
        "product": "chronus",
        "capabilities": ["capability.alpha", "capability.beta"],
        "not_before": "2026-01-01T00:00:00Z",
        "not_after": "2027-01-01T00:00:00Z",
        "issued_at": "2025-12-15T00:00:00Z",
        "binding": {"policy": "all", "fingerprints": [FP_A, FP_B]},
    }
    lease.update(changes)
    return lease


def _sign(document, member="lease", private_key=PRIVATE_KEY, kid=KID):
    signature = private_key.sign(canonical_bytes(document))
    return {"alg": "Ed25519", "kid": kid, member: document, "signature": base64.b64encode(signature).decode("ascii")}


def _verify(envelope, **kwargs):
    kwargs.setdefault("trust_store", TRUST)
    if "providers" not in kwargs:
        kwargs.setdefault("fingerprints", [FP_A, FP_B])
    kwargs.setdefault("now", NOW)
    return verify_lease(envelope, **kwargs)


def _revocations(*lease_ids, issued_at="2026-05-01T00:00:00Z", private_key=PRIVATE_KEY, kid=KID):
    document = {"schema": "hyba.revocations/1", "issued_at": issued_at, "lease_ids": list(lease_ids)}
    return _sign(document, "revocations", private_key, kid)


def test_valid_lease_verifies_and_exposes_entitlements():
    envelope = _sign(_lease())
    lease = _verify(json.dumps(envelope).encode("utf-8"))
    assert lease.lease_id == "lease-0001"
    assert lease.serial == 1
    assert lease.licensee_id == "participant-01"
    assert lease.product == "chronus"
    assert lease.capabilities == frozenset({"capability.alpha", "capability.beta"})
    assert lease.not_after == datetime(2027, 1, 1, tzinfo=timezone.utc)
    assert lease.kid == KID
    assert lease.verified_at == NOW
    assert lease.lease_sha256 == hashlib.sha256(canonical_bytes(_lease())).hexdigest()
    assert lease.as_dict()["capabilities"] == ["capability.alpha", "capability.beta"]
    assert FP_A not in json.dumps(lease.as_dict())
    _raises(AttributeError, setattr, lease, "serial", 99)


def test_tampered_field_breaks_the_signature():
    envelope = _sign(_lease())
    envelope["lease"]["capabilities"] = ["capability.alpha", "capability.beta", "capability.gamma"]
    _raises(SignatureInvalid, _verify, envelope)
    envelope = _sign(_lease())
    envelope["lease"]["not_after"] = "2030-01-01T00:00:00Z"
    _raises(SignatureInvalid, _verify, envelope)


def test_signature_from_another_key_is_rejected():
    other_key, _ = _keypair()
    _raises(SignatureInvalid, _verify, _sign(_lease(), private_key=other_key))


def test_unknown_kid_is_rejected():
    _raises(UnknownKey, _verify, _sign(_lease(), kid="hyba-unknown-kid"))


def test_empty_trust_store_fails_closed():
    envelope = _sign(_lease())
    assert "empty" in str(_raises(UnknownKey, _verify, envelope, trust_store={}))
    _raises(UnknownKey, _verify, envelope, trust_store=TrustStore())
    _raises(UnknownKey, lambda: _verify(envelope, trust_store=load_trust_store()))
    package_dir = Path(licensing.__file__).resolve().parent
    if (package_dir.parents[2] / "pyproject.toml").is_file():
        # Source checkout: the committed store must stay empty (keys are embedded at build time).
        committed = json.loads((package_dir / "trust_store.json").read_text(encoding="utf-8"))
        assert committed == {"schema": "hyba.trust-store/1", "keys": {}}
        assert len(load_trust_store()) == 0


def test_trust_store_files_are_strict():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory, "trust_store.json")
        path.write_text(json.dumps({"schema": "hyba.trust-store/1", "keys": TRUST}))
        store = load_trust_store(path)
        assert store.kids == (KID,)
        assert _verify(_sign(_lease()), trust_store=store).kid == KID
        path.write_text(json.dumps({"schema": "hyba.trust-store/1", "keys": {KID: base64.b64encode(b"short").decode()}}))
        _raises(UnknownKey, load_trust_store, path)
        path.write_text('{"schema": "hyba.trust-store/1", "keys": {}, "keys": {}}')
        _raises(UnknownKey, load_trust_store, path)
        _raises(UnknownKey, load_trust_store, Path(directory, "missing.json"))


def test_expired_and_not_yet_valid_leases_are_rejected():
    envelope = _sign(_lease())
    not_after = datetime(2027, 1, 1, tzinfo=timezone.utc)
    not_before = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert _verify(envelope, now=not_after + timedelta(seconds=299)).lease_id == "lease-0001"
    _raises(LeaseExpired, _verify, envelope, now=not_after + timedelta(seconds=300))
    _raises(LeaseExpired, _verify, envelope, now=not_after, clock_skew_seconds=0)
    assert _verify(envelope, now=not_before - timedelta(seconds=300)).lease_id == "lease-0001"
    _raises(LeaseNotYetValid, _verify, envelope, now=not_before - timedelta(seconds=301))
    _raises(LeaseNotYetValid, _verify, envelope, now=not_before - timedelta(seconds=1), clock_skew_seconds=0)


def test_binding_policy_all():
    envelope = _sign(_lease(binding={"policy": "all", "fingerprints": [FP_A, FP_B]}))
    assert _verify(envelope, fingerprints=[FP_A, FP_B, FP_C]).binding_policy == "all"
    _raises(HardwareMismatch, _verify, envelope, fingerprints=[FP_A])
    _raises(HardwareMismatch, _verify, envelope, fingerprints=[])


def test_binding_policy_any():
    envelope = _sign(_lease(binding={"policy": "any", "fingerprints": [FP_A, FP_B]}))
    assert _verify(envelope, fingerprints=[FP_B]).binding_policy == "any"
    _raises(HardwareMismatch, _verify, envelope, fingerprints=[FP_C])


def test_binding_policy_threshold():
    binding = {"policy": "threshold", "threshold": 2, "fingerprints": [FP_A, FP_B, FP_C]}
    envelope = _sign(_lease(binding=binding))
    assert _verify(envelope, fingerprints=[FP_A, FP_C]).binding_policy == "threshold"
    _raises(HardwareMismatch, _verify, envelope, fingerprints=[FP_C])
    for bad in (0, 4, True, "2"):
        _raises(MalformedLease, _verify, _sign(_lease(binding=dict(binding, threshold=bad))))
    _raises(MalformedLease, _verify, _sign(_lease(binding={"policy": "any", "threshold": 1, "fingerprints": [FP_A]})))
    _raises(MalformedLease, _verify, _sign(_lease(binding={"policy": "most", "fingerprints": [FP_A]})))


def test_providers_hash_identifiers_and_skip_unavailable_ones():
    with tempfile.TemporaryDirectory() as directory:
        machine_id = Path(directory, "machine-id")
        machine_id.write_text("0123456789ABCDEF0123456789abcdef\n")
        gpus = Path(directory, "gpu-uuids")
        gpus.write_text("GPU-2\r\nGPU-1\n\nGPU-2\n")
        providers = [
            MachineIdProvider(machine_id),
            DmiProductUuidProvider(Path(directory, "unreadable-product-uuid")),
            FileProvider("gpu-uuids", gpus, sort_lines=True),
        ]
        expected_machine = "sha256:" + hashlib.sha256(
            b"hyba.lease.fp/1|machine-id|0123456789abcdef0123456789abcdef"
        ).hexdigest()
        expected_gpus = fingerprint("gpu-uuids", b"GPU-1\nGPU-2")
        assert collect_fingerprints(providers) == frozenset({expected_machine, expected_gpus})
        envelope = _sign(_lease(binding={"policy": "all", "fingerprints": [expected_machine, expected_gpus]}))
        assert _verify(envelope, providers=providers).lease_id == "lease-0001"
        machine_id.write_text("00000000000000000000000000000000\n")
        assert MachineIdProvider(machine_id).read() is None
        _raises(HardwareMismatch, _verify, envelope, providers=providers)
    _raises(ValueError, FileProvider, "Bad|Name", "/nonexistent")
    _raises(TypeError, _verify, _sign(_lease()), fingerprints=[FP_A], providers=[])


def test_revoked_lease_is_rejected():
    envelope = _sign(_lease())
    assert _verify(envelope, revocations=_revocations("lease-other")).lease_id == "lease-0001"
    _raises(LeaseRevoked, _verify, envelope, revocations=_revocations("lease-0001"))
    other_key, _ = _keypair()
    _raises(SignatureInvalid, _verify, envelope, revocations=_revocations("lease-0001", private_key=other_key))
    _raises(UnknownKey, _verify, envelope, revocations=_revocations("lease-0001", kid="hyba-unknown-kid"))
    tampered = _revocations("lease-0001")
    tampered["revocations"]["lease_ids"] = []
    _raises(SignatureInvalid, _verify, envelope, revocations=tampered)
    listed = verify_revocations(_revocations("lease-0001", "lease-0002"), trust_store=TRUST)
    assert "lease-0002" in listed
    lease_signature = _sign(_lease())
    _raises(MalformedLease, verify_revocations, lease_signature, trust_store=TRUST)


def test_revocations_are_remembered_in_the_state_file():
    with tempfile.TemporaryDirectory() as directory:
        state_path = Path(directory, "lease-state.json")
        envelope = _sign(_lease())
        _raises(LeaseRevoked, _verify, envelope, revocations=_revocations("lease-0001"), state_path=state_path)
        _raises(LeaseRevoked, _verify, envelope, state_path=state_path)


def test_serial_rollback_is_detected():
    with tempfile.TemporaryDirectory() as directory:
        state_path = Path(directory, "lease-state.json")
        newer = _sign(_lease(lease_id="lease-0002", serial=2))
        older = _sign(_lease(lease_id="lease-0001", serial=1))
        assert _verify(newer, state_path=state_path).serial == 2
        assert _verify(newer, state_path=state_path, now=NOW + timedelta(hours=1)).serial == 2
        _raises(LeaseRollback, _verify, older, state_path=state_path, now=NOW + timedelta(hours=2))
        reused = _sign(_lease(lease_id="lease-0003", serial=2))
        _raises(LeaseRollback, _verify, reused, state_path=state_path, now=NOW + timedelta(hours=2))
        other_licensee = _sign(_lease(lease_id="lease-0100", licensee={"id": "participant-02", "name": "Second"}))
        assert _verify(other_licensee, state_path=state_path, now=NOW + timedelta(hours=2)).serial == 1


def test_clock_rollback_is_detected():
    with tempfile.TemporaryDirectory() as directory:
        state_path = Path(directory, "lease-state.json")
        envelope = _sign(_lease())
        _verify(envelope, state_path=state_path)
        assert _verify(envelope, state_path=state_path, now=NOW - timedelta(seconds=300)).serial == 1
        _raises(ClockRollback, _verify, envelope, state_path=state_path, now=NOW - timedelta(seconds=301))
    issued_later = _sign(_lease(issued_at="2026-07-01T00:00:00Z"))
    _raises(ClockRollback, _verify, issued_later)
    later_list = _revocations(issued_at="2026-08-01T00:00:00Z")
    _raises(ClockRollback, _verify, _sign(_lease()), revocations=later_list)


def test_damaged_state_file_fails_closed():
    with tempfile.TemporaryDirectory() as directory:
        state_path = Path(directory, "lease-state.json")
        envelope = _sign(_lease(serial=5))
        _verify(envelope, state_path=state_path)
        state = json.loads(state_path.read_text())
        assert state["licensees"]["participant-01"]["serial"] == 5
        state["licensees"]["participant-01"]["serial"] = 1
        state_path.write_text(json.dumps(state))
        _raises(LeaseRollback, _verify, envelope, state_path=state_path)
        state_path.write_text("not json")
        _raises(LeaseRollback, _verify, envelope, state_path=state_path)
        assert isinstance(_raises(LeaseError, _verify, envelope, state_path=state_path), LeaseRollback)


def test_capability_gate():
    lease = _verify(_sign(_lease()))
    lease.require("capability.alpha", now=NOW)
    assert lease.has("capability.beta")
    assert not lease.has("capability.gamma")
    _raises(CapabilityNotLicensed, lease.require, "capability.gamma", now=NOW)
    _raises(LeaseExpired, lease.require, "capability.alpha", now=datetime(2027, 1, 2, tzinfo=timezone.utc))


def test_canonical_bytes_are_stable():
    document = {"b": 1, "a": [True, None, "\u00e9", {"z": "", "y": -7}], "c": "x"}
    expected = '{"a":[true,null,"\u00e9",{"y":-7,"z":""}],"b":1,"c":"x"}'.encode("utf-8")
    assert canonical_bytes(document) == expected
    assert canonical_bytes(dict(reversed(list(document.items())))) == expected
    assert canonical_bytes(loads_strict(expected)) == expected
    assert canonical_bytes(_lease()) == canonical_bytes(json.loads(json.dumps(_lease(), indent=4)))
    _raises(MalformedLease, canonical_bytes, {"n": 1 << 53})


def test_floats_nan_duplicate_and_non_string_keys_are_rejected():
    for value in ({"x": 1.5}, {"x": float("nan")}, [float("inf")], {1: "x"}, {"x": b"bytes"}):
        _raises(MalformedLease, canonical_bytes, value)
    for text in ('{"x": 1.0}', '{"x": 1e3}', '{"x": NaN}', '{"x": -Infinity}', '{"x": 1, "x": 2}', b"\xff"):
        _raises(MalformedLease, loads_strict, text)
    envelope = json.dumps(_sign(_lease()))
    _raises(MalformedLease, _verify, envelope.replace('"serial": 1', '"serial": 1.0'))
    duplicated = envelope.replace('"serial": 1', '"serial": 1, "serial": 1')
    _raises(MalformedLease, _verify, duplicated)


def test_malformed_envelopes_and_leases_are_rejected():
    envelope = _sign(_lease())
    for broken in (
        {key: value for key, value in envelope.items() if key != "kid"},
        dict(envelope, extra="member"),
        dict(envelope, alg="EdDSA"),
        dict(envelope, signature="not base64!"),
        dict(envelope, signature=base64.b64encode(b"\x00" * 63).decode("ascii")),
        [envelope],
    ):
        _raises(MalformedLease, _verify, broken)
    for changes in (
        {"schema": "hyba.lease/2"},
        {"serial": 0},
        {"serial": True},
        {"lease_id": ""},
        {"capabilities": []},
        {"capabilities": ["capability.alpha", "capability.alpha"]},
        {"not_after": "2027-01-01T00:00:00+00:00"},
        {"not_after": "2027-02-30T00:00:00Z"},
        {"not_before": "2027-01-01T00:00:00Z"},
        {"binding": {"policy": "all", "fingerprints": ["sha256:" + "A" * 64]}},
        {"binding": {"policy": "all", "fingerprints": [FP_A, FP_A]}},
        {"licensee": {"id": "participant-01"}},
        {"unexpected": "member"},
    ):
        _raises(MalformedLease, _verify, _sign(_lease(**changes)))


def test_verification_does_not_touch_the_network():
    originals = (socket.socket, socket.create_connection, socket.getaddrinfo)

    def refuse(*args, **kwargs):
        raise AssertionError("network access attempted during lease verification")

    socket.socket = refuse
    socket.create_connection = refuse
    socket.getaddrinfo = refuse
    try:
        with tempfile.TemporaryDirectory() as directory:
            lease = _verify(
                _sign(_lease()),
                revocations=_revocations("lease-other"),
                state_path=Path(directory, "lease-state.json"),
            )
    finally:
        socket.socket, socket.create_connection, socket.getaddrinfo = originals
    assert lease.lease_id == "lease-0001"


def test_package_source_has_no_network_imports():
    package_dir = Path(licensing.__file__).resolve().parent
    sources = sorted(package_dir.glob("*.py"))
    assert sources, "no Python source found for chronus.licensing"
    for path in sources:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module]
            elif isinstance(node, ast.Call) and getattr(node.func, "id", getattr(node.func, "attr", "")) in {
                "__import__",
                "import_module",
            }:
                raise AssertionError(f"{path.name}:{node.lineno} performs a dynamic import")
            for name in names:
                assert name.split(".")[0] not in FORBIDDEN_IMPORTS, f"{path.name}:{node.lineno} imports {name}"


def test_importing_and_verifying_loads_no_network_module():
    # Covers compiled installs, where the module sources are not shipped.
    package_parent = Path(licensing.__file__).resolve().parents[2]
    code = textwrap.dedent(
        """
        import base64, sys
        from datetime import datetime, timezone
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
        before = set(sys.modules)
        import chronus.licensing as lic
        key = Ed25519PrivateKey.generate()
        raw = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        fp = lic.fingerprint("test-id", b"value")
        lease = {"schema": "hyba.lease/1", "lease_id": "l-1", "serial": 1,
                 "licensee": {"id": "p-1", "name": "Participant"}, "product": "chronus",
                 "capabilities": ["capability.alpha"], "not_before": "2026-01-01T00:00:00Z",
                 "not_after": "2027-01-01T00:00:00Z", "issued_at": "2025-12-01T00:00:00Z",
                 "binding": {"policy": "all", "fingerprints": [fp]}}
        envelope = {"alg": "Ed25519", "kid": "k", "lease": lease,
                    "signature": base64.b64encode(key.sign(lic.canonical_bytes(lease))).decode()}
        lic.verify_lease(envelope, trust_store={"k": raw}, fingerprints=[fp],
                         now=datetime(2026, 6, 1, tzinfo=timezone.utc))
        network = {"socket", "_socket", "ssl", "_ssl", "http.client", "urllib.request", "requests", "httpx"}
        print(",".join(sorted(m for m in set(sys.modules) - before if m in network or m.split(".")[0] in {"requests", "httpx"})))
        """
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(package_parent), env.get("PYTHONPATH")]))
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, timeout=120)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "", f"network modules loaded: {result.stdout.strip()}"
