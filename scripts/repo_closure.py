#!/usr/bin/env python3
"""Repository-wide production-closure inventory for Agent H.

This tool is deliberately evidence-first:
- ownership is derived from tracked Git paths and must resolve to exactly one lane;
- defect discovery records every textual occurrence matching the programme's
  discovery categories without pretending that a lexical match is a defect;
- only path-safe classifications (tests/research/legacy) are automatic;
- production-path findings remain OPEN until the owning lane fixes or classifies them.

The generated artifacts are machine-readable evidence for CI/release gates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

ROOT = Path(__file__).resolve().parents[1]

AGENT_PREFIXES = {
    "A": (
        "Intelligence/",
        "euclid/",
        "toe/",
        "resonance_intelligence/",
        "agi/",
        "enhanced_intelligence/",
        "pythagoras/",
        "mtheory/",
        "millennium/",
        "omega/",
        "core_engine/",
    ),
    "B": ("mining/", "python_backend/", "hyba_substrate/", "phi_rotation/", "thermo/"),
    "C": (
        "chronus/",
        "chronos/",
        "gpu/",
        "opencl/",
        "kernels/",
        "compiler/",
        "abi/",
        "isa/",
        "pci/",
        "asic/",
        "distributed/",
        "emulator/",
        "conformance/",
        "chronus/packages/chronos-one-igpu/",
        "packages/chronos-one-igpu/",
    ),
    "D": (
        "turing_universal_quantum_computer/",
        "quantum_compute_substrate/",
        "kellogg/",
        "aethel/",
        "lucas/",
        "golden_quantum/",
        "tensor/",
        "proofs/",
        "cross_verification/",
        "format/",
        "standard/",
    ),

    "E": (
        "hyba_db/",
        "evidence/",
        "release-evidence/",
        "artifacts/",
        "schema/",
        "manifests/",
        "hyba_contracts/",
        "hyba_profiles/",
    ),
    "F": ("salamander/", "asi/", "asi_validation/", "al_haras/", "l_hras/", "governance/"),
    "G": (
        "frontend/",
        "services/",
        "hyba/",
        "hyba_services/",
        "hyba_compat/",
        "integrations/",
        "plugins/",
        "deploy/",
        "packaging/",
        "packages/pythia-consumer/",
        "observability/",
        "runbooks/",
        "tools/",
    ),
    "H": (
        "tests/",
        "bench/",
        "benchmarks/",
        "benchmark_portfolio/",
        "eval_harness/",
        "experiments/",
        "notebooks/",
        "reports/",
        "scripts/",
        ".github/",
        ".agents/",
        ".devin/",
        "docs/",
        "delegation/",
        "legacy/",
        "legacy_implementations/",
        "_archive_research/",
        "make/",
        "unused/",
    ),
}


ROOT_EXPLICIT = {
    "euclid_delegation.py": "A",
    "orcle.py": "A",
    "orchestrate.py": "A",
    "turing_core.py": "D",
    "STRICT_QUANTUM_BOUNDARY.md": "D",
    "Dockerfile": "G",
    "Dockerfile.hybrid": "G",
    ".env.example": "G",
    "package.json": "G",
    "DEPLOYMENT.md": "G",
}

CONFIG_RULES = (
    ("B", re.compile(r"(?:^|/)(?:mining|pythia|stratum|pool|hendrix)", re.I)),
    ("F", re.compile(r"(?:al[-_]?haras|security|salamander|governance|promotion|assurance|gate)", re.I)),
)

DISCOVERY_PATTERNS = {
    "STUB_TODO_FIXME_NOTIMPLEMENTED": re.compile(
        r"\b(?:TODO|FIXME|NotImplemented(?:Error)?|stub(?:bed|s)?|placeholder)\b", re.I
    ),
    "MOCK_FAKE_DUMMY": re.compile(r"\b(?:mock(?:ed|s)?|fake(?:d|s)?|dummy)\b", re.I),
    "SIMULATION_DEMO_SAMPLE_FIXTURE_SYNTHETIC": re.compile(
        r"\b(?:simulation|simulated|simulator|demo|sample|fixture|synthetic)\b", re.I
    ),
    "APPROXIMATION": re.compile(
        r"\b(?:approx(?:imate|imation|imately)?|epsilon|tolerance|floating[- ]point|float\d*)\b",
        re.I,
    ),
}

AUTO_CLASSIFICATIONS = {
    "test": "VALID_TEST_FIXTURE",
    "research": "VALID_RESEARCH_ONLY",
    "legacy": "LEGACY_ISOLATED_FROM_PRODUCTION",
}

RESEARCH_PREFIXES = ("bench/", "benchmarks/", "eval_harness/", "experiments/", "notebooks/")
MANUAL_CLASSIFICATIONS_PATH = "reports/DEFECT_CLASSIFICATIONS.json"
EXCLUDED_SCAN_PATHS = {
    "reports/DEFECT_REGISTER.json",
    "reports/REPO_FILE_OWNERSHIP.json",
    MANUAL_CLASSIFICATIONS_PATH,
}
TEXT_SUFFIXES = {
    ".py", ".pyi", ".md", ".txt", ".rst", ".json", ".jsonl", ".yaml", ".yml", ".toml",
    ".ini", ".cfg", ".conf", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".css", ".scss",
    ".html", ".xml", ".sql", ".sh", ".ps1", ".bat", ".c", ".h", ".cc", ".cpp", ".hpp", ".cl",
    ".cu", ".sv", ".v", ".rs", ".go", ".java", ".kt", ".gradle", ".properties", ".csv",
}
BASELINE_DISCOVERY_LEADS = {
    "STUB_TODO_FIXME_NOTIMPLEMENTED": 429,
    "MOCK_FAKE_DUMMY": 593,
    "SIMULATION_DEMO_SAMPLE_FIXTURE_SYNTHETIC": 2784,
    "APPROXIMATION": 2291,
}

ALLOWED_CLASSIFICATIONS = (
    "FIXED_PRODUCTION_IMPLEMENTATION",
    "VALID_TEST_FIXTURE",
    "VALID_RESEARCH_ONLY",
    "LEGACY_ISOLATED_FROM_PRODUCTION",
    "FALSE_POSITIVE_PROVEN",
    "BLOCKED_EXTERNAL_EVIDENCE",
)


@dataclass(frozen=True)
class Ownership:
    path: str
    owners: tuple[str, ...]
    rule: str


def _git(*args: str, root: Path = ROOT) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout


def tracked_files(root: Path = ROOT) -> list[str]:
    return [p for p in _git("ls-files", "-z", root=root).split("\0") if p]


def current_sha(root: Path = ROOT) -> str:
    return _git("rev-parse", "HEAD", root=root).strip()


def owners_for_path(path: str) -> Ownership:
    owners: list[str] = []
    reasons: list[str] = []

    if "/" not in path:
        explicit = ROOT_EXPLICIT.get(path)
        if explicit:
            owners.append(explicit)
            reasons.append("root-explicit")
        elif path.startswith("docker-compose") or path == "docker-cleanup.sh":
            owners.append("G")
            reasons.append("root-product-deployment")
        else:
            owners.append("H")
            reasons.append("root-infrastructure-fallback")
        return Ownership(path, tuple(owners), "+".join(reasons))

    if path.startswith("config/"):
        for agent, pattern in CONFIG_RULES:
            if pattern.search(path):
                owners.append(agent)
                reasons.append(f"config-{agent}")
        return Ownership(path, tuple(sorted(set(owners))), "+".join(reasons) or "config-unassigned")

    for agent, prefixes in AGENT_PREFIXES.items():
        matched = [prefix for prefix in prefixes if path.startswith(prefix)]
        if matched:
            owners.append(agent)
            reasons.extend(f"{agent}:{prefix}" for prefix in matched)

    return Ownership(path, tuple(sorted(set(owners))), "+".join(reasons) or "unassigned")


def ownership_document(paths: Sequence[str], *, sha: str) -> dict:
    records = [owners_for_path(path) for path in paths]
    unowned = [r.path for r in records if len(r.owners) == 0]
    multi = [r.path for r in records if len(r.owners) > 1]
    by_agent = Counter(r.owners[0] for r in records if len(r.owners) == 1)
    return {
        "schema_version": 1,
        "source_sha": sha,
        "tracked_file_count": len(records),
        "unowned_files": unowned,
        "multi_owned_files": multi,
        "counts_by_agent": dict(sorted(by_agent.items())),
        "files": {
            r.path: {"owner": r.owners[0] if len(r.owners) == 1 else None, "owners": list(r.owners), "rule": r.rule}
            for r in records
        },
    }


def _is_test_path(path: str) -> bool:
    name = Path(path).name
    return (
        path.startswith("tests/")
        or "/tests/" in path
        or name.startswith("test_")
        or name.endswith("_test.py")
    )


def _auto_classification(path: str) -> str | None:
    if path.startswith("legacy/"):
        return AUTO_CLASSIFICATIONS["legacy"]
    if _is_test_path(path):
        return AUTO_CLASSIFICATIONS["test"]
    if path.startswith(RESEARCH_PREFIXES):
        return AUTO_CLASSIFICATIONS["research"]
    return None


def _looks_text(path: Path) -> bool:
    if path.name in {"Dockerfile", "Makefile"}:
        return True
    return path.suffix.lower() in TEXT_SUFFIXES or path.suffix == ""


def load_manual_classifications(root: Path) -> dict[str, dict]:
    """Load evidence-backed classifications for reviewed production hits.

    Manual closure is deliberately strict.  An annotation binds to the exact
    occurrence id *and* repeats its path/line/category/match metadata so an
    unrelated source edit cannot silently inherit an old approval.
    """
    path = root / MANUAL_CLASSIFICATIONS_PATH
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"invalid defect classification register: {exc}") from exc
    if payload.get("schema_version") != 1:
        raise RuntimeError("unsupported defect classification register schema")
    entries = payload.get("classifications")
    if not isinstance(entries, list):
        raise RuntimeError("defect classification register must contain a classifications list")
    out: dict[str, dict] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise RuntimeError("defect classification entries must be objects")
        occurrence_id = str(entry.get("id") or "").strip()
        classification = str(entry.get("classification") or "").strip()
        evidence = str(entry.get("evidence") or "").strip()
        reviewer = str(entry.get("reviewer") or "").strip()
        if not occurrence_id or occurrence_id in out:
            raise RuntimeError("defect classification ids must be non-empty and unique")
        if classification not in ALLOWED_CLASSIFICATIONS:
            raise RuntimeError(f"unsupported defect classification: {classification}")
        if not evidence or not reviewer:
            raise RuntimeError(
                f"classification {occurrence_id} requires evidence and reviewer"
            )
        out[occurrence_id] = dict(entry)
    return out


def iter_occurrences(
    root: Path,
    paths: Sequence[str],
    *,
    manual_classifications: dict[str, dict] | None = None,
) -> Iterable[dict]:
    manual_classifications = manual_classifications or {}
    for rel in paths:
        if rel in EXCLUDED_SCAN_PATHS:
            continue
        path = root / rel
        if not path.is_file() or not _looks_text(path):
            continue
        try:
            raw = path.read_bytes()
        except OSError:
            continue
        if b"\0" in raw:
            continue
        text = raw.decode("utf-8", errors="replace")
        owner = owners_for_path(rel)
        owner_name = owner.owners[0] if len(owner.owners) == 1 else None
        classification = _auto_classification(rel)
        for lineno, line in enumerate(text.splitlines(), 1):
            for category, pattern in DISCOVERY_PATTERNS.items():
                for match in pattern.finditer(line):
                    token = match.group(0)
                    occurrence_key = f"{rel}:{lineno}:{category}:{match.start()}:{token.casefold()}"
                    occurrence_id = hashlib.sha256(occurrence_key.encode()).hexdigest()[:20]
                    evidence = None
                    reviewer = None
                    classification_source = "automatic" if classification else None
                    manual = manual_classifications.get(occurrence_id)
                    if manual is not None:
                        expected = {
                            "path": rel,
                            "line": lineno,
                            "category": category,
                            "match": token,
                        }
                        for key, value in expected.items():
                            if manual.get(key) != value:
                                raise RuntimeError(
                                    f"stale defect classification {occurrence_id}: "
                                    f"{key}={manual.get(key)!r}, expected {value!r}"
                                )
                        classification = str(manual["classification"])
                        evidence = str(manual["evidence"])
                        reviewer = str(manual["reviewer"])
                        classification_source = "reviewed"
                    yield {
                        "id": occurrence_id,
                        "category": category,
                        "path": rel,
                        "line": lineno,
                        "match": token,
                        "owner": owner_name,
                        "classification": classification,
                        "classification_source": classification_source,
                        "evidence": evidence,
                        "reviewer": reviewer,
                        "status": "CLASSIFIED" if classification else "OPEN",
                    }


def defect_document(root: Path, paths: Sequence[str], *, sha: str) -> dict:
    manual_classifications = load_manual_classifications(root)
    occurrences = list(
        iter_occurrences(root, paths, manual_classifications=manual_classifications)
    )
    by_category = Counter(o["category"] for o in occurrences)
    by_status = Counter(o["status"] for o in occurrences)
    by_classification = Counter(
        o["classification"] for o in occurrences if o["classification"] is not None
    )
    open_by_owner = Counter((o["owner"] or "UNOWNED") for o in occurrences if o["status"] == "OPEN")
    return {
        "schema_version": 1,
        "source_sha": sha,
        "discovery_leads_from_programme": BASELINE_DISCOVERY_LEADS,
        "note": (
            "Discovery leads are not deletion instructions. Lexical hits on test/research/legacy paths "
            "receive only safe path-based classifications; every production-path hit remains OPEN "
            "until its owning implementation lane supplies evidence for an allowed classification."
        ),
        "manual_classification_register": MANUAL_CLASSIFICATIONS_PATH,
        "allowed_classifications": list(ALLOWED_CLASSIFICATIONS),
        "counts": {
            "total_occurrences": len(occurrences),
            "by_category": dict(sorted(by_category.items())),
            "by_status": dict(sorted(by_status.items())),
            "by_classification": dict(sorted(by_classification.items())),
            "open_by_owner": dict(sorted(open_by_owner.items())),
        },
        "occurrences": occurrences,
    }


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def cmd_ownership(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    paths = tracked_files(root)
    doc = ownership_document(paths, sha=current_sha(root))
    if args.output:
        write_json(root / args.output, doc)
    summary = {
        "tracked_file_count": doc["tracked_file_count"],
        "counts_by_agent": doc["counts_by_agent"],
        "unowned_files": len(doc["unowned_files"]),
        "multi_owned_files": len(doc["multi_owned_files"]),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 1 if doc["unowned_files"] or doc["multi_owned_files"] else 0


def cmd_defects(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    paths = tracked_files(root)
    doc = defect_document(root, paths, sha=current_sha(root))
    if args.output:
        write_json(root / args.output, doc)
    print(json.dumps(doc["counts"], indent=2, sort_keys=True))
    open_count = doc["counts"]["by_status"].get("OPEN", 0)
    blocked_count = doc["counts"]["by_classification"].get(
        "BLOCKED_EXTERNAL_EVIDENCE", 0
    )
    return 1 if args.require_closed and (open_count or blocked_count) else 0


def cmd_release(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    paths = tracked_files(root)
    sha = current_sha(root)
    ownership = ownership_document(paths, sha=sha)
    defects = defect_document(root, paths, sha=sha)
    if args.ownership_output:
        write_json(root / args.ownership_output, ownership)
    if args.defect_output:
        write_json(root / args.defect_output, defects)
    failures = []
    if ownership["unowned_files"]:
        failures.append(f"UNOWNED_FILES={len(ownership['unowned_files'])}")
    if ownership["multi_owned_files"]:
        failures.append(f"MULTI_OWNED_FILES={len(ownership['multi_owned_files'])}")
    open_count = defects["counts"]["by_status"].get("OPEN", 0)
    if open_count:
        failures.append(f"OPEN_DEFECT_OCCURRENCES={open_count}")
    blocked_count = defects["counts"]["by_classification"].get(
        "BLOCKED_EXTERNAL_EVIDENCE", 0
    )
    if blocked_count:
        failures.append(f"BLOCKED_EXTERNAL_EVIDENCE={blocked_count}")
    print(json.dumps({"source_sha": sha, "failures": failures}, indent=2))
    return 1 if failures else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT))
    sub = parser.add_subparsers(dest="command", required=True)

    ownership = sub.add_parser("ownership")
    ownership.add_argument("--output", default="reports/REPO_FILE_OWNERSHIP.json")
    ownership.set_defaults(func=cmd_ownership)

    defects = sub.add_parser("defects")
    defects.add_argument("--output", default="reports/DEFECT_REGISTER.json")
    defects.add_argument("--require-closed", action="store_true")
    defects.set_defaults(func=cmd_defects)

    release = sub.add_parser("release")
    release.add_argument("--ownership-output", default="reports/REPO_FILE_OWNERSHIP.json")
    release.add_argument("--defect-output", default="reports/DEFECT_REGISTER.json")
    release.set_defaults(func=cmd_release)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
