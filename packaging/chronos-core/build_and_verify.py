"""Build and verify the standalone chronos-core release artefacts.

Artefact-first, like TOE/KELLOGG's scripts:

    stage only the v33 Chronos maths boundary → build wheel + sdist
    → twine check → inspect the wheel boundary + secret/local-path scan
    → clean venv: install the wheel (no source tree on the path) → import
      every shipped module, assert the monorepo surfaces are absent, run the
      capability-manifest audit and a deterministic seeded render, then the
      v33 release tests against the installed wheel
    → rebuild a wheel from the sdist and verify it the same way
    → machine-readable evidence in packaging/chronos-core/dist/

Nothing is published. ``publishable`` stays false while CI has not produced
a commit-bound verdict for the exact artefacts.

Usage: python packaging/chronos-core/build_and_verify.py [--python PATH ...]
       (extra --python interpreters re-run the installed check on the
       same artefacts for cross-version evidence)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import venv
import zipfile
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
DIST = HERE / "dist"
REPOSITORY = "QuantumPhiRedux/PhiMiner"

# Monorepo surfaces chronos-core must NOT ship (the product/runtime plane —
# device detect, OpenCL host, seam, mla1517, virtual iGPU — stays in the
# monorepo distribution pythia-mla1517 / future chronus-igpu package).
BOUNDARY_PREFIX = "chronus/v33/"
BOUNDARY_FILE = "chronus/__init__.py"
ABSENT_MODULES = (
    "chronus.engine",
    "chronus.device",
    "chronus.detect",
    "chronus.fabric",
    "chronus.delivery",
    "chronus.telemetry",
    "chronus.opencl_host",
    "chronus.seam",
    "chronus.mla1517",
    "chronus.virtual_igpu",
    "chronus.m5_ultra",
    "chronus.consortium_push",
    "chronos",
)
REQUIRED_FILES = (
    "chronus/__init__.py",
    "chronus/v33/__init__.py",
    "chronus/v33/CAPABILITY_MANIFEST.json",
    "chronus/v33/engine.py",
    "chronus/v33/manifold.py",
    "chronus/v33/hamiltonian.py",
    "chronus/v33/evolution_engine.py",
    "chronus/v33/reconstruction.py",
    "chronus/v33/qsdl_compiler.py",
    "chronus/v33/memory/__init__.py",
    "chronus/v33/academic/__init__.py",
)
# v33 suite minus monorepo-coupled checks:
#   test_research_reconciliation -> imports al_haras (monorepo governance plane)
#   test_research_registry       -> asserts repo-relative test-node paths exist
#   test_qx_bridge               -> imports chronus.production (product plane)
RELEASE_TESTS = (
    "test_chronus_v33/test_academic.py",
    "test_chronus_v33/test_academic_integration.py",
    "test_chronus_v33/test_gap_close.py",
    "test_chronus_v33/test_memory.py",
    "test_chronus_v33/test_qx.py",
    "test_chronos_v33_real_workloads.py",
    "test_chronos_v33_render_elevation.py",
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


def v33_version() -> str:
    m = re.search(
        r'^__version__ = "([^"]+)"',
        (REPO / "chronus" / "v33" / "__init__.py").read_text(encoding="utf-8"),
        re.M,
    )
    if not m:
        raise RuntimeError("chronus/v33/__init__.py has no __version__ literal")
    declared = re.search(
        r'^version = "([^"]+)"', (HERE / "pyproject.toml").read_text(encoding="utf-8"), re.M
    )
    if not declared or declared.group(1) != m.group(1):
        raise RuntimeError(
            f"pyproject version {declared and declared.group(1)!r} != v33 __version__ {m.group(1)!r}"
        )
    return m.group(1)


def dist_name() -> str:
    m = re.search(r'^name = "([^"]+)"', (HERE / "pyproject.toml").read_text(encoding="utf-8"), re.M)
    if not m:
        raise RuntimeError("packaging/chronos-core/pyproject.toml has no name")
    return m.group(1)


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


def stage(root: Path) -> Path:
    """Ship exactly the declared boundary: chronus/__init__.py + chronus/v33/**."""
    src = root / "chronos-core-src"
    chronus = src / "chronus"
    chronus.mkdir(parents=True)
    shutil.copy2(REPO / "chronus" / "__init__.py", chronus / "__init__.py")
    shutil.copytree(
        REPO / "chronus" / "v33",
        chronus / "v33",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )
    for name in ("pyproject.toml", "README.md"):
        shutil.copy2(HERE / name, src / name)
    shutil.copy2(REPO / "LICENSE", src / "LICENSE")
    return src


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


def _in_boundary(name: str) -> bool:
    return name == BOUNDARY_FILE or name.startswith(BOUNDARY_PREFIX)


def inspect_wheel(wheel: Path, version: str) -> Dict[str, Any]:
    names = _names(wheel)
    dist_info = {n.split("/", 1)[0] + "/" for n in names if ".dist-info/" in n}
    if len(dist_info) != 1:
        raise RuntimeError(f"expected one dist-info, found {sorted(dist_info)}")
    di = next(iter(dist_info))
    outside = [
        n for n in names
        if not (n.startswith(di) or (n.startswith("chronus/") and _in_boundary(n)))
    ]
    if outside:
        raise RuntimeError(f"wheel ships files outside the chronos-core boundary: {outside[:20]}")
    leaked = [
        n for n in names
        if n.startswith("chronus/") and not _in_boundary(n)
    ]
    if leaked:
        raise RuntimeError(f"wheel ships monorepo-only Chronus surfaces: {leaked[:20]}")
    missing = sorted(set(REQUIRED_FILES) - set(names))
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
ABSENT = %r
FORBIDDEN = {"aethel", "kellogg", "toe", "euclid", "Intelligence", "mining", "lucas",
             "millennium", "turing_core", "turing_universal_quantum_computer", "al_haras",
             "tensor", "mtheory", "resonance_intelligence", "asi", "phi_rotation",
             "thermo", "salamander", "chronos", "pythagoras", "omega"}

import chronus, chronus.v33
assert "site-packages" in chronus.__file__.replace("\\", "/"), chronus.__file__
assert "site-packages" in chronus.v33.__file__.replace("\\", "/"), chronus.v33.__file__
assert chronus.v33.__version__ == EXPECTED_VERSION, chronus.v33.__version__
md = importlib.metadata.metadata(DIST)
assert md["Name"] == DIST and md["Version"] == EXPECTED_VERSION, (md["Name"], md["Version"])
assert md["Requires-Python"] == ">=3.12", md["Requires-Python"]
reqs = [r for r in (importlib.metadata.requires(DIST) or []) if "extra ==" not in r]
assert sorted(r.split(">")[0].split("<")[0].split("=")[0].strip().lower() for r in reqs) == ["numpy"], reqs
urls = md.get_all("Project-URL") or []
assert any("QuantumPhiRedux/PhiMiner" in u for u in urls), urls

mods = sorted(m.name for m in pkgutil.walk_packages(chronus.v33.__path__, "chronus.v33."))
failed = {}
for name in mods:
    try:
        importlib.import_module(name)
    except Exception as exc:
        failed[name] = f"{type(exc).__name__}: {exc}"
assert not failed, failed
for gone in ABSENT:
    assert importlib.util.find_spec(gone) is None, gone

# Packaging-contract step 4: the capability manifest must match the wheel.
from chronus.v33.capability_audit import audit_capability_surface
report = audit_capability_surface()
assert report.ok, report.missing

# Deterministic seeded render — real pipeline, recorded as a fixture digest so
# cross-interpreter evidence can prove bit-identical maths.
import numpy as np
from chronus.v33.engine import ChronosEngine
scene = (
    "scene smoke {\n"
    "  manifold M32\n"
    "  object sphere {\n"
    "    geometry sphere(radius=1.0, center=(0,0,0))\n"
    "    material glass { dielectric = 1.5\n"
    "      absorption = 0.001\n"
    "      quantum { resonance = [0.5] } }\n"
    "  }\n"
    "  light sun { type = directional\n"
    "    position = (1,1,1)\n"
    "    intensity = 1.0\n"
    "    driving = zero() }\n"
    "  camera { resolution = (320, 180)\n"
    "    fov = 60.0\n"
    "    position = (0, 0, 5)\n"
    "    readout = { observables = [intensity, depth, normal] } }\n"
    "  quality { layers = 2\n"
    "    evolution_steps = 20\n"
    "    learning_rate = 0.08\n"
    "    damping = 0.01\n"
    "    seed = 0 }\n"
    "}\n"
)
out = ChronosEngine().render(scene)
assert out.frame_shape == (180, 320, 3), out.frame_shape
assert np.isfinite(out.energy) and out.rendered_pixels_hit <= out.total_pixels
fixture = {
    "energy": out.energy,
    "frame_shape": list(out.frame_shape),
    "pixels_hit": out.rendered_pixels_hit,
    "distribution_sha256": hashlib.sha256(np.ascontiguousarray(out.distribution).tobytes()).hexdigest(),
}
digest = hashlib.sha256(json.dumps(fixture, sort_keys=True).encode()).hexdigest()
leaked = sorted(n for n in FORBIDDEN if n in sys.modules)
assert not leaked, leaked
print(json.dumps({
    "python": sys.version.split()[0],
    "chronus_file": chronus.__file__,
    "v33_file": chronus.v33.__file__,
    "module_count": len(mods),
    "modules": mods,
    "capability_audit": {"modules": report.modules, "classes": report.classes,
                         "functions": report.functions, "ok": report.ok},
    "render": {"frame_shape": list(out.frame_shape), "energy": out.energy,
               "pixels_hit": out.rendered_pixels_hit},
    "fixture_digest": digest,
    "siblings_loaded": leaked,
}, sort_keys=True))
"""


def installed_check(
    python: Path, wheels: List[Path], workdir: Path, label: str, version: str
) -> Dict[str, Any]:
    env_dir = workdir / "venv"
    sh([python, "-m", "venv", "--clear", env_dir])
    py = _py(env_dir)
    sh([py, "-m", "pip", "install", "-q", *[str(w) for w in wheels], "pytest"])
    check = workdir / "installed_check.py"
    check.write_text(INSTALLED_CHECK % (ABSENT_MODULES,), encoding="utf-8")
    out = sh([py, "-I", check, version, dist_name()], cwd=workdir, capture_output=True)
    record = json.loads(out.stdout.strip().splitlines()[-1])
    tests = workdir / "release_tests"
    for rel in RELEASE_TESTS:
        dest = tests / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / "tests" / rel, dest)
    (tests / "test_chronus_v33" / "__init__.py").write_text("", encoding="utf-8")
    shutil.copy2(
        REPO / "tests" / "test_chronus_v33" / "conftest.py",
        tests / "test_chronus_v33" / "conftest.py",
    )
    res = subprocess.run(
        [
            str(py), "-m", "pytest", "-q", "-p", "no:cacheprovider",
            "--rootdir", str(tests), str(tests),
        ],
        cwd=workdir,
        text=True,
        capture_output=True,
        env=_NO_CACHE,
    )
    record["release_tests"] = {
        "returncode": res.returncode,
        "summary": res.stdout.strip().splitlines()[-1] if res.stdout else res.stderr[-400:],
    }
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
    ap.add_argument(
        "--python", action="append", default=[], help="extra interpreter for the installed check"
    )
    args = ap.parse_args(argv)
    version = v33_version()
    name = dist_name()
    shutil.rmtree(DIST, ignore_errors=True)
    DIST.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix="chronos-core-release-") as tmp:
        root = Path(tmp)
        tool = tooling_python(root)
        sh([tool, "-m", "build", "--wheel", "--sdist", "--outdir", DIST, stage(root)])
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
            records.append(installed_check(interp, [wheel], work, f"wheel@{interp.name}", version))
        rebuilt = rebuild_from_sdist(tool, sdist, root)
        work = root / "check-sdist"
        work.mkdir()
        sdist_record = installed_check(
            Path(sys.executable), [rebuilt], work, "sdist-rebuilt-wheel", version
        )
        digests = {r["fixture_digest"] for r in records} | {sdist_record["fixture_digest"]}
        if len(digests) != 1:
            raise RuntimeError(f"deterministic fixture differs across installs: {digests}")
        evidence = {
            "product": "chronos-core",
            "import_name": "chronus.v33",
            "distribution": name,
            "version": version,
            "repository": REPOSITORY,
            "git_sha": git_sha(),
            "build_python": platform.python_version(),
            "platform": platform.platform(),
            "wheel": {"file": wheel.name, "sha256": sha256(wheel)},
            "sdist": {"file": sdist.name, "sha256": sha256(sdist)},
            "rebuilt_wheel_sha256": sha256(rebuilt),
            "twine_check": True,
            "wheel_boundary_verified": True,
            "secret_scan_passed": all(not s["findings"] for s in scans),
            "installed_checks": records,
            "sdist_installed_check": sdist_record,
            "pythons_verified": sorted({r["python"] for r in records}),
            "fixture_digest": next(iter(digests)),
            "wheel_manifest_file_count": manifest["file_count"],
            "release_tests_excluded": [
                "test_chronus_v33/test_research_reconciliation.py (requires al_haras governance plane)",
                "test_chronus_v33/test_research_registry.py (asserts source-checkout test-node paths)",
                "test_chronus_v33/test_qx_bridge.py (requires chronus.production product plane)",
            ],
            "publication_blockers": [
                "final publication requires the commit-bound CI wheel-build verdict",
                "final publication requires owner sign-off on the distribution name and version",
            ],
            "publishable": False,
            "published": False,
        }
        (DIST / "chronos-core-verification.json").write_text(
            json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8"
        )
        print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
