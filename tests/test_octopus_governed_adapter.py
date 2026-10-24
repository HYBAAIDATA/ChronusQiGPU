"""Local adapter fixtures: real headers and lease ledger, no external pool writes."""

import asyncio
from dataclasses import replace
from types import SimpleNamespace

import pytest

from chronus.mla1517.mining.agentic_controller import AgenticMiningController
from chronus.mla1517.mining.causal import CausalLedger
from chronus.mla1517.mining.m3_coordinator import M3PythiaProductionMiningCoordinator
from chronus.mla1517.mining.octopus_adapter import GovernedOctopusAdapter
from chronus.mla1517.mining.search_plan import WorkIdentity
from chronus.mla1517.mining.stratum_adapter import StratumProofAdapter
from chronus.octopus_execution import OctopusExecutionEngine


def fixture(tmp_path, result=True, transport_error=False, allowed=True, stale=False):
    proof = StratumProofAdapter()
    proof.handle_subscribe_result([[], "00", 4])
    proof.set_exact_target((1 << 256) - 1)
    proof.handle_message(
        {
            "method": "mining.notify",
            "params": ["job", "00" * 32, "01", "02", [], "20000000", "207fffff", "65000000", True],
        }
    )
    identity = WorkIdentity("session", 1, "job", "fingerprint", 1, True, 1.0)
    coord = M3PythiaProductionMiningCoordinator.__new__(M3PythiaProductionMiningCoordinator)
    from chronus.mla1517.mining.hashrate_governor import HashrateGovernor

    coord.governor = HashrateGovernor(max_network_fraction=None)
    coord._refresh_governor = lambda: None
    coord._search_lock = asyncio.Lock()
    coord.mining_enabled = True
    coord.work_throttled = False
    coord.agentic = AgenticMiningController()
    coord.agentic.bind_work(identity)
    coord.causal = CausalLedger()
    coord._pending_correlation = None
    counter = {"writes": 0, "calls": 0}
    coord.client = SimpleNamespace(
        proof_adapter=proof, wire_writes_for=lambda method: counter["writes"]
    )
    refreshes = {"count": 0}

    def refresh():
        refreshes["count"] += 1
        if stale and refreshes["count"] > 1:
            return replace(identity, generation=2)
        return identity

    coord._refresh_work_identity = refresh
    coord.submission_permitted = lambda: allowed

    async def submit(**kwargs):
        counter["calls"] += 1
        proof.validate_candidate(**{k: v for k, v in kwargs.items() if k != "cycle_reporting"})
        counter["writes"] += 1
        if transport_error:
            raise TimeoutError("local fixture: response lost after write")
        return result

    coord.submit_candidate = submit
    engine = OctopusExecutionEngine(tmp_path / "shadow")
    return GovernedOctopusAdapter(coord, engine), coord, counter


@pytest.mark.asyncio
@pytest.mark.parametrize("result,outcome", [(True, "ACCEPTED"), (False, "REJECTED")])
async def test_literal_pool_outcomes_and_consumed_lease(tmp_path, result, outcome):
    adapter, coord, calls = fixture(tmp_path, result=result)
    receipt = await adapter.search_current_job(request_submission=True)
    assert receipt.pool_outcome == outcome
    assert receipt.accepted is result
    assert receipt.execution.submitted_live is True
    assert calls == {"writes": 1, "calls": 1}
    assert coord.agentic.lease(receipt.lease_id).state.value == "COMPLETE"
    assert coord._pending_correlation is None


@pytest.mark.asyncio
async def test_shadow_never_invokes_submission(tmp_path):
    adapter, _, calls = fixture(tmp_path)
    receipt = await adapter.search_current_job()
    assert receipt.pool_outcome == "SHADOW"
    assert receipt.accepted is False
    assert receipt.execution.submitted_live is False
    assert calls["calls"] == 0


@pytest.mark.asyncio
async def test_lost_ack_is_unknown_never_retried(tmp_path):
    adapter, _, calls = fixture(tmp_path, transport_error=True)
    receipt = await adapter.search_current_job(request_submission=True)
    assert receipt.pool_outcome == "OUTCOME_UNKNOWN"
    assert receipt.accepted is False
    assert calls["calls"] == 1


@pytest.mark.asyncio
async def test_unauthorized_adapter_never_dispatches_or_submits(tmp_path):
    adapter, _, calls = fixture(tmp_path, allowed=False)
    with pytest.raises(PermissionError):
        await adapter.search_current_job(request_submission=True)
    assert calls["calls"] == 0
    assert not list((tmp_path / "shadow").glob("octopus_*.jsonl"))


@pytest.mark.asyncio
async def test_changed_generation_discards_winner(tmp_path):
    adapter, _, calls = fixture(tmp_path, stale=True)
    receipt = await adapter.search_current_job(request_submission=True)
    assert receipt.pool_outcome == "STALE"
    assert receipt.accepted is False
    assert calls["calls"] == 0


def test_plain_unsecured_coordinator_is_not_an_adapter(tmp_path):
    with pytest.raises(TypeError):
        GovernedOctopusAdapter(object(), OctopusExecutionEngine(tmp_path))


def test_independent_submitter_cannot_share_adapter_correlation(tmp_path):
    adapter, coord, _ = fixture(tmp_path)
    coord._asynchronous_submission = True
    with pytest.raises(ValueError, match="synchronous"):
        GovernedOctopusAdapter(coord, adapter.engine)


@pytest.mark.asyncio
async def test_repeated_campaigns_never_reuse_a_nonce_lease(tmp_path):
    adapter, coord, _ = fixture(tmp_path)
    first = await adapter.search_current_job()
    second = await adapter.search_current_job()
    a = coord.agentic.lease(first.lease_id)
    b = coord.agentic.lease(second.lease_id)
    assert a.lease_id != b.lease_id
    assert a.extranonce2 != b.extranonce2 or a.end <= b.start or b.end <= a.start


@pytest.mark.asyncio
async def test_governor_denial_precedes_execution_and_pool_write(tmp_path):
    adapter, coord, calls = fixture(tmp_path)
    coord.governor = SimpleNamespace(admit=lambda: False)
    with pytest.raises(PermissionError, match="governor"):
        await adapter.search_current_job(request_submission=True)
    assert calls == {"writes": 0, "calls": 0}
    assert adapter.engine.campaign_counter == 0


@pytest.mark.asyncio
async def test_runtime_policy_changes_bind_seed_budget_and_receipt(tmp_path, monkeypatch):
    from chronus.mla1517_platform.python import runtime_config

    monkeypatch.setenv("PYTHIA_RUNTIME_CONFIG", str(tmp_path / "policy.json"))
    runtime_config.save(
        {"window": 600, "intelligence": {"seed": 42, "max_workers": 1, "max_nonces_per_arm": 1}}
    )
    adapter, coord, calls = fixture(tmp_path)
    receipt = await adapter.search_current_job()
    assert len(receipt.execution.runtime_policy_digest) == 64
    assert coord.governor.hashes == receipt.execution.nonces_evaluated
    assert calls["writes"] == 0
    with pytest.raises(ValueError, match="runtime config"):
        await adapter.search_current_job(window=601)


@pytest.mark.asyncio
async def test_octopus_cannot_mislabel_cpu_route_as_scale_stack(tmp_path, monkeypatch):
    from chronus.mla1517_platform.python import runtime_config

    monkeypatch.setenv("PYTHIA_RUNTIME_CONFIG", str(tmp_path / "policy.json"))
    runtime_config.save({"execution": {"mode": "scale_stack"}})
    adapter, coord, calls = fixture(tmp_path)
    with pytest.raises(PermissionError, match="cannot satisfy scale_stack"):
        await adapter.search_current_job()
    assert adapter.engine.campaign_counter == 0
    assert calls["writes"] == 0
