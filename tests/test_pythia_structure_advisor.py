from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np

from Intelligence.mining_structure_advisor import (
    active_model,
    advise_faces,
    clear_active_model,
    install_from_pythia,
)
from Intelligence.mining_structure_training import (
    DEFAULT_CORPUS_CSV,
    DEFAULT_CORPUS_MANIFEST,
    train_pythia_structure,
)
from Intelligence.pythia_learning import PythiaLearning
from chronus.mla1517.mining.pythia_search import (
    COARSE_FACE_COUNT,
    DUAL_VERTEX_COUNT,
    precompute_pythia_search,
    vertex_itinerary,
)


class _Store:
    def __init__(self, tmp_path: Path):
        self.tmp_path = tmp_path
        self.runs = []

    def record_run(self, kind, payload):
        self.runs.append((kind, dict(payload)))
        return {"kind": kind, "payload": dict(payload)}

    def save(self):
        path = self.tmp_path / "snapshot.json"
        path.write_text("{}", encoding="utf-8")
        return path


def test_trained_structure_installs_read_only_advisor(tmp_path):
    clear_active_model()
    learner = PythiaLearning(n_units=32)
    store = _Store(tmp_path)
    orchestrator = SimpleNamespace(pythia=learner, store=store)

    report = train_pythia_structure(
        orchestrator,
        DEFAULT_CORPUS_CSV,
        DEFAULT_CORPUS_MANIFEST,
        persist=False,
    )
    evidence_before = {key: list(value) for key, value in learner._evidence.items()}
    totals_before = list(learner._totals)
    weights_before = learner.weights.copy()

    snapshot = install_from_pythia(learner)
    advice = advise_faces(1_000_000, 4_096)

    assert report.rows_train == 160
    assert snapshot.reference_count == 160
    assert active_model() is snapshot
    assert advice.state == "ACTIVE"
    assert advice.reference_count == 160
    assert advice.model_digest == snapshot.model_digest
    assert advice.preferred_face is not None
    assert 0 <= advice.preferred_face < COARSE_FACE_COUNT
    assert len(advice.scores) == COARSE_FACE_COUNT
    assert all(score is None or np.isfinite(score) for score in advice.scores)
    assert advice.proof_authority is False
    assert advice.preserves_candidate_membership is True

    # Runtime advice is read-only: scoring a live lease must not teach PYTHIA.
    assert learner._evidence == evidence_before
    assert learner._totals == totals_before
    assert np.array_equal(learner.weights, weights_before)
    clear_active_model()


def test_untrained_advisor_is_explicitly_unavailable():
    clear_active_model()
    advice = advise_faces(0, 64)
    assert advice.state == "UNAVAILABLE_UNTRAINED"
    assert advice.preferred_face is None
    assert advice.model_digest is None
    assert advice.proof_authority is False


def test_learned_face_scores_reorder_without_losing_any_of_600_vertices():
    state = precompute_pythia_search()
    header = bytes(80)
    scores = tuple(1.0 if face == 5 else 0.0 for face in range(COARSE_FACE_COUNT))

    baseline = vertex_itinerary(header, state)
    learned = vertex_itinerary(
        header,
        state,
        structure_face_scores=scores,
    )

    assert len(baseline) == DUAL_VERTEX_COUNT
    assert len(learned) == DUAL_VERTEX_COUNT
    assert set(baseline) == set(range(DUAL_VERTEX_COUNT))
    assert set(learned) == set(range(DUAL_VERTEX_COUNT))
    assert state.coarse_anchor[learned[0]] == 5


def test_explicit_preferred_face_remains_above_learned_refinement():
    state = precompute_pythia_search()
    header = bytes(80)
    scores = tuple(1.0 if face == 5 else 0.0 for face in range(COARSE_FACE_COUNT))

    order = vertex_itinerary(
        header,
        state,
        preferred_face=7,
        structure_face_scores=scores,
    )

    assert len(order) == DUAL_VERTEX_COUNT
    assert len(set(order)) == DUAL_VERTEX_COUNT
    assert state.coarse_anchor[order[0]] == 7


def test_invalid_structural_scores_fail_closed():
    state = precompute_pythia_search()
    header = bytes(80)

    try:
        vertex_itinerary(header, state, structure_face_scores=(0.0,) * 31)
    except ValueError as exc:
        assert "32 entries" in str(exc)
    else:
        raise AssertionError("31-face structural advice must be refused")

    bad = [0.0] * COARSE_FACE_COUNT
    bad[3] = float("nan")
    try:
        vertex_itinerary(header, state, structure_face_scores=bad)
    except ValueError as exc:
        assert "finite or None" in str(exc)
    else:
        raise AssertionError("non-finite structural advice must be refused")
