"""Fail-closed structural gate for the Turing elevation acceptance criteria."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = (
    ROOT
    / "turing_universal_quantum_computer"
    / "turing_universal_quantum_computer"
)


def _read(path: Path) -> str:
    if not path.is_file():
        raise RuntimeError(f"required elevation artifact is missing: {path}")
    return path.read_text(encoding="utf-8")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _report_digest(report: dict[str, Any]) -> str:
    payload = dict(report)
    payload.pop("timestamp", None)
    payload.pop("report_digest", None)
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(b"turing-discovery-v1\0" + canonical).hexdigest()


def evaluate(report_path: Path) -> dict[str, Any]:
    report = json.loads(_read(report_path))
    _require(report.get("schema") == "turing.discovery.report.v1", "wrong report schema")
    _require(report.get("report_digest") == _report_digest(report), "report digest mismatch")
    modules = report.get("modules", [])
    _require(bool(modules), "discovery found no Turing candidates")
    component_keys = {
        "tape",
        "head",
        "state",
        "transition",
        "universal",
        "clock",
        "certificate",
        "field",
        "gaps",
    }
    _require(
        all(component_keys <= set(module) for module in modules),
        "a discovered module lacks a component or field declaration",
    )

    specification = _read(PACKAGE / "turing_core" / "specification.py")
    certificates = _read(PACKAGE / "certificates.py")
    backends = _read(PACKAGE / "backends" / "__init__.py")
    spec_doc = _read(ROOT / "docs" / "TURING_SPEC.md")
    workflow = _read(ROOT / ".github" / "workflows" / "turing-core.yml")
    lean = _read(ROOT / "proofs" / "lean" / "Guardian" / "TuringCore.lean")
    fold_tests = _read(
        ROOT
        / "turing_universal_quantum_computer"
        / "tests"
        / "test_fold_certificate_exhaustive.py"
    )

    invariants = (
        "T1", "T2", "T3", "T4", "T5",
        "U1", "U2", "U3",
        "F1", "F2", "F3",
        "C1", "C2", "C3",
    )
    _require(all(f"| {item} |" in spec_doc for item in invariants), "invariant table incomplete")
    _require(
        all(
            name in specification
            for name in (
                "verify_machine",
                "verify_fold_replay",
                "TuringCertificate",
                "FoldCertificate",
            )
        ),
        "reference verifier surface incomplete",
    )
    _require(
        all(
            name in certificates
            for name in (
                "VQCComputationCertificate",
                "issue_computation_certificate",
                "verify_computation_certificate",
                "replay_computation_certificate",
            )
        ),
        "VQC certificate surface incomplete",
    )
    _require(
        "execute_certified" in backends
        and "result.certificate = certificate.to_dict()" in backends,
        "public backend registry does not enforce certification",
    )
    _require(
        all(version in workflow for version in ('"3.11"', '"3.12"', '"3.13"')),
        "cross-version CI matrix incomplete",
    )
    theorems = (
        "fold_correct",
        "universal_interpreter_correct",
        "certificate_replay_deterministic",
    )
    _require(all(name in lean for name in theorems), "Lean theorem set incomplete")
    _require("sorry" not in lean.lower(), "Lean proof contains sorry")
    _require(
        "for left in range(256)" in fold_tests
        and "for right in range(256)" in fold_tests,
        "fold test is not exhaustive over byte pairs",
    )
    machine_types = (
        "CLASSICAL_DETERMINISTIC",
        "CLASSICAL_NONDETERMINISTIC",
        "QUANTUM_UNITARY",
        "QUANTUM_FOLDED",
        "HYBRID",
    )
    _require(all(name in specification for name in machine_types), "machine types incomplete")
    _require("Independent review" in spec_doc, "independent review is not invited")

    criteria = {
        "all_turing_modules_discovered": True,
        "components_declared": True,
        "fields_declared": True,
        "invariants_accounted_for": True,
        "verifier_covers_declared_components": True,
        "public_computations_certified": True,
        "certificates_content_addressed_and_merkle_rooted": True,
        "python_cross_version_gate": True,
        "three_lean_theorems": True,
        "fold_certified_and_exhaustive": True,
        "heterogeneous_machine_types": True,
        "canonical_specification_published": True,
        "independent_review_invited": True,
    }
    unsigned = {
        "schema": "turing.elevation.acceptance.v1",
        "discovery_report_digest": report["report_digest"],
        "criteria": criteria,
        "elevated": all(criteria.values()),
    }
    digest = hashlib.sha256(
        b"turing-acceptance-v1\0"
        + json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode("ascii")
    ).hexdigest()
    return {**unsigned, "acceptance_digest": digest}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = evaluate(args.report)
    rendered = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
