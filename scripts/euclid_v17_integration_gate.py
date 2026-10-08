"""Fail-closed admission gate for the canonical EUCLID 17 integration.

This gate intentionally distinguishes the reported research release from
whole-product production qualification. It may pass source-presence checks
only when the exact v17 implementation is in the repository; runtime behavior
is then proved by the dedicated production-integration tests.
"""

from __future__ import annotations

import ast
import json
import re
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


def main() -> int:
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

    # F1-F6 are behavioral. Presence of the exact implementation is not enough:
    # the production integration test module is mandatory and must be executed.
    production_test = ROOT / "tests" / "test_euclid_v17_production_integration.py"
    checks["production_integration_test_present"] = production_test.exists()
    if not production_test.exists():
        failures.append(
            "tests/test_euclid_v17_production_integration.py is absent; "
            "F1-F6 have no executable qualification"
        )

    result = {
        "schema": "euclid.v17.integration-gate-result/1",
        "passed": not failures,
        "checks": checks,
        "failures": failures,
        "closure_requirements": config["closure_requirements"],
        "claim_boundary": config["claim_boundary"],
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
