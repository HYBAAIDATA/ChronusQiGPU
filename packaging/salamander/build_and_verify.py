"""Build and verify the hyba-salamander 1.0.0 wheel (artefact-first, nothing published).

Stages only the product (``salamander`` plus the bundled ``al_haras`` guardian
substrate, without caches or runtime state), builds the wheel in an isolated
build environment, inspects and secret-scans it, installs it into a fresh
virtual environment *outside* the repository with full dependency resolution,
imports every shipped module in an isolated interpreter, and proves the
fail-closed actuation boundary from the installed copy.  Writes a
verification record with the wheel's SHA-256.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import venv
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
DIST = HERE / "dist"
VERSION = "1.0.0"
WHEEL_STEM = "hyba_salamander"
PACKAGES = ("salamander", "al_haras")
FORBIDDEN_TOP_LEVEL = {"toe", "Intelligence", "kellogg", "mining", "chronus", "aethel",
                       "lucas", "turing_universal_quantum_computer", "millennium",
                       "euclid", "hyba_substrate", "resonance_intelligence"}
SECRET_PATTERNS = (
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"ghp_[A-Za-z0-9]{30,}"),
    re.compile(rb"github_pat_[A-Za-z0-9_]{40,}"),
    re.compile(rb"pypi-AgEI[A-Za-z0-9_-]{20,}"),
    re.compile(rb"AKIA[0-9A-Z]{16}"),
)
MODULES = (
    "salamander.control_plane",
    "salamander.authority",
    "salamander.models",
    "salamander.outcome_evidence",
    "salamander.runtime",
    "salamander.discovery_optimisation",
    "al_haras.guardian",
    "al_haras.models",
)
SMOKE = r"""
import json, sys
import salamander
mods = %s
for name in mods:
    __import__(name)
assert all("site-packages" in (sys.modules[m].__file__ or "") for m in mods), "not the installed copy"
assert salamander.__version__ == "%s", salamander.__version__
from salamander import ActionRegistry, EvidenceLedger
from salamander.control_plane import FailClosed
ledger = EvidenceLedger()
digest = ledger.append("boot", {"ok": True}, at_ns=1)
assert ledger.verify() and ledger.head == digest
registry = ActionRegistry()
closed = False
try:
    registry.execute(None)
except FailClosed:
    closed = True
assert closed, "unauthorised actuation was not refused"
# discovery_optimisation must import cleanly without toe.intelligences, and
# must refuse fail-closed rather than skip the forbidden-domain check.
from salamander.discovery_optimisation import DiscoveryOptimisationCandidate, DiscoveryRefused
refused = False
try:
    DiscoveryOptimisationCandidate(
        source_kind="emergence", discovery_id="d1", discovery_passed=True,
        baseline_measurements={"latency": 1.0}, candidate_measurements={"latency": 0.5},
        sample_count=4, evidence_ref="ev", temporal_lineage="lin",
    )
except DiscoveryRefused:
    refused = True
print(json.dumps({"modules": len(mods), "ledger_verified": True, "fail_closed": closed,
                  "authority_boundary_refused_without_toe": refused}))
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
    for package in PACKAGES:
        shutil.copytree(REPO / package, src / package, ignore=ignore)
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
    missing = [m for m in MODULES
               if m.replace(".", "/") + ".py" not in names
               and m.replace(".", "/") + "/__init__.py" not in names]
    return {"files": len(names), "top_level": sorted(top), "forbidden_top_level": forbidden,
            "secret_hits": secrets, "test_or_cache_files": bad[:20], "missing_modules": missing,
            "passed": not (forbidden or secrets or bad or missing)}


def main() -> int:
    DIST.mkdir(exist_ok=True)
    for stale in DIST.glob(f"{WHEEL_STEM}-*.whl"):
        stale.unlink()
    record: dict = {"product": "hyba-salamander", "version": VERSION}
    with tempfile.TemporaryDirectory(prefix="salamander-") as tmp:
        tmp_path = Path(tmp)
        src = stage(tmp_path)
        # Build isolation fetches the declared backend into a throwaway
        # environment; the interpreter running this script is not modified.
        sh([sys.executable, "-m", "pip", "wheel", "--no-deps", "--wheel-dir", DIST, src],
           cwd=tmp_path)
        wheel = next(DIST.glob(f"{WHEEL_STEM}-*.whl"))
        record["wheel"] = wheel.name
        record["wheel_sha256"] = sha256(wheel)
        record["inspection"] = inspect(wheel)
        env_dir = tmp_path / "venv"
        venv.EnvBuilder(with_pip=True).create(env_dir)
        python = env_dir / ("Scripts" if sys.platform == "win32" else "bin") / "python"
        # Declared dependencies (PyYAML) resolve from the index exactly as a
        # real install would.
        sh([python, "-m", "pip", "install", "-q", str(wheel)], cwd=tmp_path)
        smoke = SMOKE % (repr(MODULES), VERSION)
        completed = sh([python, "-I", "-c", smoke], cwd=tmp_path, capture_output=True)
        record["installed_smoke"] = json.loads(completed.stdout.strip().splitlines()[-1])
        record["installed_outside_repository"] = str(REPO) not in str(env_dir)
    record["passed"] = bool(
        record["inspection"]["passed"]
        and record["installed_smoke"]["fail_closed"]
        and record["installed_smoke"]["ledger_verified"]
    )
    (DIST / "hyba-salamander-verification.json").write_text(
        json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0 if record["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
