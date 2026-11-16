"""Evaluate verified Actions artifact; verification is performed by gh attestation verify.

This tool MUST be called only after the external gh attestation verify command
returns success for the exact evidence file and expected repository.
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
    a=p.parse_args()
    try:
        evidence=json.loads(Path(a.evidence).read_text())
        identity_ok=(evidence.get("commit")==a.expected_commit and evidence.get("run_id")==a.expected_run_id and evidence.get("schema")=="chronus-ci-test-evidence-v1")
        test_ok=evidence.get("status")=="PASS" and evidence.get("tests",{}).get("skipped")==0 and evidence.get("tests",{}).get("failed")==0 and evidence.get("tests",{}).get("total",0)>0
    except (ValueError, OSError, TypeError) as exc:
        identity_ok=test_ok=False
        evidence={"error":str(exc)}
    try:
        verification=subprocess.run(["gh","attestation","verify",a.evidence,"--repo",a.repository],capture_output=True,text=True,timeout=60,check=False)
        attestation_ok=verification.returncode==0
    except (OSError, subprocess.TimeoutExpired):
        attestation_ok=False
    # Individual product gates are NOT inferred from a green pytest run.
    gates={gate:"UNQUALIFIED" for gate in MANDATORY}
    verdict=qualify(ci_gates=gates, attestation_verified=bool(attestation_ok and identity_ok and test_ok))
    output={"status":verdict.status,"blockers":list(verdict.unqualified),
            "attestation_verified":bool(attestation_ok and identity_ok),
            "test_suite_pass":bool(test_ok),"gates":gates,
            "claims":dispositions(gates, bool(attestation_ok and identity_ok and test_ok))}
    target=Path(a.output)
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(output,indent=2,sort_keys=True)+"\n")
    print(json.dumps(output,sort_keys=True))
    return 0 if verdict.status=="PASS" else 1
if __name__=="__main__":
    raise SystemExit(main())
