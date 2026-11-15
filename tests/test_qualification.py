from chronus.core.qualification import qualify, MANDATORY
from chronus.core.claims import dispositions
from chronus.crypto import signers

def test_pq_gate_unqualified_without_provider(monkeypatch):
    monkeypatch.setattr(signers, "ml_dsa", None)
    verdict = qualify(require_pq=True)
    assert verdict.status == "UNQUALIFIED"
    assert "ML-DSA-65" in verdict.unqualified[0]

def test_skipped_gate_never_passes():
    gates = {gate: "PASS" for gate in MANDATORY}
    gates["CO-SIGN"] = "SKIPPED"
    assert qualify(ci_gates=gates, attestation_verified=True, key_provider="azure-managed-hsm").status == "UNQUALIFIED"
    assert dispositions(gates, True)["CO-001"] == "held"

def test_unattested_all_green_still_held():
    gates = {gate: "PASS" for gate in MANDATORY}
    assert dispositions(gates, False)["FN-001"] == "held"
    assert qualify(require_pq=False, ci_gates=gates, attestation_verified=False, key_provider="azure-managed-hsm").status == "UNQUALIFIED"
