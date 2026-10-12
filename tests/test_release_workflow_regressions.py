"""Executable regressions for receipt identity and fail-closed release creation."""

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def workflow(name):
    return yaml.load((ROOT / ".github/workflows" / name).read_text(), Loader=yaml.BaseLoader)


def step_code(job, name):
    steps = workflow("consumer-publication.yml")["jobs"][job]["steps"]
    return next(s["run"] for s in steps if s.get("name") == name)


def test_installed_receipt_identifies_its_registry(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RC_SHA", "a" * 40)
    monkeypatch.setenv("CI_RUN_URL", "https://example.invalid/run/1")
    exec(compile(step_code("installed-smoke", "Emit execution receipt"), "<receipt>", "exec"), {})
    receipt = json.loads(Path("receipts/receipt.json").read_text())
    assert receipt["registry"] == "installed-wheel"
    assert receipt["source_commit"] == "a" * 40


def prepare_release(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RC_SHA", "a" * 40)
    monkeypatch.setenv("CI_RUN_URL", "https://example.invalid/run/1")
    Path("dist").mkdir()
    Path("dist/package.whl").write_bytes(b"fixture")
    Path("dist/package.tar.gz").write_bytes(b"fixture")
    Path("verdicts").mkdir()
    Path("verdicts/consumer-release-verdict.json").write_text(
        json.dumps({"product": "hyba-pythia-consumer"})
    )
    for registry in ("installed-wheel", "testpypi", "pypi"):
        for version in ("3.10", "3.11", "3.12", "3.13"):
            directory = Path(f"receipts/consumer-{registry}-smoke-{version}")
            directory.mkdir(parents=True)
            (directory / "receipt.json").write_text(
                json.dumps(
                    {
                        "registry": registry,
                        "python": version,
                        "source_commit": "a" * 40,
                        "status": "PASS",
                        "product": "hyba-pythia-consumer",
                        "checks": {"execution": True},
                    }
                )
            )
    run = step_code("github-release", "Retain complete publication evidence and create the release")
    return run.split("python - <<'PY'\n", 1)[1].split("\nPY", 1)[0]


def test_release_command_failure_does_not_emit_final_evidence(tmp_path, monkeypatch):
    code = prepare_release(tmp_path, monkeypatch)
    with patch.object(subprocess, "run", side_effect=subprocess.CalledProcessError(1, ["gh"])):
        with patch.object(os, "system", side_effect=AssertionError("unchecked shell command")):
            with pytest.raises(subprocess.CalledProcessError):
                exec(compile(code, "<release>", "exec"), {})
    assert not Path("consumer-publication.json").exists()


def test_successful_release_emits_final_evidence(tmp_path, monkeypatch):
    code = prepare_release(tmp_path, monkeypatch)
    with patch.object(subprocess, "run") as run:
        exec(compile(code, "<release>", "exec"), {})
    assert run.call_args.kwargs["check"] is True
    command = run.call_args.args[0]
    assert command[:3] == ["gh", "release", "create"]
    assert "dist/package.whl" in command
    assert json.loads(Path("consumer-publication.json").read_text())["published"] is True


@pytest.mark.parametrize("name", ["consumer-publication.yml", "euclid-v17-release.yml"])
def test_dispatch_input_is_not_interpolated_into_shell_source(name):
    for job in workflow(name)["jobs"].values():
        for step in job.get("steps", []):
            assert "${{ inputs.rc_sha }}" not in step.get("run", "")


@pytest.mark.parametrize("name", ["consumer-publication.yml", "euclid-v17-release.yml"])
def test_release_repository_identity_comes_from_github_context(name):
    document = workflow(name)
    assert document["env"]["REPOSITORY"] == "${{ github.repository }}"
    source = (ROOT / ".github/workflows" / name).read_text()
    assert '"repository": os.environ["REPOSITORY"]' in source


@pytest.mark.parametrize("tag_filter", ["tags", "tags-ignore"])
def test_tag_only_workflow_does_not_duplicate_branch_pr_runs(tmp_path, tag_filter):
    from scripts import deploy_sentry

    directory = tmp_path / ".github/workflows"
    directory.mkdir(parents=True)
    (directory / "release.yml").write_text(
        f"on:\n  push:\n    {tag_filter}: ['v*.*.*']\n  pull_request:\n"
    )
    findings = deploy_sentry.check_ci_triggers(tmp_path, branches={"main"})
    assert not [f for f in findings if f.severity == "error"]


def test_tag_and_wildcard_branch_workflow_still_reports_duplicate_runs(tmp_path):
    from scripts import deploy_sentry

    directory = tmp_path / ".github/workflows"
    directory.mkdir(parents=True)
    (directory / "release.yml").write_text(
        "on:\n  push:\n    branches: ['**']\n    tags: ['v*.*.*']\n  pull_request:\n"
    )
    assert any(
        f.severity == "error" for f in deploy_sentry.check_ci_triggers(tmp_path, branches={"main"})
    )


@pytest.mark.parametrize(
    "key,value",
    [
        ("product", "other-package"),
        ("source_commit", "c" * 40),
        ("checks", {}),
        ("checks", {"execution": False}),
        ("registry", "pypi"),
        ("python", "3.14.0"),
    ],
)
def test_release_rejects_substituted_or_incomplete_receipts(tmp_path, monkeypatch, key, value):
    code = prepare_release(tmp_path, monkeypatch)
    receipt_path = Path("receipts/consumer-installed-wheel-smoke-3.10/receipt.json")
    receipt = json.loads(receipt_path.read_text())
    receipt[key] = value
    receipt_path.write_text(json.dumps(receipt))
    with patch.object(subprocess, "run") as run:
        with pytest.raises(AssertionError):
            exec(compile(code, "<release>", "exec"), {})
    run.assert_not_called()
    assert not Path("consumer-publication.json").exists()


def test_scaffold_pool_password_is_explicitly_empty():
    source = (ROOT / "chronus/mla1517_platform/build_pythia_layout.sh").read_text()
    environment = source.split("<<'ENV'\n", 1)[1].split("\nENV", 1)[0]
    assignments = dict(
        line.split("=", 1) for line in environment.splitlines() if line and not line.startswith("#")
    )
    assert assignments["MLA1517_STRATUM_PASSWORD"].split(" #", 1)[0] == '""'
    assert assignments["MLA1517_ENABLE_LIVE_SUBMIT"] == "0"
