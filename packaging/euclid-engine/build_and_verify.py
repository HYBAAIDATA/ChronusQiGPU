"""Build and verify the 1.0.0 sdist and wheel (research generation 17.0.0).

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
import tarfile
import tempfile
import venv
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
DIST = HERE / "dist"
VERSION = "1.0.0"
RESEARCH_VERSION = "17.0.0"
PACKAGES = ("euclid", "hyba_substrate", "resonance_intelligence")
FORBIDDEN_TOP_LEVEL = {
    "toe",
    "Intelligence",
    "kellogg",
    "mining",
    "chronus",
    "aethel",
    "lucas",
    "turing_universal_quantum_computer",
    "millennium",
}
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
import json, sys, importlib.metadata
import euclid
from euclid.cognition.worlds import generate_suite, WorldExecutor
from euclid.cognition.integrated import IntegratedAgent, SYSTEMS
mods = %s
for name in mods:
    __import__(name)
assert all("site-packages" in (sys.modules[m].__file__ or "") for m in mods), "not the installed copy"
assert euclid.__version__ == "%s", euclid.__version__
assert importlib.metadata.version("hyba-euclid-intelligence") == "%s"
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

RUNTIME_READER = r"""
import json, sys
from pathlib import Path
from aethel.enterprise.lifecycle import CompositionRoot
from euclid.runtime import EuclidRuntime
root = Path(sys.argv[1])
prior = json.loads((root / "receipt.json").read_text())
lifecycle = CompositionRoot(root / "custody", tenant="installed-test", hmac_key=b"k" * 32)
lifecycle.start()
runtime = EuclidRuntime(creator_id="installed-creator", state_dir=root / "reader")
try:
    runtime.bind_adaptive_data_port(lifecycle.data_port("euclid"))
    runtime.compose_adaptive_intelligence()
    result = runtime.verify_adaptive_restart_receipt(prior)
    assert runtime.adaptive.knowledge.episodes == prior["episodes"]
    assert "site-packages" in sys.modules["euclid.runtime"].__file__
    print(json.dumps(result))
finally:
    runtime.close()
    lifecycle.stop()
"""

RUNTIME_SMOKE = r"""
import json, subprocess, sys
from pathlib import Path
from aethel.enterprise.lifecycle import CompositionRoot
from euclid.cognition.worlds import MechanismWorld, WorldExecutor, generate_task
from euclid.runtime import EuclidRuntime
root = Path(sys.argv[1])
lifecycle = CompositionRoot(root / "custody", tenant="installed-test", hmac_key=b"k" * 32)
lifecycle.start()
runtime = EuclidRuntime(creator_id="installed-creator", state_dir=root / "writer")
try:
    runtime.bind_adaptive_data_port(lifecycle.data_port("euclid"))
    runtime.compose_adaptive_intelligence()
    spec, truth = generate_task("program-transformation", seed=37, partition="evaluation")
    runtime.solve_task(spec, WorldExecutor(MechanismWorld(spec, truth)), seed=37)
    receipt = runtime.adaptive_restart_receipt()
    (root / "receipt.json").write_text(json.dumps(receipt))
    assert not runtime.rights.snapshot()["grants"]
    assert not (runtime.state_dir / "adaptive_knowledge.json").exists()
    assert "site-packages" in sys.modules["euclid.runtime"].__file__
    assert "site-packages" in sys.modules["aethel.enterprise.lifecycle"].__file__
finally:
    runtime.close()
    lifecycle.stop()
completed = subprocess.run([sys.executable, "-I", "-c", %s, str(root)],
                           capture_output=True, text=True, check=True, timeout=180)
result = json.loads(completed.stdout.strip().splitlines()[-1])
assert result["passed"]
assert result["current_process_id"] != result["prior_process_id"]
print(json.dumps({"episodes": receipt["episodes"], "restart": result, "passed": True}))
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
    missing = [
        m
        for m in V17_MODULES
        if m.replace(".", "/") + ".py" not in names
        and m.replace(".", "/") + "/__init__.py" not in names
    ]
    return {
        "files": len(names),
        "top_level": sorted(top),
        "forbidden_top_level": forbidden,
        "secret_hits": secrets,
        "test_or_cache_files": bad[:20],
        "missing_v17": missing,
        "passed": not (forbidden or secrets or bad or missing),
    }


def _sibling_wheel(pattern: str, dist: Path) -> Path:
    wheels = sorted(dist.glob(pattern))
    if not wheels:
        raise RuntimeError(f"sibling wheel {pattern} not found in {dist}; build that product first")
    return wheels[0]


def build_dependencies(root: Path) -> list[Path]:
    """Build the declared sibling products from this source, without vendoring."""
    wheelhouse = root / "dependencies"
    wheelhouse.mkdir()
    for product, package in (("kellogg-tensor", "kellogg"), ("toe", "toe"), ("theseus", "aethel")):
        project = root / product
        project.mkdir()
        destination = project / "src" if product == "theseus" else project
        destination.mkdir(exist_ok=True)
        shutil.copytree(
            REPO / package,
            destination / package,
            ignore=shutil.ignore_patterns("tests", "__pycache__", "*.pyc", "var"),
        )
        for name in ("pyproject.toml", "README.md"):
            shutil.copy2(REPO / "packaging" / product / name, project / name)
        shutil.copy2(REPO / "LICENSE", project / "LICENSE")
        sh([sys.executable, "-m", "build", "--wheel", "--outdir", wheelhouse, project], cwd=root)
    return sorted(wheelhouse.glob("*.whl"))


def package_manifest(source: Path) -> dict[str, str]:
    return {
        path.relative_to(source).as_posix(): sha256(path)
        for package in PACKAGES
        for path in sorted((source / package).rglob("*.py"))
    }


def inspect_sdist(sdist: Path, extracted: Path) -> dict:
    """Inspect and safely unpack the exact source artifact used for the wheel."""
    forbidden: list[str] = []
    secrets: list[str] = []
    with tarfile.open(sdist) as archive:
        members = archive.getmembers()
        for member in members:
            parts = Path(member.name).parts
            if (
                not parts
                or Path(member.name).is_absolute()
                or ".." in parts
                or member.issym()
                or member.islnk()
                or not (member.isfile() or member.isdir())
            ):
                raise ValueError("unsafe sdist member")
            if len(parts) > 1 and parts[1] in FORBIDDEN_TOP_LEVEL:
                forbidden.append(member.name)
            if any(p in {"tests", "__pycache__"} for p in parts) or member.name.endswith(".pyc"):
                forbidden.append(member.name)
            target = extracted / member.name
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            content = archive.extractfile(member).read()
            if any(pattern.search(content) for pattern in SECRET_PATTERNS):
                secrets.append(member.name)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
    return {
        "files": len(members),
        "forbidden_members": forbidden,
        "secret_hits": secrets,
        "passed": not (forbidden or secrets),
    }


def main() -> int:
    DIST.mkdir(exist_ok=True)
    for stale in (
        *DIST.glob("hyba_euclid_intelligence-*.whl"),
        *DIST.glob("hyba_euclid_intelligence-*.tar.gz"),
    ):
        stale.unlink()
    record: dict = {
        "product": "hyba-euclid-intelligence",
        "version": VERSION,
        "research_version": RESEARCH_VERSION,
        "classification": "RESEARCH_RELEASE",
    }
    with tempfile.TemporaryDirectory(prefix="euclid-engine-") as tmp:
        tmp_path = Path(tmp)
        src = stage(tmp_path)
        manifest = package_manifest(src)
        record["source_manifest_sha256"] = hashlib.sha256(
            json.dumps(manifest, sort_keys=True).encode()
        ).hexdigest()
        commit = sh(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True)
        record["source_commit"] = commit.stdout.strip()
        dependencies = build_dependencies(tmp_path)
        record["dependency_wheels"] = {path.name: sha256(path) for path in dependencies}
        sh([sys.executable, "-m", "build", "--sdist", "--outdir", DIST, src], cwd=tmp_path)
        sdist = next(DIST.glob("hyba_euclid_intelligence-*.tar.gz"))
        record["sdist"] = sdist.name
        record["sdist_sha256"] = sha256(sdist)
        extracted = tmp_path / "extracted"
        record["sdist_inspection"] = inspect_sdist(sdist, extracted)
        rebuilt = extracted / f"hyba_euclid_intelligence-{VERSION}"
        record["sdist_source_matches"] = package_manifest(rebuilt) == manifest
        if not record["sdist_inspection"]["passed"] or not record["sdist_source_matches"]:
            raise ValueError("sdist does not match the qualified source")
        sh([sys.executable, "-m", "build", "--wheel", "--outdir", DIST, rebuilt], cwd=tmp_path)
        wheel = next(DIST.glob("hyba_euclid_intelligence-*.whl"))
        record["wheel"] = wheel.name
        record["wheel_sha256"] = sha256(wheel)
        record["inspection"] = inspect(wheel)
        with zipfile.ZipFile(wheel) as archive:
            record["wheel_source_matches"] = all(
                hashlib.sha256(archive.read(name)).hexdigest() == digest
                for name, digest in manifest.items()
            )
        if not record["inspection"]["passed"] or not record["wheel_source_matches"]:
            raise ValueError("wheel does not match the qualified source")
        env_dir = tmp_path / "venv"
        venv.EnvBuilder(with_pip=True).create(env_dir)
        python = env_dir / ("Scripts" if sys.platform == "win32" else "bin") / "python"
        # Full dependency resolution is exercised: the sibling product wheels
        # satisfy the declared kellogg-toe/hyba-toe-intelligence requirements and numpy is
        # fetched from the index, exactly as a real install would resolve.
        sh([python, "-m", "pip", "install", "-q", *dependencies, wheel], cwd=tmp_path)
        smoke = SMOKE % (repr(V17_MODULES), RESEARCH_VERSION, VERSION)
        completed = sh([python, "-I", "-c", smoke], cwd=tmp_path, capture_output=True)
        record["installed_smoke"] = json.loads(completed.stdout.strip().splitlines()[-1])
        completed = sh(
            [python, "-I", "-c", RUNTIME_SMOKE % repr(RUNTIME_READER), tmp_path],
            cwd=tmp_path,
            capture_output=True,
        )
        record["installed_runtime"] = json.loads(completed.stdout.strip().splitlines()[-1])
        record["installed_outside_repository"] = str(REPO) not in str(env_dir)
    record["passed"] = bool(
        record["inspection"]["passed"]
        and record["sdist_inspection"]["passed"]
        and record["sdist_source_matches"]
        and record["wheel_source_matches"]
        and record["installed_smoke"]["episodes"]
        and record["installed_runtime"]["passed"]
    )
    (DIST / "euclid-engine-verification.json").write_text(
        json.dumps(record, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0 if record["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
