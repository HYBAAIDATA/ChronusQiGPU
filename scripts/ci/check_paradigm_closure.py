"""Run exact closure sentinels, source purity, and commit-bound findings checks."""
from __future__ import annotations

import argparse
import ast
import datetime
import json
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from chronus.core.purity_scanner import scan_file
from chronus.research.paradigm_seal import seal, validate_findings, verify_seal

ROOT = Path(__file__).resolve().parents[2]
SOURCES = (
    "src/chronus/storage/chrn_frame.py",
    "src/chronus/storage/chrn_rs257.py",
    "src/chronus/storage/positional_codec.py",
    "src/chronus/math/fold_ledger.py",
    "src/chronus/research/torus_certificate.py",
    "src/chronus/research/paradigm_seal.py",
)
TESTS = ("tests/test_chrn_frame.py", "tests/test_paradigm_closure.py", "tests/test_chrn_rs257.py")
FINDINGS = "evidence/storage/paradigm_findings.json"


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-only", action="store_true",
                        help="Allow open findings in evidence reports; never allow failed tests.")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    commit = git("rev-parse", "HEAD").decode().strip()
    if git("status", "--porcelain", "--untracked-files=no"):
        raise SystemExit("closure evidence requires a clean tracked worktree")
    violations = []
    for relative in SOURCES:
        path = ROOT / relative
        violations.extend(scan_file(path))
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and type(node.value) in (float, complex):
                violations.append(f"{relative}:{node.lineno}: inexact literal")
    registry = json.loads(git("show", f"{commit}:{FINDINGS}"))
    if registry.get("schema") != "chronus.closure-findings/1":
        raise SystemExit("unsupported findings schema")
    pending = validate_findings(ROOT, registry["items"], commit)
    with tempfile.TemporaryDirectory() as tmp:
        xml = Path(tmp) / "junit.xml"
        proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "-rs",
                               *TESTS, "-o", "addopts=", f"--junitxml={xml}"],
                              cwd=ROOT, check=False)
        cases = list(ET.parse(xml).getroot().iter("testcase")) if xml.exists() else []
        passed = sum(not any(c.find(tag) is not None for tag in ("failure","error","skipped"))
                     for c in cases)
        names = [c.attrib.get("name","") for c in cases]
        sentinels = ("test_sentinel_positional_total", "test_sentinel_group_law_and_inverse",
                     "test_sentinel_torus", "test_sentinel_content_only_digest",
                     "test_recovery_known_answer_and_boundary")
        present = all(any(n==s or n.startswith(s+"[") for n in names) for s in sentinels)
        tests_ok = proc.returncode==0 and bool(cases) and passed==len(cases) and present
    software_ok = tests_ok and not violations
    content = {"source_commit":commit,"tests":len(cases),"passed":passed,
               "all_sentinels_present":present,"test_exit_code":proc.returncode,
               "purity_violations":violations,"open_findings":list(pending),
               "software_checks_passed":software_ok,
               "closure_sealed":software_ok and not pending,
               "production_qualification":"NOT_ASSESSED"}
    envelope = seal(content, sealed_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
    if not verify_seal(envelope):
        raise SystemExit("closure evidence verification failed")
    encoded = json.dumps(envelope,indent=2,sort_keys=True)+"\n"
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(encoded,encoding="utf-8")
    print(encoded)
    return 0 if software_ok and (args.report_only or not pending) else 1


if __name__ == "__main__":
    raise SystemExit(main())
