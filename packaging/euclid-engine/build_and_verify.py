"""Build and verify the euclid-engine 17.0.0 wheel (artefact-first, nothing published).

Stages only the product (``euclid`` without its in-package tests or runtime
state, plus the two bundled runtime dependencies), builds the wheel in an
isolated build environment,
inspects and secret-scans it, installs it into a fresh virtual environment
*outside* the repository, imports every v17 module in an isolated interpreter
and runs real v17 episodes from the installed copy.  Writes a verification
record with the wheel's SHA-256.
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
VERSION = "17.0.0"
PACKAGES = ("euclid", "hyba_substrate", "resonance_intelligence")
FORBIDDEN_TOP_LEVEL = {"toe", "Intelligence", "kellogg", "mining", "chronus", "aethel",
                       "lucas", "turing_universal_quantum_computer", "millennium"}
SECRET_PATTERNS = (
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"ghp_[A-Za-z0-9]{30,}"),
    re.compile(rb"github_pat_[A-Za-z0-9_]{40,}"),
    re.compile(rb"pypi-AgEI[A-Za-z0-9_-]{20,}"),
    re.compile(rb"AKIA[0-9A-Z]{16}"),
)
V17_MODULES = (
    "euclid.cognition.core",
    "euclid.cognition.worlds",
    "euclid.cognition.worlds.families",
    "euclid.cognition.integrated",
    "euclid.cognition.integrated.world_model",
    "euclid.cognition.integrated.analogy",
    "euclid.cognition.integrated.skills",
    "euclid.cognition.integrated.self_improvement",
    "euclid.cognition.research.programme",
    "euclid.cognition.research.report",
    "euclid.cognition.research.cli",
)
SMOKE = r"""
import json, sys
import euclid
from euclid.cognition.worlds import generate_suite, WorldExecutor
from euclid.cognition.integrated import IntegratedAgent, SYSTEMS
mods = %s
for name in mods:
    __import__(name)
assert all("site-packages" in (sys.modules[m].__file__ or "") for m in mods), "not the installed copy"
assert euclid.__version__ == "%s", euclid.__version__
suite = generate_suite(9100, train_per_family=1, development_per_family=0,
                       evaluation_per_family=1, held_out_per_family=1,
                       adversarial_per_tag=0, analogy_pairs=1)
agent = IntegratedAgent.for_system("integrated")
for i, task in enumerate(suite["train"]):
    agent.solve(task.spec, WorldExecutor(task.world(seed=i)), seed=i)
frozen = IntegratedAgent(knowledge=agent.knowledge.freeze())
results = [frozen.solve(t.spec, WorldExecutor(t.world(seed=7)), seed=7).summary()
           for t in suite["evaluation"] + suite["held-out"] + suite["analogy"]]
print(json.dumps({"modules": len(mods), "systems": len(SYSTEMS),
                  "episodes": len(results), "solved": sum(r["solved"] for r in results)}))
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
    missing = [m for m in V17_MODULES
               if m.replace(".", "/") + ".py" not in names
               and m.replace(".", "/") + "/__init__.py" not in names]
    return {"files": len(names), "top_level": sorted(top), "forbidden_top_level": forbidden,
            "secret_hits": secrets, "test_or_cache_files": bad[:20], "missing_v17": missing,
            "passed": not (forbidden or secrets or bad or missing)}


def _sibling_wheel(pattern: str, dist: Path) -> Path:
    wheels = sorted(dist.glob(pattern))
    if not wheels:
        raise RuntimeError(
            f"sibling wheel {pattern} not found in {dist}; build that product first"
        )
    return wheels[0]


def main() -> int:
    DIST.mkdir(exist_ok=True)
    for stale in DIST.glob("euclid_engine-*.whl"):
        stale.unlink()
    record: dict = {"product": "euclid-engine", "version": VERSION}
    with tempfile.TemporaryDirectory(prefix="euclid-engine-") as tmp:
        tmp_path = Path(tmp)
        src = stage(tmp_path)
        # Build isolation fetches the declared backend into a throwaway
        # environment; the interpreter running this script is not modified.
        sh([sys.executable, "-m", "pip", "wheel", "--no-deps", "--wheel-dir", DIST, src],
           cwd=tmp_path)
        wheel = next(DIST.glob("euclid_engine-*.whl"))
        record["wheel"] = wheel.name
        record["wheel_sha256"] = sha256(wheel)
        record["inspection"] = inspect(wheel)
        env_dir = tmp_path / "venv"
        venv.EnvBuilder(with_pip=True).create(env_dir)
        python = env_dir / ("Scripts" if sys.platform == "win32" else "bin") / "python"
        kellogg_wheel = _sibling_wheel(
            "kellogg_tensor-*.whl", REPO / "packaging" / "kellogg-tensor" / "dist"
        )
        toe_wheel = _sibling_wheel(
            "hyba_toe-*.whl", REPO / "packaging" / "toe" / "dist"
        )
        # Full dependency resolution is exercised: the sibling product wheels
        # satisfy the declared kellogg-toe/hyba-toe requirements and numpy is
        # fetched from the index, exactly as a real install would resolve.
        sh([python, "-m", "pip", "install", "-q", str(kellogg_wheel), str(toe_wheel), str(wheel)], cwd=tmp_path)
        smoke = SMOKE % (repr(V17_MODULES), VERSION)
        completed = sh([python, "-I", "-c", smoke], cwd=tmp_path, capture_output=True)
        record["installed_smoke"] = json.loads(completed.stdout.strip().splitlines()[-1])
        record["installed_outside_repository"] = str(REPO) not in str(env_dir)
    record["passed"] = bool(record["inspection"]["passed"] and record["installed_smoke"]["episodes"])
    (DIST / "euclid-engine-verification.json").write_text(
        json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0 if record["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
