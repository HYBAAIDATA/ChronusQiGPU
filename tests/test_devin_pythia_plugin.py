from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "plugins" / "pythia" / "scripts"
PLUGIN = ROOT / "plugins" / "pythia"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_with_scripts(name: str, path: Path):
    sys.path.insert(0, str(SCRIPTS))
    try:
        return _load(name, path)
    finally:
        sys.path.remove(str(SCRIPTS))


def test_plugin_metadata_is_private_v03_and_has_augmentation_skills():
    manifest = json.loads(
        (PLUGIN / ".devin-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    assert manifest["name"] == "pythia"
    assert manifest["version"] == "0.3.0"
    assert manifest["license"] == "UNLICENSED"

    required = {
        "pythia-plugin-status",
        "pythia-long-context",
        "pythia-repo-ontology",
        "pythia-systematic-debugging",
        "pythia-tdd",
        "pythia-agent-fabric",
        "pythia-engineering-quality",
        "pythia-promotion-gate",
        "pythia-deploy-rollback",
        "pythia-evidence-pack",
        "pythia-finish-the-job",
        "pythia-stop-check",
    }
    present = {
        path.parent.name
        for path in (PLUGIN / "skills").glob("*/SKILL.md")
        if path.is_file()
    }
    assert required <= present


def test_plugin_product_skill_preserves_canonical_authority_language():
    skill = (PLUGIN / "skills" / "hyba-products" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "PYTHIA is not a HYBA product" in skill
    assert "THESEUS" in skill and "durable custody" in skill
    assert "OVID" in skill and "transformation" in skill
    assert "Never repeat the superseded model" in skill


def test_plugin_status_reports_source_revision_and_available_skills(
    tmp_path, monkeypatch
):
    plugin_status = _load("plugin_status_test", SCRIPTS / "plugin_status.py")
    monkeypatch.setattr(plugin_status, "RECEIPT", tmp_path / "runtime.json")
    monkeypatch.setattr(plugin_status, "JOURNAL", tmp_path / "checkpoint.jsonl")

    status = plugin_status.build_status(record_skill="pythia-plugin-status")

    assert status["plugin"] == "pythia"
    assert status["plugin_version"] == "0.3.0"
    assert status["private_repo_local"] is True
    assert status["plugin_source_sha"] != "UNAVAILABLE"
    assert "pythia-evidence-pack" in status["available_skills"]
    assert "pythia-plugin-status" in status["skills_invoked"]
    assert "checkpoint-assisted continuity" in status["memory_mode"]


def test_engineering_evidence_is_hash_chained_and_detects_tamper(
    tmp_path, monkeypatch
):
    evidence = _load_with_scripts(
        "engineering_evidence_chain_test",
        SCRIPTS / "engineering_evidence.py",
    )
    ledger = tmp_path / "evidence.jsonl"
    monkeypatch.setattr(
        evidence,
        "build_status",
        lambda: {
            "plugin_version": "0.3.0",
            "plugin_source_sha": "plugin-sha",
            "workspace_head_sha": "work-sha",
            "skills_invoked": ["pythia-plugin-status"],
        },
    )
    monkeypatch.setattr(evidence, "write_runtime_receipt", lambda _: None)

    first = evidence.record_event(
        "TASK_STARTED",
        task_id="task-1",
        path=ledger,
    )
    second = evidence.record_event(
        "SKILL_INVOKED",
        task_id="task-1",
        skill="pythia-repo-ontology",
        path=ledger,
    )
    events = evidence._read_events(ledger)

    assert first["prev_event_sha256"] == "GENESIS"
    assert second["prev_event_sha256"] == first["event_sha256"]
    assert evidence.verify_chain(events) == (True, None)

    tampered = dict(events[0])
    tampered["payload"] = {"tampered": True}
    ledger.write_text(
        json.dumps(tampered) + "\n" + json.dumps(events[1]) + "\n",
        encoding="utf-8",
    )
    ok, reason = evidence.verify_chain(evidence._read_events(ledger))
    assert ok is False
    assert "hash mismatch" in str(reason)


def test_engineering_evidence_seals_content_addressed_pack(
    tmp_path, monkeypatch
):
    evidence = _load_with_scripts(
        "engineering_evidence_pack_test",
        SCRIPTS / "engineering_evidence.py",
    )
    ledger = tmp_path / "evidence.jsonl"
    runtime_skills = [
        "pythia-plugin-status",
        "pythia-long-context",
        "pythia-engineering-quality",
        "pythia-evidence-pack",
    ]
    monkeypatch.setattr(
        evidence,
        "build_status",
        lambda: {
            "plugin_version": "0.3.0",
            "plugin_source_sha": "plugin-sha",
            "workspace_head_sha": "work-sha",
            "skills_invoked": runtime_skills,
        },
    )
    monkeypatch.setattr(evidence, "write_runtime_receipt", lambda _: None)
    monkeypatch.setattr(evidence, "EVENT_LOG", ledger)

    evidence.record_event("TASK_STARTED", task_id="task-2")
    evidence.record_event(
        "VERIFICATION",
        task_id="task-2",
        payload={"passed": True, "exit_code": 0},
    )
    evidence.record_event(
        "COMPLETION_GATE",
        task_id="task-2",
        payload={"decision": "pass", "classification": "READY_FOR_REVIEW"},
    )

    output = tmp_path / "published"
    path = evidence.seal_pack("task-2", output)
    pack = json.loads(path.read_text(encoding="utf-8"))

    assert path.stem == pack["pack_sha256"]
    assert pack["task_id"] == "task-2"
    assert pack["verification"]["runs"] == 1
    assert pack["verification"]["passed"] == 1
    assert set(runtime_skills) <= set(pack["skills_invoked"])
    assert "plugin-sha" in pack["plugin_source_shas"]


def _write_valid_pack(root: Path, stop_gate, task_id: str, plugin_sha: str) -> Path:
    pack = {
        "schema": "pythia.devin-engineering-pack/1",
        "task_id": task_id,
        "sealed_at": "2026-10-06T16:30:00Z",
        "plugin_source_shas": [plugin_sha],
        "workspace_start_sha": "a",
        "workspace_end_sha": "b",
        "skills_invoked": sorted(stop_gate._REQUIRED_PACK_SKILLS),
        "event_count": 4,
        "event_hashes": ["1", "2", "3", "4"],
        "verification": {"runs": 1, "passed": 1, "failed": 0},
        "completion_gate": {
            "decision": "pass",
            "classification": "READY_FOR_REVIEW",
        },
        "ledger_tip_sha256": "tip",
        "claim_boundary": "observed evidence only",
    }
    digest = hashlib.sha256(stop_gate._canonical(pack)).hexdigest()
    pack["pack_sha256"] = digest
    path = root / "evidence" / "devin" / task_id / f"{digest}.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(pack), encoding="utf-8")
    return path


def test_stop_gate_requires_valid_content_addressed_pack(
    tmp_path, monkeypatch, capsys
):
    stop_gate = _load_with_scripts(
        "stop_gate_pack_test",
        SCRIPTS / "stop_gate.py",
    )
    task_id = "task-3"
    plugin_sha = "plugin-sha"
    pack_path = _write_valid_pack(tmp_path, stop_gate, task_id, plugin_sha)
    journal = tmp_path / "checkpoint.jsonl"
    journal.write_text(
        json.dumps(
            {
                "task_id": task_id,
                "goal": "audit",
                "done": "verified",
                "next": "done",
                "files": ["x"],
                "plugin_source_sha": plugin_sha,
                "skills_invoked": sorted(stop_gate._REQUIRED_SKILLS),
                "verification": ["pytest tests/example.py -q -> passed"],
                "evidence_pack": str(pack_path.relative_to(tmp_path)),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(stop_gate, "ROOT", tmp_path)
    monkeypatch.setattr(stop_gate, "JOURNAL", journal)
    monkeypatch.setattr(
        stop_gate,
        "build_status",
        lambda **_: {
            "plugin_source_sha": plugin_sha,
            "skills_invoked": sorted(stop_gate._REQUIRED_SKILLS),
        },
    )
    monkeypatch.setattr(stop_gate, "write_runtime_receipt", lambda _: None)

    assert stop_gate.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["decision"] == "pass"
    assert result["task_id"] == task_id


def test_stop_gate_rejects_tampered_pack(tmp_path, monkeypatch, capsys):
    stop_gate = _load_with_scripts(
        "stop_gate_tamper_test",
        SCRIPTS / "stop_gate.py",
    )
    task_id = "task-4"
    plugin_sha = "plugin-sha"
    pack_path = _write_valid_pack(tmp_path, stop_gate, task_id, plugin_sha)
    pack = json.loads(pack_path.read_text(encoding="utf-8"))
    pack["completion_gate"]["classification"] = "TAMPERED"
    pack_path.write_text(json.dumps(pack), encoding="utf-8")

    journal = tmp_path / "checkpoint.jsonl"
    journal.write_text(
        json.dumps(
            {
                "task_id": task_id,
                "next": "done",
                "plugin_source_sha": plugin_sha,
                "verification": ["verified"],
                "evidence_pack": str(pack_path.relative_to(tmp_path)),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(stop_gate, "ROOT", tmp_path)
    monkeypatch.setattr(stop_gate, "JOURNAL", journal)
    monkeypatch.setattr(
        stop_gate,
        "build_status",
        lambda **_: {
            "plugin_source_sha": plugin_sha,
            "skills_invoked": sorted(stop_gate._REQUIRED_SKILLS),
        },
    )
    monkeypatch.setattr(stop_gate, "write_runtime_receipt", lambda _: None)

    assert stop_gate.main() == 2
    result = json.loads(capsys.readouterr().out)
    assert "SHA256 mismatch" in result["reason"]
