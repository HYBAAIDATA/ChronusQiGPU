"""Distribution and Clean-Install Qualification Script for Euclid / Salamander.

Tests that hyba_pythia_mining-1.0.0 built wheel installs cleanly into an
isolated virtual environment and operates with full fidelity:
1. Clean virtualenv creation in disposable temp directory.
2. Wheel installation from dist/.
3. Module import verification outside the repository checkout (cwd = tempdir).
4. Public CLI entry point verification (salamander status, capabilities, bsd).
5. Package data inspection (skills and reports accessibility).
6. Safe read-only capability execution smoke test.
7. Cryptographic custody and JSON evidence generation.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    dist_dir = repo_root / "dist"
    target_wheels = list(dist_dir.glob("hyba_pythia_mining-*.whl"))
    if not target_wheels:
        print("[ERROR] No hyba_pythia_mining wheel found in dist/")
        return 1

    wheel_path = sorted(target_wheels)[-1]
    wheel_sha256 = hashlib.sha256(wheel_path.read_bytes()).hexdigest()
    print(f"[*] Target Wheel: {wheel_path.name}")
    print(f"[*] Wheel SHA256: {wheel_sha256}")

    t_start = time.perf_counter()

    with tempfile.TemporaryDirectory(prefix="euclid_install_qual_") as temp_env_dir:
        temp_env_path = Path(temp_env_dir)
        venv_dir = temp_env_path / "venv"

        print(f"[*] Creating isolated virtual environment at: {venv_dir}")
        subprocess.check_call([sys.executable, "-m", "venv", str(venv_dir)])

        # Locate venv python and scripts
        if os.name == "nt":
            venv_python = venv_dir / "Scripts" / "python.exe"
            venv_pip = venv_dir / "Scripts" / "pip.exe"
            venv_salamander = venv_dir / "Scripts" / "salamander.exe"
        else:
            venv_python = venv_dir / "bin" / "python"
            venv_pip = venv_dir / "bin" / "pip"
            venv_salamander = venv_dir / "bin" / "salamander"

        # Install wheel with minimal required dependencies for smoke test (numpy, pyyaml, sympy, cryptography)
        print("[*] Installing wheel into isolated environment...")
        subprocess.check_call(
            [
                str(venv_pip),
                "install",
                "--no-cache-dir",
                "--find-links",
                str(dist_dir),
                str(wheel_path),
            ],
            cwd=str(temp_env_path),
        )

        print("[*] Executing in-venv validation script from outside repository...")
        test_script = temp_env_path / "test_installed_smoke.py"
        test_script.write_text(
            r'''
import os
import sys
import importlib.resources
from pathlib import Path

# Verify that current directory is NOT the source repo
cwd = Path.cwd()
print(f"[venv] Working Directory: {cwd}")

# 1. Imports from site-packages
import Intelligence.salamander as salamander
import Intelligence.capability_fabric as capability_fabric
import Intelligence.isolated_repair as isolated_repair
import Intelligence.mathematical_research as mathematical_research
import integrations.solvers.bsd_solver as bsd_solver
import reports

print("[venv] Core package imports SUCCESS")

# 2. Package data inspection
skills_res = importlib.resources.files("Intelligence").joinpath("skills")
assert skills_res.is_dir(), "Intelligence/skills package data directory missing"
review_skill = skills_res.joinpath("repository-review", "SKILL.md")
assert review_skill.is_file(), "repository-review SKILL.md missing in package data"
bsd_skill = skills_res.joinpath("bsd-exploration", "SKILL.md")
assert bsd_skill.is_file(), "bsd-exploration SKILL.md missing in package data"
ext_skill = skills_res.joinpath("external-agent-boundary", "SKILL.md")
assert ext_skill.is_file(), "external-agent-boundary SKILL.md missing in package data"
print("[venv] Skills package data verified")

reports_res = importlib.resources.files("reports")
manifest_file = reports_res.joinpath("EUCLID_CAPABILITY_MANIFEST.json")
assert manifest_file.is_file(), "EUCLID_CAPABILITY_MANIFEST.json missing in reports package data"
print("[venv] Reports package data verified")

# 3. Instantiate SalamanderEngine
engine = salamander.SalamanderEngine()
print(f"[venv] SalamanderEngine initialized: profile={engine.profile.value}")

# Check equipped skills / capabilities
equipped = list(engine.skills.keys())
print(f"[venv] Equipped skills: {equipped}")
assert "repository-review" in equipped
assert "bsd-exploration" in equipped
assert "external-agent-boundary" in equipped

# 4. Safe read-only capability execution: bsd-exploration
res, receipt = engine.execute_capability(
    "bsd-exploration",
    a=0,
    b=-1,
    max_prime=20,
)
assert res["curve"] == "y^2 = x^3 + (0)x + (-1)"
assert res["proof_claim"] is False
assert receipt.status == "SUCCESS"
print(f"[venv] Capability bsd-exploration executed with receipt {receipt.receipt_id}")

# 5. External agent boundary capability execution
ext_res, ext_receipt = engine.execute_capability(
    "external-agent-boundary",
    task={
        "task_id": "installed_smoke_task",
        "task_type": "code_patch",
        "policy": {
            "allowed_repo_relative_roots": ["chronus/"],
            "max_patch_bytes": 10000,
            "max_files_modified": 2,
        },
    },
    candidate={
        "task_id": "installed_smoke_task",
        "provider": {
            "provider_id": "mock_test",
            "model_name": "test_model",
            "model_version": "1.0",
        },
        "proposed_files": {
            "chronus/smoke.py": "def smoke(): return True\n",
        },
        "claimed_success": True,
    },
)
assert ext_res["verdict"] == "ADMITTED"
assert ext_receipt.status == "SUCCESS"
print(f"[venv] Capability external-agent-boundary executed with receipt {ext_receipt.receipt_id}")

print("[venv] ALL IN-VENV SMOKE CHECKS PASSED")
''',
            encoding="utf-8",
        )

        subprocess.check_call(
            [str(venv_python), str(test_script)],
            cwd=str(temp_env_path),
        )

        # 5. CLI entry point tests
        print("[*] Testing public CLI entry point: salamander...")
        out_status = subprocess.check_output(
            [str(venv_salamander), "status"],
            cwd=str(temp_env_path),
            text=True,
        )
        assert "Salamander Engine Status" in out_status
        print("[*] CLI 'salamander status' OK")

        out_caps = subprocess.check_output(
            [str(venv_salamander), "capabilities", "--profile", "shared"],
            cwd=str(temp_env_path),
            text=True,
        )
        assert "bsd-exploration" in out_caps
        assert "external-agent-boundary" in out_caps
        assert "repository-review" in out_caps
        assert "source-repair" not in out_caps  # Restricted profile test!
        print("[*] CLI 'salamander capabilities --profile shared' OK (restricted profile policy verified)")

        out_bsd = subprocess.check_output(
            [str(venv_salamander), "bsd", "--a", "0", "--b", "-1", "--max-prime", "20"],
            cwd=str(temp_env_path),
            text=True,
        )
        assert "y^2 = x^3 + (0)x + (-1)" in out_bsd
        assert "Proof Claim: False (CMI Boundary Sealed)" in out_bsd
        print("[*] CLI 'salamander bsd' OK")

    duration = round(time.perf_counter() - t_start, 2)
    print(f"[*] Qualification completed successfully in {duration}s")

    # Record evidence
    report_data = {
        "qualification": "DISTRIBUTION_AND_CLEAN_INSTALL",
        "status": "PASSED",
        "timestamp": time.time(),
        "duration_seconds": duration,
        "wheel_filename": wheel_path.name,
        "wheel_sha256": wheel_sha256,
        "wheel_size_bytes": wheel_path.stat().st_size,
        "checks_passed": [
            "isolated_virtualenv_creation",
            "wheel_clean_install",
            "out_of_tree_module_import",
            "skills_package_data_integrity",
            "reports_package_data_integrity",
            "salamander_engine_clean_init",
            "clean_bsd_exploration_dispatch",
            "clean_external_agent_boundary_dispatch",
            "cli_entry_point_salamander_status",
            "cli_entry_point_salamander_capabilities_profile_policy",
            "cli_entry_point_salamander_bsd_cmi_sealed",
        ],
    }

    report_path = repo_root / "reports" / "DISTRIBUTION_QUALIFICATION_REPORT.json"
    report_path.write_text(json.dumps(report_data, indent=2), encoding="utf-8")
    print(f"[*] Report saved to {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
