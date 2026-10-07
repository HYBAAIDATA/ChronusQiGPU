"""Mining as TOE's first full production workload — without moving authority.

TOE advises the work-window size; PYTHIA authorizes; check_pow (plus an
independent SHA256d recheck) alone decides validity; telemetry feeds TOE
learning; THESEUS keeps it across a restart.
"""

from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path

import pytest

from chronus.mla1517.mining import toe_problem
from toe.custody import theseus_available

ROOT = Path(__file__).resolve().parent.parent


def _voyage():
    spec = importlib.util.spec_from_file_location("toe_mining_voyage", ROOT / "scripts" / "toe_mining_voyage.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def report(tmp_path_factory):
    root = tmp_path_factory.mktemp("custody") if theseus_available() else None
    return _voyage().run(root, rounds=2)


def test_toe_advice_is_bounded_and_authorized(report):
    assert report["toe"]["ok"] is True
    assert report["toe"]["status"] == "ACT"
    assert report["pythia_authority"]["authority"] == "PYTHIA"
    assert report["pythia_authority"]["authorized"] is True
    assert report["toe"]["recommended_window"] in toe_problem.WINDOW_LEVELS


def test_validity_is_decided_by_check_pow_only(report):
    ex = report["execution"]
    assert ex["candidates_found_by_check_pow"] == ex["candidates_rechecked_valid"]
    assert "check_pow" in ex["validity_authority"]


def test_no_consensus_field_is_a_toe_variable():
    p = toe_problem.MiningWindowAdapter(10.0).to_problem(
        [{"window_size": 1024.0, "hashes_per_s": 1.0, "latency_ms": 1.0}] * 4
    )
    forbidden = {"nonce", "target", "header", "sha256d", "share", "bits", "merkle_root"}
    names = set(p.state) | set(p.structure.all_nodes()) | {op.node for op in p.operators}
    assert not names & forbidden


def test_toe_never_touches_the_proof_boundary():
    # The adapter imports the proof boundary; the TOE package never does.
    toe_root = ROOT / "toe"
    for path in toe_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "check_pow" not in text, path
    assert "check_pow" in inspect.getsource(toe_problem.execute_window)


def test_decision_effect_is_measured_not_assumed(report):
    eff = report["decision_effect"]
    assert set(eff) >= {"toe_changed_window", "toe_within_budget", "baseline_within_budget"}
    assert eff["toe_within_budget"] is True


def test_feedback_reaches_learning_and_survives_restart(report):
    assert report["learning"]["ok"] is True
    if not theseus_available():
        assert report["restart"]["available"] is False
        return
    assert report["learning"]["persisted"]["available"] is True
    r = report["restart"]
    assert r["recovered_from"]["recovered"] is True
    assert r["bindings_after_restart"] >= 1
    assert r["replay_first_episode"]["identical"] is True
