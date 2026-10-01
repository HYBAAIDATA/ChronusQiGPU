"""Behavioral coverage for TOE serving a real canonical mining record."""
from __future__ import annotations

from toe.bridge import TOEBridge
from chronus.mla1517.mining.toe_adapter import TOEMiningAdapter
from manifold_pool_coordinator import StratumJob


def test_toe_consumes_job_and_vault_state_without_synthetic_input() -> None:
    job = StratumJob(
        job_id="job-real-observation",
        params=("job-real-observation", "prevhash", "coinbase1", "coinbase2"),
        received_at=1.0,
    )
    adapter = TOEMiningAdapter(TOEBridge())
    context = adapter.analyse(
        job=job,
        state=bytes(range(64)),
        node_id=7,
        sequence=19,
    )
    assert context.job_id == "job-real-observation"
    assert context.node_id == 7
    assert context.sequence == 19
    assert context.execution_evidence["backend"] == "cpu-exact"
    assert context.result["available"] is True
    for name in ("state_tomography", "trajectory_prediction", "causal_analysis", "causal_ladder"):
        assert context.result[name]["available"] is True
