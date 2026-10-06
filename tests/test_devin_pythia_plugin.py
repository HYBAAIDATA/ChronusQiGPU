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


def test_plugin_metadata_is_private_v04_euclid_aptitude():
    manifest = json.loads(
        (PLUGIN / ".devin-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    assert manifest["name"] == "pythia"
    assert manifest["version"] == "0.4.1"
    assert manifest["license"] == "UNLICENSED"
    assert "EUCLID aptitude" in manifest["description"]


def test_required_manifest_declares_mandatory_session_scope():
    manifest = json.loads(
        (ROOT / "plugins" / "ORG_REQUIRED_MANIFEST.json").read_text(
            encoding="utf-8"
        )
    )
    augmentation = manifest["augmentation"]
    assert augmentation["identity"] == "EUCLID_APTITUDE"
    assert augmentation["activation"] == "MANDATORY_SESSION_START"
    assert augmentation["reinvocation"] == "POST_COMPACTION"
    assert augmentation["scope"] == "SESSION"
    assert "plugins/pythia/skills" in augmentation["skill_roots"]
    assert "Intelligence/skills" in augmentation["skill_roots"]


def test_plugin_status_invokes_complete_plugin_and_euclid_skill_set(
    tmp_path, monkeypatch
):
    plugin_status = _load("plugin_status_v04_test", SCRIPTS / "plugin_status.py")
    monkeypatch.setattr(plugin_status, "RECEIPT", tmp_path / "runtime.json")
    monkeypatch.setattr(plugin_status, "JOURNAL", tmp_path / "checkpoint.jsonl")

    before = plugin_status.build_status()
    assert before["augmentation"] == "EUCLID_APTITUDE"
    assert before["mandatory_skills_complete"] is False

    status = plugin_status.build_status(
        event="SessionStart",
        invoke_all=True,
    )

    mandatory = set(status["mandatory_skills"])
    invoked = set(status["skills_invoked"])
    assert status["plugin"] == "pythia"
    assert status["plugin_version"] == "0.4.1"
    assert len(status["aptitude_digest_sha256"]) == 64
    assert status["mandatory_skills_complete"] is True
    assert status["mandatory_skills_missing"] == []
    assert mandatory
    assert mandatory <= invoked
    assert "plugin:pythia-long-context" in mandatory
    assert "plugin:pythia-evidence-pack" in mandatory
    assert "euclid:systematic-debugging" in mandatory
    assert "euclid:verification-before-completion" in mandatory
    assert "euclid:counterfactual-analysis" in mandatory
    assert "euclid:codebase-healing" in mandatory
    assert "SessionStart" in status["hook_events"]


def test_lifecycle_hooks_force_invocation_on_start_and_after_compaction():
    start = (SCRIPTS / "session_start.py").read_text(encoding="utf-8")
    compact = (SCRIPTS / "post_compaction.py").read_text(encoding="utf-8")

    assert 'build_status(event="SessionStart", invoke_all=True)' in start
    assert 'build_status(event="PostCompaction", invoke_all=True)' in compact
    assert "mandatory_skills_complete" in start
    assert "mandatory_skills_complete" in compact
    assert "_skill_bundle()" in start
    assert "_skill_bundle()" in compact


def test_lifecycle_hooks_resolve_via_plugin_root_not_cwd():
    """Hook commands must not depend on the session working directory.

    The plugin is managed-installed, so its hooks fire in sessions whose cwd
    is not the repository root (observed: C:\\Windows\\system32). Commands
    must anchor on DEVIN_PLUGIN_ROOT, which plugin hooks receive.
    """
    hooks = json.loads((PLUGIN / "hooks.json").read_text(encoding="utf-8"))
    commands = [
        hook["command"]
        for entries in hooks.values()
        for entry in entries
        for hook in entry["hooks"]
    ]
    assert len(commands) == 3
    for command in commands:
        assert "DEVIN_PLUGIN_ROOT" in command
        assert command.startswith("python ")


def test_workspace_resolution_prefers_session_project_dir(
    tmp_path, monkeypatch
):
    plugin_status = _load(
        "plugin_status_workspace_test", SCRIPTS / "plugin_status.py"
    )
    workspace = tmp_path / "PhiMiner"
    (workspace / "plugins" / "pythia" / "skills").mkdir(parents=True)
    (workspace / "Intelligence" / "skills").mkdir(parents=True)
    monkeypatch.setenv("DEVIN_PROJECT_DIR", str(workspace))

    assert plugin_status._resolve_workspace_root() == workspace.resolve()
    assert plugin_status._looks_like_workspace(workspace)


def test_workspace_resolution_rejects_foreign_directories(
    tmp_path, monkeypatch
):
    plugin_status = _load(
        "plugin_status_foreign_test", SCRIPTS / "plugin_status.py"
    )
    foreign = tmp_path / "Windows" / "system32"
    foreign.mkdir(parents=True)
    monkeypatch.setenv("DEVIN_PROJECT_DIR", str(foreign))
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.chdir(foreign)
    # Simulate the script running from the managed-plugin cache instead of
    # the repository checkout.
    monkeypatch.setattr(
        plugin_status, "__file__", str(foreign / "cache" / "plugin_status.py")
    )

    assert not plugin_status._looks_like_workspace(foreign)
    assert plugin_status._resolve_workspace_root() == foreign.resolve()


def test_stop_gate_noops_outside_workspace(tmp_path, monkeypatch, capsys):
    stop_gate = _load_with_scripts(
        "stop_gate_noworkspace_test",
        SCRIPTS / "stop_gate.py",
    )
    monkeypatch.setattr(stop_gate, "WORKSPACE_AVAILABLE", False)
    assert stop_gate.main() == 0
    assert capsys.readouterr().out == ""


def test_plugin_product_skill_preserves_canonical_authority_language():
    skill = (PLUGIN / "skills" / "hyba-products" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "PYTHIA is not a HYBA product" in skill
    assert "THESEUS" in skill and "durable custody" in skill
    assert "OVID" in skill and "transformation" in skill


def _aptitude_status(plugin_sha: str = "plugin-sha") -> dict:
    skills = [
        "plugin:pythia-long-context",
        "plugin:pythia-evidence-pack",
        "euclid:systematic-debugging",
        "euclid:verification-before-completion",
    ]
    return {
        "plugin_version": "0.4.1",
        "augmentation": "EUCLID_APTITUDE",
        "plugin_source_sha": plugin_sha,
        "workspace_head_sha": "work-sha",
        "mandatory_skills": skills,
        "skills_invoked": skills,
        "mandatory_skills_complete": True,
        "mandatory_skills_missing": [],
        "aptitude_digest_sha256": "a" * 64,
    }


def test_engineering_evidence_is_hash_chained_and_detects_tamper(
    tmp_path, monkeypatch
):
    evidence = _load_with_scripts(
        "engineering_evidence_chain_v04_test",
        SCRIPTS / "engineering_evidence.py",
    )
    ledger = tmp_path / "evidence.jsonl"
    monkeypatch.setattr(evidence, "build_status", _aptitude_status)
    monkeypatch.setattr(evidence, "write_runtime_receipt", lambda _: None)

    first = evidence.record_event(
        "TASK_STARTED",
        task_id="task-1",
        path=ledger,
    )
    second = evidence.record_event(
        "ROOT_CAUSE",
        task_id="task-1",
        payload={"summary": "first failing transition"},
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


def test_task_pack_snapshots_session_aptitude_without_owning_skills(
    tmp_path, monkeypatch
):
    evidence = _load_with_scripts(
        "engineering_evidence_pack_v04_test",
        SCRIPTS / "engineering_evidence.py",
    )
    ledger = tmp_path / "evidence.jsonl"
    monkeypatch.setattr(evidence, "build_status", _aptitude_status)
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
    assert pack["session_aptitude"]["augmentation"] == "EUCLID_APTITUDE"
    assert pack["session_aptitude"]["mandatory_skills_complete"] is True
    assert pack["session_aptitude"]["aptitude_digest_sha256"] == "a" * 64
    assert pack["session_aptitude"]["skills_invoked"]
    assert "skills_invoked" not in {
        key for key in pack if key != "session_aptitude"
    }
    assert "plugin-sha" in pack["plugin_source_shas"]


def _write_valid_pack(
    root: Path,
    stop_gate,
    task_id: str,
    plugin_sha: str,
) -> Path:
    pack = {
        "schema": "pythia.devin-engineering-pack/1",
        "task_id": task_id,
        "sealed_at": "2026-10-06T17:30:00Z",
        "plugin_source_shas": [plugin_sha],
        "workspace_start_sha": "a",
        "workspace_end_sha": "b",
        "session_aptitude": {
            "augmentation": "EUCLID_APTITUDE",
            "mandatory_skills_complete": True,
            "mandatory_skills": ["euclid:systematic-debugging"],
            "skills_invoked": ["euclid:systematic-debugging"],
            "aptitude_digest_sha256": "b" * 64,
        },
        "event_count": 3,
        "event_hashes": ["1", "2", "3"],
        "verification": {"runs": 1, "passed": 1, "failed": 0},
        "completion_gate": {
            "decision": "pass",
            "classification": "READY_FOR_REVIEW",
        },
        "ledger_tip_sha256": "tip",
        "claim_boundary": "observed task outcome plus session aptitude snapshot",
    }
    digest = hashlib.sha256(stop_gate._canonical(pack)).hexdigest()
    pack["pack_sha256"] = digest
    path = root / "evidence" / "devin" / task_id / f"{digest}.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(pack), encoding="utf-8")
    return path


def _write_checkpoint(
    root: Path,
    task_id: str,
    plugin_sha: str,
    pack_path: Path,
) -> Path:
    journal = root / "checkpoint.jsonl"
    journal.write_text(
        json.dumps(
            {
                "task_id": task_id,
                "goal": "audit",
                "done": "verified",
                "next": "done",
                "files": ["x"],
                "plugin_source_sha": plugin_sha,
                "verification": ["pytest -> passed"],
                "evidence_pack": str(pack_path.relative_to(root)),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return journal


def test_stop_gate_requires_complete_session_aptitude_and_valid_pack(
    tmp_path, monkeypatch, capsys
):
    stop_gate = _load_with_scripts(
        "stop_gate_pack_v04_test",
        SCRIPTS / "stop_gate.py",
    )
    task_id = "task-3"
    plugin_sha = "plugin-sha"
    pack_path = _write_valid_pack(tmp_path, stop_gate, task_id, plugin_sha)
    journal = _write_checkpoint(tmp_path, task_id, plugin_sha, pack_path)

    monkeypatch.setattr(stop_gate, "ROOT", tmp_path)
    monkeypatch.setattr(stop_gate, "JOURNAL", journal)
    monkeypatch.setattr(
        stop_gate,
        "build_status",
        lambda **_: {
            "plugin_source_sha": plugin_sha,
            "mandatory_skills_complete": True,
            "mandatory_skills_missing": [],
            "aptitude_digest_sha256": "b" * 64,
        },
    )
    monkeypatch.setattr(stop_gate, "write_runtime_receipt", lambda _: None)

    assert stop_gate.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["decision"] == "pass"
    assert result["task_id"] == task_id


def test_stop_gate_blocks_if_session_aptitude_is_incomplete(
    tmp_path, monkeypatch, capsys
):
    stop_gate = _load_with_scripts(
        "stop_gate_incomplete_aptitude_test",
        SCRIPTS / "stop_gate.py",
    )
    task_id = "task-4"
    plugin_sha = "plugin-sha"
    pack_path = _write_valid_pack(tmp_path, stop_gate, task_id, plugin_sha)
    journal = _write_checkpoint(tmp_path, task_id, plugin_sha, pack_path)

    monkeypatch.setattr(stop_gate, "ROOT", tmp_path)
    monkeypatch.setattr(stop_gate, "JOURNAL", journal)
    monkeypatch.setattr(
        stop_gate,
        "build_status",
        lambda **_: {
            "plugin_source_sha": plugin_sha,
            "mandatory_skills_complete": False,
            "mandatory_skills_missing": ["euclid:counterfactual-analysis"],
            "aptitude_digest_sha256": "b" * 64,
        },
    )
    monkeypatch.setattr(stop_gate, "write_runtime_receipt", lambda _: None)

    assert stop_gate.main() == 2
    result = json.loads(capsys.readouterr().out)
    assert "Mandatory EUCLID aptitude" in result["reason"]
    assert "counterfactual-analysis" in result["reason"]


def test_stop_gate_rejects_pack_without_aptitude_digest(
    tmp_path, monkeypatch, capsys
):
    stop_gate = _load_with_scripts(
        "stop_gate_missing_digest_v04_test",
        SCRIPTS / "stop_gate.py",
    )
    task_id = "task-missing-digest"
    plugin_sha = "plugin-sha"
    pack_path = _write_valid_pack(tmp_path, stop_gate, task_id, plugin_sha)
    pack = json.loads(pack_path.read_text(encoding="utf-8"))
    pack["session_aptitude"].pop("aptitude_digest_sha256", None)

    unsigned = dict(pack)
    unsigned.pop("pack_sha256", None)
    digest = hashlib.sha256(stop_gate._canonical(unsigned)).hexdigest()
    pack["pack_sha256"] = digest
    replacement = pack_path.with_name(f"{digest}.json")
    replacement.write_text(json.dumps(pack), encoding="utf-8")
    pack_path.unlink()

    journal = _write_checkpoint(tmp_path, task_id, plugin_sha, replacement)
    monkeypatch.setattr(stop_gate, "ROOT", tmp_path)
    monkeypatch.setattr(stop_gate, "JOURNAL", journal)
    monkeypatch.setattr(
        stop_gate,
        "build_status",
        lambda **_: {
            "plugin_source_sha": plugin_sha,
            "mandatory_skills_complete": True,
            "mandatory_skills_missing": [],
            "aptitude_digest_sha256": "b" * 64,
        },
    )
    monkeypatch.setattr(stop_gate, "write_runtime_receipt", lambda _: None)

    assert stop_gate.main() == 2
    result = json.loads(capsys.readouterr().out)
    assert "aptitude digest" in result["reason"]


def test_stop_gate_rejects_tampered_pack(tmp_path, monkeypatch, capsys):
    stop_gate = _load_with_scripts(
        "stop_gate_tamper_v04_test",
        SCRIPTS / "stop_gate.py",
    )
    task_id = "task-5"
    plugin_sha = "plugin-sha"
    pack_path = _write_valid_pack(tmp_path, stop_gate, task_id, plugin_sha)
    pack = json.loads(pack_path.read_text(encoding="utf-8"))
    pack["completion_gate"]["classification"] = "TAMPERED"
    pack_path.write_text(json.dumps(pack), encoding="utf-8")
    journal = _write_checkpoint(tmp_path, task_id, plugin_sha, pack_path)

    monkeypatch.setattr(stop_gate, "ROOT", tmp_path)
    monkeypatch.setattr(stop_gate, "JOURNAL", journal)
    monkeypatch.setattr(
        stop_gate,
        "build_status",
        lambda **_: {
            "plugin_source_sha": plugin_sha,
            "mandatory_skills_complete": True,
            "mandatory_skills_missing": [],
        },
    )
    monkeypatch.setattr(stop_gate, "write_runtime_receipt", lambda _: None)

    assert stop_gate.main() == 2
    result = json.loads(capsys.readouterr().out)
    assert "SHA256 mismatch" in result["reason"]
