"""Three explicit regression mutants in disposable copies, never the checkout.

A control must pass first. A mutant is detected only by a real test failure,
not a collection/infrastructure error. This is not a whole-project mutation score.
"""

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from uuid import uuid4
from xml.etree import ElementTree

PROJECT = Path(__file__).resolve().parents[1]
MUTANTS = (
    (
        "parameter_identity",
        "contracts.py",
        "if self.names != tuple(s.name for s in schema):",
        "if False:",
        "test_public_api_dropin.py::test_parameter_identity",
    ),
    (
        "exact_ordering",
        "optimizer.py",
        "return (a < 0) if a * a > 2 * b * b else (b < 0)",
        "return (a > 0) if a * a > 2 * b * b else (b > 0)",
        "test_public_api_dropin.py::test_exact_comparison_near_float_tie",
    ),
    (
        "normalization",
        "native_adapter.py",
        "if (norm_a, norm_b) != (Fraction(1), Fraction(0)):",
        "if False:",
        "test_release_qualification.py::test_non_normalized_exact_state_is_rejected",
    ),
)


def run(output):
    output.mkdir(parents=True, exist_ok=True)
    path = output / ("targeted_mutations_" + uuid4().hex + ".json")
    report = {
        "schema": "turing.targeted_mutations.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "scope": "three_explicit_regression_mutants_not_full_project_score",
        "status": "running",
        "mutants": [],
    }
    from run_experiment import source_identity

    report["source"] = source_identity(PROJECT.parent)
    failure = None
    try:
        with tempfile.TemporaryDirectory(prefix="turing-targeted-mutations-") as directory:
            root = Path(directory)
            tests = root / "tests"
            tests.mkdir()
            for name in ("test_public_api_dropin.py", "test_release_qualification.py"):
                shutil.copy2(PROJECT / "tests" / name, tests / name)
            code = """
from pathlib import Path
import sys
sys.path.insert(0, sys.argv[1])
import turing_universal_quantum_computer as t
assert Path(t.__file__).resolve().parent.parent == Path(sys.argv[1]).resolve()
import pytest
raise SystemExit(pytest.main(sys.argv[2:]))
"""
            for label, module, original, replacement, target in [
                ("control", None, None, None, None),
                *MUTANTS,
            ]:
                copy_root = root / label
                copy_root.mkdir()
                package = copy_root / "turing_universal_quantum_computer"
                shutil.copytree(
                    PROJECT / "turing_universal_quantum_computer",
                    package,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
                )
                if module:
                    file = package / module
                    text = file.read_text()
                    if text.count(original) != 1:
                        raise ValueError("Mutation anchor drift: " + label)
                    file.write_text(text.replace(original, replacement, 1))
                junit = root / (label + ".xml")
                selected = str(tests) if target is None else str(tests / target)
                process = subprocess.run(
                    [
                        sys.executable,
                        "-I",
                        "-c",
                        code,
                        str(copy_root),
                        "--rootdir=" + str(root),
                        "--confcutdir=" + str(root),
                        selected,
                        "-q",
                        "--junitxml=" + str(junit),
                    ],
                    cwd=root,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if not junit.exists():
                    raise RuntimeError("No JUnit evidence for " + label)
                xml = ElementTree.parse(junit)
                failures = len(xml.findall(".//testcase/failure"))
                errors = len(xml.findall(".//testcase/error"))
                if label == "control":
                    report["control"] = {
                        "exit_code": process.returncode,
                        "failures": failures,
                        "errors": errors,
                    }
                    if process.returncode != 0 or failures or errors:
                        raise RuntimeError("Unmutated control did not pass")
                else:
                    killed = process.returncode == 1 and failures > 0 and errors == 0
                    report["mutants"].append(
                        {
                            "name": label,
                            "module": module,
                            "target": target,
                            "detected": killed,
                            "exit_code": process.returncode,
                            "assertion_failures": failures,
                            "errors": errors,
                        }
                    )
                    if not killed:
                        raise RuntimeError("Mutant survived or infrastructure failed: " + label)
        report["status"] = "passed"
    except Exception as error:
        failure = error
        report["status"] = "failed"
        report["failure"] = str(error)
    report["manifest_digest"] = sha256(
        json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    with path.open("x") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    if failure:
        raise RuntimeError("Targeted mutation check failed: " + str(path)) from failure
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    print(run(parser.parse_args().output))
