"""Produce Actions test evidence from JUnit, never from claimed pass counts."""
from __future__ import annotations
import argparse
import json
import os
import ssl
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
import cryptography

def build(xml_path: Path, out: Path) -> int:
    root=ET.parse(xml_path).getroot()
    cases=list(root.iter("testcase"))
    if not cases:
        raise ValueError("no test cases")
    failed=sum(bool(list(c.iter("failure")) or list(c.iter("error"))) for c in cases)
    skipped=sum(bool(list(c.iter("skipped"))) for c in cases)
    data={
        "schema": "chronus-ci-test-evidence-v1",
        "repository": os.environ.get("GITHUB_REPOSITORY", "UNAVAILABLE"),
        "commit": os.environ.get("GITHUB_SHA", "UNAVAILABLE"),
        "run_id": os.environ.get("GITHUB_RUN_ID", "UNAVAILABLE"),
        "runner": os.environ.get("RUNNER_OS", "UNAVAILABLE"),
        "python": sys.version.split()[0],
        "cryptography": cryptography.__version__,
        "openssl": ssl.OPENSSL_VERSION,
        "tests": {"total": len(cases), "failed": failed, "skipped": skipped, "passed": len(cases)-failed-skipped},
        "status": "PASS" if failed == 0 and skipped == 0 else "UNQUALIFIED",
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2, sort_keys=True)+"\n")
    return 0 if data["status"]=="PASS" else 1

def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument("--junit", required=True)
    p.add_argument("--output", required=True)
    a=p.parse_args()
    try:
        return build(Path(a.junit), Path(a.output))
    except Exception as exc:
        print(f"UNQUALIFIED: {exc}")
        return 1
if __name__=="__main__":
    raise SystemExit(main())
