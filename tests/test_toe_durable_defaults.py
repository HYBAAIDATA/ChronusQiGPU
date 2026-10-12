"""Configuration tests only: not a trained-model or hardware qualification."""

import os

from toe.engine import PredictiveEngine


def test_model_default_uses_durable_intelligence_volume(monkeypatch, tmp_path):
    monkeypatch.setenv("PYTHIA_INTELLIGENCE_DIR", str(tmp_path))
    config = PredictiveEngine._default_config(object())
    assert config["model_dir"] == os.path.join(str(tmp_path), "models")


def test_local_default_remains_compatible_without_volume(monkeypatch):
    monkeypatch.delenv("PYTHIA_INTELLIGENCE_DIR", raising=False)
    assert PredictiveEngine._default_config(object())["model_dir"] == "models/"
