"""Static release-contract regressions for standalone TURING publication."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_turing_public_identity_and_repository_are_canonical() -> None:
    pyproject = (ROOT / "turing_universal_quantum_computer" / "pyproject.toml").read_text(
        encoding="utf-8"
    )
    assert 'name = "hyba-turing-vqc"' in pyproject
    assert 'version = "1.0.0"' in pyproject
    assert 'authors = [{ name = "HYBA Software Limited" }]' in pyproject
    assert "hyba-kellogg-tensor>=1.0" in pyproject
    assert "https://github.com/QuantumPhiRedux/PhiMiner" in pyproject
    assert "QuantumPhi2/PhiMiner" not in pyproject
    for version in ("3.11", "3.12", "3.13"):
        assert f"Programming Language :: Python :: {version}" in pyproject


def test_turing_build_is_wheel_sdist_metadata_and_secret_scan_bound() -> None:
    build = (ROOT / "packaging" / "turing" / "build_wheel.py").read_text(encoding="utf-8")
    for required in (
        '"--wheel"',
        '"--sdist"',
        '"twine"',
        '"check"',
        "_SECRET_PATTERNS",
        "wheel-manifest.json",
        "sdist-manifest.json",
        "artifact-build.json",
        "hyba-kellogg-tensor",
        "QuantumPhiRedux/PhiMiner",
    ):
        assert required in build


def test_turing_release_workflow_uses_verified_artifact_and_oidc() -> None:
    workflow = (ROOT / ".github" / "workflows" / "turing-release.yml").read_text(
        encoding="utf-8"
    )
    for required in (
        "pull_request:",
        "workflow_dispatch:",
        'python: ["3.11", "3.12", "3.13"]',
        "packaging/verify_release_candidates.py",
        "python -m turing_universal_quantum_computer.benchmark",
        "tests/test_shared_system_relations_production.py",
        "lake-package-directory: turing_universal_quantum_computer/formal",
        "id-token: write",
        "pypa/gh-action-pypi-publish@release/v1",
        "publish-testpypi:",
        "testpypi-verified:",
        "publish-pypi:",
        "pypi-verified:",
        "packaging/verify_registry_release.py",
        "turing-1.0.0-release",
        "artifact-build.json",
        "testpypi-smoke:",
    ):
        assert required in workflow
    publish_section = workflow.split("\n  publish-pypi:", 1)[1].split("\n  pypi-smoke:", 1)[0]
    assert "python -m build" not in publish_section
    assert "pip install build" not in publish_section
    assert "api-token" not in workflow.lower()
    assert "password" not in workflow.lower()
    assert "github.event_name == 'workflow_dispatch'" in workflow


def test_mining_capacity_proof_is_not_a_turing_release_claim() -> None:
    turing_formal = (
        ROOT
        / "turing_universal_quantum_computer"
        / "formal"
        / "PureQuantumMath.lean"
    ).read_text(encoding="utf-8")
    mining_formal = (ROOT / "mining" / "formal" / "MiningCapacity.lean").read_text(
        encoding="utf-8"
    )
    assert "ten_eh_canonical_floor" not in turing_formal
    assert "capacityFloorMet" not in turing_formal
    assert "ten_eh_canonical_floor" in mining_formal
    assert "namespace MiningCapacity" in mining_formal


def test_kellogg_release_verifier_accepts_pep639_license_expression() -> None:
    verifier = (ROOT / "packaging" / "kellogg-tensor" / "build_and_verify.py").read_text(
        encoding="utf-8"
    )
    assert 'metadata.get("License-Expression") or metadata.get("License")' in verifier
