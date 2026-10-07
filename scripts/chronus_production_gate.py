"""Execute the CHRONUS standalone production gate and emit digest-bound evidence.

This runner is intentionally software-first. A physical GPU is not a prerequisite
for the core gate. Accelerator certification is a separate workflow.

Run from repository root:
    python scripts/chronus_production_gate.py --out artifacts/chronus-production

The runner stops neither at imports nor at source inspection. It executes focused
contracts, first workload, clean-wheel installation, and the complete configured
pytest suite. Every command receives its own log and digest. The final evidence JSON
is suitable as input to chronus-readiness --evidence only when every required gate passes.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class CommandResult:
    name: str
    command: tuple[str, ...]
    exit_code: int
    log_path: str
    log_sha256: str

    @property
    def passed(self) -> bool:
        return self.exit_code == 0


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _git(*args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip() if proc.returncode == 0 else ""


def _run(name: str, command: Sequence[str], out_dir: Path) -> CommandResult:
    log = out_dir / f"{name}.log"
    with log.open("w", encoding="utf-8", errors="replace") as handle:
        proc = subprocess.run(
            list(command),
            cwd=ROOT,
            stdout=handle,
            stderr=subprocess.STDOUT,
            check=False,
            env=os.environ.copy(),
        )
    return CommandResult(
        name=name,
        command=tuple(command),
        exit_code=int(proc.returncode),
        log_path=str(log.relative_to(ROOT) if log.is_relative_to(ROOT) else log),
        log_sha256=_sha256(log),
    )


def _python() -> str:
    return sys.executable


def _focused_commands() -> list[tuple[str, list[str]]]:
    py = _python()
    return [
        (
            "two_mode_contract",
            [py, "-m", "pytest", "tests/test_chronus_two_mode_contract.py", "-q", "--tb=short"],
        ),
        (
            "delivery_contract",
            [py, "-m", "pytest", "tests/test_chronus_delivery.py", "-q", "--tb=short"],
        ),
        (
            "vigpu_fail_closed",
            [py, "-m", "pytest", "tests/test_chronus_vigpu_fail_closed_contract.py", "-q", "--tb=short"],
        ),
        (
            "production_route",
            [py, "-m", "pytest", "tests/test_chronus_production_route.py", "-q", "--tb=short"],
        ),
        (
            "theseus_restart",
            [py, "-m", "pytest", "tests/test_chronus_theseus_restart_contract.py", "-q", "--tb=short"],
        ),
        (
            "first_workload",
            [py, "-m", "pytest", "tests/test_chronus_first_workload.py", "-q", "--tb=short"],
        ),
        (
            "import_audit",
            [py, "scripts/import_audit.py"],
        ),
    ]


def _clean_wheel_gate(out_dir: Path) -> CommandResult:
    py = _python()
    dist = out_dir / "dist"
    dist.mkdir(parents=True, exist_ok=True)
    build = _run("wheel_build", [py, "-m", "build", "--outdir", str(dist)], out_dir)
    if not build.passed:
        return build

    wheels = sorted(dist.glob("*.whl"))
    if not wheels:
        marker = out_dir / "clean_wheel.log"
        marker.write_text("no wheel produced\n", encoding="utf-8")
        return CommandResult(
            name="clean_wheel",
            command=("wheel-build",),
            exit_code=2,
            log_path=str(marker),
            log_sha256=_sha256(marker),
        )

    venv_dir = out_dir / "clean-venv"
    if venv_dir.exists():
        shutil.rmtree(venv_dir)
    subprocess.run([py, "-m", "venv", str(venv_dir)], cwd=ROOT, check=True)
    vpy = (
        venv_dir / "Scripts" / "python.exe"
        if os.name == "nt"
        else venv_dir / "bin" / "python"
    )
    log = out_dir / "clean_wheel.log"
    commands = [
        [str(vpy), "-m", "pip", "install", "--disable-pip-version-check", str(wheels[0])],
        [
            str(vpy),
            "-c",
            (
                "from chronus.virtual_igpu import RuntimeDaemon, CPUEmulatorAdapter; "
                "from chronus.readiness import audit_core_surfaces; "
                "d=RuntimeDaemon(adapters=[CPUEmulatorAdapter()]); "
                "assert all(g.passed for g in audit_core_surfaces()); "
                "print(d.health())"
            ),
        ],
    ]
    rc = 0
    with log.open("w", encoding="utf-8", errors="replace") as handle:
        for cmd in commands:
            proc = subprocess.run(
                cmd,
                cwd=tempfile.gettempdir(),
                stdout=handle,
                stderr=subprocess.STDOUT,
                check=False,
            )
            if proc.returncode:
                rc = int(proc.returncode)
                break
    return CommandResult(
        name="clean_wheel",
        command=tuple(commands[-1]),
        exit_code=rc,
        log_path=str(log.relative_to(ROOT) if log.is_relative_to(ROOT) else log),
        log_sha256=_sha256(log),
    )


def _evidence_ref(kind: str, subject: str, producer: str, artifact: Path, **metadata):
    return {
        "kind": kind,
        "artifact_sha256": _sha256(artifact),
        "observed_at": _utc_now(),
        "subject": subject,
        "producer": producer,
        "metadata": metadata,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="artifacts/chronus-production")
    parser.add_argument(
        "--skip-full-suite",
        action="store_true",
        help="diagnostic only; a skipped full suite can never produce production-ready evidence",
    )
    args = parser.parse_args()

    head = _git("rev-parse", "HEAD") or "unknown"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out_dir = (ROOT / args.out / f"{stamp}-{head[:12]}").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    results: list[CommandResult] = []
    for name, command in _focused_commands():
        results.append(_run(name, command, out_dir))

    results.append(
        _run(
            "capability_probe",
            [
                _python(),
                "scripts/chronus_capability_probe.py",
                "--quick",
                "--out",
                str(out_dir / "capability.json"),
            ],
            out_dir,
        )
    )

    results.append(_clean_wheel_gate(out_dir))

    if args.skip_full_suite:
        full = None
    else:
        full = _run(
            "full_suite",
            [_python(), "-m", "pytest", "-q", "-rs", "--tb=short"],
            out_dir,
        )
        results.append(full)

    summary = {
        "schema": "chronus.production-gate/1",
        "generated_at": _utc_now(),
        "git_head": head,
        "git_branch": _git("branch", "--show-current"),
        "working_tree_clean": not bool(_git("status", "--porcelain")),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "results": [asdict(result) | {"passed": result.passed} for result in results],
        "full_suite_executed": full is not None,
        "all_required_passed": bool(
            full is not None and all(result.passed for result in results)
        ),
        "claim_boundary": (
            "standalone CHRONUS software evidence only; no physical accelerator, "
            "hardware-rooted, live-pool, fleet or throughput claim is inferred"
        ),
    }
    summary_path = out_dir / "gate-summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    producer = "scripts/chronus_production_gate.py"
    evidence = {}
    if summary["all_required_passed"]:
        capability_path = out_dir / "capability.json"
        evidence = {
            "software_execution": _evidence_ref(
                "chronus_software_execution",
                "standalone CHRONUS execution on current head",
                producer,
                capability_path,
                git_head=head,
                mode="standalone_software",
            ),
            "independent_verification": _evidence_ref(
                "chronus_independent_verification",
                "CHRONUS independent verification contracts",
                producer,
                out_dir / "production_route.log",
                git_head=head,
            ),
            "receipt_identity": _evidence_ref(
                "chronus_receipt_identity",
                "Virtual iGPU receipt and fail-closed contracts",
                producer,
                out_dir / "vigpu_fail_closed.log",
                git_head=head,
            ),
            "custody_restart": _evidence_ref(
                "chronus_custody_restart",
                "THESEUS fresh-process custody/restart contract",
                producer,
                out_dir / "theseus_restart.log",
                git_head=head,
            ),
            "clean_install": _evidence_ref(
                "chronus_clean_install",
                "clean wheel install and CHRONUS import/execution",
                producer,
                out_dir / "clean_wheel.log",
                git_head=head,
            ),
            "full_suite": _evidence_ref(
                "chronus_full_suite",
                "complete repository pytest suite on current head",
                producer,
                out_dir / "full_suite.log",
                git_head=head,
            ),
        }

    evidence_path = out_dir / "readiness-evidence.json"
    evidence_path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "gate_summary": str(summary_path),
                "readiness_evidence": str(evidence_path),
                "all_required_passed": summary["all_required_passed"],
                "git_head": head,
            },
            indent=2,
        )
    )
    return 0 if summary["all_required_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
