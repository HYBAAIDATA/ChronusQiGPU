#!/usr/bin/env python3
"""Build the fail-closed EUCLID 17.0.0 drop-in release archive and SHA-256 manifest.

Gates (every one must pass, otherwise nothing is archived):

1. focused tests — legacy cognition suites plus every v17 suite;
2. research evidence — the pre-registered report exists, is leakage-free and
   was produced on the pre-registered suite base;
3. wheel — ``packaging/euclid-engine/build_and_verify.py`` builds the wheel,
   installs it into a clean venv outside the repository and runs v17 episodes.

The archive mirrors repository paths, so extracting it at the repository root
is a drop-in install.  The manifest records the SHA-256 of every file, of the
wheel and of the archive itself.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE_VERSION = "17.0.0"
INCLUDE = (
    "euclid",
    "hyba_substrate",
    "resonance_intelligence",
    "docs/EUCLID_V17_RESEARCH_RELEASE.md",
    "docs/INTELLIGENCE_CONVERGENCE.md",
    "reports/euclid_v17/research_report.md",
    "reports/euclid_v17/research_report.json",
    "reports/euclid_v17/run.log",
    "scripts/run_euclid_v17_research.py",
    "scripts/render_euclid_v17_release_results.py",
    "scripts/run_euclid_v17_benchmark.py",
    "scripts/build_euclid_intelligence_release.py",
    "packaging/euclid-engine/pyproject.toml",
    "packaging/euclid-engine/README.md",
    "packaging/euclid-engine/build_and_verify.py",
    "tests/test_cognition_loop.py",
    "tests/test_adaptive_intelligence.py",
    "tests/test_intelligence_convergence.py",
    "tests/test_euclid_v17_worlds.py",
    "tests/test_euclid_v17_world_model.py",
    "tests/test_euclid_v17_phi_and_skills.py",
    "tests/test_euclid_v17_integrated_loop.py",
    "tests/test_euclid_v17_runtime.py",
    "UNIVERSAL_PRINCIPLE_MAP.md",
    "pyproject.toml",
)
EXCLUDE_PARTS = {"__pycache__", "var"}
FOCUSED_TESTS = (
    "tests/test_cognition_loop.py",
    "euclid/tests/test_cognition_core.py",
    "tests/test_adaptive_intelligence.py",
    "tests/test_intelligence_convergence.py",
    "tests/test_euclid_v17_worlds.py",
    "tests/test_euclid_v17_world_model.py",
    "tests/test_euclid_v17_phi_and_skills.py",
    "tests/test_euclid_v17_integrated_loop.py",
    "tests/test_euclid_v17_runtime.py",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_gate(name: str, command: list[str]) -> dict:
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    return {
        "name": name,
        "command": command,
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-6000:],
        "stderr_tail": completed.stderr[-6000:],
        "passed": completed.returncode == 0,
    }


def research_gate() -> dict:
    path = ROOT / "reports" / "euclid_v17" / "research_report.json"
    if not path.is_file():
        return {"name": "research-evidence", "passed": False, "reason": "report missing"}
    report = json.loads(path.read_text(encoding="utf-8"))
    protocol = report.get("protocol", {})
    checks = {
        "leakage_free": bool(report.get("leakage_free")),
        "pre_registered_suite_base": protocol.get("suite_base") == 2000,
        "five_seeds": len(protocol.get("seeds", ())) >= 5,
        "all_required_systems": {
            "v16.4-reference", "integrated", "minus-world-model", "minus-causal",
            "minus-analogy", "minus-meta-learning", "minus-learned-primitives",
            "minus-representation", "minus-phi-lucas-manifold", "minus-replanning",
        } <= set(protocol.get("systems", ())),
    }
    return {
        "name": "research-evidence",
        "checks": checks,
        "release_gate": report.get("release_gate", {}).get("passed"),
        "passed": all(checks.values()),
    }


def files() -> list[Path]:
    selected: list[Path] = []
    for relative in INCLUDE:
        path = ROOT / relative
        if path.is_dir():
            selected.extend(
                item for item in path.rglob("*")
                if item.is_file() and not (EXCLUDE_PARTS & set(item.relative_to(ROOT).parts))
                and item.suffix not in (".pyc", ".pyo")
            )
        elif path.is_file():
            selected.append(path)
        else:
            raise FileNotFoundError(f"required release path missing: {relative}")
    return sorted(set(selected))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist" / "euclid-17.0.0")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    gates = [
        run_gate("focused-tests", [sys.executable, "-m", "pytest", *FOCUSED_TESTS, "-q",
                                   "-p", "no:cacheprovider"]),
        research_gate(),
        run_gate("wheel-build-install-smoke",
                 [sys.executable, "packaging/euclid-engine/build_and_verify.py"]),
    ]
    if not all(gate["passed"] for gate in gates):
        evidence = args.output / "euclid-17.0.0-release-gates.failed.json"
        evidence.write_text(json.dumps(gates, indent=2), encoding="utf-8")
        print(f"RELEASE_BLOCKED={evidence}")
        return 1
    wheel_dir = ROOT / "packaging" / "euclid-engine" / "dist"
    wheel = next(wheel_dir.glob("euclid_engine-*.whl"))
    verification = json.loads((wheel_dir / "euclid-engine-verification.json").read_text(
        encoding="utf-8"))
    archive = args.output / f"euclid-intelligence-{RELEASE_VERSION}.zip"
    selected = files()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in selected:
            bundle.write(path, path.relative_to(ROOT).as_posix())
        bundle.write(wheel, f"wheels/{wheel.name}")
        bundle.writestr("RELEASE_GATES.json", json.dumps(gates, sort_keys=True, indent=2))
        bundle.writestr("WHEEL_VERIFICATION.json",
                        json.dumps(verification, sort_keys=True, indent=2))
    manifest = {
        "schema": "euclid.release-integrity/2",
        "version": RELEASE_VERSION,
        "archive": archive.name,
        "archive_sha256": sha256(archive),
        "wheel": wheel.name,
        "wheel_sha256": sha256(wheel),
        "files": {path.relative_to(ROOT).as_posix(): sha256(path) for path in selected},
        "gates": [{k: v for k, v in gate.items() if k not in ("stdout_tail", "stderr_tail")}
                  for gate in gates],
    }
    manifest_path = archive.with_suffix(".manifest.json")
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2), encoding="utf-8")
    with zipfile.ZipFile(archive) as bundle:
        bad = bundle.testzip()
        if bad is not None:
            print(f"RELEASE_BLOCKED=corrupt member {bad}")
            return 1
        for path in selected:
            member = path.relative_to(ROOT).as_posix()
            if hashlib.sha256(bundle.read(member)).hexdigest() != manifest["files"][member]:
                print(f"RELEASE_BLOCKED=hash mismatch {member}")
                return 1
    print(f"ARCHIVE={archive}")
    print(f"SHA256={manifest['archive_sha256']}")
    print(f"WHEEL_SHA256={manifest['wheel_sha256']}")
    print(f"MANIFEST={manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
