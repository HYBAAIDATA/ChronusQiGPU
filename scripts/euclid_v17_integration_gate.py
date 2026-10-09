"""Fail-closed admission gate for the canonical EUCLID 17 integration.

Source checks and fresh, named behavioral tests must both pass. The result
records source identity and does not certify whole-product production readiness.
"""

from __future__ import annotations

import ast
import argparse
import hashlib
import json
import platform
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "euclid-v17-integration-gates.json"


def _method_names(path: Path, class_name: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return {
                item.name
                for item in node.body
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
    return set()


def _version() -> str | None:
    text = (ROOT / "euclid" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', text, re.MULTILINE)
    return match.group(1) if match else None


def run_qualification(root: Path, nodes: list[str], *, timeout: float) -> dict[str, object]:
    """Execute required nodes and reject absent, skipped or malformed evidence."""
    result: dict[str, object] = {"passed": False, "required_nodes": nodes}
    if not nodes or len(nodes) != len(set(nodes)):
        return {**result, "error": "qualification nodes must be nonempty and unique"}
    with tempfile.TemporaryDirectory(prefix="euclid-qualification-") as tmp:
        report = Path(tmp) / "qualification.xml"
        try:
            completed = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", *nodes, f"--junitxml={report}"],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {**result, "error": type(exc).__name__}
        result["exit_code"] = completed.returncode
        result["output_tail"] = (completed.stdout + completed.stderr)[-6000:]
        try:
            document = ET.parse(report).getroot()
            if document.tag not in {"testsuites", "testsuite"}:
                raise ValueError("unexpected JUnit root")
            cases = list(document.iter("testcase"))
            expected = []
            for node in nodes:
                parts = node.split("::")
                if len(parts) < 2:
                    raise ValueError("qualification must name individual tests")
                expected.append(
                    (parts[-1], ".".join(parts[:-1]).replace(".py", "").replace("/", "."))
                )
            observed = [(case.get("name"), case.get("classname")) for case in cases]
            rejected = [
                case.get("name")
                for case in cases
                if any(case.find(tag) is not None for tag in ("failure", "error", "skipped"))
            ]
            suites = list(document.iter("testsuite"))
            reported = sum(int(suite.attrib["tests"]) for suite in suites)
            result.update(
                {
                    "tests": len(cases),
                    "rejected_tests": rejected,
                    "missing_tests": [name for name in expected if name not in observed],
                    "junit_sha256": hashlib.sha256(report.read_bytes()).hexdigest(),
                }
            )
            result["passed"] = bool(
                completed.returncode == 0
                and not rejected
                and reported == len(cases)
                and sorted(observed) == sorted(expected)
            )
        except (OSError, ET.ParseError, ValueError, KeyError, TypeError) as exc:
            result["error"] = f"invalid qualification evidence: {type(exc).__name__}"
    return result


def source_identity(root: Path) -> dict[str, object]:
    """Hash the executable integration inputs separately from Git's commit id."""
    paths: set[Path] = set()
    for package in (
        "euclid",
        "aethel",
        "hyba_db",
        "hyba_substrate",
        "resonance_intelligence",
        "toe",
        "kellogg",
    ):
        paths.update((root / package).rglob("*.py"))
    paths.update((root / "tests").glob("test_euclid_v17_*.py"))
    paths.update((root / "tests").glob("test_theseus_long_paths.py"))
    paths.update((root / "tests").glob("test_euclid_v17_integration_gate.py"))
    paths.update((root / "tests").glob("test_m3_adversarial.py"))
    paths.update((root / "tests").glob("test_storage_database_ontology_v3.py"))
    paths.update({root / "config/euclid-v17-integration-gates.json", Path(__file__).resolve()})
    manifest = {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(paths)
    }
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=False
    )
    if commit.returncode != 0:
        raise ValueError("source commit is unavailable")
    return {
        "commit": commit.stdout.strip(),
        "files": len(manifest),
        "manifest_sha256": hashlib.sha256(
            json.dumps(manifest, sort_keys=True).encode()
        ).hexdigest(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--timeout", type=float, default=480)
    args = parser.parse_args(argv)
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    failures: list[str] = []
    checks: dict[str, object] = {}

    version = _version()
    checks["version"] = version
    if version != config["version"]:
        failures.append(f"euclid.__version__={version!r}; expected {config['version']!r}")

    missing = [path for path in config["required_paths"] if not (ROOT / path).exists()]
    checks["missing_required_paths"] = missing
    if missing:
        failures.append("missing exact v17 source paths: " + ", ".join(missing))

    runtime = ROOT / "euclid" / "runtime.py"
    methods = _method_names(runtime, "EuclidRuntime")
    missing_methods = sorted(set(config["required_runtime_methods"]) - methods)
    checks["missing_runtime_methods"] = missing_methods
    if missing_methods:
        failures.append("canonical EuclidRuntime lacks v17 methods: " + ", ".join(missing_methods))

    runtime_text = runtime.read_text(encoding="utf-8")
    private_adaptive_json = "adaptive_knowledge.json" in runtime_text
    checks["private_adaptive_json_in_runtime"] = private_adaptive_json
    if private_adaptive_json:
        failures.append(
            "EuclidRuntime still names private adaptive_knowledge.json; canonical "
            "OVID/THESEUS persistence must own production adaptive state"
        )

    final_doc = ROOT / "docs" / "EUCLID_V17_RESEARCH_RELEASE.md"
    doc_text = final_doc.read_text(encoding="utf-8") if final_doc.exists() else ""
    checks["release_doc_rc"] = "17.0.0-rc" in doc_text
    if "17.0.0-rc" in doc_text:
        failures.append("EUCLID v17 release document is still an RC document")

    # Each F1-F6 requirement is qualified by named, freshly executed tests.
    production_test = ROOT / "tests" / "test_euclid_v17_production_integration.py"
    checks["production_integration_test_present"] = production_test.exists()
    if not production_test.exists():
        failures.append(
            "tests/test_euclid_v17_production_integration.py is absent; "
            "F1-F6 have no executable qualification"
        )

    try:
        before = source_identity(ROOT)
        checks["source"] = before
        declared = [
            f"tests/test_euclid_v17_production_integration.py::{node.name}::{method.name}"
            for node in ast.parse(production_test.read_text(encoding="utf-8")).body
            if isinstance(node, ast.ClassDef)
            for method in node.body
            if isinstance(method, ast.FunctionDef) and method.name.startswith("test_")
        ]
        coverage = {f"F{number}" for node in declared for number in re.findall(r"f([1-6])", node)}
        if set(config["qualification_nodes"]) != set(declared) or coverage != {
            "F1",
            "F2",
            "F3",
            "F4",
            "F5",
            "F6",
        }:
            failures.append("qualification configuration omits required integration tests")
        qualification = run_qualification(ROOT, config["qualification_nodes"], timeout=args.timeout)
        checks["qualification"] = qualification
        if not qualification["passed"]:
            failures.append("fresh F1-F6 qualification failed or evidence was incomplete")
        if source_identity(ROOT) != before:
            failures.append("source changed during qualification")
    except (OSError, ValueError, KeyError) as exc:
        failures.append(f"qualification/source identity unavailable: {type(exc).__name__}")

    result = {
        "schema": "euclid.v17.integration-gate-result/1",
        "passed": not failures,
        "checks": checks,
        "failures": failures,
        "closure_requirements": config["closure_requirements"],
        "claim_boundary": config["claim_boundary"],
        "python": sys.version,
        "platform": platform.platform(),
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
