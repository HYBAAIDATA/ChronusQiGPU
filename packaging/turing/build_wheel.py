"""Build the turing-universal-quantum-computer wheel from a staged copy.

The distribution's own pyproject lives in turing_universal_quantum_computer/.
Building from a staged copy keeps build/ and egg-info out of the source tree.
Verification against the installed wheel is packaging/verify_release_candidates.py.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent.parent / "turing_universal_quantum_computer"


def main() -> int:
    dist = HERE / "dist"
    dist.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="turing-build-") as tmp:
        stage = Path(tmp) / "src"
        stage.mkdir()
        for name in ("pyproject.toml", "README.md", "LICENSE"):
            shutil.copy2(SOURCE / name, stage / name)
        shutil.copytree(
            SOURCE / "turing_universal_quantum_computer",
            stage / "turing_universal_quantum_computer",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        subprocess.run([sys.executable, "-m", "build", "--wheel", "--outdir", str(dist), str(stage)], check=True)
    wheel = sorted(dist.glob("turing_universal_quantum_computer-*.whl"), key=lambda p: p.stat().st_mtime)[-1]
    print("wheel:", wheel)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
