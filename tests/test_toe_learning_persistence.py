"""Learning changes behaviour; THESEUS keeps it across a restart.

prediction → action → observed consequence → prediction error → revision
→ later related problem → changed decision; then persistence through
THESEUS custody, recovery in a fresh process, replay, tamper refusal and
the negative-transfer guard.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from toe.custody import SnapshotIntegrityError, SnapshotStore, open_theseus_custody, theseus_available
from toe.machine import ACQUIRE_EVIDENCE, ACT, TOEMachine
from toe.voyage import TRUE_WEIGHTS, canonical_voyage, simulated_world, voyage_problem
from toe.world_model import MODEL_CONTRADICTED

ROOT = Path(__file__).resolve().parent.parent

pytestmark = pytest.mark.skipif(not theseus_available(), reason="THESEUS custody not importable")


@pytest.fixture()
def store_factory(tmp_path):
    key = os.urandom(32)

    def factory():
        return open_theseus_custody(tmp_path / "theseus", hmac_key=key)

    factory.root = tmp_path / "theseus"
    factory.key = key
    return factory


def test_learning_changes_a_later_decision(store_factory):
    report = canonical_voyage(store_factory)
    e1, e2 = report["episode_1"], report["episode_2_same_process"]
    assert e1["status"] == ACQUIRE_EVIDENCE and e1["selected"] == "raise_x=1.0"
    assert report["learning"]["assessment"] == MODEL_CONTRADICTED
    assert report["learning"]["revised"] is True
    w = report["learning"]["weights_after"]["x->y"]
    se = report["learning"]["standard_errors"]["x->y"]
    assert abs(w - TRUE_WEIGHTS[("x", "y")]) < 4 * se
    # Learned evidence both changes the choice and removes the doubt.
    assert e2["selected"] == "raise_z=1.0" and e2["status"] == ACT
    assert e2["voi"] == {"edge:x->y": False}
    assert report["decision_changed"] is True


def test_restart_recovers_instead_of_starting_newborn(store_factory):
    report = canonical_voyage(store_factory)
    r = report["restart"]
    assert r["recovered_from"]["recovered"] is True
    assert r["model_revision_after_restart"] == 1
    assert r["matches_pre_restart_decision"] is True
    assert r["replay_after_restart"]["identical"] is True


def test_replay_and_negative_transfer_guard(store_factory):
    report = canonical_voyage(store_factory)
    assert report["replay_episode_1"]["identical"] is True
    guard = report["negative_transfer_guard"]
    assert guard["guard_held"] is True and guard["other_domain_selected"] == "raise_x=1.0"


def test_fresh_process_recovers_and_reuses(store_factory):
    machine = TOEMachine(custody=store_factory(), stream="voyage")
    ep = machine.run(voyage_problem())
    machine.learn(ep, simulated_world(ep["recommendation"]["interventions"], n=6, seed=101))
    child = textwrap.dedent(
        f"""
        import json, sys
        sys.path.insert(0, {str(ROOT)!r})
        from toe.custody import open_theseus_custody
        from toe.machine import TOEMachine
        from toe.voyage import voyage_problem
        m = TOEMachine(custody=open_theseus_custody({str(store_factory.root)!r},
                       hmac_key=bytes.fromhex({store_factory.key.hex()!r})), stream="voyage")
        ep = m.run(voyage_problem(z_state=0.25))
        print(json.dumps({{"recovered": m.recovered_from, "selected": ep["decision"]["selected_action"],
                          "revision": ep["identity"]["model_revision"],
                          "replay": m.replay({ep['episode_sha256']!r})["identical"]}}))
        """
    )
    out = subprocess.run([sys.executable, "-c", child], capture_output=True, text=True, check=True, cwd=str(ROOT))
    data = json.loads(out.stdout.strip().splitlines()[-1])
    assert data["recovered"]["recovered"] is True
    assert data["revision"] == 1
    assert data["selected"] == "raise_z=1.0"
    assert data["replay"] is True


def test_tampered_snapshot_chain_fails_closed(store_factory):
    machine = TOEMachine(custody=store_factory(), stream="tamper")
    ep = machine.run(voyage_problem())
    machine.learn(ep, simulated_world({"x": 1.0}, n=4, seed=3))
    machine.learn(ep, simulated_world({"x": 1.0}, n=4, seed=4))
    custody = store_factory()
    from aethel.enterprise.records import OperationalRecord

    forged = OperationalRecord(
        record_id="toe-tamper-00000003",
        producer="toe",
        producer_version="forged",
        schema_version=1,
        kind="toe.machine.snapshot",
        payload=json.dumps({"schema": "toe.snapshot/v1", "stream": "tamper", "revision": 3,
                            "parent_digest": "0" * 64, "toe_version": "x", "payload": {},
                            "digest": "0" * 64}).encode(),
        evidence_state="MEASURED",
    )
    custody.put_record(forged)
    with pytest.raises(SnapshotIntegrityError):
        SnapshotStore(store_factory(), stream="tamper").load_head()
    with pytest.raises(SnapshotIntegrityError):
        TOEMachine(custody=store_factory(), stream="tamper")


def test_no_custody_means_persistence_unavailable():
    machine = TOEMachine()
    ep = machine.run(voyage_problem())
    out = machine.learn(ep, simulated_world({"x": 1.0}, n=4, seed=9))
    assert out["persisted"]["available"] is False
    assert "UNAVAILABLE" in out["persisted"]["reason"]


def test_explicit_transfer_requires_matching_shape():
    from dataclasses import replace

    from toe.problem import Structure

    m = TOEMachine()
    ep = m.run(voyage_problem())
    m.learn(ep, simulated_world({"x": 1.0}, n=6, seed=101), persist=False)
    target = voyage_problem(domain="voyage.sister")
    moved = m.transfer(ep["identity"]["namespace"], target, reason="owner-declared same mechanism")
    assert moved["transferred"] is True
    assert m.run(target)["decision"]["selected_action"] == "raise_z=1.0"
    other_shape = replace(target, domain="voyage.other", structure=Structure.of([("x", "y", 2.0)]),
                          operators=target.operators[:1], uncertain={})
    refused = m.transfer(ep["identity"]["namespace"], other_shape, reason="wrong shape")
    assert refused["transferred"] is False


def test_contradiction_that_cannot_be_refit_widens_uncertainty():
    # Both levers held fixed: the outcome contradicts the model, but the
    # design is singular, so no revision is possible. The machine must say
    # so — wider uncertainty, an evidence request, replanning — not refit.
    m = TOEMachine(min_evidence=3)
    ep = m.run(voyage_problem())
    out = m.learn(ep, simulated_world({"x": 1.0, "z": 0.0}, n=5, seed=2), persist=False)
    assert out["assessment"]["status"] == MODEL_CONTRADICTED
    assert out["revision"] is None
    assert out["evidence_requested"] is True and out["noise_inflation"] > 1.0
    assert m.contradictions[-1]["consequences"] == ["uncertainty increase", "new evidence request", "replanning"]
    assert m.negative_results[-1]["kind"] == "model_contradiction"
