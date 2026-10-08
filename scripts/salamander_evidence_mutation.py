"""Execute bounded evidence-boundary mutants in isolated copies, never production.

These mutants qualify contract tests only. They do not certify missing owner
actuators, rollback, recovery budgets or real-component production voyages.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
MUTANTS = (
    ("remove_authorization_decision", "salamander/outcome_evidence.py",
     'if authorization.get("decision") != "ALLOW" or not authorization.get("policy_version"):',
     'if not authorization.get("policy_version"):'),
    ("allow_synthetic_observation", "salamander/outcome_evidence.py",
     'self.evidence_class in {EvidenceClass.OBSERVED, EvidenceClass.MEASURED}',
     'self.evidence_class in {EvidenceClass.OBSERVED, EvidenceClass.MEASURED, EvidenceClass.SIMULATED}'),
    ("ignore_postcondition_contract", "salamander/outcome_evidence.py",
     'if not obs.matches_contract():', 'if False:'),
    ("allow_self_verification", "salamander/outcome_evidence.py",
     'if postcondition.get("verifier_id") == execution.get("actuator_id"):', 'if False:'),
    ("ignore_custody_corruption", "salamander/outcome_evidence.py",
     'if verdict.get("passed") is not True:', 'if False:'),
    ("shadow_domain_authority", "salamander/outcome_evidence.py",
     'if binding is None or binding.get("source_system") != source:', 'if binding is None:'),
    ("restore_false_green_health", "salamander/runtime.py",
     'execution_health = "FAILED" if completion == "DEVICE_ERROR" else None',
     'execution_health = "FAILED" if completion == "DEVICE_ERROR" else "HEALTHY"'),
)


def execute(root: Path):
    started = time.monotonic()
    completed = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests",
         "-p", "test_salamander_outcome_evidence.py"],
        cwd=root, capture_output=True, text=True, timeout=30,
    )
    output = completed.stdout + completed.stderr
    return {"exit_code": completed.returncode, "duration_seconds": time.monotonic() - started,
            "log_sha256": hashlib.sha256(output.encode()).hexdigest(), "output": output}


def main():
    report = {"schema": "salamander.local-evidence-mutations/v1",
              "evidence_class": "LOCAL_CONTRACT_TEST", "production_composition": "UNAVAILABLE"}
    baseline = execute(ROOT)
    report["baseline"] = baseline
    if baseline["exit_code"] != 0:
        raise SystemExit("baseline failed; mutants not executable")
    results = []
    for name, filename, old, new in MUTANTS:
        with tempfile.TemporaryDirectory(prefix="salamander-mutation-") as directory:
            root = Path(directory)
            shutil.copytree(ROOT / "salamander", root / "salamander", ignore=shutil.ignore_patterns("__pycache__"))
            (root / "tests").mkdir()
            shutil.copy(ROOT / "tests/test_salamander_outcome_evidence.py", root / "tests")
            path = root / filename
            text = path.read_text()
            if text.count(old) != 1:
                raise SystemExit(f"mutation anchor not unique: {name}")
            path.write_text(text.replace(old, new, 1))
            result = execute(root)
            result.update(name=name, killed=result["exit_code"] != 0,
                          mutated_source_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            results.append(result)
    report["mutants"] = results
    report["killed"] = sum(r["killed"] for r in results)
    report["survived"] = sum(not r["killed"] for r in results)
    destination = ROOT / "reports/salamander_evidence_mutations.json"
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("killed", "survived")}))
    return 0 if report["survived"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
