"""Behavioral coverage for TOE serving a real canonical mining record."""

from __future__ import annotations

from kellogg.exact_tensor import ExactTOETensor
from toe.bridge import TOEBridge
from chronus.mla1517.mining.toe_adapter import TOEMiningAdapter
from chronus.mla1517.mining.toe_decision import build_toe_decision_frame
from chronus.mla1517.mining.toe_signal import build_toe_signal
from manifold_pool_coordinator import StratumJob


def test_toe_consumes_kellogg_state_and_job_without_synthetic_input(monkeypatch) -> None:
    job = StratumJob(
        job_id="job-real-observation",
        params=("job-real-observation", "prevhash", "coinbase1", "coinbase2"),
        received_at=1.0,
    )
    encoded_digests = []
    encode = ExactTOETensor.encode

    def recording_encode(tensor, data):
        state, digest = encode(tensor, data)
        encoded_digests.append(digest)
        return state, digest

    monkeypatch.setattr(ExactTOETensor, "encode", recording_encode)
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
    assert context.result["exact_tensor"]["input_digest"] in encoded_digests
    assert (
        context.result["exact_tensor"]["input_digest"]
        == context.result["toe_expansion"]["input_digest"]
    )
    assert build_toe_decision_frame(context).is_valid()
    signal = build_toe_signal(context)
    assert signal.is_valid()
    assert signal.causal_throttle
    for name in ("state_tomography", "trajectory_prediction", "causal_analysis", "causal_ladder"):
        assert context.result[name]["available"] is True
