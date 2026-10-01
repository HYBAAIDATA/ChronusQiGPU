"""
Host-Repository Integration Runner (FIX-04 · ENH-05 on the host's own code)
===========================================================================
Runs PYTHAGORAS inside a host repository with the host's own test suite as the
behaviour gate, and produces a patch the repository owner reviews and pushes.

    1. Baseline   the host test command runs on an untouched private copy and must pass
                  (a failing baseline cannot serve as a behaviour gate; the run stops).
    2. Evolution  for each target file, Condition A (meta OFF) and Condition B (meta ON).
                  Every changed candidate is written into the private copy and the host
                  tests run against it with a timeout (FIX-04); the file is then restored.
    3. Integrate  B's evolved files are written into the copy together and the full host
                  suite runs once more on the integrated tree.
    4. Output     report.json, report.md and pythagoras.patch (applies with `git apply`).
                  The original repository is untouched unless --apply is given.

Usage:
    python3 -m pythagoras.integration.repo_runner /path/to/repo
        [--files pkg/a.py pkg/b.py] [--max-files 5] [--generations 10] [--seed 0]
        [--test-cmd "python -m pytest -x -q tests/"] [--timeout 300]
        [--allow-behaviour-changing] [--apply] [--out pythagoras_integration]
"""
import argparse
import difflib
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import tokenize
from typing import Any, Dict, List, Optional

from pythagoras.engine.primitive_repository import CrossFilePrimitiveRepository
from pythagoras.engine.evolution import PythagorasEvolutionEngine

_IGNORED_DIRS = {".git", ".hg", ".venv", "venv", "env", "node_modules", "__pycache__", ".tox", ".nox",
                 ".pytest_cache", ".mypy_cache", ".ruff_cache", "build", "dist", "site-packages", ".eggs"}


def _read_source(path: str):
    """PEP 263-aware source read; returns text and the declared/detected encoding."""
    with open(path, "rb") as raw:
        encoding, _ = tokenize.detect_encoding(raw.readline)
    with open(path, encoding=encoding) as fh:
        return fh.read(), encoding


def _write_source(path: str, text: str, encoding: str = "utf-8") -> None:
    with open(path, "w", encoding=encoding, newline="") as fh:
        fh.write(text)


def default_test_command() -> List[str]:
    try:
        import pytest  # noqa: F401
        return [sys.executable, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider"]
    except ImportError:
        return [sys.executable, "-m", "unittest", "discover"]


def _copy_repo(src: str, dst: str) -> None:
    shutil.copytree(src, dst, ignore=lambda d, names: [n for n in names if n in _IGNORED_DIRS or n.endswith(".pyc")])


def run_tests(workspace: str, test_cmd: List[str], timeout: float) -> Dict[str, Any]:
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
               PYTHONPATH=workspace + os.pathsep + os.environ.get("PYTHONPATH", ""))
    t = time.time()
    try:
        p = subprocess.run(test_cmd, cwd=workspace, capture_output=True, text=True, timeout=timeout, env=env)
        ok = p.returncode == 0
        tail = (p.stdout + p.stderr).strip().splitlines()[-6:]
    except subprocess.TimeoutExpired:
        ok, tail = False, [f"timeout after {timeout}s"]
    return {"passed": ok, "seconds": round(time.time() - t, 2), "output_tail": tail}


class HostTestRunner:
    """external_test_runner for the engine: candidate → host tests on the private copy."""

    def __init__(self, workspace: str, rel_path: str, test_cmd: List[str], timeout: float):
        self.workspace, self.rel_path = workspace, rel_path
        self.path = os.path.join(workspace, rel_path)
        self.original, self.encoding = _read_source(self.path)
        self.test_cmd, self.timeout = test_cmd, timeout
        self.cache: Dict[str, bool] = {}
        self.test_runs = 0
        self.failures: List[Dict[str, Any]] = []

    def __call__(self, code_str: str) -> bool:
        key = hashlib.sha256(code_str.encode("utf-8")).hexdigest()
        if key in self.cache:
            return self.cache[key]
        try:
            _write_source(self.path, code_str, self.encoding)
            res = run_tests(self.workspace, self.test_cmd, self.timeout)
        finally:
            _write_source(self.path, self.original, self.encoding)
        self.test_runs += 1
        if not res["passed"]:
            self.failures.append({"output_tail": res["output_tail"]})
        self.cache[key] = res["passed"]
        return res["passed"]


def discover_targets(root: str, max_files: int) -> List[str]:
    found = []
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x not in _IGNORED_DIRS and x != "pythagoras" and not x.startswith(".")]
        rel_dir = os.path.relpath(d, root)
        if any(part in ("tests", "test", "testing") for part in rel_dir.split(os.sep)):
            continue
        for f in files:
            if not f.endswith(".py") or f.startswith("test_") or f.endswith("_test.py") \
                    or f in ("conftest.py", "setup.py", "__init__.py"):
                continue
            p = os.path.join(d, f)
            found.append((os.path.getsize(p), os.path.relpath(p, root)))
    return [rel for _, rel in sorted(found, reverse=True)[:max_files]]


def run_on_repo(root: str, files: Optional[List[str]] = None, max_files: int = 5, generations: int = 10,
                seed: int = 0, test_cmd: Optional[List[str]] = None, timeout: float = 300.0,
                allow_behaviour_changing: bool = False, apply: bool = False,
                out_dir: Optional[str] = None) -> Dict[str, Any]:
    root = os.path.abspath(root)
    test_cmd = test_cmd or default_test_command()
    targets = files or discover_targets(root, max_files)
    report: Dict[str, Any] = {"repository": root, "test_command": test_cmd, "generations": generations,
                              "seed": seed, "targets": targets, "files": {}}

    with tempfile.TemporaryDirectory(prefix="pythagoras_ws_") as ws:
        workspace = os.path.join(ws, "repo")
        _copy_repo(root, workspace)
        report["baseline"] = run_tests(workspace, test_cmd, timeout)
        if not report["baseline"]["passed"]:
            report["status"] = "stopped: baseline tests fail, so they cannot gate behaviour"
            return _write(report, {}, root, out_dir)

        engines = {
            cond: PythagorasEvolutionEngine(
                repository=CrossFilePrimitiveRepository(), seed=seed,
                meta_evolution=(cond == "B"),
                allow_behaviour_changing=allow_behaviour_changing)
            for cond in ("A", "B")
        }
        evolved: Dict[str, str] = {}
        source_encodings: Dict[str, str] = {}
        for rel in targets:
            runner = HostTestRunner(workspace, rel, test_cmd, timeout)
            source_encodings[rel] = runner.encoding
            entry = {}
            for cond, eng in engines.items():
                r = eng.run_optimization(rel, runner.original, generations, external_test_runner=runner)
                entry[cond] = {"initial_phi": r["initial_phi"], "final_phi": r["final_phi"],
                               "delta_phi": r["total_delta_phi"], "accepted_steps": len(r["accepted_steps"]),
                               "generation_reached_final": max([s["generation"] for s in r["accepted_steps"]] or [0]),
                               "operators": [s["winning_operator"] for s in r["accepted_steps"]],
                               "phase_transitions": len(r["phase_transitions"]),
                               "barrier_crossings": sum(1 for s in r["accepted_steps"] if s["is_barrier_crossing"]),
                               "candidates_rejected_by_tests": len(r["validity_failures"])}
                if cond == "B":
                    evolved[rel] = r["final_code"]
            entry["host_test_runs"] = runner.test_runs
            report["files"][rel] = entry

        for rel, code in evolved.items():
            _write_source(os.path.join(workspace, rel), code, source_encodings.get(rel, "utf-8"))
        report["integrated_tests"] = run_tests(workspace, test_cmd, timeout)

    files_rep = report["files"].values()
    a = sum(f["A"]["delta_phi"] for f in files_rep)
    b = sum(f["B"]["delta_phi"] for f in files_rep)
    report["summary"] = {
        "total_delta_phi_A_meta_off": round(a, 6),
        "total_delta_phi_B_meta_on": round(b, 6),
        "B_vs_A_percent": round(100.0 * (b - a) / a, 1) if a > 0 else None,
        "files_changed": sum(1 for rel, code in evolved.items() if code != _read(os.path.join(root, rel))),
        "integrated_tests_passed": report["integrated_tests"]["passed"],
    }
    report["status"] = "ok" if report["integrated_tests"]["passed"] else "integrated tree fails host tests; patch not applied"
    if apply and report["integrated_tests"]["passed"]:
        for rel, code in evolved.items():
            _, enc = _read_source(os.path.join(root, rel))
            _write_source(os.path.join(root, rel), code, enc)
        report["applied"] = True
    return _write(report, evolved, root, out_dir)


def _read(path: str) -> str:
    return _read_source(path)[0]


def _patch(root: str, evolved: Dict[str, str]) -> str:
    chunks = []
    for rel, new in sorted(evolved.items()):
        old = _read(os.path.join(root, rel))
        if old == new:
            continue
        chunks.extend(difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True),
                                           fromfile=f"a/{rel}", tofile=f"b/{rel}"))
    return "".join(chunks)


def _write(report: Dict[str, Any], evolved: Dict[str, str], root: str, out_dir: Optional[str]) -> Dict[str, Any]:
    if report.get("applied"):
        report["patch"] = "already applied to the working tree"
        patch = ""
    else:
        patch = _patch(root, evolved)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "report.json"), "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
        with open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8") as fh:
            fh.write(_markdown(report))
        if patch:
            with open(os.path.join(out_dir, "pythagoras.patch"), "w", encoding="utf-8") as fh:
                fh.write(patch)
    report["patch_text"] = patch
    return report


def _markdown(r: Dict[str, Any]) -> str:
    lines = ["# PYTHAGORAS integration run", "", f"Repository: `{r['repository']}`",
             f"Test command: `{' '.join(r['test_command'])}`", "",
             f"Baseline tests: **{'pass' if r['baseline']['passed'] else 'FAIL'}** ({r['baseline']['seconds']} s)"]
    if "integrated_tests" in r:
        lines.append(f"Integrated tree tests: **{'pass' if r['integrated_tests']['passed'] else 'FAIL'}**")
    lines += ["", f"Status: {r['status']}", ""]
    if r["files"]:
        lines += ["| File | φ start | A (meta off) | B (meta on) | B reached at gen | host test runs |",
                  "|---|---|---|---|---|---|"]
        for rel, f in r["files"].items():
            lines.append(f"| `{rel}` | {f['A']['initial_phi']} | {f['A']['final_phi']} | {f['B']['final_phi']} | "
                         f"{f['B']['generation_reached_final']} (A: {f['A']['generation_reached_final']}) | {f['host_test_runs']} |")
        s = r.get("summary", {})
        lines += ["", f"Total Δφ — A: {s.get('total_delta_phi_A_meta_off')}, B: {s.get('total_delta_phi_B_meta_on')}"]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("repo")
    ap.add_argument("--files", nargs="*")
    ap.add_argument("--max-files", type=int, default=5)
    ap.add_argument("--generations", type=int, default=10)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--test-cmd", default=None)
    ap.add_argument("--timeout", type=float, default=300.0)
    ap.add_argument("--allow-behaviour-changing", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--out", default="pythagoras_integration")
    a = ap.parse_args()
    rep = run_on_repo(a.repo, a.files, a.max_files, a.generations, a.seed,
                      shlex.split(a.test_cmd) if a.test_cmd else None, a.timeout,
                      a.allow_behaviour_changing, a.apply, a.out)
    print(_markdown(rep))
    sys.exit(0 if rep["status"] == "ok" else 1)


if __name__ == "__main__":
    main()
