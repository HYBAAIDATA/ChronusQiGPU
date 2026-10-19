"""Full engine constructor/dispatch; positive receipt is explicitly a contract double."""

import subprocess
from pathlib import Path

import pytest

from Intelligence.salamander import SalamanderEngine
from Intelligence.salamander_transaction import ValidationResult, source_digest


class ReceiptContractDouble:
    """Tests host plumbing only. NOT an OS sandbox, test executor or production validator."""

    def __init__(self, passed=True):
        self.calls = []
        self.passed = passed

    def validate(self, path, baseline, candidate):
        self.calls.append((path, baseline, candidate))
        return ValidationResult(
            self.passed,
            source_digest(candidate),
            source_digest(baseline),
            1,
            True,
            "UNIT CONTRACT DOUBLE ONLY: no sandbox qualification",
        )


def make_repo(root):
    target = root / "Intelligence" / "unit.py"
    target.parent.mkdir()
    target.write_text("def value():\n    return 1\n")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    return target


def test_full_constructor_keeps_host_root_and_validator_in_one_controller(tmp_path):
    validator = ReceiptContractDouble()
    engine = SalamanderEngine(repo_root=tmp_path, source_validator=validator)
    assert engine.agentic_controller.repo_root == tmp_path
    assert engine.codebase_optimizer is engine.agentic_controller.optimizer
    assert engine.codebase_scanner is engine.agentic_controller.scanner
    assert engine.codebase_optimizer.validator is validator
    assert {"source-repair", "repository-review"} <= set(engine.skills)


def test_source_dispatch_can_publish_through_bound_contract_receipt(tmp_path):
    target = make_repo(tmp_path)
    baseline = target.read_bytes()
    candidate = "def value():\n    return 2\n"
    validator = ReceiptContractDouble()
    engine = SalamanderEngine(repo_root=tmp_path, source_validator=validator)
    result = engine.execute_skill(
        "source-repair", target_file=Path("Intelligence/unit.py"), replacement=candidate
    )
    assert result["status"] == "COMMITTED" and result["committed"] is True
    assert target.read_text() == candidate
    assert validator.calls == [(Path("Intelligence/unit.py"), baseline, candidate.encode())]
    assert not list(target.parent.glob("*.salamander.lock"))


def test_default_engine_cannot_silently_replace_missing_validator(tmp_path):
    target = make_repo(tmp_path)
    before = target.read_bytes()
    engine = SalamanderEngine(repo_root=tmp_path)
    result = engine.execute_skill("source-repair", target_file=target, replacement="x=2\n")
    assert result["committed"] is False
    assert "No isolated validator" in result["reason"]
    assert target.read_bytes() == before


def test_rejected_receipt_preserves_original_bytes(tmp_path):
    target = make_repo(tmp_path)
    before = target.read_bytes()
    engine = SalamanderEngine(repo_root=tmp_path, source_validator=ReceiptContractDouble(False))
    result = engine.execute_skill("source-repair", target_file=target, replacement="x=2\n")
    assert result["committed"] is False and target.read_bytes() == before


def test_source_dispatch_protects_tests_and_refuses_callback_parameters(tmp_path):
    make_repo(tmp_path)
    target = tmp_path / "Intelligence/test_unit.py"
    target.write_text("x=1\n")
    validator = ReceiptContractDouble()
    engine = SalamanderEngine(repo_root=tmp_path, source_validator=validator)
    result = engine.execute_skill("source-repair", target_file=target, replacement="x=2\n")
    assert result["committed"] is False and validator.calls == []
    with pytest.raises(TypeError):
        engine.execute_skill(
            "source-repair", target_file=target, replacement="x=2\n", test_callable=lambda: True
        )


def test_actual_audit_cycle_uses_host_repository_not_fresh_default_controller(tmp_path):
    make_repo(tmp_path)
    validator = ReceiptContractDouble()
    engine = SalamanderEngine(repo_root=tmp_path, source_validator=validator)
    controller = engine.agentic_controller
    result = engine.execute_skill("codebase-healing", auto_heal=False)
    assert "audit_summary" in result and result["healing_actions"] == []
    assert engine.agentic_controller is controller
    assert engine.agentic_controller.optimizer.validator is validator
    assert validator.calls == []


def test_constructor_does_not_swallow_broken_skill_loader(tmp_path, monkeypatch):
    from Intelligence import skill_loader

    def broken():
        raise RuntimeError("loader unavailable")

    monkeypatch.setattr(skill_loader, "load_skills", broken)
    with pytest.raises(RuntimeError, match="loader unavailable"):
        SalamanderEngine(repo_root=tmp_path)


def test_reload_does_not_replace_equipment_with_invalid_loader_result(tmp_path, monkeypatch):
    from Intelligence import skill_loader

    engine = SalamanderEngine(repo_root=tmp_path)
    before = engine.skills
    monkeypatch.setattr(skill_loader, "load_skills", lambda: None)
    with pytest.raises(TypeError, match="equipped-skill mapping"):
        engine.load_skills()
    assert engine.skills is before
