"""Build/test installed M5+resident RC artifacts; never publish or certify product.

Run from a complete checkout. Each variant uses a clean staging tree and venv.
Both original and sdist-rebuilt wheels are tested outside the source tree.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import xml.etree.ElementTree as ET
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import venv
import zipfile

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]
TESTS = ("test_m5_model.py", "test_m5_resident.py", "test_m5_quantum.py", "test_execution_binding.py", "test_generic_m5_features.py", "test_m5_ultra_contract.py", "test_m5_exact_opencl.py", "test_m5_release_gates.py", "test_opencl_adapter_replacement.py", "test_m32_public_replacement.py")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def python_in(path):
    return path / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=("native", "portable"), required=True)
    parser.add_argument("--skip-benchmark", action="store_true", help="bounded contract pass: no new rate measurement")
    parser.add_argument("--contract-rc-sha", help="revision binding for installed bounded evidence campaign")
    args = parser.parse_args()
    out = PACKAGE / "dist" / ("m5-" + args.variant)
    out.mkdir(parents=True, exist_ok=True)
    if any(out.glob("*.whl")) or any(out.glob("*.tar.gz")):
        raise SystemExit("Use a fresh artifact directory; refusing stale artifacts")
    report = {"schema": "chronos_m5_package_verification/1", "variant": args.variant,
              "commands": [], "package_checks_passed": False, "publishable": False,
              "production_certified": False, "published": False,
              "scope": "M5 model/resident/CLI package checks, not full product suite",
              "python": sys.version, "platform": platform.platform()}
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.pop("CHRONOS_REFERENCE_APPROVALS_FILE", None)
    env["CHRONOS_DISABLE_NATIVE"] = "1" if args.variant == "portable" else "0"

    def run(command, cwd, capture=False):
        proc = subprocess.run(list(map(str, command)), cwd=cwd, env=env,
                              text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        report["commands"].append({"argv": list(map(str, command)), "exit_code": proc.returncode})
        with (out / "commands.log").open("a", encoding="utf-8") as log:
            log.write("$ " + " ".join(map(str, command)) + "\n" + proc.stdout + "\n")
        if proc.returncode:
            raise RuntimeError("command failed; see commands.log: " + str(command))
        return proc.stdout if capture else None

    try:
        revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, text=True,
                                  capture_output=True)
        report["source_revision"] = revision.stdout.strip() if revision.returncode == 0 else "UNAVAILABLE"
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=REPO, text=True, capture_output=True)
        report["worktree_state"] = "UNKNOWN" if dirty.returncode else ("DIRTY" if dirty.stdout.strip() else "CLEAN")
        run([sys.executable, PACKAGE / "scripts/sync_m5_model.py"], REPO)
        report["canonical_model_sha256"] = digest(REPO / "chronus/m5_ultra.py")
        report["source_inventory"] = {str(p.relative_to(PACKAGE)): digest(p)
            for p in sorted((PACKAGE / "src/chronos_one_igpu").rglob("*"))
            if p.is_file() and p.suffix in (".py", ".cl", ".c", ".json", ".md")}
        with tempfile.TemporaryDirectory(prefix="chronos-m5-package-") as temp:
            root = Path(temp)
            stage = root / "source"
            shutil.copytree(PACKAGE, stage, ignore=shutil.ignore_patterns(
                "dist", "build", "*.egg-info", "__pycache__", "*.pyc", "*.so", "*.pyd"))
            run([sys.executable, "-m", "build", "--wheel", "--sdist", "--outdir", out, stage], root)
            wheel, = out.glob("*.whl")
            sdist, = out.glob("*.tar.gz")
            run([sys.executable, "-m", "twine", "check", wheel, sdist], root)
            with zipfile.ZipFile(wheel) as archive:
                names = archive.namelist()
                assert not any(n.startswith(("chronos/", "chronus/")) for n in names), "namespace collision"
                assert archive.read("chronos_one_igpu/m5_ultra.py") == (REPO / "chronus/m5_ultra.py").read_bytes()
                native = any(n.endswith((".so", ".pyd")) and "_sha256d_native" in n for n in names)
                assert native == (args.variant == "native"), "native artifact variant mismatch"
            report["wheel"] = {"name": wheel.name, "sha256": digest(wheel)}
            report["sdist"] = {"name": sdist.name, "sha256": digest(sdist)}
            extract = root / "sdist"
            extract.mkdir()
            with tarfile.open(sdist) as archive:
                if sys.version_info >= (3, 12):
                    archive.extractall(extract, filter="data")
                else:
                    # Reject traversal and links before extraction on older Python.
                    for member in archive.getmembers():
                        dest = (extract / member.name).resolve()
                        if extract.resolve() not in dest.parents or member.issym() or member.islnk():
                            raise ValueError("unsafe sdist member")
                    archive.extractall(extract)
            source, = (p for p in extract.iterdir() if p.is_dir())
            rebuilt_dir = root / "rebuilt"
            run([sys.executable, "-m", "build", "--wheel", "--outdir", rebuilt_dir, source], root)
            rebuilt, = rebuilt_dir.glob("*.whl")
            report["sdist_rebuilt_wheel_sha256"] = digest(rebuilt)
            for label, artifact in (("wheel", wheel), ("sdist", rebuilt)):
                work = root / ("installed-" + label)
                work.mkdir()
                environment = work / "venv"
                venv.EnvBuilder(with_pip=True).create(environment)
                py = python_in(environment)
                run([py, "-m", "pip", "install", artifact, "pytest>=8,<10"], work)
                run([py, "-I", "-c", "import importlib.metadata as m, chronos_one_igpu as c; assert 'site-packages' in c.__file__.replace('\\\\','/'); assert m.version('hyba-chronos-one-igpu') == c.__version__; print(c.__file__)"], work)
                for name in TESTS:
                    shutil.copy2(PACKAGE / "tests" / name, work / name)
                junit = out / (label + "-tests.xml")
                run([py, "-I", "-m", "pytest", "-q", "-p", "no:cacheprovider",
                     "--rootdir", work, "--junitxml", junit, *[work / n for n in TESTS]], work)
                report[label + "_tests"] = {"junit_sha256": digest(junit),
                    "results": [{k: suite.get(k) for k in ("tests", "failures", "errors", "skipped")}
                                for suite in ET.parse(junit).getroot().iter("testsuite")]}
                if not args.skip_benchmark:
                    benchmark_file=out/(label+"-feature-benchmark.json")
                    run([py,"-I",PACKAGE/"scripts/benchmark_generic_features.py","--output",benchmark_file],work)
                    report[label+"_feature_benchmark"]={"sha256":digest(benchmark_file),"scope":"equal-work exact kernel control; not physical M5 or mining"}
                else:report[label+"_feature_benchmark"]={"status":"NOT_RUN", "reason":"contract increment forbids new throughput/speedup claims"}
                if args.contract_rc_sha:
                    contract_file=out/(label+"-ultra-contract.json")
                    run([py,"-I",PACKAGE/"scripts/audit_m5_ultra_contract.py","--rc-sha",args.contract_rc_sha,"--output",contract_file],work)
                    report[label+"_ultra_contract"]={"sha256":digest(contract_file),"scope":"bounded contract incremental evidence only", "rc_sha_binding":args.contract_rc_sha}
                    replay_file=out/(label+"-independent-replay.json")
                    run([py,"-I",PACKAGE/"scripts/replay_m5_ultra_evidence.py","--source-report",contract_file,"--report-sha256",digest(contract_file),"--rc-sha",args.contract_rc_sha,"--output",replay_file],work)
                    report[label+"_independent_replay"]={"sha256":digest(replay_file),"scope":"same-host fresh-process independent replay; no hardware redispatch, not cross-machine proof"}

            report["package_checks_passed"] = True
            report["publication_blockers"] = [
                "current-head whole-product certification and unresolved QC/import/platform closure",
                "owner approval of release promotion; registry upload not performed",
                "Apple M5/Metal/ANE lane claims require separate physical device evidence",
            ]
    except Exception as exc:
        report["failure"] = str(exc)
        raise
    finally:
        (out / "verification.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
