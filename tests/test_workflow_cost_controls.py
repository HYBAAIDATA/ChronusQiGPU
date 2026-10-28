from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
MANUAL_ONLY = (
    "azure-package.yml",
    "azure-staticwebapp.yml",
    "azure-webapps-node.yml",
    "azure-webapps-python.yml",
    "azure-container-webapp.yml",
    "arc-native-research.yml",
    "mayhem-for-api.yml",
    "neuralegion.yml",
    "mining-production-network.yml",
    "hardware-acceptance.yml",
    "mutation.yml",
    "msvc.yml",
)


def load_workflow(name):
    return yaml.load(
        (WORKFLOWS / name).read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )


def test_costly_workflows_are_manual_and_bounded():
    for name in MANUAL_ONLY:
        workflow = load_workflow(name)
        assert set(workflow["on"]) == {"workflow_dispatch"}, name
        assert workflow["concurrency"]["cancel-in-progress"] == "true", name
        assert workflow["concurrency"]["group"], name
        for job_name, job in workflow["jobs"].items():
            assert 0 < int(job["timeout-minutes"]) <= 45, (name, job_name)
        if name == "arc-native-research.yml":
            assert workflow["jobs"]["canonical-runtime"]["if"] == (
                "github.ref_name == 'research/arc-native-20261023'"
            )


def test_mainline_ci_is_path_scoped_and_merge_queue_aware():
    for name in ("ci.yml", "pythia-ci.yml", "pythia-push-gate.yml"):
        workflow = load_workflow(name)
        assert workflow["on"]["push"]["branches"] == ["main"], name
        assert workflow["on"]["push"]["paths"], name
        ignored = workflow["on"]["pull_request"]["paths-ignore"]
        assert "docs/**" in ignored, name
        assert "**/*.md" in ignored, name
        assert workflow["on"]["merge_group"]["types"] == ["checks_requested"], name

    evidence = load_workflow("al-haras-evidence-gates.yml")
    assert evidence["on"]["push"]["branches"] == ["main"]
    assert evidence["on"]["push"]["paths"]
    assert "feat/**" not in evidence["on"]["push"]["branches"]


def test_runner_matrices_do_not_multiply_operating_systems():
    for name in (
        "agent-capability-qualification.yml",
        "euclid-enterprise-clean-install.yml",
        "euclid-v17-integration.yml",
        "trio-release-tooling.yml",
    ):
        matrix = load_workflow(name)["jobs"]
        job = next(iter(matrix.values()))
        assert job["strategy"]["matrix"]["os"] == ["ubuntu-latest"], name

    codeql = load_workflow("codeql.yml")
    codeql_job = codeql["jobs"]["analyze"]
    assert codeql_job["runs-on"] == "ubuntu-latest"
    assert codeql_job["strategy"]["matrix"]["include"] == [
        {"language": language, "build-mode": "none"}
        for language in (
            "actions",
            "c-cpp",
            "javascript-typescript",
            "python",
            "rust",
        )
    ]


def test_dependabot_groups_weekly_frontend_updates():
    config = yaml.load(
        (ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )
    npm = next(update for update in config["updates"] if update["package-ecosystem"] == "npm")
    assert npm["schedule"]["interval"] == "weekly"
    assert npm["groups"]["frontend-dependencies"]["patterns"] == ["*"]


def test_dependency_review_stays_pr_scoped_to_dependency_changes():
    workflow = load_workflow("dependency-review.yml")
    assert set(workflow["on"]) == {"pull_request"}
    assert workflow["on"]["pull_request"]["paths"]


def test_copilot_setup_keeps_the_hyba_and_cogito_contracts():
    setup = (WORKFLOWS / "copilot-setup-steps.yml").read_text(encoding="utf-8")
    assert 'python-version: "3.12"' in setup
    assert 'pip install "numpy>=1.26,<3"' in setup
    assert "from hyba_mcp.server import HybaMCPServer" in setup
    assert '[sys.executable, "-m", "mcp.cogito.server"]' in setup
    assert 'assert len(hyba["result"]["tools"]) == 11' in setup
    assert 'assert len(tools) == 12 and {tool["name"] for tool in tools} == expected' in setup
    assert 'assert envelope["theorem_proven"] is False' in setup
