"""The control API serves even when an optional service cannot start.

The deployed image runs as an unprivileged user with the source tree
read-only; the repo engineer's store under <repo>/data could not be created
there, the exception escaped serve() before the socket was bound, and the
container never answered /healthz.
"""

from __future__ import annotations

import json
from pathlib import Path

import control_api
from Intelligence import repo_engineer


def test_the_repo_engineer_store_follows_the_intelligence_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("PYTHIA_INTELLIGENCE_DIR", str(tmp_path / "state"))
    assert repo_engineer.default_store_dir(Path("/app")) == tmp_path / "state" / "repo_engineer"
    monkeypatch.delenv("PYTHIA_INTELLIGENCE_DIR")
    assert repo_engineer.default_store_dir(Path("/repo")) == Path("/repo/data/repo_engineer")


def test_a_failing_repo_engineer_is_audited_not_fatal(monkeypatch, tmp_path):
    audit_path = tmp_path / "audit.jsonl"
    monkeypatch.setenv("PYTHIA_BOOT_AUDIT", str(audit_path))
    monkeypatch.setattr(control_api, "_AUDIT", None)

    def refuse():
        raise PermissionError(13, "Permission denied", "/app/data/repo_engineer")

    monkeypatch.setattr(control_api.system_fabric, "initialize_repo_engineer", refuse)
    assert control_api.start_repo_engineer() is False
    events = [json.loads(line) for line in audit_path.read_text().splitlines() if line.strip()]
    assert any(
        e.get("event") == "repo_engineer_unavailable"
        or "repo_engineer_unavailable" in json.dumps(e)
        for e in events
    )
