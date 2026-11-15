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
    gate_identity_ok=False
    gate_attestation_ok=False
    if a.product_gates:
        try:
            gate_doc=json.loads(Path(a.product_gates).read_text())
            gate_identity_ok=(
                gate_doc.get("schema")=="chronus-product-gates-v1"
                and gate_doc.get("commit")==a.expected_commit
                and str(gate_doc.get("run_id"))==str(a.expected_run_id)
            )
            gate_verification=subprocess.run(
                ["gh","attestation","verify",a.product_gates,"--repo",a.repository],
                capture_output=True,text=True,timeout=60,check=False
            )
            gate_attestation_ok=gate_verification.returncode==0
            if gate_identity_ok and gate_attestation_ok:
                supplied=gate_doc.get("gates",{})
                gates={gate:("PASS" if supplied.get(gate)=="PASS" else "UNQUALIFIED") for gate in MANDATORY}
        except (ValueError,OSError,TypeError,subprocess.TimeoutExpired):
            gate_identity_ok=gate_attestation_ok=False

    verified=bool(attestation_ok and identity_ok and test_ok and gate_identity_ok and gate_attestation_ok)
    verdict=qualify(
        ci_gates=gates,
        attestation_verified=verified,
        key_provider=a.key_provider,
    )
    output={
        "status":verdict.status,
        "blockers":list(verdict.unqualified),
        "attestation_verified":verified,
        "test_suite_pass":bool(test_ok),
        "gate_attestation_verified":bool(gate_identity_ok and gate_attestation_ok),
        "gates":gates,
        "claims":dispositions(gates, verified),
    }
    target=Path(a.output)
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(output,indent=2,sort_keys=True)+"\n")
    print(json.dumps(output,sort_keys=True))
    # Evaluation integrity and product admission are deliberately separate.
    # A verified evidence bundle may truthfully produce UNQUALIFIED while the
    # workflow itself succeeds. Release publication must inspect output.status
    # and require PASS separately.
    evaluation_integrity_ok = bool(attestation_ok and identity_ok)
    if a.product_gates:
        evaluation_integrity_ok = bool(
            evaluation_integrity_ok and gate_identity_ok and gate_attestation_ok
        )
    return 0 if evaluation_integrity_ok else 1

if __name__=="__main__":
    raise SystemExit(main())
