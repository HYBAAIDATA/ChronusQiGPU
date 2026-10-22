"""Standalone installed-artifact learning contract, without a custody substitute.

THESEUS restart/tamper integration stays in test_toe_learning_persistence.py.
These tests prove in-process learning and truthful unavailable persistence only.
They deliberately have no skip, fake custody backend, or source-path injection.
"""
import pytest

from toe import custody
from toe.custody import CustodyUnavailable, open_theseus_custody
from toe.machine import ACQUIRE_EVIDENCE, ACT
from toe.voyage import TRUE_WEIGHTS, canonical_voyage
from toe.world_model import MODEL_CONTRADICTED


@pytest.fixture(scope="module")
def voyage():
    return canonical_voyage(None)


def test_standalone_learning_changes_decision(voyage):
    assert voyage["episode_1"]["status"] == ACQUIRE_EVIDENCE
    assert voyage["episode_1"]["selected"] == "raise_x=1.0"
    learning = voyage["learning"]
    assert learning["assessment"] == MODEL_CONTRADICTED
    assert learning["revised"] is True
    assert abs(learning["weights_after"]["x->y"] - TRUE_WEIGHTS[("x", "y")]) < (
        4 * learning["standard_errors"]["x->y"]
    )
    assert voyage["episode_2_same_process"]["status"] == ACT
    assert voyage["episode_2_same_process"]["selected"] == "raise_z=1.0"
    assert voyage["decision_changed"] is True


def test_standalone_replay_and_negative_transfer(voyage):
    assert voyage["replay_episode_1"]["identical"] is True
    assert voyage["negative_transfer_guard"]["guard_held"] is True
    assert voyage["negative_transfer_guard"]["other_domain_selected"] == "raise_x=1.0"


def test_unbound_restart_is_unavailable_not_certified(voyage):
    assert voyage["restart"]["available"] is False
    assert "UNAVAILABLE" in voyage["restart"]["reason"]
    assert not voyage["learning"]["persisted"].get("available", False)


def test_unavailable_custody_cannot_silently_create_private_store(tmp_path, monkeypatch):
    # Failure-path injection works in both source and standalone test contexts.
    # The installed import-origin probe separately enforces the sibling boundary.
    monkeypatch.setattr(custody, "theseus_available", lambda: False)
    with pytest.raises(CustodyUnavailable, match="UNAVAILABLE"):
        open_theseus_custody(tmp_path / "must-not-exist", hmac_key=b"x" * 32)
    assert not (tmp_path / "must-not-exist").exists()
