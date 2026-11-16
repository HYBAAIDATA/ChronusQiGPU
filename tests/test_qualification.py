from chronus.core.qualification import qualify, MANDATORY
from chronus.core.claims import dispositions, required_claims_for_profile
from chronus.crypto import signers


def test_pq_gate_unqualified_without_provider(monkeypatch):
    monkeypatch.setattr(signers, "ml_dsa", None)
    verdict = qualify(require_pq=True)
    assert verdict.status == "UNQUALIFIED"
    assert "ML-DSA-65" in verdict.unqualified[0]


def test_skipped_gate_never_passes():
    gates = {gate: "PASS" for gate in MANDATORY}
    gates["CO-SIGN"] = "SKIPPED"
    assert qualify(
        ci_gates=gates,
        attestation_verified=True,
        key_provider="azure-managed-hsm",
    ).status == "UNQUALIFIED"
    assert dispositions(gates, True)["CO-001"] == "held"


def test_unattested_all_green_still_held():
    gates = {gate: "PASS" for gate in MANDATORY}
    assert dispositions(gates, False)["FN-001"] == "held"
    assert qualify(
        require_pq=False,
        ci_gates=gates,
        attestation_verified=False,
        key_provider="azure-managed-hsm",
    ).status == "UNQUALIFIED"


def test_provider_name_does_not_create_custody_credit(monkeypatch):
    monkeypatch.setattr(signers, "ml_dsa_available", lambda: True)
    gates = {gate: "PASS" for gate in MANDATORY}
    assert qualify(
        ci_gates=gates,
        attestation_verified=True,
        key_provider="local-memory",
    ).status == "PASS"
    assert qualify(
        ci_gates=gates,
        attestation_verified=True,
        key_provider="azure-managed-hsm",
    ).status == "PASS"


def test_external_custody_claim_is_held_for_software_base():
    gates = {gate: "PASS" for gate in MANDATORY}
    claims = dispositions(
        gates,
        True,
        deployment_profile="software-base",
        product_facts={
            "custody": {
                "authority": "THESEUS",
                "verified": True,
                "external_customer_key_custody": False,
            }
        },
    )
    for claim in required_claims_for_profile("software-base"):
        assert claims[claim] == "supported"
    assert claims["FN-001"] == "held"


def test_external_custody_claim_requires_attested_external_fact():
    gates = {gate: "PASS" for gate in MANDATORY}
    claims = dispositions(
        gates,
        True,
        deployment_profile="enterprise",
        product_facts={
            "custody": {
                "authority": "THESEUS",
                "verified": True,
                "external_customer_key_custody": True,
            }
        },
    )
    assert claims["FN-001"] == "supported"
