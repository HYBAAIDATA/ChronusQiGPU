from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from Intelligence.mining_structure_training import (
    CorpusIntegrityError,
    load_nonce_corpus,
    split_by_height,
    structural_vector,
    train_pythia_structure,
)
from Intelligence.pythia_learning import PythiaLearning

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "artifacts" / "pythia_training" / "real_nonces_200.csv"
MANIFEST = ROOT / "artifacts" / "pythia_training" / "real_nonces_200.manifest.json"


class _Store:
    def __init__(self, tmp_path: Path):
        self.tmp_path = tmp_path
        self.runs = []
        self.saves = 0

    def record_run(self, kind, payload):
        self.runs.append((kind, dict(payload)))
        return {"kind": kind, "payload": dict(payload)}

    def save(self):
        self.saves += 1
        path = self.tmp_path / "memory_snapshot.json"
        path.write_text("{}", encoding="utf-8")
        return path


def test_corpus_is_bound_to_exact_200_real_rows():
    rows, manifest = load_nonce_corpus(CSV, MANIFEST)
    assert len(rows) == 200
    assert manifest["source_type"] == "real"
    assert manifest["synthetic_excluded"] is True
    assert manifest["verification_level"] == "bundle_local_pow_verified"
    assert min(r.height for r in rows) == 963991
    assert max(r.height for r in rows) == 965900


def test_feature_vector_is_exactly_32d_and_bounded():
    rows, _ = load_nonce_corpus(CSV, MANIFEST)
    vec = structural_vector(rows[0], rows[1])
    assert vec.shape == (32,)
    assert np.all(np.isfinite(vec))
    assert np.all(vec >= 0.0)
    assert np.all(vec <= 1.0)


def test_newest_twenty_percent_is_blind_holdout():
    rows, _ = load_nonce_corpus(CSV, MANIFEST)
    train, holdout = split_by_height(rows, 0.20)
    assert len(train) == 160
    assert len(holdout) == 40
    assert max(r.height for r in train) < min(r.height for r in holdout)


def test_structure_training_does_not_manufacture_failure_labels(tmp_path):
    learner = PythiaLearning(n_units=32)
    store = _Store(tmp_path)
    orchestrator = SimpleNamespace(pythia=learner, store=store)

    report = train_pythia_structure(orchestrator, CSV, MANIFEST, persist=True)

    assert report.rows_train == 160
    assert report.rows_holdout == 40
    assert report.rows_newly_taught == 160
    assert report.pythia_outcome_evidence_unchanged is True
    assert learner._totals == [0, 0]
    assert learner._evidence == {}
    assert len(learner.patterns()) == 160
    assert store.runs[-1][0] == "pythia_structure_training"
    assert store.saves == 1


def test_training_is_idempotent_for_same_corpus(tmp_path):
    learner = PythiaLearning(n_units=32)
    store = _Store(tmp_path)
    orchestrator = SimpleNamespace(pythia=learner, store=store)

    first = train_pythia_structure(orchestrator, CSV, MANIFEST, persist=False)
    second = train_pythia_structure(orchestrator, CSV, MANIFEST, persist=False)

    assert first.rows_newly_taught == 160
    assert second.rows_newly_taught == 0
    assert second.rows_already_known == 160
    assert len(learner.patterns()) == 160


def test_training_preserves_unrelated_pending_short_term_memory(tmp_path):
    learner = PythiaLearning(n_units=32)
    store = _Store(tmp_path)
    orchestrator = SimpleNamespace(pythia=learner, store=store)

    pending_id = learner.learn(
        np.linspace(0.0, 1.0, 32),
        mining_success=True,
        pattern_id=123456789,
    )
    assert len(learner._short_term) == 1
    evidence_before = {key: list(value) for key, value in learner._evidence.items()}
    totals_before = list(learner._totals)

    report = train_pythia_structure(orchestrator, CSV, MANIFEST, persist=False)

    assert report.rows_newly_taught == 160
    assert len(learner.patterns()) == 160
    assert len(learner._short_term) == 1
    assert learner._short_term[0]["pattern_id"] == pending_id
    assert learner._evidence == evidence_before
    assert learner._totals == totals_before


def test_synthetic_or_unbound_manifest_fails_closed(tmp_path):
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest["source_type"] = "synthetic"
    bad = tmp_path / "manifest.json"
    bad.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(CorpusIntegrityError):
        load_nonce_corpus(CSV, bad)

    manifest["source_type"] = "real"
    manifest["csv_sha256"] = "0" * 64
    bad.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(CorpusIntegrityError):
        load_nonce_corpus(CSV, bad)
