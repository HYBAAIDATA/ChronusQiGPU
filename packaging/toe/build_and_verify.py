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
import venv
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
DIST = HERE / "dist"
REPOSITORY = "QuantumPhiRedux/PhiMiner"
KELLOGG_VERSION = "1.0.0"

# Monorepo integration surfaces TOE does not ship (mining-facing coordinator,
# the five nonce-authority intelligences, and an alias of aethel's code).
EXCLUDED = ("system.py", "manifold_bridge.py", "hardened_unified_substrate.py", "intelligences")
RELEASE_TESTS = (
    "test_toe_machine.py",
    "test_toe_geometry.py",
    "test_toe_runtime_solve.py",
    "test_toe_learning_persistence.py",
)
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
    return subprocess.run([str(c) for c in cmd], check=True, text=True, **kw)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def toe_version() -> str:
    m = re.search(r'^__version__ = "([^"]+)"', (REPO / "toe" / "__init__.py").read_text(encoding="utf-8"), re.M)
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
        return subprocess.check_output(["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True).strip()
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
    spec = importlib.util.spec_from_file_location("kellogg_build", REPO / "packaging" / "kellogg-tensor" / "build_and_verify.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    staged = mod.stage(root / "kellogg-stage")
    out = root / "kellogg-dist"
    sh([py, "-m", "build", "--wheel", "--outdir", out, staged])
    wheels = sorted(out.glob(f"kellogg_tensor-{KELLOGG_VERSION}-*.whl"))
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
    leaked = [n for n in names if any(n == f"toe/{x}" or n.startswith(f"toe/{x}/") for x in EXCLUDED)]
    if leaked:
        raise RuntimeError(f"wheel ships monorepo-only surfaces: {leaked}")
    required = {
        "toe/__init__.py", "toe/py.typed", "toe/machine.py", "toe/problem.py",
        "toe/CAPABILITY_MANIFEST.json", "toe/CLAIM_REGISTER.json", "toe/default_propagators.json",
        "toe/adapters/__init__.py", "toe/unified/__init__.py",
    }
    missing = sorted(required - set(names))
    if missing:
        raise RuntimeError(f"wheel missing required files: {missing}")
    if not [n for n in names if n.startswith(di) and n.upper().endswith("LICENSE")]:
        raise RuntimeError("wheel is missing the licence")
    bad = [n for n in names if any(p in "/" + n for p in _BAD_NAME_PARTS)]
    if bad:
        raise RuntimeError(f"wheel contains forbidden paths: {bad[:20]}")
    manifest = {"wheel": wheel.name, "version": version, "sha256": sha256(wheel), "files": sorted(names), "file_count": len(names)}
    (DIST / "wheel-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
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
assert sorted(r.split(">")[0].split("<")[0].strip().lower() for r in reqs) == ["kellogg-tensor", "numpy"], reqs
urls = md.get_all("Project-URL") or []
assert any("QuantumPhiRedux/PhiMiner" in u for u in urls) and not any("QuantumPhi2" in u for u in urls), urls

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


def installed_check(python: Path, wheels: List[Path], workdir: Path, label: str, version: str) -> Dict[str, Any]:
    env_dir = workdir / "venv"
    sh([python, "-m", "venv", "--clear", env_dir])
    py = _py(env_dir)
    sh([py, "-m", "pip", "install", "-q", *[str(w) for w in wheels], "pytest"])
    check = workdir / "installed_check.py"
    check.write_text(INSTALLED_CHECK, encoding="utf-8")
    out = sh([py, "-I", check, version, dist_name()], cwd=workdir, capture_output=True)
    record = json.loads(out.stdout.strip().splitlines()[-1])
    tests = workdir / "release_tests"
    tests.mkdir()
    for name in RELEASE_TESTS:
        shutil.copy2(REPO / "tests" / name, tests / name)
    res = subprocess.run(
        [str(py), "-m", "pytest", "-q", "-p", "no:cacheprovider", "--rootdir", str(tests), str(tests)],
        cwd=workdir, text=True, capture_output=True, env=_NO_CACHE,
    )
    record["release_tests"] = {"returncode": res.returncode, "summary": res.stdout.strip().splitlines()[-1] if res.stdout else res.stderr[-400:]}
    if res.returncode != 0:
        raise RuntimeError(f"release tests failed under {label}: {res.stdout[-2000:]}")
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


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--python", action="append", default=[], help="extra interpreter for the installed check")
    args = ap.parse_args(argv)
    version = toe_version()
    name = dist_name()
    shutil.rmtree(DIST, ignore_errors=True)
    DIST.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix="toe-release-") as tmp:
        root = Path(tmp)
        tool = tooling_python(root)
        kellogg_wheel = build_kellogg_wheel(tool, root)
        shutil.copy2(kellogg_wheel, DIST / kellogg_wheel.name)
        sh([tool, "-m", "build", "--wheel", "--sdist", "--outdir", DIST, stage_toe(root)])
        stem = name.replace("-", "_")
        wheels = sorted(DIST.glob(f"{stem}-{version}-*.whl"))
        sdists = sorted(DIST.glob(f"{stem}-{version}.tar.gz"))
        if len(wheels) != 1 or len(sdists) != 1:
            raise RuntimeError(f"expected one wheel and one sdist: {wheels} {sdists}")
        wheel, sdist = wheels[0], sdists[0]
        sh([tool, "-m", "twine", "check", wheel, sdist])
        manifest = inspect_wheel(wheel, version)
        scans = [scan(wheel), scan(sdist)]
        records = []
        interpreters = [Path(sys.executable)] + [Path(p) for p in args.python]
        for i, interp in enumerate(interpreters):
            work = root / f"check-{i}"
            work.mkdir()
            records.append(installed_check(interp, [kellogg_wheel, wheel], work, f"wheel@{interp.name}", version))
        rebuilt = rebuild_from_sdist(tool, sdist, root)
        work = root / "check-sdist"
        work.mkdir()
        sdist_record = installed_check(Path(sys.executable), [kellogg_wheel, rebuilt], work, "sdist-rebuilt-wheel", version)
        digests = {r["fixture_digest"] for r in records} | {sdist_record["fixture_digest"]}
        if len(digests) != 1:
            raise RuntimeError(f"deterministic fixture differs across installs: {digests}")
        decisions = owner_decisions()
        blockers = []
        if not decisions["distribution_name_approved"]:
            blockers.append("distribution name not owner-approved (OWNER_DECISIONS.md §1)")
        if not decisions["version_approved"]:
            blockers.append("release version not owner-approved (OWNER_DECISIONS.md §2)")
        evidence = {
            "product": "TOE",
            "import_name": "toe",
            "distribution": name,
            "distribution_name_status": "APPROVED" if decisions["distribution_name_approved"] == name else "PROVISIONAL",
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
            "publication_blockers": blockers,
            "publishable": not blockers,
            "published": False,
        }
    (DIST / "artifact-verdict.json").write_text(json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({k: v for k, v in evidence.items() if k not in ("installed_checks", "sdist_installed_check")}, indent=2, sort_keys=True))
    print("VERIFIED (artefacts)" + ("" if not blockers else " — publication blocked: " + "; ".join(blockers)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
