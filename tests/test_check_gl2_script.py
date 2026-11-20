"""Regression for formal/check_gl2.sh: theorem enumeration comes from Lean itself, so
attributed or private theorems are axiom-audited too (an ``@[simp] theorem`` proved
by ``native_decide`` used to pass the source-regex enumeration)."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.real

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "formal" / "check_gl2.sh"
SOURCE = ROOT / "formal" / "GL2Mod256.lean"
PINNED = Path.home() / ".elan" / "toolchains" / "leanprover--lean4---v4.36.0" / "bin" / "lean"


def _lean_env() -> dict | None:
    env = dict(os.environ)
    if env.get("LEAN_BIN") and Path(env["LEAN_BIN"]).exists():
        return env
    if PINNED.exists():
        env["LEAN_BIN"] = str(PINNED)
        return env
    if shutil.which("elan") and shutil.which("lean"):
        return env                       # script uses `lean +leanprover/lean4:v4.36.0`
    return None


def _run(lean_file: Path, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(SCRIPT)], env={**env, "GL2_LEAN_FILE": str(lean_file)},
                          capture_output=True, text=True, timeout=600)


@pytest.fixture(scope="module")
def lean_env():
    env = _lean_env()
    if env is None:
        pytest.skip("pinned Lean v4.36.0 toolchain not installed")
    return env


def test_repository_proofs_pass(lean_env):
    out = _run(SOURCE, lean_env)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "theorems (Lean-enumerated) kernel-checked" in out.stdout


@pytest.mark.parametrize("decl", [
    "@[simp] theorem sneaky : (2 : Nat) + 2 = 4 := by native_decide",
    "private theorem sneaky : (2 : Nat) + 2 = 4 := by native_decide",
])
def test_attributed_or_private_native_decide_is_rejected(lean_env, tmp_path, decl):
    bad = tmp_path / "GL2Mod256.lean"
    bad.write_text(SOURCE.read_text() + f"\nnamespace GL2Mod256\n{decl}\nend GL2Mod256\n")
    out = _run(bad, lean_env)
    assert out.returncode != 0
    assert "axiom" in out.stderr.lower()


@pytest.mark.parametrize("modifier", ["@[simp]", "private"])
def test_attributed_or_private_kernel_proof_is_accepted(lean_env, tmp_path, modifier):
    good = tmp_path / "GL2Mod256.lean"
    good.write_text(
        "namespace GL2Mod256\n"
        f"{modifier} theorem checked : (2 : Nat) + 2 = 4 := by decide\n"
        "end GL2Mod256\n"
    )
    out = _run(good, lean_env)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "GL2DECL GL2Mod256.checked AXIOMS []" in out.stdout
    assert "GL2DECLS 1" in out.stdout
