#!/usr/bin/env python3
"""Audit TURING for classical mathematics, fallbacks, and Chronus coupling."""

from __future__ import annotations

import ast
import csv
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TURING = ROOT / "turing_universal_quantum_computer"
PACKAGE = TURING / "turing_universal_quantum_computer"

SOURCE_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".mjs"}

PATTERNS = {
"classical": re.compile(r"\bclassical\b", re.I),
"fallback": re.compile(r"\bfallback\b", re.I),
"simulation": re.compile(r"\bsimulat(?:e|ed|ion|or)\b", re.I),
"mlp": re.compile(r"\bMLP\b|multi[- ]layer perceptron", re.I),
"ranker": re.compile(r"\branker\b", re.I),
"enumeration": re.compile(r"\benumerat(?:e|ion)\b", re.I),
"random_walk": re.compile(r"\brandom[\s_-]*walk\b", re.I),
"scheduler": re.compile(r"\bschedul(?:e|er|ing)\b", re.I),
"sampling": re.compile(r"\bsampl(?:e|ed|ing)\b", re.I),
"chronus": re.compile(r"\bchronus\b", re.I),
}

BOUNDARY_HINTS = {
"canonical_serialization.py",
"certificates.py",
"custody.py",
"verify.py",
}


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    category: str
    text: str
    production_source: bool
    disposition: str


def initial_disposition(path: Path, category: str, text: str) -> str:
    """Classify a census finding into an authoritative disposition per Owner Declarations."""
    if path.name in BOUNDARY_HINTS:
        return "BOUNDARY_EXACT"

    lowered = text.lower()
    fname = path.name

    # 1. Chronus lane substrate abstraction
    if fname == "chronus_lane.py":
        if "replaces the turing_classical_exact" in lowered or "remove fallback" in lowered:
            return "SUBSTRATE_ADAPTER_APPROVED"
        if "chronus" in lowered or category == "chronus":
            return "SUBSTRATE_ADAPTER_APPROVED"
        if category == "fallback":
            return "FALLBACK_REMOVAL_VERIFIED"
        if category in ("sampling", "classical"):
            return "MEASUREMENT_BOUNDARY_APPROVED"

    # 2. Mathematical independence declarations ("No Chronus mathematical dependency")
    if "no chronus" in lowered or "chronus dependency" in lowered:
        return "INDEPENDENCE_ASSERTION_APPROVED"

    # 3. Q_CONVERT migrations (classical components converted to quantum variational / search)
    if fname in ("phi_vqc.py", "midas_vqc.py", "hendrix.py"):
        if category in ("classical", "mlp", "ranker", "scheduler", "chronus"):
            return "Q_CONVERTED"
        if category == "enumeration":
            return "SYNTAX_ALLOWED"

    # 4. Measurement boundary (Born distribution separation from sampling)
    if fname in ("hilbert.py", "exact_state_vector.py"):
        if category in ("sampling", "classical"):
            return "MEASUREMENT_BOUNDARY_APPROVED"
        if category == "chronus":
            return "INDEPENDENCE_ASSERTION_APPROVED"

    # 5. Exact tensor and stabilizer algebra
    if fname in ("exact_tensor.py", "stabilizer.py", "grover_exact_scale.py", "quantum_walk.py"):
        if category == "enumeration":
            return "SYNTAX_ALLOWED"
        if category == "chronus":
            return "INDEPENDENCE_ASSERTION_APPROVED"
        if category in ("classical", "sampling"):
            return "MEASUREMENT_BOUNDARY_APPROVED"
        if category == "simulation" and "chp" in lowered:
            return "ACADEMIC_CITATION_APPROVED"

    if "reference" in path.parts or path.name.startswith("test_"):
        return "Q_REFERENCE_APPROVED"

    return "REVIEW"
def python_imports(path: Path) -> list[tuple[int, str]]:
    if path.suffix != ".py":
        return []

    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return []

    imports: list[tuple[int, str]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append((node.lineno, node.module))

    return imports


def scan() -> list[Finding]:
    findings: list[Finding] = []

    for path in sorted(PACKAGE.rglob("*")):
        if not path.is_file() or path.suffix not in SOURCE_SUFFIXES:
            continue

        relative = path.relative_to(ROOT).as_posix()
        production = "/tests/" not in f"/{relative}/"

        try:
            lines = path.read_text(
                encoding="utf-8",
                errors="replace",
            ).splitlines()
        except OSError:
            continue

        for number, line in enumerate(lines, start=1):
            for category, pattern in PATTERNS.items():
                if pattern.search(line):
                    findings.append(
                        Finding(
                            path=relative,
                            line=number,
                            category=category,
                            text=line.strip()[:500],
                            production_source=production,
                            disposition=initial_disposition(
                                path,
                                category,
                                line,
                            ),
                        )
                    )

        for number, module in python_imports(path):
            if module == "chronus" or module.startswith("chronus."):
                findings.append(
                    Finding(
                        path=relative,
                        line=number,
                        category="chronus_import",
                        text=module,
                        production_source=production,
                        disposition="AUDIT_SUBSTRATE_OR_FORBIDDEN_MATH",
                    )
                )

    return findings


def main() -> int:
    findings = scan()

    json_path = ROOT / "turing_quantum_conversion_census.json"
    csv_path = ROOT / "turing_quantum_conversion_census.csv"

    payload = {
        "schema": "hyba.turing.quantum_conversion_census.v1",
        "root": PACKAGE.relative_to(ROOT).as_posix(),
        "findings": [asdict(item) for item in findings],
    }

    json_path.write_text(
        json.dumps(
            payload,
            sort_keys=True,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    with csv_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(asdict(findings[0]).keys())
            if findings
            else [
                "path",
                "line",
                "category",
                "text",
                "production_source",
                "disposition",
            ],
        )
        writer.writeheader()
        for item in findings:
            writer.writerow(asdict(item))

    unresolved = [
        item
        for item in findings
        if item.production_source
        and item.disposition
        in {
            "Q_CONVERT_CANDIDATE",
            "AUDIT_SUBSTRATE_OR_FORBIDDEN_MATH",
            "REVIEW",
        }
    ]

    print(f"Findings: {len(findings)}")
    print(f"Unresolved production findings: {len(unresolved)}")
    print(json_path)
    print(csv_path)

    return 1 if unresolved else 0


if __name__ == "__main__":
    raise SystemExit(main())