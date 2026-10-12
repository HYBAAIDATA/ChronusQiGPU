"""Positive and negative controls for the signed release boundary."""

from copy import deepcopy
from pathlib import Path
import importlib.util

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "release_tag", ROOT / "scripts/verify_release_tag.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
COMMIT = "a" * 40
TAG_SHA = "b" * 40


def fixture():
    return (
        {"object": {"type": "tag", "sha": TAG_SHA}},
        {
            "sha": TAG_SHA,
            "tag": "v1.2.3",
            "verification": {"verified": True, "reason": "valid"},
            "object": {"type": "commit", "sha": COMMIT},
        },
    )


def test_valid_signed_release():
    reference, tag = fixture()
    MODULE.validate_tag("v1.2.3", reference, tag, COMMIT)


@pytest.mark.parametrize(
    "name", ["v1.2", "v01.2.3", "v1.2.3-rc1", "main", "v1.2.3;echo bad"]
)
def test_invalid_release_names(name):
    reference, tag = fixture()
    with pytest.raises(ValueError):
        MODULE.validate_tag(name, reference, tag, COMMIT)


@pytest.mark.parametrize(
    "section,key,value",
    [
        ("verification", "verified", False),
        ("verification", "verified", "true"),
        ("verification", "reason", "unknown_key"),
        ("object", "sha", "c" * 40),
        ("object", "type", "tree"),
    ],
)
def test_invalid_signature_or_target(section, key, value):
    reference, tag = fixture()
    tag = deepcopy(tag)
    tag[section][key] = value
    with pytest.raises(ValueError):
        MODULE.validate_tag("v1.2.3", reference, tag, COMMIT)


def test_lightweight_tag_is_rejected():
    reference, tag = fixture()
    reference["object"]["type"] = "commit"
    with pytest.raises(ValueError):
        MODULE.validate_tag("v1.2.3", reference, tag, COMMIT)


def test_substituted_tag_object_is_rejected():
    reference, tag = fixture()
    tag["sha"] = "d" * 40
    with pytest.raises(ValueError):
        MODULE.validate_tag("v1.2.3", reference, tag, COMMIT)


def test_ghcr_publication_is_gated_and_pr_build_cannot_push():
    document = yaml.load(
        (ROOT / ".github/workflows/container-release.yml").read_text(),
        Loader=yaml.BaseLoader,
    )
    jobs = document["jobs"]
    assert jobs["publish"]["environment"] == "DOCKER_USER"
    assert set(jobs["publish"]["needs"]) == {
        "checks",
        "signed-tag",
        "security",
        "secret-scan",
    }
    assert "github.event_name == 'push'" in jobs["publish"]["if"]
    assert jobs["publish"]["permissions"]["packages"] == "write"
    for job in (jobs["checks"], jobs["signed-tag"], jobs["preview"]):
        assert job.get("permissions", {}).get("packages") != "write"
    preview_build = next(
        s
        for s in jobs["preview"]["steps"]
        if s.get("uses", "").startswith("docker/build-push-action")
    )
    assert preview_build["with"]["push"] == "false"
    source = (ROOT / ".github/workflows/container-release.yml").read_text()
    assert "DOCKER_PAT" not in source
    assert "VIABTC" not in source
    assert "BRAIINS" not in source


def test_security_audit_has_no_fail_open_fallback():
    document = yaml.load(
        (ROOT / ".github/workflows/dependency-audit.yml").read_text(),
        Loader=yaml.BaseLoader,
    )
    assert "workflow_call" in document["on"]
    source = (ROOT / ".github/workflows/dependency-audit.yml").read_text()
    assert "||" not in source
    assert 'scripts/ci_install.sh "dev,ml"' in source
    assert "importlib.metadata.distributions()" in source
    assert "cyclonedx-py environment" in source
    assert "document.get('components')" in source


def test_publication_requires_standalone_intelligence_and_turing_suites():
    document = yaml.load(
        (ROOT / ".github/workflows/container-release.yml").read_text(),
        Loader=yaml.BaseLoader,
    )
    jobs = document["jobs"]
    assert "checks" in jobs["publish"]["needs"]
    steps = jobs["checks"]["steps"]
    intelligence = next(
        s for s in steps if s.get("name") == "Intelligence standalone self-test"
    )
    turing = next(s for s in steps if s.get("name") == "TURING standalone test suite")
    assert intelligence["run"] == "python -X utf8 -m Intelligence.self_test"
    assert turing["working-directory"] == "turing_universal_quantum_computer"
    assert "python -m pytest tests -q" in turing["run"]
    for step in (intelligence, turing):
        assert "if" not in step
        assert step.get("continue-on-error", "false") == "false"
        assert "|| true" not in step["run"]
    assert jobs["checks"].get("continue-on-error", "false") == "false"


def test_standalone_changes_trigger_release_candidate_validation():
    document = yaml.load(
        (ROOT / ".github/workflows/container-release.yml").read_text(),
        Loader=yaml.BaseLoader,
    )
    paths = document["on"]["pull_request"]["paths"]
    assert "Intelligence/**" in paths
    assert "turing_universal_quantum_computer/**" in paths
