"""Publishing safety contracts; mocked Docker responses are not deployment proof."""

import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from urllib.error import HTTPError, URLError
from unittest.mock import Mock

import pytest
import yaml

from scripts.ci import check_dockerhub_repositories as guard


ROOT = Path(__file__).resolve().parents[1]


def response(value):
    return io.BytesIO(json.dumps(value).encode())


def test_organization_auth_uses_modern_api_and_requires_private_repository():
    opener = Mock(side_effect=[
        response({"access_token": "test-only-session"}),
        response({"name": "chronus-api", "is_private": True}),
    ])
    guard.check_private_repository(
        "hybadataintelligence", "chronus-api", "test-only-credential", open_request=opener,
    )
    auth, lookup = [call.args[0] for call in opener.call_args_list]
    assert auth.full_url == "https://hub.docker.com/v2/auth/token"
    assert auth.method == "POST"
    assert json.loads(auth.data) == {
        "identifier": "hybadataintelligence", "secret": "test-only-credential",
    }
    assert lookup.full_url == (
        "https://hub.docker.com/v2/namespaces/hybadataintelligence/repositories/chronus-api"
    )
    assert lookup.get_header("Authorization") == "Bearer test-only-session"
    assert all(call.kwargs["timeout"] == 20 for call in opener.call_args_list)


@pytest.mark.parametrize("metadata", [{"is_private": False}, {}, {"is_private": "true"}, {"is_private": 1}])
def test_public_or_unverifiable_destination_is_blocked(metadata):
    opener = Mock(side_effect=[response({"access_token": "test-only-session"}), response(metadata)])
    with pytest.raises(guard.PublicationBlocked, match="as private"):
        guard.check_private_repository("hybadataintelligence", "chronus-api", "test-only", open_request=opener)


@pytest.mark.parametrize("namespace,repository,credential", [
    ("", "chronus-api", "test-only"),
    ("hybadataintelligence", "chronus-api", ""),
    ("other.example/path", "chronus-api", "test-only"),
    ("hybadataintelligence", "../unexpected", "test-only"),
    ("hybadataintelligence\n", "chronus-api", "test-only"),
])
def test_missing_settings_or_invalid_names_are_blocked_without_network(namespace, repository, credential):
    opener = Mock()
    with pytest.raises(guard.PublicationBlocked):
        guard.check_private_repository(namespace, repository, credential, open_request=opener)
    opener.assert_not_called()


@pytest.mark.parametrize("metadata", [{}, {"access_token": ""}, {"access_token": 1}])
def test_missing_authentication_token_never_queries_a_repository(metadata):
    opener = Mock(return_value=response(metadata))
    with pytest.raises(guard.PublicationBlocked, match="authentication token"):
        guard.check_private_repository("hybadataintelligence", "chronus-api", "test-only", open_request=opener)
    assert opener.call_count == 1


def test_redirects_cannot_forward_credentials():
    with pytest.raises(guard.PublicationBlocked, match="redirects"):
        guard.NoCredentialRedirects().redirect_request(None, None, 302, "", {}, "https://other.example")


@pytest.mark.parametrize("error", [
    HTTPError("https://hub.docker.com", 403, "test-only-private-detail", {}, None),
    URLError("test-only-private-detail"),
    ValueError("test-only-private-detail"),
])
def test_failed_preflight_exits_nonzero_without_printing_sensitive_details(monkeypatch, capsys, error):
    monkeypatch.setattr(guard, "check_private_repository", Mock(side_effect=error))
    assert guard.main(["--repository", "chronus-api"]) == 1
    output = capsys.readouterr()
    assert not output.out
    assert "blocked" in output.err
    assert "test-only-private-detail" not in output.err


def workflow():
    # BaseLoader preserves GitHub's YAML `on` key rather than treating it as a boolean.
    return yaml.load((ROOT / ".github/workflows/docker-publish.yml").read_text(), Loader=yaml.BaseLoader)


def step_with(steps, command):
    return next(step for step in steps if command in step.get("run", ""))


def test_workflow_only_publishes_the_exact_successful_trusted_main_push():
    config = workflow()
    ci = yaml.load((ROOT / ".github/workflows/ci.yml").read_text(), Loader=yaml.BaseLoader)
    assert config["on"]["workflow_run"] == {
        "workflows": [ci["name"]], "types": ["completed"], "branches": ["main"],
    }
    assert "push" in ci["on"]
    assert "pull_request" in config["on"]
    assert config["permissions"] == {"contents": "read"}
    assert config["env"]["SOURCE_SHA"] == "${{ github.event.workflow_run.head_sha || github.sha }}"
    publisher = config["jobs"]["publish"]
    assert publisher["needs"] == "build-and-smoke"
    assert "github.event_name == 'workflow_run'" in publisher["if"]
    for required in [
        "github.event.workflow_run.conclusion == 'success'",
        "github.event.workflow_run.event == 'push'",
        "github.event.workflow_run.head_branch == 'main'",
        "github.event.workflow_run.head_repository.full_name == github.repository",
        "github.event.workflow_run.path == '.github/workflows/ci.yml'",
    ]:
        assert required in publisher["if"]
        assert required in config["jobs"]["build-and-smoke"]["if"]
    for job in config["jobs"].values():
        checkout = job["steps"][0]
        assert checkout["with"]["ref"] == "${{ env.SOURCE_SHA }}"
        assert checkout["with"]["persist-credentials"] == "false"
        for step in job["steps"]:
            if "uses" in step:
                assert re.fullmatch(r"[\w/-]+@[0-9a-f]{40}", step["uses"])
    assert publisher["env"]["DOCKER_USER"] == "${{ vars.DOCKER_USER }}"
    assert "DOCKER_PAT" not in publisher["env"]
    assert "secrets." not in json.dumps(config["jobs"]["build-and-smoke"])


def test_all_images_pass_smoke_before_the_same_artifacts_can_publish():
    config = workflow()
    build_steps = config["jobs"]["build-and-smoke"]["steps"]
    build = step_with(build_steps, "docker build ")["run"]
    assert 'test "$(git rev-parse HEAD)" = "$SOURCE_SHA"' in build
    assert '[[ "$SOURCE_SHA" =~ ^[0-9a-f]{40}$ ]]' in build
    assert "for image in api web miner" in build
    for dockerfile, targets in [("Dockerfile", ["api-runtime", "miner-runtime"]), ("frontend/Dockerfile", ["runtime"])]:
        for target in targets:
            assert f" AS {target}" in (ROOT / dockerfile).read_text()
    smoke = step_with(build_steps, "mining_selftest")
    archive = step_with(build_steps, "docker save ")
    assert build_steps.index(smoke) < build_steps.index(archive)
    assert "continue-on-error" not in json.dumps(config)
    assert "docker image inspect" in archive["run"]
    assert "sha256sum images.tar" in archive["run"]
    upload = build_steps[-1]
    publisher = config["jobs"]["publish"]["steps"]
    download = publisher[1]
    assert upload["with"]["name"] == download["with"]["name"]
    assert upload["with"]["if-no-files-found"] == "error"
    load = step_with(publisher, "docker load ")["run"]
    assert "sha256sum --check images.tar.sha256" in load
    assert "org.opencontainers.image.revision" in load
    assert 'test "$(docker inspect --format \'{{.Id}}\' "$ref")" = "$expected"' in load
    assert "docker build " not in json.dumps(publisher)
    push = step_with(publisher, "docker push ")["run"]
    assert 'docker tag "chronus-${image}:sha-${SOURCE_SHA}" "$destination"' in push
    assert 'destination="docker.io/${DOCKER_USER}/chronus-${image}:sha-${SOURCE_SHA}"' in push
    assert ":latest" not in json.dumps(config)


def test_offline_smoke_overrides_miner_and_checks_restart_and_recreation():
    steps = workflow()["jobs"]["build-and-smoke"]["steps"]
    smoke = step_with(steps, "mining_selftest")["run"]
    assert 'docker run --rm --network none --entrypoint python "chronus-miner:sha-${SOURCE_SHA}"' in smoke
    assert "chronus_live_miner.py" not in smoke
    assert "--network none" in smoke
    assert '--mount "type=volume,src=$volume,dst=/var/lib/chronus"' in smoke
    assert "docker cp tests/container_smoke.py" in smoke
    assert 'workload_id=$(smoke_api submit)' in smoke
    assert 'docker restart "$api_id"' in smoke
    assert smoke.count('smoke_api verify "$workload_id"') == 2
    assert smoke.index('docker rm -f "$api_id"') < smoke.rindex('smoke_api verify "$workload_id"')
    assert "trap cleanup EXIT" in smoke
    # Every container, not just the miner, must be externally network-isolated.
    assert all("--network none" in line for line in smoke.splitlines() if "docker run " in line)


def test_credentials_only_reach_guard_and_stdin_after_all_smoke_checks():
    steps = workflow()["jobs"]["publish"]["steps"]
    guard_step = step_with(steps, "mktemp -d")
    login = step_with(steps, "docker login ")
    push = step_with(steps, "docker push ")
    assert steps.index(guard_step) < steps.index(login) < steps.index(push)
    assert "for image in api web miner" in guard_step["run"]
    assert "check_dockerhub_repositories.py" in push["run"]
    assert push["run"].index("check_dockerhub_repositories.py") < push["run"].index("docker push ")
    for step in [guard_step, login, push]:
        assert step["env"]["DOCKER_PAT"] == "${{ secrets.DOCKER_PAT }}"
        assert "set -euo pipefail" in step["run"]
    assert 'printf \'%s\' "$DOCKER_PAT" | docker login' in login["run"]
    assert "--password-stdin" in login["run"]
    assert steps[-1]["if"] == "always()"
    assert steps[-1]["run"] == "docker logout docker.io"


@pytest.mark.parametrize("source_sha", ["main", "a" * 39, "a" * 40 + "; echo unsafe", "0" * 40])
def test_build_shell_rejects_any_unchecked_source_before_docker(source_sha, tmp_path):
    bash = shutil.which("bash")
    if bash is None or shutil.which("git") is None:
        pytest.skip("bash/git are not available on this host")
    marker = tmp_path / "docker-called"
    fake_docker = tmp_path / "docker"
    fake_docker.write_text('#!/bin/sh\nprintf called > "$DOCKER_CALLED"\nexit 99\n')
    fake_docker.chmod(0o755)
    build = step_with(workflow()["jobs"]["build-and-smoke"]["steps"], "docker build ")["run"]
    result = subprocess.run(
        [bash, "-c", build], cwd=ROOT, capture_output=True, text=True,
        env={**os.environ, "SOURCE_SHA": source_sha, "DOCKER_CALLED": str(marker),
             "PATH": str(tmp_path) + os.pathsep + os.environ.get("PATH", "")},
    )
    assert result.returncode != 0
    assert not marker.exists()


def test_workflow_shell_scripts_parse_without_github_expression_injection():
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash is not available on this host")
    for job in workflow()["jobs"].values():
        for step in job["steps"]:
            if "run" not in step:
                continue
            assert "${{" not in step["run"]
            subprocess.run([bash, "-n"], input=step["run"], text=True, check=True, capture_output=True)


@pytest.mark.parametrize("auth,metadata", [(None, {}), ([], {}), ({"access_token": "fixture"}, None), ({"access_token": "fixture"}, [])])
def test_malformed_api_response_is_blocked_without_sensitive_output(monkeypatch, capsys, auth, metadata):
    opener = Mock(side_effect=[response(auth), response(metadata)])
    monkeypatch.setattr(guard, "build_opener", Mock(return_value=Mock(open=opener)))
    monkeypatch.setenv("DOCKER_USER", "hybadataintelligence")
    monkeypatch.setenv("DOCKER_PAT", "test-only-sensitive-fixture")
    assert guard.main(["--repository", "chronus-api"]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "blocked" in output.err
    assert "test-only-sensitive-fixture" not in output.err


def test_successful_cli_uses_environment_and_never_prints_credentials(monkeypatch, capsys):
    opener = Mock(side_effect=[response({"access_token": "test-only-bearer"}), response({"is_private": True})])
    monkeypatch.setattr(guard, "build_opener", Mock(return_value=Mock(open=opener)))
    monkeypatch.setenv("DOCKER_USER", "hybadataintelligence")
    monkeypatch.setenv("DOCKER_PAT", "test-only-sensitive-fixture")
    assert guard.main(["--repository", "chronus-api"]) == 0
    output = capsys.readouterr()
    assert "Verified an existing private" in output.out
    assert "test-only" not in output.out + output.err
