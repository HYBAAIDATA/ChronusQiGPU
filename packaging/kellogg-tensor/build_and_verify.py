"""Build the kellogg-tensor wheel from the monorepo and verify it in isolation.

Steps (the packaging/README.md verification protocol):

1. stage ``kellogg/`` with this pyproject, README and the repository LICENSE;
2. ``python -m build --wheel`` into ``packaging/kellogg-tensor/dist``;
3. create a clean virtual environment, install only the wheel (and numpy);
4. from outside the repository, import every module, check the capability
   manifest version against the wheel, and run the quick correctness and
   meta benchmarks against the installed wheel.

Nothing is published. Exit status is non-zero if any step fails.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent


def sh(cmd, **kw) -> subprocess.CompletedProcess:
    print("$", " ".join(str(c) for c in cmd), flush=True)
    return subprocess.run([str(c) for c in cmd], check=True, **kw)


def stage(root: Path) -> Path:
    src = root / "src"
    src.mkdir(parents=True)
    shutil.copytree(
        REPO / "kellogg",
        src / "kellogg",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    for name in ("pyproject.toml", "README.md"):
        shutil.copy2(HERE / name, src / name)
    shutil.copy2(REPO / "LICENSE", src / "LICENSE")
    return src


def main() -> int:
    dist = HERE / "dist"
    dist.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="kellogg-build-") as tmp:
        src = stage(Path(tmp))
        sh([sys.executable, "-m", "build", "--wheel", "--outdir", dist, src])
    wheels = sorted(dist.glob("kellogg_tensor-*.whl"), key=lambda p: p.stat().st_mtime)
    wheel = wheels[-1]
    print("wheel:", wheel.name, wheel.stat().st_size, "bytes")
    with tempfile.TemporaryDirectory(prefix="kellogg-venv-") as tmp:
        env_dir = Path(tmp) / "venv"
        venv.EnvBuilder(with_pip=True, clear=True).create(env_dir)
        py = env_dir / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        sh([py, "-m", "pip", "install", "-q", str(wheel)])
        check = r"""
import importlib, json, pkgutil, sys
import kellogg
assert 'site-packages' in kellogg.__file__, kellogg.__file__
mods = sorted(m.name for m in pkgutil.iter_modules(kellogg.__path__))
failed = {}
for m in mods:
    try:
        importlib.import_module('kellogg.' + m)
    except Exception as e:
        failed[m] = repr(e)
from importlib.resources import files
manifest = json.loads(files('kellogg').joinpath('CAPABILITY_MANIFEST.json').read_text())
siblings = [s for s in ('aethel', 'chronus', 'turing_core', 'lucas', 'toe', 'mining') if s in sys.modules]
from kellogg.spec import verify_registry
from kellogg.benchmark import BENCHMARKS, run
reg = verify_registry()
results = {}
for bid, (axis, _) in BENCHMARKS.items():
    if axis in ('correctness', 'meta'):
        results[bid] = run(bid, quick=True)['passed']
print(json.dumps({'version': kellogg.__version__, 'manifest_version': manifest['version'],
                  'modules': len(mods), 'failed': failed, 'siblings_loaded': siblings,
                  'registry_ok': reg['ok'], 'benchmarks': results}))
"""
        out = sh([py, "-c", check], cwd=tmp, capture_output=True, text=True)
        report = json.loads(out.stdout.strip().splitlines()[-1])
    print(json.dumps(report, indent=1))
    ok = (
        not report["failed"]
        and not report["siblings_loaded"]
        and report["version"] == report["manifest_version"]
        and report["registry_ok"]
        and all(v is not False for v in report["benchmarks"].values())
    )
    print("VERIFIED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
