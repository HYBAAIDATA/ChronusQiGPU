from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "plugins" / "pythia" / "scripts"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_plugin_metadata_is_private_and_has_status_skill():
    manifest = json.loads(
        (ROOT / "plugins" / "pythia" / ".devin-plugin" / "plugin.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["name"] == "pythia"
    assert manifest["version"] == "0.2.0"
    assert manifest["license"] == "UNLICENSED"
    assert (ROOT / "plugins" / "pythia" / "skills" / "pythia-plugin-status" / "SKILL.md").is_file()


def test_plugin_product_skill_preserves_canonical_authority_language():
    skill = (
        ROOT / "plugins" / "pythia" / "skills" / "hyba-products" / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert "PYTHIA is not a HYBA product" in skill
    assert "THESEUS" in skill and "durable custody" in skill
    assert "OVID" in skill and "transformation" in skill
    assert "Never repeat the superseded model" in skill


def test_plugin_status_reports_source_revision_and_available_skills(tmp_path, monkeypatch):
    plugin_status = _load("plugin_status_test", SCRIPTS / "plugin_status.py")
    monkeypatch.setattr(plugin_status, "RECEIPT", tmp_path / "runtime.json")
    monkeypatch.setattr(plugin_status, "JOURNAL", tmp_path / "checkpoint.jsonl")

    status = plugin_status.build_status(record_skill="pythia-plugin-status")

    assert status["plugin"] == "pythia"
    assert status["plugin_version"] == "0.2.0"
    assert status["private_repo_local"] is True
    assert status["plugin_source_sha"] != "UNAVAILABLE"
    assert "pythia-plugin-status" in status["available_skills"]
    assert "pythia-plugin-status" in status["skills_invoked"]
    assert "checkpoint-assisted continuity" in status["memory_mode"]


def test_stop_gate_blocks_missing_checkpoint(tmp_path, monkeypatch, capsys):
    sys.path.insert(0, str(SCRIPTS))
    try:
        stop_gate = _load("stop_gate_missing_test", SCRIPTS / "stop_gate.py")
    finally:
        sys.path.remove(str(SCRIPTS))

    monkeypatch.setattr(stop_gate, "JOURNAL", tmp_path / "missing.jsonl")
    monkeypatch.setattr(
        stop_gate,
        "build_status",
        lambda **_: {
            "plugin_source_sha": "abc",
            "skills_invoked": sorted(stop_gate._REQUIRED_SKILLS),
        },
    )
    monkeypatch.setattr(stop_gate, "write_runtime_receipt", lambda _: None)

    assert stop_gate.main() == 2
    assert "checkpoint is missing" in json.loads(capsys.readouterr().out)["reason"]


def test_stop_gate_requires_bound_revision_skills_and_verification(tmp_path, monkeypatch):
    sys.path.insert(0, str(SCRIPTS))
    try:
        stop_gate = _load("stop_gate_success_test", SCRIPTS / "stop_gate.py")
    finally:
        sys.path.remove(str(SCRIPTS))

    journal = tmp_path / "checkpoint.jsonl"
    journal.write_text(
        json.dumps(
            {
                "goal": "audit",
                "done": "verified",
                "next": "done",
                "files": ["x"],
                "plugin_source_sha": "abc",
                "skills_invoked": sorted(stop_gate._REQUIRED_SKILLS),
                "verification": ["pytest tests/example.py -q -> passed"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(stop_gate, "JOURNAL", journal)
    monkeypatch.setattr(
        stop_gate,
        "build_status",
        lambda **_: {
            "plugin_source_sha": "abc",
            "skills_invoked": sorted(stop_gate._REQUIRED_SKILLS),
        },
    )
    monkeypatch.setattr(stop_gate, "write_runtime_receipt", lambda _: None)

    assert stop_gate.main() == 0
