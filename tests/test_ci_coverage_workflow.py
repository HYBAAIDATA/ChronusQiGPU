"""Keep merge-result validation distinct from head-attributed coverage reporting."""
from pathlib import Path
import shlex

import pytest
import yaml

pytestmark = pytest.mark.real

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())


def test_merge_result_passes_before_head_coverage_is_measured():
    steps = WORKFLOW["jobs"]["tests"]["steps"]
    checkouts = [i for i, step in enumerate(steps)
                 if step.get("uses", "").startswith("actions/checkout@")]
    assert len(checkouts) == 2
    merge, head = checkouts
    assert "ref" not in steps[merge].get("with", {})
    assert steps[head]["with"]["ref"] == "${{ github.event.pull_request.head.sha }}"
    assert steps[head]["if"] == "github.event_name == 'pull_request'"
    runs = [i for i, step in enumerate(steps)
            if shlex.split(step.get("run", ""))[:3] == ["python", "-m", "pytest"]]
    assert len(runs) == 2
    assert merge < runs[0] < head < runs[1]
    assert "if" not in steps[runs[0]]
    assert steps[runs[1]]["if"] == "github.event_name == 'pull_request'"
    assert all("continue-on-error" not in steps[i] for i in runs)
    assert all("--cov" in shlex.split(steps[i]["run"]) for i in runs)
    for database in ("CHRONUS_WORKLOAD_DB_PATH", "CHRONUS_QUALIFICATION_DB_PATH"):
        assert steps[runs[0]]["env"][database] != steps[runs[1]]["env"][database]
    assert steps[head + 1]["run"] == "python -m pip install -e '.[dev]'"
    assert steps[head + 1]["if"] == "github.event_name == 'pull_request'"
    artifact = next(i for i, step in enumerate(steps)
                    if step.get("with", {}).get("name") == "coverage-report-python")
    assert runs[1] < artifact
    assert steps[artifact]["with"]["if-no-files-found"] == "error"
    assert "always()" not in steps[artifact].get("if", "")


def test_reporting_keeps_success_and_fork_safety_guards():
    jobs = WORKFLOW["jobs"]
    assert jobs["tests"]["runs-on"] == ["self-hosted", "windows"]
    guard = "github.event.pull_request.head.repo.full_name == github.repository"
    assert guard in jobs["tests"]["if"]
    upload = jobs["upload-coverage-python"]
    assert upload["needs"] == "tests"
    assert "needs.tests.result == 'success'" in upload["if"]
    assert guard in upload["if"]
    assert upload["permissions"] == {
        "contents": "read", "code-quality": "write", "pull-requests": "read",
    }
    assert upload["steps"][0]["with"]["name"] == "coverage-report-python"
    assert upload["steps"][1]["with"]["file"] == "coverage.xml"


def test_qigpu_measurements_override_the_project_source_filter():
    steps = WORKFLOW["jobs"]["qigpu-model"]["steps"]
    commands = "\n".join(step.get("run", "") for step in steps)
    assert "coverage run --branch --source=docs/qigpu docs/qigpu/pasted-text.txt" in commands
    assert "branch=True,source=['docs/qigpu']" in commands
