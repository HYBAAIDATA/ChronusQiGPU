"""Consensus-boundary preservation tests for the StratumClient remediation.

Advisory 1 (merge-blocking): the M1-M6 remediation modifies transport,
acknowledgement, and counter semantics ONLY. It must not move, bypass, or
invoke the consensus boundary -- double-SHA256, block-header assembly, and
the target comparison remain the sole arbiters of share validity, reachable
exclusively through the explicitly-labelled firewall/local-validation path.

Invariants asserted here:
  1. A live-approval share submission (submit -> wire -> pool ACK) performs
     zero hashing and zero target comparison. Any hashing leak into the
     transport path fails the test immediately.
  2. The consensus primitives' source text is digest-pinned. Any edit to
     double_sha256, coinbase/merkle construction, header serialization, the
     wire nonce encoding, the difficulty->target conversion, or
     validate_sha256d breaks this suite loudly.
  3. Hashing is reachable ONLY through the firewall path: an unapproved
     (non-live) submission still invokes validate_sha256d and advances only
     the firewall_* counters -- never pool_accepted.
"""

import asyncio
import hashlib
import inspect
import os
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import pytest

import stratum_client as sc
import test_stratum_handshake_integrity as harness

armed_env = harness.armed_env  # reuse the same env-arming fixture


# ---------------------------------------------------------------------------
# Digest pins: source of every consensus-adjacent primitive in this module.
# These digests were taken from the pre-remediation implementation (verified
# byte-identical to this file) -- a changed digest means the consensus
# boundary moved under the transport layer. Do NOT re-pin without sign-off.
# ---------------------------------------------------------------------------
_CONSENSUS_PINS = {
    "module": {
        "double_sha256": "b4080c9493ce9d683436f7a8d690a1b66ea0acc8fca9c0ec7ea2775532aeeea0",
        "compute_stratum_merkle_root": "8afda86881f9d71674ed702f5c281468f8995982d92f4c68922e6caf2aab0093",
        "_raw_field_bytes": "8d2f52d7c55383f6d90ba18c84980542b9e0d7bc948f1bf3d385dfb3ece0e484",
        "build_stratum_block_header": "b1c996d7721b08b7c70bdb9cfcab92ad08cf8d989ad23efb3e34629289404061",
        "nonce_to_wire_hex": "6cd6c7d6cf801415c223d536f9d42e187f36fc82f11ed2f538f4b9a06b7373db",
    },
    "class": {
        "_difficulty_to_target": "7d989bd71be9a340b7349fde45c5b7d8ae41573179a4812ea0655b15079396cb",
        "set_difficulty": "cc7834bf0b60bcd402cc51dbab65254279b3d905bb8beb90df7659e85fde521a",
        "validate_sha256d": "ad61ecba6c8ebcf5d6a13ee96d49ea5c074aaa9e945a57668dcb6c77ed42509b",
    },
}


def test_consensus_primitives_source_pinned():
    """Every consensus-side primitive must hash to its pinned digest."""
    for name, want in _CONSENSUS_PINS["module"].items():
        digest = hashlib.sha256(inspect.getsource(getattr(sc, name)).encode()).hexdigest()
        assert digest == want, (
            f"CONSENSUS BOUNDARY MOVED: stratum_client.{name} source changed. "
            "The remediation must not alter double-SHA256, merkle/header "
            "construction, or wire encoding -- re-pin requires consensus sign-off."
        )
    for name, want in _CONSENSUS_PINS["class"].items():
        digest = hashlib.sha256(
            inspect.getsource(getattr(sc.StratumClient, name)).encode()
        ).hexdigest()
        assert digest == want, (
            f"CONSENSUS BOUNDARY MOVED: StratumClient.{name} source changed. "
            "The target comparison and difficulty conversion are consensus "
            "code -- re-pin requires consensus sign-off."
        )


def _raise_boundary_breach(*args, **kwargs):
    raise AssertionError(
        "CONSENSUS BREACH: hashing/validation invoked from the transport "
        "submission path -- stratum_client must submit pre-computed nonces "
        "and never evaluate share validity itself on the live wire path."
    )


@pytest.mark.asyncio
async def test_live_submit_path_performs_no_hashing(armed_env, monkeypatch):
    """A live-approval submit (wire + pool ACK) must not touch sha256."""
    # Tripwires on every consensus primitive AND on hashlib.sha256 itself:
    # the remediation is in violation if ANY of them fires while the share
    # traverses connect -> submit -> wire -> pool ACK.
    for name in (
        "double_sha256",
        "compute_stratum_merkle_root",
        "_raw_field_bytes",
        "build_stratum_block_header",
        "nonce_to_wire_hex",
    ):
        monkeypatch.setattr(sc, name, _raise_boundary_breach)
    for name in ("_difficulty_to_target", "validate_sha256d"):
        monkeypatch.setattr(sc.StratumClient, name, _raise_boundary_breach)
    monkeypatch.setattr(hashlib, "sha256", _raise_boundary_breach)
    monkeypatch.setattr(hashlib, "sha512", _raise_boundary_breach)

    server = harness.MockStratumServer()
    await server.start()
    client = harness.make_client(server, monkeypatch)
    try:
        assert await client.connect(connect_timeout=3.0, handshake_timeout=3.0) is True
        assert await harness._wait_for(lambda: client.current_job is not None)

        accepted, req_id = await client.submit_share(
            job_id=client.current_job["job_id"], nonce="00000001"
        )
        # Tripwires did not fire; the verdict came from the pool alone.
        assert accepted is True
        assert req_id >= sc._SUBMIT_ID_FLOOR
        assert client.pool_accepted == 1
        assert client.firewall_accepted == 0
        assert client.firewall_rejected == 0
    finally:
        await client.close()
        await server.stop()


@pytest.mark.asyncio
async def test_hashing_reachable_only_through_firewall_path(monkeypatch):
    """Unarmed (non-live) submits DO hash -- but only via the labelled
    firewall path, and only firewall_* counters may advance."""
    # Live submit NOT approved (no armed_env fixture) -> submit_share takes
    # the local-validation branch, which is the module's only hash user.
    calls = {"validate_sha256d": 0}
    real_validate = sc.StratumClient.validate_sha256d

    def spy(self, header_hex, target_hex=None):
        calls["validate_sha256d"] += 1
        return real_validate(self, header_hex, target_hex)

    monkeypatch.setattr(sc.StratumClient, "validate_sha256d", spy)

    server = harness.MockStratumServer()
    await server.start()
    client = harness.make_client(server, monkeypatch)
    try:
        assert await client.connect(connect_timeout=3.0, handshake_timeout=3.0) is True
        assert await harness._wait_for(lambda: client.current_job is not None)

        accepted, req_id = await client.submit_share(
            job_id=client.current_job["job_id"], nonce="00000001"
        )
        assert calls["validate_sha256d"] == 1  # hashing confined to firewall
        assert req_id == sc.UNSUBMITTED_REQUEST_ID  # nothing hit the wire
        assert len(server.submits()) == 0
        assert client.pool_accepted == 0
        assert client.pool_rejected == 0
        assert client.firewall_accepted + client.firewall_rejected == 1
    finally:
        await client.close()
        await server.stop()
