#!/usr/bin/env python3
"""Local, no-Actions TOE gate evidence. Never tags, uploads or enables readiness.

Run from a complete checkout after installing the repository dependencies:
    python scripts/run_toe_production_gates.py --full
A partial source export can use --scoped, but cannot qualify Gate A.
Human reviews are never manufactured by this runner.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def junit_passes(path: Path) -> bool:
    try:
        cases = list(ET.parse(path).getroot().iter("testcase"))
        return bool(cases) and not any(
            list(case.iter("failure")) or list(case.iter("error")) or list(case.iter("skipped"))
            for case in cases
        ) and not list(ET.parse(path).getroot().iter("error"))
    except (OSError, ET.ParseError):
        return False


def manifest() -> dict[str, str]:
    paths = []
    bases = ("toe", "kellogg", "Intelligence", "asi", "tests", "experiments",
             "scripts", "frontend/src/lib", "turing_universal_quantum_computer",
             "chronus", "salamander", "al_haras", "hyba_compat", "lucas", "aethel", "compiler")
    for base in bases:
        for suffix in ("*.py", "*.ts", "*.json"):
            paths.extend((ROOT / base).rglob(suffix))
    paths.extend(ROOT / name for name in ("package.json", "package-lock.json", "turing_core.py", "requirements.txt"))
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(set(paths)) if p.is_file()
            and "__pycache__" not in p.parts and "node_modules" not in p.parts
            and not p.name.endswith("_results.json")}


def baseline() -> tuple[str | None, bool]:
    """Capture BEFORE evidence creation or commands; include untracked files."""
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT,
            stderr=subprocess.DEVNULL, text=True).strip()
        status = subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=ROOT, text=True)
        return sha, not status.strip()
    except (OSError, subprocess.CalledProcessError):
        return None, False


def execute(name: str, args: list[str], output: Path, env: dict[str, str], timeout: int = 3600) -> dict:
    started = time.time()
    log = output / (name + ".log")
    before = manifest()
    try:
        with log.open("w") as stream:
            result = subprocess.run(args, cwd=ROOT, env=env, stdout=stream,
                                    stderr=subprocess.STDOUT, timeout=timeout)
        code = result.returncode
    except subprocess.TimeoutExpired:
        code = 124
    except OSError as exc:
        log.write_text(type(exc).__name__ + ": command unavailable\n")
        code = 127
    stable = before == manifest()
    return {"command": args, "exit_code": code, "passed": code == 0 and stable,
            "source_manifest_stable": stable, "elapsed_seconds": time.time()-started,
            "log": log.name, "log_sha256": hashlib.sha256(log.read_bytes()).hexdigest()}


def run() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--full", action="store_true")
    scope.add_argument("--scoped", action="store_true")
    opts = parser.parse_args()
    sha, clean = baseline()
    run_id = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + uuid.uuid4().hex[:8]
    output = ROOT / "release-evidence/toe" / run_id
    output.mkdir(parents=True)
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([str(ROOT), str(ROOT/"turing_universal_quantum_computer"), env.get("PYTHONPATH", "")])
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    (output/"tmp").mkdir()
    frozen = manifest()
    tasks = {}
    suites = {
        "D": ["tests/test_toe_runtime.py"],
        "E": ["tests/test_asi_core.py"],
        "C": ["tests/test_toe_consensus_boundary.py"],
        "G": ["tests/test_toe_ciaas_api.py", "tests/test_toe_machine.py", "tests/test_toe_cross_domain.py", "tests/test_toe_http_closeout.py"],
        "F_technical": ["tests/test_toe_domain_qualification.py"],
    }
    for name, files in suites.items():
        xml = output/(name+".xml")
        tasks[name] = execute(name, [sys.executable, "-m", "pytest", *files, "-q", "-p", "no:cacheprovider", "--basetemp="+str(output/"tmp"/name), "--junitxml="+str(xml)], output, env)
        tasks[name]["passed"] = tasks[name]["passed"] and junit_passes(xml)
    tasks["B"] = execute("B", [sys.executable, "experiments/toe_enterprise_collapse.py"], output, env)
    result_path = ROOT/"experiments/toe_enterprise_collapse_results.json"
    if tasks["B"]["passed"]:
        try:
            result = json.loads(result_path.read_text())
            rows = result["checks"]
            ids = [row["name"].split("_", 1)[0] for row in rows]
            tasks["B"]["passed"] = (result.get("all_passed") is True and len(ids) == 16
                                    and set(ids) == {f"T{i}" for i in range(1, 17)}
                                    and all(row.get("passed") is True and not row.get("skipped") for row in rows))
            (output/"collapse_results.json").write_text(json.dumps(result, indent=2)+"\n")
        except (OSError, KeyError, ValueError, TypeError):
            tasks["B"]["passed"] = False
    tasks["turing_registry"] = execute("turing_registry", [sys.executable, "-c", "from turing_universal_quantum_computer.product_registry import verify_registry; r=verify_registry(); print(r); raise SystemExit(0 if r.get('ok') is True else 1)"], output, env)
    tasks["turing_benchmark"] = execute("turing_benchmark", [sys.executable, "-m", "turing_universal_quantum_computer.benchmark", "--quick"], output, env)
    tasks["A"] = {"passed": False, "reason": "full clean Git checkout required; no subset substitution"}
    if opts.full and clean:
        xml = output/"A.xml"
        tasks["A"] = execute("A", [sys.executable, "-m", "pytest", "tests/", "-q", "-p", "no:cacheprovider", "--basetemp="+str(output/"tmp"/"A"), "--junitxml="+str(xml)], output, env, timeout=14400)
        tasks["A_lint"] = execute("A_lint", [sys.executable, "-m", "flake8", "--count"], output, env)
        tasks["A"]["passed"] = tasks["A"]["passed"] and junit_passes(xml) and tasks["A_lint"]["passed"]
    tasks["F"] = {"passed": False, "reason": "named independent domain reviews and domain-specific validity remain mandatory", "technical_passed": tasks["F_technical"]["passed"]}
    gates = {key: tasks[key]["passed"] for key in "ABCDEFG"}
    stable = frozen == manifest()
    ready = all(gates.values()) and stable and tasks["turing_registry"]["passed"] and tasks["turing_benchmark"]["passed"]
    report = {"schema": "toe.gates/v1", "run_id": run_id, "source_commit": sha,
              "complete_checkout_asserted": opts.full, "clean_tree_before_execution": clean,
              "source_manifest_stable": stable, "gates": gates, "tasks": tasks,
              "production_ready": ready, "receipt_flag_changed": False}
    (output/"report.json").write_text(json.dumps(report, indent=2)+"\n")
    (output/"source_manifest.json").write_text(json.dumps(frozen, indent=2)+"\n")
    domains = sorted((ROOT/"toe/adapters/qualification").glob("*.json"))
    text = ["# TOE Production Readiness Report", "", f"Run: `{run_id}`", "", f"**PRODUCTION READY: {str(ready).lower()}**", "", "| Gate | Passed |", "| --- | --- |"]
    text += [f"| {key} | {str(value).lower()} |" for key, value in gates.items()]
    text += ["", "Gate H is this report, not an independent approval. See report.json for commands, failures and hashes.", "", "## Domain approval", "", "| Domain | Production ready | Expert approval |", "| --- | --- | --- |"]
    text += [f"| {json.loads(path.read_text())['domain']} | false | PENDING |" for path in domains]
    text += ["", "Synthetic technical fixtures are not clinical, financial, linguistic or security certification. Healthcare is decision-support-only and requires IRB/clinical review.", "", "TOE advises search; PYTHIA owns SHA256d validity and pool outcomes. No deployment, publication or receipt readiness flag is changed by this runner.", ""]
    (output/"PRODUCTION_READINESS_REPORT.md").write_text("\n".join(text))
    print(json.dumps({"report": str(output.relative_to(ROOT)), "gates": gates, "production_ready": ready}))
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(run())
