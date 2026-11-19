"""Synthetic policy and transport rejection tests; no external pool is contacted."""
import asyncio
import json
import threading
from unittest.mock import AsyncMock

import pytest

pytestmark = [pytest.mark.usefixtures("mining_custody"), pytest.mark.simulated]

from chronus.security.mining_policy import MiningSubmissionPolicy
from chronus.stratum.endpoint import PoolEndpoint
from chronus.stratum.gateway import StratumGateway
from chronus.execution.geometric_galois_miner import GeometricGaloisMiner


def test_allowlist_is_exact_and_default_denied(monkeypatch):
    monkeypatch.delenv("CHRONUS_ALLOWED_POOL_ENDPOINTS", raising=False)
    endpoint = PoolEndpoint("approved.example", 3333, True)
    with pytest.raises(PermissionError):
        MiningSubmissionPolicy.check_endpoint(endpoint)
    monkeypatch.setenv("CHRONUS_ALLOWED_POOL_ENDPOINTS", json.dumps([str(endpoint)]))
    MiningSubmissionPolicy.check_endpoint(endpoint)
    for other in [PoolEndpoint("evil.example", 3333, True), PoolEndpoint("approved.example", 3333, False), PoolEndpoint("approved.example", 4444, True)]:
        with pytest.raises(PermissionError):
            MiningSubmissionPolicy.check_endpoint(other)


def test_arming_and_only_literal_correlated_acceptance_count():
    policy = MiningSubmissionPolicy()
    assert not policy.status()["share_submit_armed"]
    with pytest.raises(PermissionError):
        policy.authorize(1)
    policy.arm("operator-reviewed-config", 1)
    policy.authorize(1)
    with pytest.raises(PermissionError):
        policy.authorize(2)
    policy.observe({"id": 2, "result": True})
    policy.observe({"id": 1, "result": "true"})
    assert policy.accepted == 0
    policy.observe({"id": 1, "result": True})
    policy.observe({"id": 1, "result": True})
    assert policy.accepted == 1
    assert not policy.armed
    assert policy.events[-1] == "AUTO_DISARMED_TARGET_REACHED"


def test_raw_submit_transport_bypass_rejected(monkeypatch):
    monkeypatch.setenv("CHRONUS_ALLOWED_POOL_ENDPOINTS", '["stratum+tcp://localhost:3333"]')
    async def scenario():
        gateway = StratumGateway("localhost", 3333, "worker")
        gateway.writer = AsyncMock()
        gateway.reader = asyncio.StreamReader()
        params = ["worker", "unknown", "00000000", "00000000", "00000000"]
        for method in [gateway.write_rpc, gateway.send_rpc]:
            with pytest.raises(PermissionError):
                await method("mining.submit", params)
        gateway.writer.write.assert_not_called()
        gateway.submission_policy.arm("synthetic-test", 1)
        for method in [gateway.write_rpc, gateway.send_rpc]:
            with pytest.raises(PermissionError):
                await method("mining.submit", params)
        gateway.writer.write.assert_not_called()
    asyncio.run(scenario())


def test_cancelled_epoch_evaluates_no_candidates():
    miner = GeometricGaloisMiner()
    cancel = threading.Event()
    cancel.set()
    result = miner.solve_header_range(bytes(76), 0, 0, 100, cancel_token=cancel)
    assert not result.found
    assert result.iterations_evaluated == 0


def test_missing_custody_cannot_arm(monkeypatch):
    monkeypatch.delenv("CHRONUS_MINING_CUSTODY_PATH", raising=False)
    policy = MiningSubmissionPolicy()
    with pytest.raises(PermissionError, match="custody"):
        policy.arm("operator-reference", 1)
    assert not policy.armed


def test_duplicate_rpc_id_cannot_be_authorized_again():
    policy = MiningSubmissionPolicy()
    policy.arm("operator-reference", 3)
    policy.authorize(1)
    with pytest.raises(PermissionError, match="RPC id"):
        policy.authorize(1)
    policy.observe({"id": 1, "result": False})
    with pytest.raises(PermissionError, match="RPC id"):
        policy.authorize(1)
    policy.authorize(2)
    assert policy.pending == {2}


def test_tampered_wire_frame_never_advances_verdict():
    policy = MiningSubmissionPolicy()
    policy.arm("operator-reference", 2)
    policy.authorize(1)
    with pytest.raises(ValueError, match="does not match"):
        policy.observe({"id": 1, "result": True}, wire_frame=b'{"id":1,"result":false}\n')
    assert policy.accepted == 0 and policy.pending == {1}
