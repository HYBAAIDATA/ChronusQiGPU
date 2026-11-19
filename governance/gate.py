"""Fail-closed Golden Ontology QC gate.

The trusted reviewer is provisioned by release governance, not by this register.
A JSON status alone is never an authenticated acceptance.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.request import Request,urlopen

ROOT=Path(__file__).resolve().parents[1]
REPO="HYBAAIDATA/ChronusQiGPU"
SCOPE=("golden_ontology","spec/GOLDEN_ONTOLOGY.md","spec/test_vectors.json",
       "tests/test_golden_ontology.py","formal/GoldenFold.lean",
       "formal/check_golden_fold.sh","verify","governance/gate.py",
       "scripts/fold_verify.py","src/chronus/math/golden_nature.py",
       "src/chronus/research/golden_nature_reference.py",
       "tests/test_golden_nature_exact.py","tests_installed/test_golden_ontology_installed.py",
       ".github/workflows/golden-ontology.yml","pyproject.toml")

def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def _github(path):
    token=os.environ.get("GITHUB_TOKEN")
    if not token:
        raise ValueError("authenticated review API unavailable")
    req=Request("https://api.github.com/repos/"+REPO+path,
                headers={"Authorization":"Bearer "+token,"Accept":"application/vnd.github+json",
                         "User-Agent":"golden-ontology-qc-gate"})
    with urlopen(req,timeout=15) as result:
        return json.load(result)

def validate(data):
    if not isinstance(data,dict) or data.get("package")!="golden_ontology" or data.get("version")!="2.0.0":
        raise ValueError("invalid package register")
    records=data.get("findings")
    if not isinstance(records,list) or not records:
        raise ValueError("missing mandatory findings")
    ids=set()
    for rec in records:
        if (not isinstance(rec,dict) or not all(type(rec.get(k)) is str and rec[k]
                for k in ("id","title","status","owner")) or rec["id"] in ids
                or rec["status"] not in {"OPEN","CLOSED"}):
            raise ValueError("invalid or duplicate finding")
        ids.add(rec["id"])
    if "QC-001" not in ids:
        raise ValueError("mandatory QC-001 missing")
    open_ids=[f["id"] for f in records if f["status"]!="CLOSED"]
    if open_ids:
        return "open findings: "+", ".join(open_ids)
    # Other findings require their own explicit validators; do not silently
    # grant closure to unknown findings merely because their status is CLOSED.
    if ids!={"QC-001"}:
        raise ValueError("no authenticated validator for additional findings")
    rec=records[0]
    reviewer=os.environ.get("GOLDEN_QC_REVIEWER")
    if not reviewer or rec.get("reviewer")!=reviewer:
        raise ValueError("authorized independent reviewer not provisioned")
    commit=rec.get("reviewed_commit","")
    review_id=rec.get("review_id")
    if not re.fullmatch(r"[0-9a-f]{40}",commit) or type(review_id) is not int or review_id<=0:
        raise ValueError("missing immutable review reference")
    for filename,key in (("spec/GOLDEN_ONTOLOGY.md","spec_sha256"),("spec/test_vectors.json","vectors_sha256")):
        if rec.get(key)!=_sha(ROOT/filename):
            raise ValueError("review digest mismatch")
    if type(rec.get("mismatch_count")) is not int or rec["mismatch_count"]!=0:
        raise ValueError("missing zero-mismatch reconstruction")
    evidence=rec.get("evidence_url","")
    if not isinstance(evidence,str) or not evidence.startswith("https://github.com/"+REPO+"/"):
        raise ValueError("missing attributable evidence URL")
    if subprocess.run(["git","diff","--exit-code",commit,"--",*SCOPE],cwd=ROOT,
                      capture_output=True,check=False).returncode:
        raise ValueError("reviewed scope changed")
    pr=_github("/pulls/207")
    review=_github("/pulls/207/reviews/"+str(review_id))
    if (pr["user"]["login"].casefold()==reviewer.casefold() or
        review.get("state")!="APPROVED" or review.get("commit_id")!=commit or
        review["user"]["login"].casefold()!=reviewer.casefold()):
        raise ValueError("no matching independent GitHub approval")
    body=review.get("body") or ""
    if not all(token in body for token in (evidence,rec["spec_sha256"],rec["vectors_sha256"])):
        raise ValueError("review does not attest the report and exact specification digests")
    return None

def main():
    try:
        reason=validate(json.loads((ROOT/"FINDINGS.json").read_text(encoding="utf-8")))
        if reason:
            print("HOLD:",reason)
            return 1
    except (OSError,ValueError,TypeError,KeyError,AttributeError,subprocess.SubprocessError) as exc:
        print("HOLD:",exc)
        return 1
    print("QC gate passed; other release gates remain independent.")
    return 0

if __name__=="__main__":
    sys.exit(main())
