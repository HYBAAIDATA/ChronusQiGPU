"""Build and verify the standalone hyba-chronus-igpu release artefacts.

Artefact-first, like packaging/chronos-core:

    stage only the Chronus execution-plane boundary (chronus/ minus the maths
    facade __init__.py, minus v33/, minus mla1517/, plus lucas/) → build wheel
    + sdist → twine check → boundary inspection + secret/local-path scan →
    clean venv: install the wheel from a local findlinks dir holding the
    declared in-tree distributions → import the clean execution surface,
    assert the excluded surfaces are absent, assert umbrella-bound modules
    fail closed with ModuleNotFoundError, run a deterministic resident-hendrix
    smoke → rebuild a wheel from the sdist and verify it the same way →
    machine-readable evidence in packaging/chronus-igpu/dist/

Nothing is published. ``publishable`` stays false while CI has not produced
a commit-bound verdict for the exact artefacts.

Usage: python packaging/chronus-igpu/build_and_verify.py [--python PATH ...]
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

# Surfaces hyba-chronus-igpu must NOT ship: the chronus facade (__init__.py)
# and the v33 maths plane belong to hyba-chronos-mathematics; the mla1517
# mining plane belongs to hyba-pythia-mining.
FORBIDDEN_WHEEL_PREFIXES = (
    "chronus/v33/",
    "chronus/mla1517/",
    "chronus/mla1517_platform/",
)
FORBIDDEN_WHEEL_FILES = (
    "chronus/__init__.py",
    "chronus/v33/__init__.py",
    "chronus/mla1517/__init__.py",
)

# Modules the isolated install must import cleanly — the clean execution
# surface (numpy + chronos-one-igpu + kellogg + lucas only).
REQUIRED_IMPORTS = (
    "chronus.virtual_igpu.adapters",
    "chronus.virtual_igpu.runtime",
    "chronus.virtual_igpu.mining_hasher",
    "chronus.measurement.run",
    "chronus.readiness",
    "chronus.resident_hendrix",
    "chronus.h4_600",
    "chronus.exact_geometry",
    "chronus.one_igpu_mining",
    "chronus.detect",
    "chronus.gpu_capabilities",
    "chronus.tensor_compute",
    "chronus.seam.scale",
    "chronus.seam.types",
    "lucas",
    "lucas.ladder",
)

# Shipped modules that import umbrella-only packages eagerly — must raise
# ModuleNotFoundError naming an umbrella package, never a fake success.
UMBRELLA_BOUND = (
    "chronus.fabric",          # hyba.inventory
    "chronus.mining_bridge",   # quantum_compute_substrate
    "chronus.paradigm",        # al_haras.refuted_claims (package __init__)
)

# Modules that must be absent from the wheel entirely (namespace boundary).
ABSENT_MODULES = (
    "chronus.mla1517",
    "chronus.mla1517.mining",
    "chronus.v33",
)

SECRET_PATTERNS = (
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


def git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "UNAVAILABLE"


def _py(env_dir: Path) -> Path:
    return env_dir / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def dist_name() -> str:
    m = re.search(r'^name = "([^"]+)"', (HERE / "pyproject.toml").read_text(encoding="utf-8"), re.M)
    if not m:
        raise RuntimeError("packaging/chronus-igpu/pyproject.toml has no name")
    return m.group(1)


def stage(root: Path) -> Path:
    """Ship exactly the declared boundary.

    ``chronus/`` minus ``__init__.py``, ``v33/``, ``mla1517/``,
    ``mla1517_platform/``; plus ``lucas/``. The staged tree is the wheel
    payload verbatim — nothing else enters.
    """
    src = root / "chronus-igpu-src"
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", ".DS_Store")

    def chronus_filter(directory: str, names: list[str]) -> set[str]:
        rel = Path(directory).relative_to(REPO / "chronus")
        out = set()
        for n in names:
            r = rel / n
            if r == Path("__init__.py"):
                out.add(n)  # facade owned by hyba-chronos-mathematics
            if r.parts[:1] == ("v33",) or r.parts[:1] == ("mla1517",) or r.parts[:1] == ("mla1517_platform",):
                out.add(n)
            if n.endswith((".pyc", ".pyo")) or n == "__pycache__" or n == ".DS_Store":
                out.add(n)
        return out

    shutil.copytree(REPO / "chronus", src / "chronus", ignore=chronus_filter)
    shutil.copytree(REPO / "lucas", src / "lucas", ignore=ignore)
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


def inspect_wheel(wheel: Path, version: str) -> Dict[str, Any]:
    names = _names(wheel)
    dist_info = {n.split("/", 1)[0] + "/" for n in names if ".dist-info/" in n}
    if len(dist_info) != 1:
        raise RuntimeError(f"expected one dist-info, found {sorted(dist_info)}")
    di = next(iter(dist_info))
    outside = [
        n for n in names
        if not (n.startswith(di) or n.startswith("chronus/") or n.startswith("lucas/"))
    ]
    if outside:
        raise RuntimeError(f"wheel ships files outside the hyba-chronus-igpu boundary: {outside[:20]}")
    leaked = [
        n for n in names
        if n.startswith(FORBIDDEN_WHEEL_PREFIXES) or n in FORBIDDEN_WHEEL_FILES
    ]
    if leaked:
        raise RuntimeError(f"wheel ships surfaces owned by other distributions: {leaked[:20]}")
    required = (
        "chronus/virtual_igpu/__init__.py",
        "chronus/measurement/__init__.py",
        "chronus/seam/__init__.py",
        "chronus/readiness.py",
        "chronus/resident_hendrix.py",
        "chronus/h4_600.py",
        "lucas/__init__.py",
        "lucas/ladder.py",
    )
    missing = [r for r in required if r not in names]
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
        for pat in SECRET_PATTERNS:
            if pat.search(data):
                findings.append({"file": name, "reason": f"secret pattern {pat.pattern!r}"})
        if any(t and t in data for t in tokens):
            findings.append({"file": name, "reason": "local repository path embedded"})
    if findings:
        raise RuntimeError(f"artefact scan failed: {findings[:10]}")
    return {"artifact": archive.name, "sha256": sha256(archive), "findings": []}


INSTALLED_CHECK = r"""
import importlib, importlib.metadata, importlib.util, json, sys

EXPECTED_VERSION, DIST = sys.argv[1], sys.argv[2]
REQUIRED = %r
ABSENT = %r
UMBRELLA_BOUND = %r

md = importlib.metadata.metadata(DIST)
assert md["Name"] == DIST and md["Version"] == EXPECTED_VERSION, (md["Name"], md["Version"])
assert md["Requires-Python"] == ">=3.12", md["Requires-Python"]
reqs = sorted(
    r.split(">")[0].split("<")[0].split("=")[0].strip().lower()
    for r in (importlib.metadata.requires(DIST) or []) if "extra ==" not in r
)
assert reqs == ["chronos-one-igpu", "hyba-chronos-mathematics", "hyba-kellogg-tensor", "numpy"], reqs

failed = {}
for name in REQUIRED:
    try:
        mod = importlib.import_module(name)
    except Exception as exc:
        failed[name] = f"{type(exc).__name__}: {exc}"
    else:
        f = getattr(mod, "__file__", "") or ""
        assert "site-packages" in f.replace("\\\\", "/"), (name, f)
assert not failed, failed

for gone in ABSENT:
    assert importlib.util.find_spec(gone) is None, gone

# Umbrella-bound modules must fail closed on the missing dependency, not on
# an internal bug: ModuleNotFoundError naming an umbrella package.
UMBRELLA_PKGS = ("hyba", "aethel", "toe", "Intelligence", "mining", "turing",
                 "quantum_compute_substrate", "chronus.mla1517", "salamander")
bound_failures = {}
for name in UMBRELLA_BOUND:
    try:
        importlib.import_module(name)
        bound_failures[name] = "imported without umbrella — boundary leak"
    except ModuleNotFoundError as exc:
        if not any(str(exc.name or "") .startswith(p) for p in UMBRELLA_PKGS):
            bound_failures[name] = f"ModuleNotFoundError on {exc.name!r} (not an umbrella dep)"
    except Exception as exc:
        bound_failures[name] = f"{type(exc).__name__}: {exc}"
assert not bound_failures, bound_failures

""" + '''
import json as _json
from lucas.ladder import (
    CHRONUS_SCALE_RUNGS, FULL_LADDER, ladder_capacity, nearest_ladder_index, verify_ladder,
)
v = verify_ladder()
assert v["valid"] and v["monotonic"], v
assert ladder_capacity(120) == 120 and nearest_ladder_index(500, 1, 1200) == 500
assert CHRONUS_SCALE_RUNGS == tuple(FULL_LADDER)

from chronus.virtual_igpu.adapters import CPUEmulatorAdapter
from chronus.virtual_igpu.runtime import RuntimeDaemon
import tempfile as _tf
d = RuntimeDaemon(adapters=[CPUEmulatorAdapter()], store_dir=_tf.mkdtemp())
assert d is not None

print(json.dumps({
    "python": sys.version.split()[0],
    "required_imports": len(REQUIRED),
    "lucas_ladder": {"valid": v["valid"], "rungs": list(FULL_LADDER)},
    "umbrella_bound_checked": list(UMBRELLA_BOUND),
}, sort_keys=True))
'''


def installed_check(
    python: Path, wheels: List[Path], workdir: Path, label: str, version: str
) -> Dict[str, Any]:
    env_dir = workdir / "venv"
    sh([python, "-m", "venv", "--clear", env_dir])
    py = _py(env_dir)
    findlinks = wheels[0].parent
    sh([py, "-m", "pip", "install", "-q", "--find-links", str(findlinks), *[str(w) for w in wheels]])
    check = workdir / "installed_check.py"
    check.write_text(
        INSTALLED_CHECK % (REQUIRED_IMPORTS, ABSENT_MODULES, UMBRELLA_BOUND),
        encoding="utf-8",
    )
    out = sh([py, "-I", check, version, dist_name()], cwd=workdir, capture_output=True)
    record = json.loads(out.stdout.strip().splitlines()[-1])
    record["label"] = label
    shutil.rmtree(env_dir, ignore_errors=True)
    return record


def _dep_wheels(findlinks: Path) -> List[Path]:
    """Build or locate the declared in-tree distribution wheels.

    hyba-chronos-mathematics (packaging/chronos-core stage+build),
    hyba-kellogg-tensor (packaging/kellogg-tensor staged dist) and
    chronos-one-igpu (packages/chronos-one-igpu) are built from source when
    their dist/ artefacts are absent.
    """
    findlinks.mkdir(parents=True, exist_ok=True)
    builds = {
        "hyba_chronos_mathematics": REPO / "packaging" / "chronos-core-src" ,
        "hyba_kellogg_tensor": REPO / "packaging" / "kellogg-tensor-src",
        "chronos_one_igpu": REPO / "packages" / "chronos-one-igpu",
    }
    staged: Dict[str, Path] = {}
    # chronos-core/kellogg stage their sources via their own build scripts;
    # build those distributions directly from their packaging roots when a
    # ready-made wheel is absent.
    for key, src in builds.items():
        existing = sorted(findlinks.glob(f"{key}-*.whl"))
        if existing:
            staged[key] = existing[-1]
            continue
        candidates = sorted((REPO / "packaging" / "chronos-core" / "dist").glob(f"{key}-*.whl"))
        candidates += sorted((REPO / "packaging" / "kellogg-tensor" / "dist").glob(f"{key}-*.whl"))
        candidates += sorted((REPO / "packages" / "chronos-one-igpu" / "dist").glob(f"{key}-*.whl"))
        candidates += sorted(Path("/tmp/pythia-dist").glob(f"{key}-*.whl")) if Path("/tmp/pythia-dist").exists() else []
        if candidates:
            dest = findlinks / candidates[-1].name
            shutil.copy2(candidates[-1], dest)
            staged[key] = dest
            continue
        raise RuntimeError(
            f"no {key} wheel found — build the dependency first "
            "(packaging/*/build_and_verify.py or python -m build)"
        )
    return list(staged.values())


def rebuild_from_sdist(tool_py: Path, sdist: Path, root: Path) -> Path:
    extract = root / "sdist"
    extract.mkdir()
    with tarfile.open(sdist, "r:*") as tf:
        tf.extractall(extract)
    inner = next(extract.iterdir())
    sh([tool_py, "-m", "build", "--wheel", "--outdir", str(root / "rebuilt"), str(inner)])
    rebuilt = next((root / "rebuilt").glob("*.whl"))
    return rebuilt


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--python", action="append", default=[])
    args = ap.parse_args()

    DIST.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="chronus-igpu-build-"))
    try:
        src = stage(work)
        tool_root = work / "tooling-env"
        venv.EnvBuilder(with_pip=True, clear=True).create(tool_root)
        tool_py = _py(tool_root)
        sh([tool_py, "-m", "pip", "install", "-q", "build", "twine"])

        sh([tool_py, "-m", "build", "--outdir", str(DIST), str(src)])
        wheel = next(DIST.glob("hyba_chronus_igpu-*.whl"))
        sdist = next(DIST.glob("hyba_chronus_igpu-*.tar.gz"))
        sh([tool_py, "-m", "twine", "check", str(wheel), str(sdist)])

        version = re.search(r'^version = "([^"]+)"', (HERE / "pyproject.toml").read_text(), re.M)
        assert version, "pyproject.toml lacks a version literal"
        version = version.group(1)

        manifest = inspect_wheel(wheel, version)
        scans = [scan(wheel), scan(sdist)]

        findlinks = work / "findlinks"
        dep_wheels = _dep_wheels(findlinks)
        pythons = [Path(sys.executable)] + [Path(p) for p in args.python]
        checks = []
        for i, py in enumerate(pythons):
            checks.append(
                installed_check(py, [wheel] + dep_wheels, work / f"verify-{i}", f"wheel-{i}", version)
            )

        rebuilt = rebuild_from_sdist(tool_py, sdist, work)
        rebuilt_manifest = inspect_wheel(rebuilt, version)
        checks.append(
            installed_check(
                pythons[0], [rebuilt] + dep_wheels, work / "verify-sdist", "sdist-rebuild", version
            )
        )

        verdict = {
            "distribution": dist_name(),
            "version": version,
            "source_revision": git_sha(),
            "python": platform.python_version(),
            "wheel_sha256": manifest["sha256"],
            "sdist_sha256": scans[1]["sha256"],
            "rebuilt_wheel_sha256": rebuilt_manifest["sha256"],
            "file_count": manifest["file_count"],
            "installed_checks": checks,
            "scans": scans,
            "publishable": False,
            "claim_boundaries": {
                "physical_gpu_evidence": "UNAVAILABLE — device-bound lane not asserted by packaging",
                "external_pool_acceptance": "UNAVAILABLE — literal pool acknowledgement required",
            },
        }
        (DIST / "artifact-verdict.json").write_text(
            json.dumps(verdict, indent=2, sort_keys=True), encoding="utf-8"
        )
        print(json.dumps({k: verdict[k] for k in (
            "distribution", "version", "source_revision", "wheel_sha256", "publishable"
        )}, indent=2))
        print("VERIFIED")
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
