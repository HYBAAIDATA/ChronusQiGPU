#!/usr/bin/env python3
"""Local CI: the repository's release checks, run on this machine.

GitHub Actions is unavailable while the account is on a billing hold, so
this runner executes the checks that matter from ``ci.yml``,
``azure-package.yml`` and the product workflows against the *committed*
tree, and writes evidence bound to the exact commit:

    python scripts/local_ci.py                # standard lane (~minutes)
    python scripts/local_ci.py --full         # + full pytest, compared to the known-failure baseline
    python scripts/local_ci.py --pr 2         # + post the summary as a PR comment

Output: ``local-ci/<sha12>/results.json``, ``summary.md``, one log per
step and, when a network namespace is available, the sovereign proof pack
run with no route out (``unshare -rn``). Exit 0 only when every required
step passes. Steps that cannot run here (no Docker, no Node) are reported
as SKIP with the reason, never as PASS.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable

# Failures known on the base branch before this work began. --full reports
# them separately so new regressions cannot hide among them.
KNOWN_FAILING_FILES = (
    "tests/test_organism_integration.py",
    "tests/test_production_api_contract.py",
    "chronus/tests/test_chronus_native_batch_route.py",
    "chronus/tests/test_chronus_namespace.py",
    "tests/test_asi_core.py",
    "tests/test_toe_package.py",
)

PRODUCT_TESTS = (
    "tests/test_sovereign_control.py",
    "tests/test_theseus_tenant_isolation.py",
    "tests/test_ovid_graph_edge_integrity.py",
    "tests/test_enterprise_custody_substrate.py",
    "tests/test_consortium_push.py",
    "chronus/tests/test_chronus_first_workload.py",
)


@dataclass
class Step:
    name: str
    status: str = "PENDING"
    seconds: float = 0.0
    detail: str = ""
    required: bool = True
    log: str = ""
    extra: dict = field(default_factory=dict)


def sh(cmd: list[str] | str, log: Path, *, env=None, timeout=3600, cwd=ROOT) -> int:
    with open(log, "w", encoding="utf-8") as handle:
        handle.write(f"$ {cmd if isinstance(cmd, str) else ' '.join(cmd)}\n")
        handle.flush()
        try:
            proc = subprocess.run(
                cmd, shell=isinstance(cmd, str), cwd=str(cwd), env=env,
                stdout=handle, stderr=subprocess.STDOUT, timeout=timeout,
            )
            return proc.returncode
        except subprocess.TimeoutExpired:
            handle.write(f"\nTIMEOUT after {timeout}s\n")
            return 124


def tail(path: Path, lines: int = 3) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace").strip().splitlines()
    except OSError:
        return ""
    return " | ".join(text[-lines:])[:400]


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True,
                          text=True, check=True).stdout.strip()


def changed_python(base: str) -> list[str]:
    try:
        names = git("diff", "--name-only", "--diff-filter=ACMR", f"{base}...HEAD")
    except subprocess.CalledProcessError:
        return []
    return [n for n in names.splitlines() if n.endswith(".py") and (ROOT / n).is_file()]


def netns_available() -> bool:
    if shutil.which("unshare") is None or shutil.which("ip") is None:
        return False
    probe = subprocess.run(["unshare", "-rn", "true"], capture_output=True)
    return probe.returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--full", action="store_true", help="also run the full pytest suite")
    parser.add_argument("--base", default="origin/production-readiness",
                        help="lint changed files relative to this ref")
    parser.add_argument("--pr", type=int, help="post the summary to this pull request")
    parser.add_argument("--allow-dirty", action="store_true",
                        help="run on an uncommitted tree (evidence is marked dirty)")
    args = parser.parse_args()

    dirty = bool(git("status", "--porcelain", "--untracked-files=no"))
    if dirty and not args.allow_dirty:
        print("local CI runs on committed work; commit first (or --allow-dirty)", file=sys.stderr)
        return 2
    sha = git("rev-parse", "HEAD")
    out = ROOT / "local-ci" / sha[:12]
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    env = {**os.environ, "PYTHONHASHSEED": "0", "PYTHONPATH": str(ROOT)}
    steps: list[Step] = []

    def run(name: str, cmd, *, required=True, timeout=3600, env_=None) -> Step:
        step = Step(name, required=required)
        log = out / f"{len(steps):02d}-{name.lower().replace(' ', '-').replace('/', '-')[:40]}.log"
        start = time.time()
        rc = sh(cmd, log, env=env_ or env, timeout=timeout)
        step.seconds = round(time.time() - start, 1)
        step.status = "PASS" if rc == 0 else "FAIL"
        step.detail = f"rc={rc}; {tail(log)}"
        step.log = log.name
        steps.append(step)
        print(f"[{step.status}] {name} ({step.seconds}s)", flush=True)
        return step

    def skip(name: str, reason: str) -> None:
        steps.append(Step(name, "SKIP", detail=reason, required=False))
        print(f"[SKIP] {name}: {reason}", flush=True)

    pytest = [PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-o", "addopts="]

    # 1. Lint, exactly as CI: changed .py files only, flake8 + fatal ruff.
    files = changed_python(args.base)
    if files:
        run("Lint flake8 (changed files)", [PY, "-m", "flake8", *files])
        run("Lint ruff E9,F (changed files)", [PY, "-m", "ruff", "check", "--select", "E9,F", *files])
    else:
        skip("Lint (changed files)", f"no changed Python files relative to {args.base}")

    # 2. Structural checks from ci.yml.
    run("Import audit", [PY, "scripts/import_audit.py"])
    run("Import graph cycles+layers",
        f"{PY} scripts/import_graph.py cycles && {PY} scripts/import_graph.py layers")
    run("PULVINI data boundary", [PY, "scripts/check_pulvini_data_boundary.py"])
    run("Canonical structured-search doctrine", [PY, "scripts/check_canonical_mining_search.py"])
    run("Repository ownership", [PY, "scripts/repo_ownership_gate.py"])
    run("Deploy sentry", [PY, "-m", "scripts.deploy_sentry"], required=False)
    run("Deployment claims boundary", [PY, "-m", "scripts.deployment_claims_gate"])

    # 3. Repository evidence gates (make gates), on the committed tree.
    gates = run("Repository gates (make -k gates)", ["make", "-k", "gates"], required=False, timeout=2400)
    statuses = {}
    for path in sorted((ROOT / "results").glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict) and "gate" in data:
            statuses[data["gate"]] = data.get("status")
    gates.extra["gates"] = statuses
    gates.detail = ", ".join(f"{k}={v}" for k, v in statuses.items())
    subprocess.run(["git", "-C", str(ROOT), "checkout", "--", "reports/REPO_FILE_OWNERSHIP.json"],
                   capture_output=True)

    # 4. Product and sovereign tests (the duty set).
    present = [t for t in PRODUCT_TESTS if (ROOT / t).is_file()]
    run("Sovereign + THESEUS/OVID/CHRONUS tests", [*pytest, *present], timeout=1800)

    # 5. Air-gap proof with real network isolation (kernel network namespace).
    if netns_available():
        key = secrets.token_hex(32)
        (out / "attestation.key").write_text(key + "\n", encoding="utf-8")
        os.chmod(out / "attestation.key", 0o600)
        inner = (
            "ip link set lo up && exec env "
            "HYBA_SOVEREIGN_MODE=air_gapped "
            f"HYBA_SOVEREIGN_AUDIT_PATH={out}/sovereign-proof/audit/sovereign.jsonl "
            f"HYBA_SOVEREIGN_ATTESTATION_KEY={key} "
            "HYBA_SOVEREIGN_NETWORK_ISOLATION=linux-network-namespace "
            f"HYBA_BUILD_COMMIT={sha} "
            f"{PY} scripts/sovereign_proof_pack.py --require-network-isolation "
            f"--out {out}/sovereign-proof/pack"
        )
        proof = run("Sovereign air-gap proof (no route out)", ["unshare", "-rn", "sh", "-c", inner])
        summary = out / "sovereign-proof" / "pack" / "summary.md"
        if summary.is_file():
            proof.extra["summary"] = summary.relative_to(out).as_posix()
        run("Offline attestation verification",
            [PY, "-m", "al_haras.sovereign_control", "verify",
             f"{out}/sovereign-proof/pack/attestation.json",
             "--audit", f"{out}/sovereign-proof/pack/audit.jsonl",
             "--key-file", f"{out}/attestation.key"])
    else:
        skip("Sovereign air-gap proof (no route out)", "no unprivileged network namespace (unshare -rn)")

    # 6. Docker image smoke: needs a Docker daemon.
    if shutil.which("docker") and subprocess.run(["docker", "info"], capture_output=True).returncode == 0:
        run("Docker build (deploy/azure/Dockerfile)",
            ["docker", "build", "-f", "deploy/azure/Dockerfile", "-t", "pythia-control:local", "."],
            timeout=3600)
    else:
        skip("Docker image build and smoke", "no Docker daemon on this machine")

    # 7. Byte-compile, as ci.yml.
    roots = [d for d in ("Intelligence", "core_engine", "mining", "hyba", "pythagoras", "scripts",
                         "tests", "chronus", "aethel", "al_haras", "hyba_db", "bench",
                         "experiments", "quantum") if (ROOT / d).is_dir()]
    run("Byte-compile sources", [PY, "-m", "compileall", "-q", *roots], timeout=1800)

    # 8. Frontend, when Node is present.
    if shutil.which("npm") and (ROOT / "frontend" / "package.json").is_file():
        run("Frontend typecheck/test/build",
            "npm ci --prefix frontend && npm run lint && npm run test:ts && npm run build",
            required=False, timeout=2400)
    else:
        skip("Frontend typecheck/test/build", "npm not available")

    # 9. Full suite, compared with the known-failure baseline.
    if args.full:
        junit = out / "pytest-full.xml"
        full = run("Full pytest (tests/ + chronus/tests)",
                   [*pytest, "-n", "2", f"--junitxml={junit}", "tests", "chronus/tests"],
                   required=False, timeout=7200)
        failed_files: dict[str, int] = {}
        if junit.is_file():
            import xml.etree.ElementTree as ET

            for case in ET.parse(junit).getroot().iter("testcase"):
                if case.find("failure") is not None or case.find("error") is not None:
                    file = (case.get("file") or case.get("classname", "").replace(".", "/") + ".py")
                    failed_files[file] = failed_files.get(file, 0) + 1
        new = {f: n for f, n in failed_files.items()
               if not any(f.endswith(k) or k.endswith(f) for k in KNOWN_FAILING_FILES)}
        full.extra = {"failed_by_file": failed_files, "new_failures": new}
        regress = Step("No new failures vs known baseline", "PASS" if not new else "FAIL",
                       detail=json.dumps(new)[:400] if new else
                       f"failures confined to {len(failed_files)} known file(s)")
        steps.append(regress)
        print(f"[{regress.status}] {regress.name}", flush=True)

    required_ok = all(s.status == "PASS" for s in steps if s.required)
    result = {
        "schema": "hyba.local-ci/1",
        "commit": sha,
        "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
        "dirty": dirty,
        "host": os.uname().nodename if hasattr(os, "uname") else "",
        "python": sys.version.split()[0],
        "passed": required_ok,
        "steps": [asdict(s) for s in steps],
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (out / "results.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    md = [
        f"## Local CI — `{sha[:12]}` ({result['branch']})",
        "",
        f"Overall (required steps): **{'PASS' if required_ok else 'FAIL'}**"
        + ("  · tree was dirty" if dirty else ""),
        "",
        "GitHub Actions is on a billing hold; these checks ran locally on the committed tree.",
        "",
        "| Step | Result | Required | Time | Detail |",
        "|---|---|---|---|---|",
    ]
    for s in steps:
        detail = s.detail.replace("|", "/").replace("\n", " ")[:160]
        md.append(f"| {s.name} | {s.status} | {'yes' if s.required else 'no'} | {s.seconds}s | {detail} |")
    proof_md = out / "sovereign-proof" / "pack" / "summary.md"
    if proof_md.is_file():
        md += ["", "<details><summary>Sovereign air-gap proof</summary>", "",
               proof_md.read_text(encoding="utf-8"), "</details>"]
    (out / "summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"\nlocal CI {'PASS' if required_ok else 'FAIL'} — evidence in {out.relative_to(ROOT)}")
    if args.pr:
        subprocess.run(["gh", "pr", "comment", str(args.pr), "--body-file", str(out / "summary.md")],
                       cwd=str(ROOT))
    return 0 if required_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
