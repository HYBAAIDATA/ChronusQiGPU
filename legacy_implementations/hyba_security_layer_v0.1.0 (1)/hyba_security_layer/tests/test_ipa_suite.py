"""HYBA security layer - IPA suite: Invariants, Properties, Adversarials.

Mirrors the AL HARAS IPA coverage map (20 Jul 2026) against the rebuilt layer.
Every adversarial must FAIL CLOSED. No assertion is allowed to be shape-only:
a tamper detector that may miss tampering is not elevated.

Run:
    python3 tests/test_ipa_suite.py
Writes evidence/hyba_security_ipa_report.json
"""

from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hyba_security import aead, audit_chain, claims, production_guard, security_posture
from hyba_security.audit_chain import AuditChain
from hyba_security.legacy import legacy_xor_obfuscate

RESULTS: list[dict] = []


def check(layer: str, kind: str, name: str):
    def decorator(fn):
        try:
            fn()
            RESULTS.append({"layer": layer, "kind": kind, "name": name, "passed": True})
        except Exception as exc:  # noqa: BLE001
            RESULTS.append(
                {
                    "layer": layer,
                    "kind": kind,
                    "name": name,
                    "passed": False,
                    "error": f"{type(exc).__name__}: {exc}",
                    "trace": traceback.format_exc(limit=3),
                }
            )
        return fn

    return decorator


def flip_bit(blob: bytes, index: int) -> bytes:
    data = bytearray(blob)
    data[index] ^= 0x01
    return bytes(data)


KEY = b"unit-test-key-material-32-bytes!!"

# =====================================================================
# LAYER 1 - AEAD
# =====================================================================


@check("aead", "invariant", "round-trip empty and non-empty")
def _():
    for payload in (b"", b"x", b"probe" * 200):
        assert aead.open_sealed(aead.seal(payload, KEY), KEY) == payload


@check("aead", "invariant", "wire magic and version")
def _():
    blob = aead.seal(b"payload", KEY)
    assert blob[:4] == b"AH1\x00"
    assert blob[4] == 1


@check("aead", "invariant", "HKDF key length is 32 bytes")
def _():
    assert len(aead.derive_key(KEY, "memory")) == 32


@check("aead", "invariant", "empty key material rejected")
def _():
    try:
        aead.seal(b"data", b"")
    except aead.AeadError:
        return
    raise AssertionError("empty key was accepted")


@check("aead", "property", "100 random seal/open round-trips")
def _():
    for _i in range(100):
        payload = secrets.token_bytes(secrets.randbelow(512))
        key = secrets.token_bytes(32)
        assert aead.open_sealed(aead.seal(payload, key), key) == payload


@check("aead", "property", "ciphertext length grows by header+tag only")
def _():
    payload = b"a" * 64
    blob = aead.seal(payload, KEY)
    assert len(blob) == len(payload) + aead.HEADER_LEN + aead.TAG_LEN


@check("aead", "property", "semantic security: 20 equal plaintexts, 20 distinct blobs")
def _():
    payload = b"identical-plaintext"
    blobs = {aead.seal(payload, KEY) for _ in range(20)}
    assert len(blobs) == 20, "deterministic ciphertext detected"


@check("aead", "property", "key separation by context")
def _():
    assert aead.derive_key(KEY, "memory") != aead.derive_key(KEY, "comms")


@check("aead", "adversarial", "AAD binding: wrong context fails closed")
def _():
    blob = aead.seal(b"secret", KEY, context="memory")
    try:
        aead.open_sealed(blob, KEY, context="comms")
    except aead.AeadAuthError:
        return
    raise AssertionError("context confusion succeeded")


@check("aead", "adversarial", "bit-flip in ciphertext is rejected")
def _():
    blob = aead.seal(b"secret payload", KEY)
    for index in (aead.HEADER_LEN, len(blob) - 1, len(blob) - 8):
        try:
            aead.open_sealed(flip_bit(blob, index), KEY)
        except aead.AeadAuthError:
            continue
        raise AssertionError(f"forgery accepted at byte {index}")


@check("aead", "adversarial", "nonce tampering is rejected")
def _():
    blob = aead.seal(b"secret payload", KEY)
    try:
        aead.open_sealed(flip_bit(blob, 6), KEY)
    except aead.AeadAuthError:
        return
    raise AssertionError("nonce tampering accepted")


@check("aead", "adversarial", "magic and version tampering rejected")
def _():
    blob = aead.seal(b"payload", KEY)
    for index in (0, 4):
        try:
            aead.open_sealed(flip_bit(blob, index), KEY)
        except aead.AeadFormatError:
            continue
        raise AssertionError(f"header tampering accepted at {index}")


@check("aead", "adversarial", "truncation is rejected")
def _():
    blob = aead.seal(b"payload" * 10, KEY)
    for cut in (0, 8, aead.HEADER_LEN, len(blob) - 1):
        try:
            aead.open_sealed(blob[:cut], KEY)
        except aead.AeadError:
            continue
        raise AssertionError(f"truncated blob accepted at {cut}")


@check("aead", "adversarial", "wrong key fails closed")
def _():
    blob = aead.seal(b"payload", KEY)
    try:
        aead.open_sealed(blob, b"a-completely-different-key-value")
    except aead.AeadAuthError:
        return
    raise AssertionError("wrong key decrypted")


@check("aead", "adversarial", "legacy XOR blob is not openable")
def _():
    legacy = legacy_xor_obfuscate(b"payload", KEY)
    try:
        aead.open_sealed(legacy, KEY)
    except aead.AeadError:
        return
    raise AssertionError("legacy blob accepted by AEAD")


@check("aead", "adversarial", "negative proof: legacy XOR is deterministic, AEAD is not")
def _():
    payload = b"identical-plaintext"
    legacy_blobs = {legacy_xor_obfuscate(payload, KEY) for _ in range(20)}
    aead_blobs = {aead.seal(payload, KEY) for _ in range(20)}
    assert len(legacy_blobs) == 1, "legacy control unexpectedly randomised"
    assert len(aead_blobs) == 20, "AEAD is deterministic - P0-1 has regressed"


@check("aead", "adversarial", "claim lane: AEAD is not PQC")
def _():
    described = aead.describe()
    assert described["post_quantum"] is False
    assert described["unhackable"] is False


# =====================================================================
# LAYER 2 - AUDIT CHAIN
# =====================================================================


@check("audit_chain", "invariant", "empty chain verifies and has genesis last-hash")
def _():
    chain = AuditChain()
    assert chain.verify() is True
    assert chain.last_hash == audit_chain.GENESIS


@check("audit_chain", "invariant", "genesis link and monotonic prev-hash")
def _():
    chain = AuditChain()
    first = chain.append({"event": "boot"})
    second = chain.append({"event": "deploy"})
    assert first["prev_hash"] == audit_chain.GENESIS
    assert second["prev_hash"] == first["entry_hash"]
    assert second["index"] == 1


@check("audit_chain", "invariant", "entries are frozen copies")
def _():
    chain = AuditChain()
    chain.append({"event": "boot"})
    exported = chain.entries
    exported[0]["payload"] = {"event": "tampered"}
    assert chain.verify() is True
    assert chain.entries[0]["payload"] == {"event": "boot"}


@check("audit_chain", "invariant", "single-leaf root equals the leaf")
def _():
    chain = AuditChain()
    entry = chain.append({"event": "only"})
    assert chain.merkle_root() == entry["entry_hash"]


@check("audit_chain", "property", "80 random payloads stay verifiable")
def _():
    chain = AuditChain()
    for i in range(80):
        chain.append({"i": i, "blob": secrets.token_hex(8)})
    assert chain.verify() is True
    assert len(chain) == 80


@check("audit_chain", "property", "hash determinism across identical chains")
def _():
    a, b = AuditChain(), AuditChain()
    for payload in ({"x": 1}, {"y": 2}, {"z": 3}):
        a.append(payload)
        b.append(payload)
    assert a.merkle_root() == b.merkle_root()


@check("audit_chain", "property", "roots are order-sensitive")
def _():
    a, b = AuditChain(), AuditChain()
    a.append({"x": 1})
    a.append({"y": 2})
    b.append({"y": 2})
    b.append({"x": 1})
    assert a.merkle_root() != b.merkle_root()


@check("audit_chain", "property", "inclusion proofs verify for every entry")
def _():
    chain = AuditChain()
    for i in range(11):
        chain.append({"i": i})
    root = chain.merkle_root()
    for i, leaf in enumerate(chain.leaves()):
        assert AuditChain.verify_proof(leaf, chain.proof(i), root), f"proof {i} failed"


@check("audit_chain", "property", "fresh proof required after growth")
def _():
    chain = AuditChain()
    for i in range(4):
        chain.append({"i": i})
    stale_root = chain.merkle_root()
    stale_proof = chain.proof(0)
    chain.append({"i": "new"})
    assert chain.merkle_root() != stale_root
    assert not AuditChain.verify_proof(
        chain.leaves()[0], stale_proof, chain.merkle_root()
    )


@check("audit_chain", "adversarial", "payload mutation is detected")
def _():
    chain = AuditChain()
    chain.append({"decision": "READY"})
    chain.append({"decision": "BLOCKED"})
    chain._entries[1]["payload"] = {"decision": "READY"}
    assert chain.verify() is False, "tamper detector missed a payload rewrite"


@check("audit_chain", "adversarial", "entry-hash bit flip is detected")
def _():
    chain = AuditChain()
    chain.append({"a": 1})
    chain.append({"b": 2})
    original = chain._entries[0]["entry_hash"]
    chain._entries[0]["entry_hash"] = "f" + original[1:]
    assert chain.verify() is False


@check("audit_chain", "adversarial", "middle splice is detected")
def _():
    chain = AuditChain()
    for i in range(5):
        chain.append({"i": i})
    del chain._entries[2]
    assert chain.verify() is False


@check("audit_chain", "adversarial", "foreign leaf is not provable")
def _():
    chain = AuditChain()
    for i in range(4):
        chain.append({"i": i})
    foreign = "a" * 64
    assert not AuditChain.verify_proof(foreign, chain.proof(0), chain.merkle_root())


@check("audit_chain", "adversarial", "attacker rewrite of READY on chain is detected")
def _():
    chain = AuditChain()
    env = {"HYBA_ENV": "production"}
    decision = production_guard.evaluate(env)
    chain.append({"gate": decision["status"], "reasons": decision["reasons"]})
    assert decision["status"] == "BLOCKED"
    chain._entries[0]["payload"]["gate"] = "READY"
    assert chain.verify() is False


# =====================================================================
# LAYER 3 - PRODUCTION GUARD
# =====================================================================

GOOD_ENV = {
    "HYBA_ENV": "production",
    "HYBA_API_KEY": "live-9f2c4b8a1d7e",
    "HYBA_RELEASE_SHA": "d735d4497f151d55654e7ea8bfda0d58bf7626eb",
    "HYBA_ROLLBACK_PLAN": "runbooks/rollback.md",
}


@check("production_guard", "invariant", "non-mapping is blocked")
def _():
    for bad in (None, "env", 42, ["HYBA_ENV"]):
        assert production_guard.evaluate(bad)["status"] == "BLOCKED"


@check("production_guard", "invariant", "empty environment is blocked")
def _():
    assert production_guard.evaluate({})["status"] == "BLOCKED"


@check("production_guard", "invariant", "clean env with rehearsal is READY")
def _():
    decision = production_guard.evaluate(GOOD_ENV, rehearsal_completed=True)
    assert decision["status"] == "READY", decision["reasons"]


@check("production_guard", "property", "every bypass fragment blocks")
def _():
    for fragment in production_guard.BYPASS_FRAGMENTS:
        env = dict(GOOD_ENV)
        env[f"HYBA_{fragment}"] = "true"
        decision = production_guard.evaluate(env, rehearsal_completed=True)
        assert decision["status"] == "BLOCKED", f"{fragment} did not block"


@check("production_guard", "property", "every private-material fragment blocks")
def _():
    for fragment in production_guard.PRIVATE_MATERIAL_FRAGMENTS:
        env = dict(GOOD_ENV)
        env[f"HYBA_{fragment}"] = "value"
        decision = production_guard.evaluate(env, rehearsal_completed=True)
        assert decision["status"] == "BLOCKED", f"{fragment} did not block"


@check("production_guard", "property", "every secret value marker blocks")
def _():
    for marker in production_guard.SECRET_VALUE_MARKERS:
        env = dict(GOOD_ENV)
        env["HYBA_CONFIG_BLOB"] = f"prefix {marker}xxxxxxxx suffix"
        decision = production_guard.evaluate(env, rehearsal_completed=True)
        assert decision["status"] == "BLOCKED", f"{marker} did not block"


@check("production_guard", "property", "missing required keys block")
def _():
    for required in production_guard.REQUIRED_KEYS:
        env = dict(GOOD_ENV)
        del env[required]
        decision = production_guard.evaluate(env, rehearsal_completed=True)
        assert decision["status"] == "BLOCKED", f"missing {required} did not block"


@check("production_guard", "adversarial", "case-insensitive truthy bypass blocks")
def _():
    for truthy in ("TRUE", "True", "YES", "On", "1", "enabled"):
        env = dict(GOOD_ENV)
        env["HYBA_BYPASS_GATE"] = truthy
        decision = production_guard.evaluate(env, rehearsal_completed=True)
        assert decision["status"] == "BLOCKED", f"bypass={truthy} slipped through"


@check("production_guard", "adversarial", "production without rehearsal blocks")
def _():
    decision = production_guard.evaluate(GOOD_ENV, rehearsal_completed=False)
    assert decision["status"] == "BLOCKED"
    assert any("rehearsal" in reason for reason in decision["reasons"])


@check("production_guard", "adversarial", "dev default values block")
def _():
    env = dict(GOOD_ENV)
    env["HYBA_API_KEY"] = "changeme"
    assert production_guard.evaluate(env, rehearsal_completed=True)["status"] == "BLOCKED"


@check("production_guard", "adversarial", "PEM and AKIA markers block")
def _():
    env = dict(GOOD_ENV)
    env["HYBA_CERT"] = "-----BEGIN DUMMY TEST KEY-----"
    assert production_guard.evaluate(env, rehearsal_completed=True)["status"] == "BLOCKED"
    env = dict(GOOD_ENV)
    env["HYBA_CLOUD"] = "AKIAIOSFODNN7EXAMPLE"
    assert production_guard.evaluate(env, rehearsal_completed=True)["status"] == "BLOCKED"


@check("production_guard", "adversarial", "no rollback plan blocks")
def _():
    env = dict(GOOD_ENV)
    env["HYBA_ROLLBACK_PLAN"] = "   "
    assert production_guard.evaluate(env, rehearsal_completed=True)["status"] == "BLOCKED"


# =====================================================================
# LAYER 4 - CLAIM BOUNDARIES
# =====================================================================


@check("claims", "invariant", "posture declares no PQC and no unhackable")
def _():
    posture = claims.posture()
    assert posture["unhackable"] is False
    assert posture["post_quantum"] is False


@check("claims", "property", "only the three real controls are external-safe")
def _():
    assert claims.is_external_safe("aead_seal")
    assert claims.is_external_safe("audit_chain")
    assert claims.is_external_safe("launch_guard")
    assert not claims.is_external_safe("pqc_kem")
    assert not claims.is_external_safe("topological_protection")


@check("claims", "adversarial", "restricted marketing language is rejected")
def _():
    for text in (
        "HYBA is unhackable by design",
        "quantum-resistant memory protection",
        "we use AES-256-GCM at rest",
        "topology replaces cryptography",
        "no keys to steal",
    ):
        try:
            claims.assert_external_safe(text)
        except claims.ClaimViolation:
            continue
        raise AssertionError(f"restricted text passed the gate: {text}")


@check("claims", "adversarial", "honest language passes the gate")
def _():
    claims.assert_external_safe(
        "Classical authenticated encryption with a tamper-evident audit chain "
        "and a fail-closed launch gate."
    )


@check("claims", "adversarial", "unregistered claim raises")
def _():
    try:
        claims.lane_of("telepathic_defence")
    except claims.ClaimViolation:
        return
    raise AssertionError("unregistered claim was allowed")


# =====================================================================
# LAYER 5 - CROSS-CUTTING
# =====================================================================


@check("cross_cutting", "property", "guard decisions compose onto the audit chain")
def _():
    chain = AuditChain()
    for env, rehearsed in (({}, False), (GOOD_ENV, False), (GOOD_ENV, True)):
        decision = production_guard.evaluate(env, rehearsal_completed=rehearsed)
        chain.append({"status": decision["status"], "reasons": decision["reasons"]})
    assert chain.verify() is True
    assert [e["payload"]["status"] for e in chain.entries] == [
        "BLOCKED",
        "BLOCKED",
        "READY",
    ]


@check("cross_cutting", "property", "sealed audit export round-trips")
def _():
    chain = AuditChain()
    chain.append({"event": "gate", "status": "READY"})
    export = json.dumps(chain.describe()).encode()
    blob = aead.seal(export, KEY, context="audit-export")
    assert json.loads(aead.open_sealed(blob, KEY, context="audit-export")) == chain.describe()


@check("cross_cutting", "invariant", "posture envelope is JSON-safe")
def _():
    json.dumps(security_posture())


@check("cross_cutting", "invariant", "legacy defect module is not re-exported")
def _():
    import hyba_security

    # This test file imports hyba_security.legacy for the negative-proof control,
    # which binds the submodule attribute in THIS process. The real boundary
    # claim is that a clean import of the package never pulls the defect module
    # in, so it must be checked in a fresh interpreter.
    assert "legacy" not in hyba_security.__all__
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            "import hyba_security, sys; "
            "print(hasattr(hyba_security, 'legacy') "
            "or 'hyba_security.legacy' in sys.modules)",
        ],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parent.parent),
        check=True,
    )
    assert probe.stdout.strip() == "False", (
        "clean import of hyba_security pulled in the legacy defect module"
    )


# =====================================================================


def main() -> int:
    passed = sum(1 for r in RESULTS if r["passed"])
    failed = [r for r in RESULTS if not r["passed"]]
    total = len(RESULTS)

    by_layer: dict[str, dict[str, int]] = {}
    for result in RESULTS:
        bucket = by_layer.setdefault(result["layer"], {"passed": 0, "failed": 0})
        bucket["passed" if result["passed"] else "failed"] += 1

    print("=" * 66)
    print("HYBA SECURITY LAYER - IPA SUITE")
    print("=" * 66)
    for layer, counts in by_layer.items():
        mark = "PASS" if counts["failed"] == 0 else "FAIL"
        print(f"  [{mark}] {layer:<18} {counts['passed']:>3} passed  {counts['failed']:>2} failed")
    print("-" * 66)
    print(f"  TOTAL: {passed}/{total} passed")
    if failed:
        print("-" * 66)
        for result in failed:
            print(f"  FAILED [{result['layer']}] {result['name']}")
            print(f"         {result.get('error')}")
    print("=" * 66)

    os.makedirs("evidence", exist_ok=True)
    report = {
        "suite": "hyba_security_ipa",
        "total": total,
        "passed": passed,
        "failed": len(failed),
        "by_layer": by_layer,
        "posture": security_posture(),
        "results": RESULTS,
    }
    with open("evidence/hyba_security_ipa_report.json", "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
