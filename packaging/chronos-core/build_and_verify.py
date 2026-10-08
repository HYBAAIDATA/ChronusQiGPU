"""Build and verify the chronos-core 3.3.0 wheel (artefact-first, nothing published).

Stages only the ``chronus.v33`` Chronos maths subtree under the ``chronus``
namespace, builds wheel + sdist, inspects and secret-scans the archives,
installs the wheel into a fresh virtual environment *outside* the repository,
and imports the shipped modules from the installed copy.  Writes a
verification record with the artefact SHA-256 digests.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import venv
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
DIST = HERE / "dist"
VERSION = "3.3.0"
WHEEL_STEM = "chronos_core"
FORBIDDEN_TOP_LEVEL = {"toe", "Intelligence", "kellogg", "mining", "aethel",
                       "lucas", "turing_universal_quantum_computer", "millennium",
                       "euclid", "hyba_substrate", "resonance_intelligence",
                       "salamander", "al_haras", "chronos_one_igpu"}
SECRET_PATTERNS = (
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"ghp_[A-Za-z0-9]{30,}"),
    re.compile(rb"github_pat_[A-Za-z0-9_]{40,}"),
    re.compile(rb"pypi-AgEI[A-Za-z0-9_-]{20,}"),
    re.compile(rb"AKIA[0-9A-Z]{16}"),
)
ALLOWED_TOP_LEVEL = {"chronus"}
MODULES = (
    "chronus.v33.engine",
    "chronus.v33.manifold",
    "chronus.v33.hamiltonian",
    "chronus.v33.evolution_engine",
    "chronus.v33.capability_audit",
)
SMOKE = r"""
import json, sys
import chronus.v33
mods = %s
for name in mods:
    __import__(name)
assert all("site-packages" in (sys.modules[m].__file__ or "") for m in mods), "not the installed copy"
from importlib.resources import files
manifest = json.loads(files("chronus.v33").joinpath("CAPABILITY_MANIFEST.json").read_text())
print(json.dumps({"modules": len(mods), "capability_manifest": bool(manifest)}))
"""


def sh(cmd: list, **kw) -> subprocess.CompletedProcess:
    print("$", " ".join(str(c) for c in cmd), flush=True)
    return subprocess.run([str(c) for c in cmd], check=True, text=True, **kw)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def stage(root: Path) -> Path:
    src = root / "src"
    src.mkdir(parents=True)
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", "tests", "var")
    chronus = src / "chronus"
    chronus.mkdir()
    init = REPO / "chronus" / "__init__.py"
    if init.exists():
        shutil.copy2(init, chronus / "__init__.py")
    shutil.copytree(REPO / "chronus" / "v33", chronus / "v33", ignore=ignore)
    for name in ("pyproject.toml", "README.md"):
        shutil.copy2(HERE / name, src / name)
    shutil.copy2(REPO / "LICENSE", src / "LICENSE")
    return src


def inspect(wheel: Path) -> dict:
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        top = {name.split("/", 1)[0] for name in names if "/" in name}
        top = {t for t in top if not t.endswith(".dist-info")}
        secrets = [n for n in names if any(p.search(archive.read(n)) for p in SECRET_PATTERNS)]
    bad = [n for n in names if "/tests/" in n or "__pycache__" in n or n.endswith(".pyc")]
    forbidden = sorted(top & FORBIDDEN_TOP_LEVEL)
    unexpected = sorted(top - ALLOWED_TOP_LEVEL)
    missing = [m for m in MODULES
               if m.replace(".", "/") + ".py" not in names
               and m.replace(".", "/") + "/__init__.py" not in names]
    return {"files": len(names), "top_level": sorted(top), "forbidden_top_level": forbidden,
            "unexpected_top_level": unexpected, "secret_hits": secrets,
            "test_or_cache_files": bad[:20], "missing_modules": missing,
            "passed": not (forbidden or unexpected or secrets or bad or missing)}


def main() -> int:
    shutil.rmtree(DIST, ignore_errors=True)
    DIST.mkdir(parents=True)
    record: dict = {"product": "chronos-core", "version": VERSION}
    with tempfile.TemporaryDirectory(prefix="chronos-core-") as tmp:
        tmp_path = Path(tmp)
        src = stage(tmp_path)
        sh([sys.executable, "-m", "build", "--wheel", "--sdist", "--outdir", DIST, src],
           cwd=tmp_path)
        wheels = sorted(DIST.glob(f"{WHEEL_STEM}-{VERSION}-*.whl"))
        sdists = sorted(DIST.glob(f"{WHEEL_STEM}-{VERSION}.tar.gz"))
        if len(wheels) != 1 or len(sdists) != 1:
            raise RuntimeError(f"expected one wheel and one sdist: {wheels} {sdists}")
        wheel, sdist = wheels[0], sdists[0]
        sh([sys.executable, "-m", "twine", "check", str(wheel), str(sdist)])
        record["wheel"] = wheel.name
        record["wheel_sha256"] = sha256(wheel)
        record["sdist"] = sdist.name
        record["sdist_sha256"] = sha256(sdist)
        record["inspection"] = inspect(wheel)
        env_dir = tmp_path / "venv"
        venv.EnvBuilder(with_pip=True).create(env_dir)
        python = env_dir / ("Scripts" if sys.platform == "win32" else "bin") / "python"
        sh([python, "-m", "pip", "install", "-q", str(wheel)], cwd=tmp_path)
        smoke = SMOKE % (repr(MODULES),)
        completed = sh([python, "-I", "-c", smoke], cwd=tmp_path, capture_output=True)
        record["installed_smoke"] = json.loads(completed.stdout.strip().splitlines()[-1])
        record["installed_outside_repository"] = str(REPO) not in str(env_dir)
    record["passed"] = bool(
        record["inspection"]["passed"] and record["installed_smoke"]["capability_manifest"]
    )
    record["publishable"] = False
    record["published"] = False
    (DIST / "chronos-core-verification.json").write_text(
        json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0 if record["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
