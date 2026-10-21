"""Build and verify the standalone TOE release artefacts.

Artefact-first, like KELLOGG's script:

    stage only what TOE owns → build wheel + sdist → twine check
    → inspect the wheel boundary + secret/local-path scan
    → clean venv: install the exact KELLOGG 1.0.0 wheel + the TOE wheel
      (no source tree on the path) → import every shipped module, block
      sibling products, check metadata/manifest/register, run the
      cross-domain and canonical voyages, the adversarial battery, the
      exact deterministic fixtures and the release tests
    → rebuild a wheel from the sdist and verify it the same way
    → machine-readable evidence in packaging/toe/dist/

Nothing is published. ``publishable`` stays false while any owner decision
in OWNER_DECISIONS.md is open.

Usage: python packaging/toe/build_and_verify.py [--python PATH ...]
       (extra --python interpreters re-run the installed check on the
       same artefacts for cross-version evidence)
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import traceback
import venv
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
DIST = HERE / "dist"
REPOSITORY = "PhiEnterprise1/EuclidPhiEnterprise"
KELLOGG_VERSION = "1.0.0"

# Monorepo integration surfaces TOE does not ship (mining-facing coordinator,
# the five nonce-authority intelligences, and an alias of aethel's code).
EXCLUDED = ("system.py", "manifold_bridge.py", "hardened_unified_substrate.py", "intelligences")
RELEASE_TESTS = (
    "test_toe_machine.py",
    "test_toe_geometry.py",
    "test_toe_learning_persistence.py",
)
# Explicit runtime regression scope, not the full repository test harness.
UNIFIED_TESTS = (
    "test_toe_unified_tenancy.py",
    "test_toe_unified_tenant_qualification.py",
    "test_toe_unified_authority.py",
    "test_toe_unified_atomic.py",
    "test_toe_unified_promotion.py",
    "test_toe_unified_tenancy.py",
)

INSTALLED_UNIFIED_PROBE = r"""
import hashlib, json, sysconfig
from pathlib import Path
import toe, kellogg
from toe.unified import UnifiedAnalyticsPlatform
from toe.unified import platform as facade
roots = {Path(sysconfig.get_path(key)).resolve() for key in ("purelib", "platlib")}
origins = {}
for name, module in (("toe", toe), ("kellogg", kellogg), ("toe.unified.platform", facade)):
    if not module.__file__:
        raise RuntimeError(f"{name} is a namespace package, not a verified installed artifact")
    path = Path(module.__file__).resolve()
    if not any(path.is_relative_to(root) for root in roots):
        raise RuntimeError(f"{name} resolved outside this interpreter's installed packages: {path}")
    origins[name] = {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
print(json.dumps(origins, sort_keys=True))
"""


_SECRET_PATTERNS = (
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"ghp_[A-Za-z0-9]{30,}"),
    re.compile(rb"github_pat_[A-Za-z0-9_]{40,}"),
    re.compile(rb"pypi-AgEI[A-Za-z0-9_-]{20,}"),
    re.compile(rb"AKIA[0-9A-Z]{16}"),
)
_BAD_NAME_PARTS = ("/.git/", "/__pycache__/", ".pyc", ".pyo", ".pypirc", ".env", "/tests/")
_NO_CACHE = {**os.environ, "PIP_NO_CACHE_DIR": "1", "PIP_DISABLE_PIP_VERSION_CHECK": "1"}


def sh(cmd: List[Any], **kw: Any) -> subprocess.CompletedProcess:
    print("$", " ".join(str(c) for c in cmd), flush=True)
    kw.setdefault("env", _NO_CACHE)
    kw.setdefault("timeout", 1800)
    return subprocess.run([str(c) for c in cmd], check=True, text=True, **kw)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def toe_version() -> str:
    m = re.search(
        r'^__version__ = "([^"]+)"',
        (REPO / "toe" / "__init__.py").read_text(encoding="utf-8"),
        re.M,
    )
    if not m:
        raise RuntimeError("toe/__init__.py has no __version__ literal")
    return m.group(1)


def dist_name() -> str:
    m = re.search(r'^name = "([^"]+)"', (HERE / "pyproject.toml").read_text(encoding="utf-8"), re.M)
    if not m:
        raise RuntimeError("packaging/toe/pyproject.toml has no name")
    return m.group(1)


def owner_decisions() -> Dict[str, Any]:
    text = (HERE / "OWNER_DECISIONS.md").read_text(encoding="utf-8")
    name = re.search(r"^APPROVED_DISTRIBUTION_NAME:\s*(\S+)", text, re.M)
    ver = re.search(r"^APPROVED_VERSION:\s*(\S+)", text, re.M)
    return {
        "distribution_name_approved": name.group(1) if name else None,
        "version_approved": ver.group(1) if ver else None,
    }


def git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "UNAVAILABLE"


def _py(env_dir: Path) -> Path:
    return env_dir / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def tooling_python(root: Path) -> Path:
    env = root / "tooling"
    venv.EnvBuilder(with_pip=True, clear=True).create(env)
    py = _py(env)
    sh([py, "-m", "pip", "install", "-q", "build", "twine"])
    return py


def stage_toe(root: Path) -> Path:
    src = root / "toe-src"
    src.mkdir(parents=True)
    shutil.copytree(
        REPO / "toe",
        src / "toe",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", *EXCLUDED),
    )
    for name in ("pyproject.toml", "README.md"):
        shutil.copy2(HERE / name, src / name)
    shutil.copy2(REPO / "LICENSE", src / "LICENSE")
    return src


def build_kellogg_wheel(py: Path, root: Path) -> Path:
    """KELLOGG's own staging function, KELLOGG's own pyproject: the exact
    1.0.0 wheel TOE declares, built from its owner's release boundary."""
    spec = importlib.util.spec_from_file_location(
        "kellogg_build", REPO / "packaging" / "kellogg-tensor" / "build_and_verify.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    staged = mod.stage(root / "kellogg-stage")
    out = root / "kellogg-dist"
    sh([py, "-m", "build", "--wheel", "--outdir", out, staged])
    wheels = sorted(out.glob(f"hyba_kellogg_tensor-{KELLOGG_VERSION}-*.whl"))
    if len(wheels) != 1:
        raise RuntimeError(f"expected one KELLOGG {KELLOGG_VERSION} wheel, got {wheels}")
    return wheels[0]


def _names(archive: Path) -> List[str]:
    if archive.suffix == ".whl":
        with zipfile.ZipFile(archive) as zf:
            return zf.namelist()
    with tarfile.open(archive, "r:*") as tf:
        return [m.name for m in tf.getmembers()]


def _members(archive: Path):
    if archive.suffix == ".whl":
        with zipfile.ZipFile(archive) as zf:
            for info in zf.infolist():
                if not info.is_dir():
                    yield info.filename, zf.read(info)
        return
    with tarfile.open(archive, "r:*") as tf:
        for m in tf.getmembers():
            if m.isfile():
                fh = tf.extractfile(m)
                if fh is not None:
                    yield m.name, fh.read()


def inspect_wheel(wheel: Path, version: str) -> Dict[str, Any]:
    names = _names(wheel)
    dist_info = {n.split("/", 1)[0] + "/" for n in names if ".dist-info/" in n}
    if len(dist_info) != 1:
        raise RuntimeError(f"expected one dist-info, found {sorted(dist_info)}")
    di = next(iter(dist_info))
    outside = [n for n in names if not (n.startswith("toe/") or n.startswith(di))]
    if outside:
        raise RuntimeError(f"wheel ships files outside the TOE boundary: {outside[:20]}")
    leaked = [
        n for n in names if any(n == f"toe/{x}" or n.startswith(f"toe/{x}/") for x in EXCLUDED)
    ]
    if leaked:
        raise RuntimeError(f"wheel ships monorepo-only surfaces: {leaked}")
    required = {
        "toe/__init__.py",
        "toe/py.typed",
        "toe/machine.py",
        "toe/problem.py",
        "toe/CAPABILITY_MANIFEST.json",
        "toe/CLAIM_REGISTER.json",
        "toe/default_propagators.json",
        "toe/adapters/__init__.py",
        "toe/unified/__init__.py",
        "toe/unified/checkpoint.py",
    }
    missing = sorted(required - set(names))
    if missing:
        raise RuntimeError(f"wheel missing required files: {missing}")
    if not [n for n in names if n.startswith(di) and n.upper().endswith("LICENSE")]:
        raise RuntimeError("wheel is missing the licence")
    bad = [n for n in names if any(p in "/" + n for p in _BAD_NAME_PARTS)]
    if bad:
        raise RuntimeError(f"wheel contains forbidden paths: {bad[:20]}")
    manifest = {
        "wheel": wheel.name,
        "version": version,
        "sha256": sha256(wheel),
        "files": sorted(names),
        "file_count": len(names),
    }
    (DIST / "wheel-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    return manifest


def scan(archive: Path) -> Dict[str, Any]:
    tokens = {str(REPO).encode(), str(REPO).replace("\\", "/").encode()}
    findings = []
    for name, data in _members(archive):
        if any(p in "/" + name for p in _BAD_NAME_PARTS):
            findings.append({"file": name, "reason": "forbidden path"})
        for pat in _SECRET_PATTERNS:
            if pat.search(data):
                findings.append({"file": name, "reason": f"secret pattern {pat.pattern!r}"})
        if any(t and t in data for t in tokens):
            findings.append({"file": name, "reason": "local repository path embedded"})
    if findings:
        raise RuntimeError(f"artefact scan failed: {findings[:10]}")
    return {"artifact": archive.name, "sha256": sha256(archive), "findings": []}


INSTALLED_CHECK = r"""
import hashlib, importlib, importlib.metadata, importlib.util, json, pkgutil, sys
from importlib.resources import files

EXPECTED_VERSION, DIST = sys.argv[1], sys.argv[2]
FORBIDDEN = {"aethel", "chronus", "euclid", "Intelligence", "mining", "lucas", "millennium",
             "turing_core", "turing_universal_quantum_computer", "mtheory", "resonance_intelligence", "asi"}

import toe, kellogg
assert "site-packages" in toe.__file__.replace("\\", "/"), toe.__file__
assert "site-packages" in kellogg.__file__.replace("\\", "/"), kellogg.__file__
assert toe.__version__ == EXPECTED_VERSION, toe.__version__
md = importlib.metadata.metadata(DIST)
assert md["Name"] == DIST and md["Version"] == EXPECTED_VERSION, (md["Name"], md["Version"])
assert md["Requires-Python"] == ">=3.11"
reqs = [r for r in (importlib.metadata.requires(DIST) or []) if "extra ==" not in r]
assert sorted(r.split(">")[0].split("<")[0].strip().lower() for r in reqs) == ["hyba-kellogg-tensor", "numpy"], reqs
urls = md.get_all("Project-URL") or []
assert any("PhiEnterprise1/EuclidPhiEnterprise" in u for u in urls), urls
assert not any(old in u for old in ("QuantumPhi2/PhiMiner", "QuantumPhiRedux/PhiMiner") for u in urls), urls

mods = sorted(m.name for m in pkgutil.walk_packages(toe.__path__, "toe."))
failed = {}
for name in mods:
    try:
        importlib.import_module(name)
    except Exception as exc:
        failed[name] = f"{type(exc).__name__}: {exc}"
assert not failed, failed
for gone in ("toe.system", "toe.manifold_bridge", "toe.hardened_unified_substrate", "toe.intelligences"):
    assert importlib.util.find_spec(gone) is None, gone
from toe import *  # noqa: F401,F403 - the public surface must resolve standalone

manifest = json.loads(files("toe").joinpath("CAPABILITY_MANIFEST.json").read_text())
assert manifest["version"] == EXPECTED_VERSION and manifest["import_name"] == "toe"
register = json.loads(files("toe").joinpath("CLAIM_REGISTER.json").read_text())
statuses = {c["id"]: c["status"] for c in register["claims"]}
assert statuses["yang-mills-continuum"] == "OPEN" and statuses["physical-quantum-execution"] == "UNSUPPORTED"

from toe.voyage import canonical_voyage, cross_domain_voyage
xd = cross_domain_voyage()
assert xd["reuse"]["adapter_code_in_any_backend_trace"] == []
assert all(d["result"]["status"] in ("ACT", "NAVIGATE", "DESCRIBE") for d in xd["domains"].values())
cv = canonical_voyage(None)
assert cv["episode_1"]["status"] == "ACQUIRE_EVIDENCE" and cv["decision_changed"] is True
assert cv["replay_episode_1"]["identical"] and cv["negative_transfer_guard"]["guard_held"]
assert cv["restart"]["available"] is False   # THESEUS is not part of this install

from toe.self_governance import machine_battery
battery = machine_battery()
assert battery["vulnerable"] == [], battery["vulnerable"]

from toe.adapters import LegacyHRAdapter, OptionalDependencyUnavailable
legacy_hr = "pandas present"
if importlib.util.find_spec("pandas") is None:
    try:
        LegacyHRAdapter().legacy_engine_predict([{"a": 1}])
    except OptionalDependencyUnavailable:
        legacy_hr = "fails cleanly without the legacy-hr extra"
    else:
        raise AssertionError("legacy HR engine ran without pandas")

# Exact, interpreter-independent fixtures (cross-version digest).
from toe.machine import TOEMachine
from toe.adapters import RecurrenceAdapter
from toe.voyage import fixture_recurrence, voyage_problem
from toe.causal_ladder import ARITHMETIC_EXACT, counterfactual_state
from toe.problem import Structure
from kellogg.scales import zeckendorf
m = TOEMachine()
fc = m.run(RecurrenceAdapter().to_problem(fixture_recurrence()))["forecast"]["value"]
scm = Structure.of([("x", "y", 0.5), ("z", "y", 1.0)]).scm()
cf = counterfactual_state(scm, {"x": 3}, {"x": 1, "z": 2, "y": 4}, ["y"], arithmetic=ARITHMETIC_EXACT)["exact_values"]
fixture = {
    "lucas_forecast_1010": fc,
    "counterfactual_exact": cf,
    "problem_content_digest": voyage_problem().content_digest(),
    "structure_shape_digest": voyage_problem().structure.shape_digest(),
    "zeckendorf_10_pow_30": zeckendorf(10 ** 30),
}
digest = hashlib.sha256(json.dumps(fixture, sort_keys=True).encode()).hexdigest()
leaked = sorted(n for n in FORBIDDEN if n in sys.modules)
assert not leaked, leaked
print(json.dumps({
    "python": sys.version.split()[0],
    "toe_file": toe.__file__,
    "kellogg_file": kellogg.__file__,
    "module_count": len(mods),
    "modules": mods,
    "cross_domain_statuses": {k: v["result"]["status"] for k, v in xd["domains"].items()},
    "canonical_voyage": {"episode_1": cv["episode_1"]["status"], "decision_changed": cv["decision_changed"]},
    "battery_counts": battery["counts"],
    "legacy_hr_extra": legacy_hr,
    "fixture_digest": digest,
    "siblings_loaded": leaked,
}, sort_keys=True))
"""


def installed_unified_check(py: Path, workdir: Path, label: str) -> Dict[str, Any]:
    """Run the four hardening suites against installed artifacts, fail closed.

    Copy tests only, never package sources or repository conftest. Retain logs,
    counts and hashes outside the temporary venv even on a failed invocation.
    Harness unit tests do not themselves establish installed-package success.
    """
    output = DIST / ("installed-" + kind) / workdir.name
    shutil.rmtree(output, ignore_errors=True)
    output.mkdir(parents=True)
    tests = workdir / (kind + "_tests")
    shutil.rmtree(tests, ignore_errors=True)
    tests.mkdir()
    env = isolated_environment()
    junit = output / "junit.xml"
    record: Dict[str, Any] = {
        "schema": "hyba.unified.installed-test-evidence/v1",
        "label": label,
        "git_sha": git_sha(),
        "scope": "installed authority, atomic-import, promotion and tenant regressions",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "test_files": list(test_files),
        "input_artifacts": [{"file": path.name, "sha256": sha256(path)} for path in (artifacts or [])],
        "source_tests": {},
        "counts": {key: 0 for key in ("tests", "failures", "errors", "skipped")},
        "test_verdict": "failed_or_incomplete",
        "production_certification": "not_assessed",
        "limitations": [
            "Four named fixture/in-process suites, not the full repository suite.",
            "No independent tenant security audit, recovery, live-vendor or SLA qualification.",
        ],
    }
    try:
        for name in test_files:
            source = REPO / "tests" / name
            shutil.copy2(source, tests / name)
            record["source_tests"][name] = sha256(source)
        probe_command = [str(py), "-I", "-c", INSTALLED_UNIFIED_PROBE]
        record["probe_command"] = probe_command
        probe = subprocess.run(
            probe_command, cwd=workdir, env=env, capture_output=True, text=True,
            timeout=INSTALLED_TIMEOUT_SECONDS
        )
        (output / "import-probe.log").write_text(
            probe.stdout + probe.stderr, encoding="utf-8"
        )
        if probe.returncode:
            raise RuntimeError("installed import-origin probe failed")
        record["installed_origins"] = json.loads(probe.stdout.strip())
        command = [
            str(py),
            "-I",
            "-m",
            "pytest",
            "-q",
            "--noconftest",
            "--import-mode=importlib",
            "-o",
            "addopts=",
            "-p",
            "no:cacheprovider",
            "--rootdir",
            str(tests),
            "--junitxml",
            str(junit),
            str(tests),
        ]
        record["command"] = command
        with (output / "pytest.log").open("w", encoding="utf-8") as log:
            result = subprocess.run(
                command, cwd=workdir, env=env, stdout=log, stderr=subprocess.STDOUT,
                timeout=INSTALLED_TIMEOUT_SECONDS
            )
        record["pytest_exit_code"] = result.returncode
        record["counts"] = validated_test_counts(junit, test_files)
        if result.returncode != 0:
            raise RuntimeError(f"installed pytest exited {result.returncode}")
        record["test_verdict"] = "passed"
    except Exception as exc:
        record["error"] = f"{type(exc).__name__}: {exc}"
    record["finished_at"] = datetime.now(timezone.utc).isoformat()
    record["artifacts"] = {
        path.name: sha256(path) for path in output.iterdir() if path.is_file()
    }
    (output / "evidence.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if record["test_verdict"] != "passed":
        raise RuntimeError(
            f"installed {kind} verification failed under {label}; see {output}"
        )
    return record


def installed_unified_check(py: Path, workdir: Path, label: str,
                            artifacts: Optional[List[Path]] = None) -> Dict[str, Any]:
    return _installed_test_check(py, workdir, label, UNIFIED_TESTS, "unified", artifacts)


def installed_check(
    python: Path, wheels: List[Path], workdir: Path, label: str, version: str
) -> Dict[str, Any]:
    env_dir = workdir / "venv"
    sh([python, "-m", "venv", "--clear", env_dir])
    py = _py(env_dir)
    sh([py, "-m", "pip", "install", "-q", *[str(w) for w in wheels], "pytest"])
    unified_record = installed_unified_check(py, workdir, label, wheels)
    check = workdir / "installed_check.py"
    check.write_text(INSTALLED_CHECK, encoding="utf-8")
    out = sh([py, "-I", check, version, dist_name()], cwd=workdir, capture_output=True,
             env=isolated_environment(), timeout=INSTALLED_TIMEOUT_SECONDS)
    record = json.loads(out.stdout.strip().splitlines()[-1])
    record["release_tests"] = _installed_test_check(
        py, workdir, label, RELEASE_TESTS, "release", wheels
    )
    record["unified_tests"] = unified_record
    record["label"] = label
    shutil.rmtree(env_dir, ignore_errors=True)
    return record


def rebuild_from_sdist(tool_py: Path, sdist: Path, root: Path) -> Path:
    extract = root / "sdist"
    extract.mkdir()
    with tarfile.open(sdist, "r:*") as tf:
        tf.extractall(extract, filter="data")
    roots = [p for p in extract.iterdir() if p.is_dir()]
    if len(roots) != 1:
        raise RuntimeError(f"unexpected sdist roots: {roots}")
    out = root / "rebuilt"
    sh([tool_py, "-m", "build", "--wheel", "--outdir", out, roots[0]])
    wheels = sorted(out.glob("*.whl"))
    if len(wheels) != 1:
        raise RuntimeError(f"sdist rebuild produced {len(wheels)} wheels")
    return wheels[0]


def _qualify(args: argparse.Namespace, attempt: Dict[str, Any]) -> int:
    attempt["stage"] = "source-preflight"
    validate_source_inputs()
    version = toe_version()
    name = dist_name()
    with tempfile.TemporaryDirectory(prefix="toe-release-") as tmp:
        root = Path(tmp)
        attempt["stage"] = "build-tooling"
        tool = tooling_python(root)
        attempt["stage"] = "kellogg-build"
        kellogg_wheel = build_kellogg_wheel(tool, root)
        shutil.copy2(kellogg_wheel, DIST / kellogg_wheel.name)
        attempt["stage"] = "toe-build"
        sh([tool, "-m", "build", "--wheel", "--sdist", "--outdir", DIST, stage_toe(root)])
        stem = name.replace("-", "_")
        wheels = sorted(DIST.glob(f"{stem}-{version}-*.whl"))
        sdists = sorted(DIST.glob(f"{stem}-{version}.tar.gz"))
        if len(wheels) != 1 or len(sdists) != 1:
            raise RuntimeError(f"expected one wheel and one sdist: {wheels} {sdists}")
        wheel, sdist = wheels[0], sdists[0]
        attempt["stage"] = "archive-inspection"
        sh([tool, "-m", "twine", "check", wheel, sdist])
        manifest = inspect_wheel(wheel, version)
        scans = [scan(wheel), scan(sdist)]
        records = []
        interpreters = [Path(sys.executable)] + [Path(p) for p in args.python]
        for i, interp in enumerate(interpreters):
            attempt["stage"] = f"installed-wheel-{i}"
            work = root / f"check-{i}"
            work.mkdir()
            records.append(
                installed_check(
                    interp, [kellogg_wheel, wheel], work, f"wheel@{interp.name}", version
                )
            )
        attempt["stage"] = "sdist-rebuild"
        rebuilt = rebuild_from_sdist(tool, sdist, root)
        work = root / "check-sdist"
        work.mkdir()
        attempt["stage"] = "installed-sdist"
        sdist_record = installed_check(
            Path(sys.executable), [kellogg_wheel, rebuilt], work, "sdist-rebuilt-wheel", version
        )
        digests = {r["fixture_digest"] for r in records} | {sdist_record["fixture_digest"]}
        if len(digests) != 1:
            raise RuntimeError(f"deterministic fixture differs across installs: {digests}")
        attempt["stage"] = "verdict-composition"
        decisions = owner_decisions()
        blockers = []
        approved_name = decisions["distribution_name_approved"]
        approved_version = decisions["version_approved"]
        if not approved_name:
            blockers.append("distribution name not owner-approved (OWNER_DECISIONS.md §1)")
        elif approved_name != name:
            blockers.append(
                f"approved distribution name {approved_name!r} does not match artifact {name!r}"
            )
        if not approved_version:
            blockers.append("release version not owner-approved (OWNER_DECISIONS.md §2)")
        elif approved_version != version:
            blockers.append(
                f"approved release version {approved_version!r} does not match artifact {version!r}"
            )
        evidence = {
            "product": "TOE",
            "import_name": "toe",
            "distribution": name,
            "distribution_name_status": (
                "APPROVED" if decisions["distribution_name_approved"] == name else "PROVISIONAL"
            ),
            "version": version,
            "repository": REPOSITORY,
            "git_sha": git_sha(),
            "build_python": platform.python_version(),
            "platform": platform.platform(),
            "wheel": {"file": wheel.name, "sha256": sha256(wheel)},
            "sdist": {"file": sdist.name, "sha256": sha256(sdist)},
            "rebuilt_wheel_sha256": sha256(rebuilt),
            "kellogg_wheel": {"file": kellogg_wheel.name, "sha256": sha256(kellogg_wheel)},
            "twine_check": True,
            "wheel_boundary_verified": True,
            "secret_scan_passed": all(not s["findings"] for s in scans),
            "installed_checks": records,
            "sdist_installed_check": sdist_record,
            "pythons_verified": sorted({r["python"] for r in records}),
            "fixture_digest": next(iter(digests)),
            "wheel_manifest_file_count": manifest["file_count"],
            "owner_decisions": decisions,
            "publication_blockers": blockers
            + [
                "final publication requires the commit-bound toe-release workflow verdict",
                "final publication requires exact VOI certification",
                "final publication requires deploy sentry clean",
                "final publication requires the full repository suite",
                "final publication requires registry prerequisites and trusted publishers",
            ],
            "artifact_verified": True,
            "owner_identity_approved": not blockers,
            # A local artifact build can never self-award publication readiness.
            # The commit-bound toe-release workflow composes the final verdict
            # only after source, installed, mining-boundary and external gates.
            "publishable": False,
            "published": False,
        }
    (DIST / "artifact-verdict.json").write_text(
        json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                k: v
                for k, v in evidence.items()
                if k not in ("installed_checks", "sdist_installed_check")
            },
            indent=2,
            sort_keys=True,
        )
    )
    print(
        "VERIFIED (artefacts)"
        + ("" if not blockers else " — publication blocked: " + "; ".join(blockers))
    )
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--python", action="append", default=[], help="extra interpreter for the installed check"
    )
    args = ap.parse_args(argv)
    shutil.rmtree(DIST, ignore_errors=True)
    DIST.mkdir(parents=True)
    attempt: Dict[str, Any] = {
        "schema": "hyba.toe.qualification-attempt/v1",
        "git_sha": git_sha(), "python": platform.python_version(),
        "platform": platform.platform(), "stage": "initializing",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "verdict": "failed_or_incomplete", "artifact_verified": False,
        "production_certification": "not_assessed", "published": False,
    }
    try:
        result = _qualify(args, attempt)
        if result != 0 or not (DIST / "artifact-verdict.json").is_file():
            raise RuntimeError("qualification completed without a verified artifact verdict")
        verdict = json.loads((DIST / "artifact-verdict.json").read_text())
        if verdict.get("artifact_verified") is not True:
            raise RuntimeError("artifact verdict is not verified")
        attempt.update(verdict="passed", artifact_verified=True, stage="complete")
        return result
    except Exception as exc:
        attempt["error"] = f"{type(exc).__name__}: {exc}"
        (DIST / "qualification-failure.log").write_text(traceback.format_exc(), encoding="utf-8")
        raise
    finally:
        attempt["finished_at"] = datetime.now(timezone.utc).isoformat()
        attempt["evidence_sha256"] = {
            str(path.relative_to(DIST)): sha256(path)
            for path in sorted(DIST.rglob("*")) if path.is_file()
        }
        (DIST / "qualification-attempt.json").write_text(
            json.dumps(attempt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    raise SystemExit(main())
