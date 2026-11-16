"""Evaluate verified Actions artifact; verification is performed by gh attestation verify.

This tool MUST be called only after the external gh attestation verification for
the exact evidence file and expected repository succeeds.
"""
from __future__ import annotations
import argparse
import json
import subprocess
from pathlib import Path
from chronus.core.qualification import qualify, MANDATORY
from chronus.core.claims import dispositions

def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument("--evidence", required=True)
    p.add_argument("--expected-commit", required=True)
    p.add_argument("--expected-run-id", required=True)
    p.add_argument("--repository", required=True)
    p.add_argument("--output", default="manifests/ci-verdict.json")
    p.add_argument("--product-gates", help="attested gate JSON; absent gates remain UNQUALIFIED")
    p.add_argument("--key-provider", default="local-memory")
    a=p.parse_args()

    try:
        evidence=json.loads(Path(a.evidence).read_text())
        identity_ok=(
            evidence.get("commit")==a.expected_commit
            and str(evidence.get("run_id"))==str(a.expected_run_id)
            and evidence.get("schema")=="chronus-ci-test-evidence-v1"
        )
        test_ok=(
            evidence.get("status")=="PASS"
            and evidence.get("tests",{}).get("skipped")==0
            and evidence.get("tests",{}).get("failed")==0
            and evidence.get("tests",{}).get("total",0)>0
        )
    except (ValueError,OSError,TypeError) as exc:
        identity_ok=test_ok=False
        evidence={"error":str(exc)}

    try:
        verification=subprocess.run(
            ["gh","attestation","verify",a.evidence,"--repo",a.repository],
            capture_output=True,text=True,timeout=60,check=False
        )
        attestation_ok=verification.returncode==0
    except (OSError,subprocess.TimeoutExpired):
        attestation_ok=False

    gates={gate:"UNQUALIFIED" for gate in MANDATORY}
    gate_attestation_ok = False
    gate_identity_ok = False
    product = {}
    if a.product_gates:
        try:
            product = json.loads(Path(a.product_gates).read_text())
            gate_identity_ok = (
                product.get("schema") == "chronus-product-gates-v1"
                and product.get("commit") == a.expected_commit
                and str(product.get("run_id")) == str(a.expected_run_id)
                and product.get("deployment_profile") == "software-base"
                and isinstance(product.get("gates"), dict)
                and isinstance(product.get("facts"), dict)
                and all(isinstance(product["facts"].get(name), dict)
                        for name in ("profile", "custody", "post_quantum_signer"))
            )
            verification = subprocess.run(
                ["gh", "attestation", "verify", a.product_gates, "--repo", a.repository],
                capture_output=True, text=True, timeout=60, check=False,
            )
            gate_attestation_ok = verification.returncode == 0 and gate_identity_ok
        except (ValueError, OSError, TypeError, subprocess.TimeoutExpired):
            gate_attestation_ok = False
    production_ok = bool(attestation_ok and identity_ok and test_ok and gate_attestation_ok)
    facts = product.get("facts", {}) if gate_attestation_ok else {}
    profile = product.get("deployment_profile") if gate_attestation_ok else None
    if production_ok:
        profile_fact = facts.get("profile", {})
        custody_fact = facts.get("custody", {})
        signer_fact = facts.get("post_quantum_signer", {})
        production_ok = bool(
            product.get("status") == "PASS"
            and profile_fact.get("name") == profile and profile_fact.get("verified") is True
            and custody_fact.get("authority") == "THESEUS" and custody_fact.get("verified") is True
            and custody_fact.get("profile") == profile
            and signer_fact.get("algorithm") == "ML-DSA-65" and signer_fact.get("verified") is True
        )
    if production_ok:
        gates = {gate: "PASS" if product["gates"].get(gate) == "PASS" else "UNQUALIFIED"
                 for gate in MANDATORY}
    verdict=qualify(ci_gates=gates, attestation_verified=production_ok)
    output={"status":verdict.status,"blockers":list(verdict.unqualified),
            "attestation_verified":bool(attestation_ok and identity_ok),
            "test_evidence_attestation_verified":bool(attestation_ok and identity_ok),
            "gate_attestation_verified":gate_attestation_ok,
            "production_evidence_verified":production_ok,
            "deployment_profile":profile,
            "product_gate_status":product.get("status") if gate_attestation_ok else None,
            "product_facts":facts,
            "test_suite_pass":bool(test_ok),"gates":gates,
            "claims":dispositions(gates, production_ok,
                                  deployment_profile=profile, product_facts=facts)}
    target=Path(a.output)
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(output,indent=2,sort_keys=True)+"\n")
    print(json.dumps(output,sort_keys=True))
    # Success here means the signed evidence was actually verified and assessed,
    # NOT that the product qualified. UNQUALIFIED remains explicit in the verdict.
    return 0 if attestation_ok and identity_ok and (not a.product_gates or gate_attestation_ok) else 1
if __name__=="__main__":
    raise SystemExit(main())
