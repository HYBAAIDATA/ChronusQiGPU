"""Repair admission regressions; unit verdicts below are NOT sandbox qualification."""

from pathlib import Path

import pytest

from Intelligence.salamander_agentic import SalamanderAgenticOptimizer
from Intelligence.salamander_transaction import ValidationResult, source_digest

BASELINE = b"def answer():\n    return 41\n"
CANDIDATE = "def answer():\n    return 42\n"


@pytest.fixture
def source(tmp_path):
    target = tmp_path / "Intelligence" / "answer.py"
    target.parent.mkdir()
    target.write_bytes(BASELINE)
    return target


def unchanged(target):
    assert target.read_bytes() == BASELINE
    assert not target.with_suffix(".py.bak").exists()
    assert not list(target.parent.glob("*.salamander.lock"))
    assert not list(target.parent.glob(".salamander-*"))


class UnitVerdict:
    """Trusted-verifier contract double only; does not execute candidate code."""

    def __init__(self, target, **overrides):
        self.target = target
        self.overrides = overrides
        self.calls = 0

    def validate(self, relative_path, baseline, candidate):
        self.calls += 1
        # The live source must remain the baseline while validation occurs.
        assert self.target.read_bytes() == BASELINE
        assert relative_path == Path("Intelligence/answer.py")
        values = dict(
            passed=True,
            candidate_digest=source_digest(candidate),
            baseline_digest=source_digest(baseline),
            tests_run=2,
            isolated=True,
            reason="unit contract fixture only",
        )
        values.update(self.overrides)
        return ValidationResult(**values)


def test_no_validator_does_not_write(source, tmp_path):
    success, _ = SalamanderAgenticOptimizer(tmp_path).apply_repair_sandboxed(source, CANDIDATE)
    assert success is False
    unchanged(source)


@pytest.mark.parametrize("returned", [True, 1, "passed"])
def test_in_process_callbacks_are_not_isolation(source, tmp_path, returned):
    called = []

    def callback():
        called.append(True)
        return returned

    success, _ = SalamanderAgenticOptimizer(tmp_path).apply_repair_sandboxed(
        source, CANDIDATE, test_callable=callback
    )
    assert success is False
    assert called == []
    unchanged(source)


def test_shell_command_not_executed(source, tmp_path):
    marker = tmp_path / "command-was-run"
    command = f"touch '{marker}'"
    success, _ = SalamanderAgenticOptimizer(tmp_path).apply_repair_sandboxed(
        source, CANDIDATE, test_cmd=command
    )
    assert success is False
    assert not marker.exists()
    unchanged(source)


def test_legacy_command_does_not_enable_healing(source, tmp_path):
    optimizer = SalamanderAgenticOptimizer(tmp_path, verify_cmd="true")
    success, _ = optimizer.apply_repair_sandboxed(source, CANDIDATE, test_cmd=optimizer.verify_cmd)
    assert success is False
    unchanged(source)


@pytest.mark.parametrize(
    "overrides",
    [
        {"passed": False},
        {"passed": 1},
        {"isolated": False},
        {"isolated": 1},
        {"tests_run": 0},
        {"tests_run": True},
        {"tests_run": -1},
        {"candidate_digest": "0" * 64},
        {"baseline_digest": "0" * 64},
    ],
)
def test_evidence_is_bound_before_writing(source, tmp_path, overrides):
    validator = UnitVerdict(source, **overrides)
    optimizer = SalamanderAgenticOptimizer(tmp_path, validator=validator)
    success, _ = optimizer.apply_repair_sandboxed(source, CANDIDATE)
    assert success is False
    assert validator.calls == 1
    unchanged(source)


def test_bound_verdict_publishes_atomically(source, tmp_path):
    validator = UnitVerdict(source)
    optimizer = SalamanderAgenticOptimizer(tmp_path, validator=validator)
    success, _ = optimizer.apply_repair_sandboxed(source, CANDIDATE)
    assert success is True
    assert validator.calls == 1
    assert source.read_text() == CANDIDATE
    assert optimizer._history[-1]["status"] == "COMMITTED"
    assert not source.with_suffix(".py.bak").exists()


@pytest.mark.parametrize(
    "location",
    [
        "outside",
        "mining",
        "tests",
        "nested_tests",
        "conftest",
        "test_name",
        "test_suffix",
        "symlink",
    ],
)
def test_repair_scope_excludes_authority_and_tests(source, tmp_path, location):
    paths = {
        "outside": tmp_path.parent / (tmp_path.name + "-outside.py"),
        "mining": tmp_path / "mining/answer.py",
        "tests": tmp_path / "tests/test_answer.py",
        "nested_tests": tmp_path / "Intelligence/tests/answer.py",
        "conftest": tmp_path / "Intelligence/conftest.py",
        "test_name": tmp_path / "Intelligence/test_answer.py",
        "test_suffix": tmp_path / "Intelligence/answer_test.py",
        "symlink": tmp_path / "Intelligence/link.py",
    }
    target = paths[location]
    target.parent.mkdir(parents=True, exist_ok=True)
    if location == "symlink":
        try:
            target.symlink_to(source)
        except OSError:
            pytest.skip("Symlink creation requires privilege on Windows")
    else:
        target.write_bytes(BASELINE)
    validator = UnitVerdict(source)
    success, _ = SalamanderAgenticOptimizer(tmp_path, validator=validator).apply_repair_sandboxed(
        target, CANDIDATE
    )
    assert success is False
    assert validator.calls == 0
    assert target.read_bytes() == BASELINE
    unchanged(source)


def test_syntax_error_never_reaches_validator(source, tmp_path):
    validator = UnitVerdict(source)
    success, _ = SalamanderAgenticOptimizer(tmp_path, validator=validator).apply_repair_sandboxed(
        source, "def broken(:\n"
    )
    assert success is False
    assert validator.calls == 0
    unchanged(source)


def test_ambiguous_snippet_is_not_a_repair(source, tmp_path):
    original = BASELINE + BASELINE
    source.write_bytes(original)
    validator = UnitVerdict(source)
    success, _ = SalamanderAgenticOptimizer(tmp_path, validator=validator).apply_repair_sandboxed(
        source, "42", target_snippet="41"
    )
    assert success is False
    assert validator.calls == 0
    assert source.read_bytes() == original


def test_validator_exception_does_not_publish(source, tmp_path):
    class Offline:
        def validate(self, *_):
            raise RuntimeError("validator unavailable")

    success, _ = SalamanderAgenticOptimizer(tmp_path, validator=Offline()).apply_repair_sandboxed(
        source, CANDIDATE
    )
    assert success is False
    unchanged(source)


def test_concurrent_edit_is_not_overwritten(source, tmp_path):
    intervening = b"# human change\n" + BASELINE

    class Changed(UnitVerdict):
        def validate(self, *args):
            result = super().validate(*args)
            self.target.write_bytes(intervening)
            return result

    success, _ = SalamanderAgenticOptimizer(
        tmp_path, validator=Changed(source)
    ).apply_repair_sandboxed(source, CANDIDATE)
    assert success is False
    assert source.read_bytes() == intervening
    assert not list(source.parent.glob("*.salamander.lock"))


def test_legacy_resonance_mutator_cannot_bypass_verification(source, tmp_path, monkeypatch):
    import sys
    import types

    mutations = []
    resonance = types.ModuleType("pythagoras.phi_resonance")
    mutation = types.ModuleType("pythagoras.pythagoras_mutation")

    class Calculator:
        def compute(self, _):
            return 0.618

    class Mutator:
        def mutate(self, path):
            mutations.append(path)
            Path(path).write_text(CANDIDATE)

    resonance.PhiResonanceCalculator = Calculator
    mutation.PythagorasMutator = Mutator
    monkeypatch.setitem(sys.modules, "pythagoras", types.ModuleType("pythagoras"))
    monkeypatch.setitem(sys.modules, "pythagoras.phi_resonance", resonance)
    monkeypatch.setitem(sys.modules, "pythagoras.pythagoras_mutation", mutation)
    success, _, _ = SalamanderAgenticOptimizer(tmp_path).optimize_resonance_with_pythagoras(source)
    assert success is False
    assert mutations == []
    unchanged(source)


def proposal(target="Intelligence/answer.py", candidate=CANDIDATE):
    from Intelligence.self_healing.self_repair import RepairProposal

    return RepairProposal(
        "unit",
        "session",
        "tests",
        "tests/test_answer.py::test_answer",
        "unclassified",
        "unit",
        "unit candidate",
        {},
        "rule_based",
        target,
        candidate,
    )


def test_self_repair_flag_alone_cannot_authorize_write(source, tmp_path, monkeypatch):
    from Intelligence.self_healing.self_repair import apply_and_verify

    monkeypatch.setenv("HYBA_SELF_REPAIR_AUTO_APPLY", "true")
    test_file = tmp_path / "tests/test_answer.py"
    test_file.parent.mkdir()
    test_file.write_text("def test_answer():\n    assert True\n")
    result = apply_and_verify(proposal(), tmp_path, tmp_path, test_timeout_s=5)
    assert result.applied is False
    assert result.verified is False
    unchanged(source)


def test_self_repair_default_is_review_only(source, tmp_path, monkeypatch):
    from Intelligence.self_healing.self_repair import apply_and_verify

    monkeypatch.delenv("HYBA_SELF_REPAIR_AUTO_APPLY", raising=False)
    validator = UnitVerdict(source)
    result = apply_and_verify(proposal(), tmp_path, tmp_path, validator=validator)
    assert result.applied is False
    assert validator.calls == 0
    unchanged(source)


def test_self_repair_uses_bound_transaction(source, tmp_path, monkeypatch):
    from Intelligence.self_healing.self_repair import apply_and_verify, _veritas_ledger

    monkeypatch.setenv("HYBA_SELF_REPAIR_AUTO_APPLY", "true")
    validator = UnitVerdict(source)
    result = apply_and_verify(proposal(), tmp_path, tmp_path, validator=validator)
    assert result.applied is True
    assert result.verified is True
    assert source.read_text() == CANDIDATE
    entry = _veritas_ledger(tmp_path).memory_buffer[-1]
    assert entry["evidence"]["candidate_sha256"] == source_digest(CANDIDATE.encode())
    assert entry["evidence"]["baseline_sha256"] == source_digest(BASELINE)


def test_self_repair_rejects_failed_candidate_before_write(source, tmp_path, monkeypatch):
    from Intelligence.self_healing.self_repair import apply_and_verify

    monkeypatch.setenv("HYBA_SELF_REPAIR_AUTO_APPLY", "true")
    result = apply_and_verify(
        proposal(), tmp_path, tmp_path, validator=UnitVerdict(source, passed=False)
    )
    assert result.applied is False
    assert result.reverted is False  # no live write occurred
    unchanged(source)


def test_self_repair_cannot_install_dependencies(source, tmp_path, monkeypatch):
    from Intelligence.self_healing.self_repair import apply_and_verify

    monkeypatch.setenv("HYBA_SELF_REPAIR_AUTO_APPLY", "true")
    target = tmp_path / "requirements.txt"
    target.write_text("baseline-dependency\n")
    validator = UnitVerdict(source)
    result = apply_and_verify(
        proposal("requirements.txt", "candidate-dependency\n"),
        tmp_path,
        tmp_path,
        validator=validator,
    )
    assert result.applied is False
    assert validator.calls == 0
    assert target.read_text() == "baseline-dependency\n"


def test_self_repair_audit_open_failure_prevents_publication(source, tmp_path, monkeypatch):
    from Intelligence.self_healing import self_repair

    monkeypatch.setenv("HYBA_SELF_REPAIR_AUTO_APPLY", "true")

    def unavailable(_):
        raise OSError("audit store unavailable")

    monkeypatch.setattr(self_repair, "_veritas_ledger", unavailable)
    validator = UnitVerdict(source)
    result = self_repair.apply_and_verify(proposal(), tmp_path, tmp_path, validator=validator)
    assert result.applied is False
    assert validator.calls == 0
    unchanged(source)


def test_self_repair_audit_save_failure_is_not_fake_rollback(source, tmp_path, monkeypatch):
    from Intelligence.self_healing import self_repair

    monkeypatch.setenv("HYBA_SELF_REPAIR_AUTO_APPLY", "true")

    class BrokenStore:
        def record_action(self, *_):
            raise OSError("audit save failed")

    monkeypatch.setattr(self_repair, "_veritas_ledger", lambda _: BrokenStore())
    result = self_repair.apply_and_verify(
        proposal(), tmp_path, tmp_path, validator=UnitVerdict(source)
    )
    assert result.applied is True
    assert result.reverted is False
    assert "Audit persistence unavailable" in result.message
    assert source.read_text() == CANDIDATE


def test_dependency_proposal_is_read_only(tmp_path, monkeypatch):
    from Intelligence.self_healing.self_repair import (
        PytestFailure,
        ClassifiedFailure,
        propose_rule_based_repair,
        CATEGORY_IMPORT_COLLECTION_ERROR,
    )

    monkeypatch.delenv("HYBA_SELF_REPAIR_AUTO_APPLY", raising=False)
    requirements = tmp_path / "requirements.txt"
    original = "# existing dependencies\n"
    requirements.write_text(original)
    failure = PytestFailure(
        "tests/test_x.py::test_x",
        "tests/test_x.py",
        None,
        "error",
        "No module named 'httpx'",
        "",
        "tests",
    )
    classified = ClassifiedFailure(
        failure, CATEGORY_IMPORT_COLLECTION_ERROR, "high", "missing optional dependency"
    )
    outcome = propose_rule_based_repair(classified, tmp_path)
    assert outcome.available is True
    assert "httpx" in outcome.proposed_file_content
    assert requirements.read_text() == original
