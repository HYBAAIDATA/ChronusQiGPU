"""Exercise CLI and receipt blockers; never qualify production evidence."""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_cli_unqualified_registry_exits_nonzero_with_retained_decision(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    artifact = tmp_path / "candidate.whl"
    artifact.write_bytes(b"test-only candidate")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-qm",
            "fixture",
        ],
        check=True,
    )
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.cedr_gate",
            "--registry",
            str(ROOT / "governance/cedr.json"),
            "--profile",
            "pilot-operations",
            "--artifact",
            str(artifact),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 1
    report = json.loads((tmp_path / "results/cedr-decision.json").read_text())
    assert report["eligible"] is False
    assert len(report["claims"]) == 19
    assert not (tmp_path / "results/promotion_receipt.json").exists()


def test_receipt_command_cannot_omit_cedr_profile_and_candidate(tmp_path):
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/advance_state.py"),
            "--subsystem",
            "guardian",
            "--target",
            "PRODUCTION",
            "--commit",
            "a" * 40,
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0
    assert "--cedr-profile" in proc.stderr
    assert not (tmp_path / "results/promotion_receipt.json").exists()


def test_production_cannot_use_weaker_pilot_profile(tmp_path):
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/advance_state.py"),
            "--subsystem",
            "guardian",
            "--target",
            "PRODUCTION",
            "--commit",
            "a" * 40,
            "--cedr-profile",
            "pilot-operations",
            "--artifact",
            "candidate.whl",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0
    assert "profile does not cover target tier" in proc.stderr
    assert not (tmp_path / "results/promotion_receipt.json").exists()
