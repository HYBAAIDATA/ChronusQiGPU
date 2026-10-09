"""Verify release-candidate wheels on every supported Python, outside the repository.

For each interpreter given, this creates a clean virtual environment, installs
only the built wheels (plus their public dependencies from PyPI), and runs,
from a directory outside the repository:

* hyba-kellogg-tensor: import of every module, capability-manifest version, the
  specification registry, and every correctness and meta benchmark;
* hyba-turing-vqc (installed beside the local Kellogg
  wheel): the product registry, the product-boundary checks and every
  correctness and meta benchmark.

Usage:
    python packaging/verify_release_candidates.py \\
        --kellogg packaging/kellogg-tensor/dist/hyba_kellogg_tensor-1.0.0-py3-none-any.whl \\
        --turing packaging/turing/dist/hyba_turing_vqc-1.0.0-py3-none-any.whl \\
        --python C:/path/python3.11.exe --python C:/path/python3.12.exe ...

Writes one JSON evidence record per interpreter and product to --out.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

KELLOGG_CHECK = r"""
import importlib, json, pkgutil, platform, sys
import kellogg
assert "site-packages" in kellogg.__file__, kellogg.__file__
mods = sorted(m.name for m in pkgutil.iter_modules(kellogg.__path__))
failed = {}
for m in mods:
    try:
        importlib.import_module("kellogg." + m)
    except Exception as e:
        failed[m] = repr(e)
from importlib.resources import files
manifest = json.loads(files("kellogg").joinpath("CAPABILITY_MANIFEST.json").read_text())
from kellogg.spec import verify_registry
from kellogg.benchmark import BENCHMARKS, run
reg = verify_registry()
bench = {b: run(b, quick=True)["passed"] for b, (axis, _) in BENCHMARKS.items() if axis in ("correctness", "meta")}
print(json.dumps({"product": "hyba-kellogg-tensor", "python": platform.python_version(),
                  "implementation": platform.python_implementation(), "version": kellogg.__version__,
                  "manifest_version": manifest["version"], "modules": len(mods), "failed_imports": failed,
                  "siblings_loaded": [s for s in ("aethel", "chronus", "turing_core", "lucas", "toe", "mining")
                                      if s in sys.modules],
                  "registry_ok": reg["ok"], "registry_items": reg["items"], "benchmarks": bench}))
"""

TURING_CHECK = r"""
import importlib
import importlib.metadata
import json
import platform
import sys

import kellogg
import turing_universal_quantum_computer as T

assert "site-packages" in str(T.__file__).replace("\\", "/"), T.__file__
assert "site-packages" in str(kellogg.__file__).replace("\\", "/"), kellogg.__file__
assert T.__version__ == "1.0.0"
assert kellogg.__version__ == "1.0.0"

metadata = importlib.metadata.metadata("hyba-turing-vqc")
assert metadata["Name"] == "hyba-turing-vqc"
assert metadata["Version"] == "1.0.0"
assert metadata["Requires-Python"] == ">=3.11"
assert metadata["Author"] == "HYBA Software Limited"
license_value = metadata.get("License-Expression") or metadata.get("License")
assert license_value == "MIT", license_value
requires = importlib.metadata.requires("hyba-turing-vqc") or []
hard_requires = [r for r in requires if "extra ==" not in r]
assert any(r.lower().startswith("hyba-kellogg-tensor") for r in hard_requires), hard_requires
project_urls = metadata.get_all("Project-URL") or []
assert any("https://github.com/QuantumPhiRedux/PhiMiner" in u for u in project_urls), project_urls
assert not any("QuantumPhi2/PhiMiner" in u for u in project_urls), project_urls

dist = importlib.metadata.distribution("hyba-turing-vqc")
entry = [e for e in dist.entry_points if e.group == "console_scripts" and e.name == "turing-vqc"]
assert len(entry) == 1
assert entry[0].value == "turing_universal_quantum_computer.console:main"

from turing_universal_quantum_computer.product_registry import verify_registry
reg = verify_registry(import_check=True)
assert reg["ok"], reg["problems"]
assert not reg["skipped_for_extras"], reg["skipped_for_extras"]

for alias in ("exact_tensor", "quantum_tensor", "exact_field"):
    public = importlib.import_module("turing_universal_quantum_computer." + alias)
    owner = importlib.import_module("kellogg." + alias)
    assert public is owner, (alias, public.__file__, owner.__file__)

from turing_universal_quantum_computer.backends import Program, QPUBackend, execute_certified
small = Program(2).then("h", 0).then("cx", 0, 1).then("t", 0)
small_run = execute_certified(small, shots=8, readout=[0, 1])
assert small_run.certificate.trace[0]["options"]["seed"] == 0

wide = Program(1000).then("h", 0)
for q in range(999):
    wide = wide.then("cx", q, q + 1)
wide = wide.then("t", 0).then("s", 999)
wide_run = execute_certified(wide, prefer="mps_exact", marginal_of=[0, 999])
assert wide_run.result.backend == "mps_exact"
assert wide_run.result.payload["marginal"]["probabilities"] == {"00": "1/2", "11": "1/2"}
assert wide_run.result.payload["max_bond"] == 2

qpu = QPUBackend().admit(Program(2).then("h", 0))
assert not qpu.admitted

from turing_universal_quantum_computer.benchmark import BENCHMARKS, _digest_corpus, run
from kellogg.benchmark import digest
bench = {
    b: run(b, quick=True)["passed"]
    for b, (axis, _) in BENCHMARKS.items()
    if axis in ("correctness", "meta")
}
assert all(value is not False for value in bench.values()), bench
cross_version_fixture = digest(_digest_corpus())

siblings = [
    s for s in ("aethel", "chronus", "toe", "mining", "Intelligence")
    if s in sys.modules
]
assert not siblings, siblings

print(json.dumps({
    "product": "hyba-turing-vqc",
    "python": platform.python_version(),
    "implementation": platform.python_implementation(),
    "version": T.__version__,
    "kellogg_version": kellogg.__version__,
    "registry_ok": reg["ok"],
    "registry_problems": reg["problems"],
    "skipped_for_extras": reg["skipped_for_extras"],
    "metadata_valid": True,
    "console_entry_point": entry[0].value,
    "kellogg_aliases_verified": True,
    "qpu_absence_fails_closed": True,
    "small_certificate_digest": small_run.certificate.certificate_digest,
    "small_effective_seed": small_run.certificate.trace[0]["options"]["seed"],
    "wide_backend": wide_run.result.backend,
    "wide_certificate_digest": wide_run.certificate.certificate_digest,
    "wide_state_root": wide_run.result.payload["state_root"],
    "cross_version_fixture": cross_version_fixture,
    "siblings_loaded": siblings,
    "benchmarks": bench,
}))
"""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_check(
    python: str,
    wheels: list[Path],
    check: str,
    workdir: Path,
    extra_packages: list[str] | None = None,
) -> dict:
    venv = workdir / "venv"
    subprocess.run([python, "-m", "venv", str(venv)], check=True)
    py = venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    subprocess.run(
        [
            str(py),
            "-m",
            "pip",
            "install",
            "-q",
            "--disable-pip-version-check",
            *[str(w) for w in wheels],
        ],
        check=True,
    )
    if extra_packages:
        subprocess.run(
            [
                str(py),
                "-m",
                "pip",
                "install",
                "-q",
                "--disable-pip-version-check",
                *extra_packages,
            ],
            check=True,
        )
    out = subprocess.run(
        [str(py), "-I", "-c", check],
        cwd=str(workdir),
        capture_output=True,
        text=True,
    )
    if out.returncode != 0:
        return {"error": (out.stdout + "\n" + out.stderr)[-4000:]}
    return json.loads(out.stdout.strip().splitlines()[-1])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kellogg", required=True)
    parser.add_argument("--turing")
    parser.add_argument("--python", action="append", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    kellogg_wheel = Path(args.kellogg).resolve()
    turing_wheel = Path(args.turing).resolve() if args.turing else None
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "kellogg_wheel": {
            "file": kellogg_wheel.name,
            "sha256": sha256(kellogg_wheel),
        },
        "runs": [],
    }
    if turing_wheel:
        summary["turing_wheel"] = {
            "file": turing_wheel.name,
            "sha256": sha256(turing_wheel),
        }
    ok = True
    for python in args.python:
        jobs = [("kellogg", [kellogg_wheel], KELLOGG_CHECK, [])]
        if turing_wheel:
            jobs.append(
                (
                    "turing",
                    [kellogg_wheel, turing_wheel],
                    TURING_CHECK,
                    ["scipy>=1.11", "networkx>=3.0"],
                )
            )
        for label, wheels, check, extra_packages in jobs:
            with tempfile.TemporaryDirectory(prefix=f"rc-{label}-") as tmp:
                record = run_check(
                    python,
                    wheels,
                    check,
                    Path(tmp),
                    extra_packages=extra_packages,
                )
            record["interpreter"] = python
            name = f"{label}-{record.get('python', 'unknown')}.json"
            (out_dir / name).write_text(
                json.dumps(record, indent=1, sort_keys=True), encoding="utf-8"
            )
            passed = (
                "error" not in record
                and record.get("registry_ok")
                and not record.get("siblings_loaded")
                and not record.get("failed_imports")
                and not record.get("skipped_for_extras")
                and all(
                    value is not False
                    for value in record.get("benchmarks", {}).values()
                )
            )
            ok = ok and bool(passed)
            summary["runs"].append(
                {
                    "product": label,
                    "python": record.get("python"),
                    "passed": bool(passed),
                    "error": record.get("error", "")[:300],
                }
            )
            print(
                f"{label:8s} python {record.get('python', '?'):8s} "
                f"{'PASS' if passed else 'FAIL'}",
                flush=True,
            )
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=1, sort_keys=True), encoding="utf-8"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
