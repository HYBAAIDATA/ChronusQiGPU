#!/usr/bin/env python3
"""Build a fail-closed EUCLID intelligence release archive and SHA-256 manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE_VERSION = "17.0.0-rc1"
INCLUDE = (
    "euclid/cognition",
    "euclid/runtime.py",
    "euclid/learning_service.py",
    "euclid/memory_database.py",
    "toe",
    "Intelligence",
    "hyba_substrate",
    "docs/INTELLIGENCE_CONVERGENCE.md",
    "docs/EUCLID_V17_RESEARCH_RELEASE.md",
    "tests/test_cognition_loop.py",
    "tests/test_intelligence_convergence.py",
    "tests/test_adaptive_intelligence.py",
    "pyproject.toml",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_gate(name: str, command: list[str]) -> dict:
    completed = subprocess.run(
        command, cwd=ROOT, text=True, capture_output=True, check=False
    )
    return {
        "name": name,
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout[-12000:],
        "stderr": completed.stderr[-12000:],
        "passed": completed.returncode == 0,
    }


def files() -> list[Path]:
    selected = []
    for relative in INCLUDE:
        path = ROOT / relative
        if path.is_dir():
            selected.extend(
                item for item in path.rglob("*")
                if item.is_file() and "__pycache__" not in item.parts
            )
        elif path.is_file():
            selected.append(path)
        else:
            raise FileNotFoundError(f"required release path missing: {relative}")
    return sorted(set(selected))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    gates = [
        run_gate("focused-tests", [
            sys.executable, "-m", "pytest",
            "tests/test_cognition_loop.py",
            "tests/test_intelligence_convergence.py",
            "tests/test_adaptive_intelligence.py", "-q",
        ]),
    ]
    with tempfile.TemporaryDirectory() as directory:
        wheel_dir = Path(directory) / "wheel"
        wheel_dir.mkdir()
        wheel = run_gate("wheel-build", [
            sys.executable, "-m", "pip", "wheel", ".", "--no-deps",
            "--wheel-dir", str(wheel_dir),
        ])
        gates.append(wheel)
        built = list(wheel_dir.glob("*.whl"))
        if wheel["passed"] and built:
            install_dir = Path(directory) / "install"
            gates.append(run_gate("wheel-install", [
                sys.executable, "-m", "pip", "install", "--no-deps",
                "--target", str(install_dir), str(built[0]),
            ]))
        else:
            gates.append({
                "name": "wheel-install", "passed": False,
                "returncode": None, "stdout": "", "stderr": "wheel not built",
            })
        if not all(gate["passed"] for gate in gates):
            evidence = args.output / "euclid-v17-release-gates.failed.json"
            evidence.write_text(json.dumps(gates, indent=2), encoding="utf-8")
            print(f"RELEASE_BLOCKED={evidence}")
            return 1

        archive = args.output / f"euclid-intelligence-{RELEASE_VERSION}.zip"
        selected = files()
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
            for path in selected:
                bundle.write(path, path.relative_to(ROOT).as_posix())
            bundle.writestr(
                "RELEASE_GATES.json", json.dumps(gates, sort_keys=True, indent=2)
            )
        manifest = {
            "schema": "euclid.release-integrity/1",
            "version": RELEASE_VERSION,
            "archive": archive.name,
            "archive_sha256": sha256(archive),
            "files": {
                path.relative_to(ROOT).as_posix(): sha256(path)
                for path in selected
            },
            "gates": gates,
        }
        manifest_path = archive.with_suffix(".manifest.json")
        manifest_path.write_text(
            json.dumps(manifest, sort_keys=True, indent=2), encoding="utf-8"
        )
        print(f"ARCHIVE={archive}")
        print(f"SHA256={manifest['archive_sha256']}")
        print(f"MANIFEST={manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())