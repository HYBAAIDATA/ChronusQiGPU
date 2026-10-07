"""Verify release-candidate wheels on every supported Python, outside the repository.

For each interpreter given, this creates a clean virtual environment, installs
only the built wheels (plus their public dependencies from PyPI), and runs,
from a directory outside the repository:

* kellogg-tensor: import of every module, capability-manifest version, the
  specification registry, and every correctness and meta benchmark;
* turing-universal-quantum-computer (installed beside the local Kellogg
  wheel): the product registry, the product-boundary checks and every
  correctness and meta benchmark.

Usage:
    python packaging/verify_release_candidates.py \\
        --kellogg packaging/kellogg-tensor/dist/kellogg_tensor-1.0.0-py3-none-any.whl \\
        --turing packaging/turing/dist/turing_universal_quantum_computer-1.0.0-py3-none-any.whl \\
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
print(json.dumps({"product": "kellogg-tensor", "python": platform.python_version(),
                  "implementation": platform.python_implementation(), "version": kellogg.__version__,
                  "manifest_version": manifest["version"], "modules": len(mods), "failed_imports": failed,
                  "siblings_loaded": [s for s in ("aethel", "chronus", "turing_core", "lucas", "toe", "mining")
                                      if s in sys.modules],
                  "registry_ok": reg["ok"], "registry_items": reg["items"], "benchmarks": bench}))
"""

TURING_CHECK = r"""
import json, platform, sys
import kellogg, turing_universal_quantum_computer as T
assert "site-packages" in T.__file__, T.__file__
from turing_universal_quantum_computer.product_registry import verify_registry
from turing_universal_quantum_computer.benchmark import BENCHMARKS, run
reg = verify_registry()
bench = {b: run(b, quick=True)["passed"] for b, (axis, _) in BENCHMARKS.items() if axis in ("correctness", "meta")}
print(json.dumps({"product": "turing-universal-quantum-computer", "python": platform.python_version(),
                  "implementation": platform.python_implementation(), "version": T.__version__,
                  "kellogg_version": kellogg.__version__, "registry_ok": reg["ok"],
                  "registry_problems": reg["problems"], "skipped_for_extras": reg["skipped_for_extras"],
                  "siblings_loaded": [s for s in ("aethel", "chronus", "toe", "mining", "Intelligence")
                                      if s in sys.modules],
                  "benchmarks": bench}))
"""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_check(python: str, wheels: list[Path], check: str, workdir: Path) -> dict:
    venv = workdir / "venv"
    subprocess.run([python, "-m", "venv", str(venv)], check=True)
    py = venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    subprocess.run([str(py), "-m", "pip", "install", "-q", "--disable-pip-version-check",
                    *[str(w) for w in wheels]], check=True)
    out = subprocess.run([str(py), "-c", check], cwd=str(workdir), capture_output=True, text=True)
    if out.returncode != 0:
        return {"error": out.stderr[-2000:]}
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
    summary = {"kellogg_wheel": {"file": kellogg_wheel.name, "sha256": sha256(kellogg_wheel)}, "runs": []}
    if turing_wheel:
        summary["turing_wheel"] = {"file": turing_wheel.name, "sha256": sha256(turing_wheel)}
    ok = True
    for python in args.python:
        jobs = [("kellogg", [kellogg_wheel], KELLOGG_CHECK)]
        if turing_wheel:
            jobs.append(("turing", [kellogg_wheel, turing_wheel], TURING_CHECK))
        for label, wheels, check in jobs:
            with tempfile.TemporaryDirectory(prefix=f"rc-{label}-") as tmp:
                record = run_check(python, wheels, check, Path(tmp))
            record["interpreter"] = python
            name = f"{label}-{record.get('python', 'unknown')}.json"
            (out_dir / name).write_text(json.dumps(record, indent=1, sort_keys=True), encoding="utf-8")
            passed = (
                "error" not in record
                and record.get("registry_ok")
                and not record.get("siblings_loaded")
                and not record.get("failed_imports")
                and all(v is not False for v in record.get("benchmarks", {}).values())
            )
            ok = ok and bool(passed)
            summary["runs"].append({"product": label, "python": record.get("python"), "passed": bool(passed),
                                    "error": record.get("error", "")[:300]})
            print(f"{label:8s} python {record.get('python', '?'):8s} {'PASS' if passed else 'FAIL'}", flush=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True), encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
