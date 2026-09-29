from __future__ import annotations

import json

from al_haras_pythia import pythia_guardian_api


def test_pythia_guardian_uses_repository_local_toe(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "AL_HARAS_SUBSCRIPTION_KEYS",
        json.dumps({"test": "k" * 32}),
    )
    monkeypatch.setenv("AL_HARAS_DATA_DIR", str(tmp_path))
    pythia_guardian_api.cache_clear()
    api = pythia_guardian_api()
    assert api.evidence_provider is not None
    assert api.evidence_provider.__module__ == "al_haras_pythia"
    assert api.public_status()["configured"] is True
