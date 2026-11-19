"""Executable product gates for the software-base release profile."""

from __future__ import annotations

from scripts.ci import build_product_gates
import pytest

pytestmark = pytest.mark.simulated


def test_software_base_product_gates_pass_when_required_providers_exist(monkeypatch):
    monkeypatch.setenv("GITHUB_SHA", "a" * 40)
    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    result = build_product_gates.build("software-base")
    assert result["schema"] == "chronus-product-gates-v1"
    assert result["deployment_profile"] == "software-base"
    assert result["commit"] == "a" * 40
    assert result["run_id"] == "123"
    assert set(result["gates"]) == {
        "CO-SIGN", "RS-RECEIPT", "RS-REPLAY", "FN-CLAIMS", "FN-CUSTODY"
    }
    if result["status"] == "PASS":
        assert set(result["gates"].values()) == {"PASS"}
        assert result["facts"]["post_quantum_signer"]["verified"] is True
        assert result["facts"]["custody"]["verified"] is True
        assert result["facts"]["custody"]["authority"] == "THESEUS"
    else:
        # Unsupported ML-DSA must fail closed rather than silently downgrading.
        assert result["gates"]["CO-SIGN"] == "UNQUALIFIED"


def test_unimplemented_deployment_profile_is_unqualified(monkeypatch):
    monkeypatch.setenv("GITHUB_SHA", "b" * 40)
    monkeypatch.setenv("GITHUB_RUN_ID", "456")
    result = build_product_gates.build("sovereign")
    assert result["status"] == "UNQUALIFIED"
    assert set(result["gates"].values()) == {"UNQUALIFIED"}
    assert result["facts"]["profile"]["verified"] is False
