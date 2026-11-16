"""Regression checks for literal subprocess invocation and mutation source safety."""

import sys
from types import SimpleNamespace

import pytest

from scripts.ci import manifest, test_the_tests, verify_chronus

pytestmark = pytest.mark.simulated


def test_manifest_invokes_literal_arguments_without_shell(monkeypatch):
    calls = []

    def runner(argv, **kwargs):
        calls.append((argv, kwargs))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(manifest.subprocess, "run", runner)
    payload = "input; echo SHOULD_NOT_EXECUTE"
    assert manifest.run_cmd([sys.executable, payload])
    assert calls == [
        (
            [sys.executable, payload],
            {
                "shell": False,
                "capture_output": True,
                "text": True,
                "cwd": manifest.REPO_ROOT,
            },
        )
    ]


def test_manifest_fails_closed_when_executable_is_missing(monkeypatch, capsys):
    def missing(*args, **kwargs):
        raise FileNotFoundError("no such executable")

    monkeypatch.setattr(manifest.subprocess, "run", missing)
    assert not manifest.run_cmd(["missing-tool", "literal;data"])
    assert "[CMD FAIL]" in capsys.readouterr().out


@pytest.mark.parametrize("bad", ["python -m pytest", "", b"python"])
def test_manifest_rejects_shell_command_strings(bad):
    with pytest.raises(TypeError):
        manifest.run_cmd(bad)


def test_verifier_git_pattern_remains_literal(monkeypatch):
    calls = []

    def runner(argv, **kwargs):
        calls.append((argv, kwargs))
        return SimpleNamespace(returncode=0, stdout="found", stderr="")

    monkeypatch.setattr(verify_chronus.subprocess, "run", runner)
    assert verify_chronus.run(["git", "grep", "-n", "--", "x;touch /tmp/nope"]) == "found"
    assert calls[0][0][-1] == "x;touch /tmp/nope"
    assert calls[0][1]["shell"] is False


def test_mutation_executes_argv_and_restores_exact_original_bytes(tmp_path, monkeypatch):
    root = tmp_path / "checkout"
    source = root / "src" / "chronus" / "stratum" / "gatekeeper.py"
    source.parent.mkdir(parents=True)
    original = b"line = 1\r\nis_share_valid = (hash_int <= share_target_int)\r\n"
    source.write_bytes(original)
    monkeypatch.setattr(test_the_tests, "REPO_ROOT", str(root))
    calls = []

    def runner(argv, **kwargs):
        calls.append((argv, kwargs))
        assert b"is_share_valid = (hash_int > share_target_int)" in source.read_bytes()
        return SimpleNamespace(returncode=1)

    monkeypatch.setattr(test_the_tests.subprocess, "run", runner)
    mutation = test_the_tests.Mutation(
        name="inversion",
        description="reject inverted target",
        target_rel_path="src/chronus/stratum/gatekeeper.py",
        original_code="is_share_valid = (hash_int <= share_target_int)",
        mutated_code="is_share_valid = (hash_int > share_target_int)",
        test_command=(sys.executable, "-m", "unittest", "tests/test_gatekeeper.py"),
    )
    assert test_the_tests.execute_mutation(mutation)
    assert source.read_bytes() == original
    assert calls[0][0] == list(mutation.test_command)
    assert calls[0][1]["shell"] is False


def test_mutation_restores_source_when_test_launch_fails(tmp_path, monkeypatch):
    root = tmp_path / "checkout"
    root.mkdir()
    source = root / "changed.py"
    original = b"value = 1\r\n"
    source.write_bytes(original)
    monkeypatch.setattr(test_the_tests, "REPO_ROOT", str(root))

    def missing(*args, **kwargs):
        raise OSError("executor unavailable")

    monkeypatch.setattr(test_the_tests.subprocess, "run", missing)
    mutation = test_the_tests.Mutation(
        name="simple",
        description="rollback on failure",
        target_rel_path="changed.py",
        original_code="value = 1",
        mutated_code="value = 2",
        test_command=(sys.executable, "-m", "unittest", "tests/test_value.py"),
    )
    with pytest.raises(OSError, match="executor unavailable"):
        test_the_tests.execute_mutation(mutation)
    assert source.read_bytes() == original


def test_mutation_commands_are_argument_vectors():
    assert all(
        isinstance(mut.test_command, tuple)
        and mut.test_command[0] == sys.executable
        for mut in test_the_tests.MUTATIONS
    )
