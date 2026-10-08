from __future__ import annotations

import json

import pytest
import al_haras_pythia
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
    assert api.public_status()["audit_durable"] is True


def test_every_privileged_route_operation_is_allowlisted():
    """Regression: a privileged route without an allowlisted op name denies
    every caller 403 OPERATION_NOT_ALLOWED (live-verified on /api/v1/tensor/*)."""
    import re
    from pathlib import Path

    import control_api
    from al_haras_pythia import _PYTHIA_ALLOWED_OPERATIONS

    source = Path(control_api.__file__).read_text(encoding="utf-8")
    literals = set(re.findall(r"['\"](/api/v1/[^'\"]+)['\"]", source))
    privileged = sorted(
        path
        for path in literals
        if path.startswith(control_api._PRIVILEGED_PREFIXES)
        and path not in control_api._PRIVILEGED_PREFIXES
    )
    assert privileged
    for path in privileged:
        operation = path.removeprefix("/api/v1/").replace("/", ".")
        assert operation in _PYTHIA_ALLOWED_OPERATIONS, (
            f"{path} derives operation {operation!r} which is not allowlisted"
        )


def test_tensor_execute_preflight_synthesizes_observation():
    """Privileged POSTs require an observation; tensor.execute synthesizes the
    same minimal map GETs receive so a natural execute body is admissible."""
    from control_api import _synthesize_preflight_observation

    body = {"operation": "add", "operands": [[1], [2]]}
    _synthesize_preflight_observation("/api/v1/tensor/execute", body)
    assert body["observation"] == {
        "operation": "tensor.execute",
        "resource": "tensor/execute",
    }
    caller = {"operation": "add", "observation": {"operation": "custom"}}
    _synthesize_preflight_observation("/api/v1/tensor/execute", caller)
    assert caller["observation"] == {"operation": "custom"}
    other = {"operation": "x"}
    _synthesize_preflight_observation("/api/v1/mining/start", other)
    assert "observation" not in other



def test_pythia_guardian_never_falls_back_to_in_memory_audit(monkeypatch):
    pythia_guardian_api.cache_clear()

    def unavailable(*args, **kwargs):
        raise RuntimeError("durable audit unavailable")

    monkeypatch.setattr(al_haras_pythia, "build_guardian", unavailable)
    with pytest.raises(RuntimeError, match="durable audit unavailable"):
        pythia_guardian_api()
    pythia_guardian_api.cache_clear()
