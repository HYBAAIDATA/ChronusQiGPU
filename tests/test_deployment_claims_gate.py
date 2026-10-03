from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from scripts import deployment_claims_gate as gate


def _write(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _fixture(root: Path, claims: list[dict[str, str]]) -> None:
    _write(root, "claims.yaml", yaml.safe_dump({"claims": claims}))


@pytest.mark.parametrize(
    ("claim_text", "status"),
    [
        ("10 EH/s", "PROHIBITED"),
        ("One device equals 20,000 NVIDIA GPUs", "PROHIBITED"),
        ("Exponential speedup", "PROHIBITED"),
        ("Lucas/Pisot quantum speedup", "REFUTED"),
    ],
)
def test_disallowed_claim_register_text_fails_external_documentation(tmp_path, claim_text, status):
    _fixture(tmp_path, [{"id": "claim", "status": status, "text": claim_text}])
    _write(tmp_path, "DEPLOYMENT.md", f"Production capability: {claim_text}.")

    findings = gate.scan(tmp_path)

    assert any("DEPLOYMENT.md" in finding and claim_text in finding for finding in findings)


@pytest.mark.parametrize(
    "text",
    [
        "Measured target: 1.2 EH/s.",
        "Unmeasured projection: 10 exahashes per second.",
        "Lucas scaling amplifies effective hashrate.",
        "One device equals 20,000 NVIDIA GPUs.",
    ],
)
def test_equivalent_operational_throughput_claims_fail(tmp_path, text):
    _fixture(tmp_path, [])
    _write(tmp_path, "docs/deployment/guide.md", text)

    assert gate.scan(tmp_path)


def test_hypothesis_is_allowed_only_when_labelled_under_experiments(tmp_path):
    claim = {
        "id": "hypothesis",
        "status": "HYPOTHESIS",
        "text": "remote OpenCL fabric reaches multi-device quorum at production scale",
        "isolated_under": "experiments/",
    }
    _fixture(tmp_path, [claim])
    _write(
        tmp_path,
        "experiments/fabric.md",
        "## Hypothesis\n\nHYPOTHESIS: remote OpenCL fabric reaches multi-device quorum at production scale.",
    )

    assert gate.scan(tmp_path) == []

    _write(tmp_path, "DEPLOYMENT.md", claim["text"])
    assert any("DEPLOYMENT.md" in finding for finding in gate.scan(tmp_path))


def test_unlabelled_hypothesis_outside_approved_research_location_fails(tmp_path):
    claim = {
        "id": "hypothesis",
        "status": "HYPOTHESIS",
        "text": "remote OpenCL fabric reaches multi-device quorum at production scale",
        "isolated_under": "experiments/",
    }
    _fixture(tmp_path, [claim])
    _write(tmp_path, "experiments/fabric.md", claim["text"])

    assert any("experiments/fabric.md" in finding for finding in gate.scan(tmp_path))


def test_repository_deployment_material_passes_the_gate():
    assert gate.scan(gate.ROOT) == []


def test_deployment_guide_documents_runtime_and_evidence_prerequisites():
    deployment = (gate.ROOT / "DEPLOYMENT.md").read_text(encoding="utf-8")

    for required in (
        "main.py",
        "docker-compose.yml",
        "Dockerfile",
        "/api/health",
        "EUCLID_ADMIN_API_KEY",
        "MLA1517_STRATUM_USER",
        "proof adapter",
        "negotiated Stratum job",
        "pool acknowledges",
        "SOURCE VERIFIED",
        "SOFTWARE EXECUTION VERIFIED",
        "HARDWARE EXECUTION VERIFIED",
        "POOL VERIFIED",
        "UNVERIFIED",
    ):
        assert required in deployment
