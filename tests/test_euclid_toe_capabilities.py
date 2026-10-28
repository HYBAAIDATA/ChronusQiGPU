"""EUCLID can exploit the whole TOE surface without TOE gaining authority."""

from __future__ import annotations

import json

import pytest

from euclid.cognition.toe_capabilities import CAPABILITIES, TOECapabilityAdapter
from euclid.evidence import EvidenceChain
from toe.voyage import simulated_world, voyage_problem


@pytest.fixture()
def adapter():
    return TOECapabilityAdapter(evidence=EvidenceChain())


@pytest.mark.parametrize("json_input", [False, True])
def test_every_capability_is_callable_and_evidence_chained(adapter, json_input):
    p = voyage_problem()
    expected_digest = p.digest()
    if json_input:
        p = json.loads(json.dumps({"domain": p.domain, **p.content()}))
    answers = {
        "represent": adapter.invoke("represent", p),
        "model": adapter.invoke("model", p),
        "identify": adapter.invoke("identify", p),
        "intervene": adapter.invoke("intervene", p, {"x": 1.0}),
        "counterfactual": adapter.invoke("counterfactual", p, {"x": 1.0}, ["y"]),
        "evaluate_futures": adapter.invoke("evaluate_futures", p),
        "uncertainty": adapter.invoke("uncertainty", p),
        "plan": adapter.invoke("plan", p),
        "request_information": adapter.invoke("request_information", p),
        "explain": adapter.invoke("explain", p),
        "run": adapter.invoke("run", p),
    }
    assert answers["identify"]["result"]["verdict"] == "IDENTIFIED"
    assert answers["request_information"]["result"]["verdict"] == "ACQUIRE_EVIDENCE"
    assert answers["run"]["result"]["status"] == "ACQUIRE_EVIDENCE"
    assert answers["counterfactual"]["result"].get("available") is False  # no factual y: refused
    assert all(a["result"] for a in answers.values())
    assert all(a["evidence"]["problem_digest"] == expected_digest for a in answers.values())
    kinds = [r.kind for r in adapter.evidence.records]
    assert kinds.count("toe-capability") == len(answers)
    adapter.evidence.verify()
    assert set(CAPABILITIES) - set(answers) == {"revise"}


@pytest.mark.parametrize("json_input", [False, True])
def test_euclid_driven_learning_changes_the_next_toe_answer(adapter, json_input):
    first = adapter.invoke("run", voyage_problem())
    episode = first["result"]["episode_sha256"]
    if json_input:
        episode = {"episode_sha256": episode}
    observed = simulated_world(first["result"]["recommendation"]["interventions"], n=6, seed=101)
    revised = adapter.invoke("revise", episode, observed)
    assert revised["result"]["revision"] is not None
    second = adapter.invoke("run", voyage_problem(z_state=0.25))
    assert second["result"]["decision"]["selected_action"] == "raise_z=1.0"
    for call in adapter.calls:
        assert call["authority"].startswith("EUCLID invoked")


def test_unknown_capability_is_refused(adapter):
    with pytest.raises(ValueError):
        adapter.invoke("execute_trade", voyage_problem())


def test_euclid_runtime_exposes_the_handle(tmp_path):
    from euclid.runtime import EuclidRuntime

    rt = EuclidRuntime(creator_id="tester", state_dir=tmp_path)
    out = rt.toe.invoke("identify", voyage_problem())
    assert out["result"]["verdict"] == "IDENTIFIED"
    assert rt.evidence.records[-1].kind == "toe-capability"
