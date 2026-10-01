#!/usr/bin/env python3
"""Behavioral acceptance gate for the canonical PYTHIA mining path.

This gate is deliberately different from a requirements/traceability audit.
It executes the M32 allocation, SHA256d proof boundary, chooser behavior, and
arbitrary-start coverage. It also scans only the active canonical path for
simulation language and synthetic acceptance. It does not claim hardware,
pool, or hashrate results; those require live deployment evidence.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOT = ROOT / "chronus/mla1517_platform" / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from chronus.mla1517.mining import (  # noqa: E402
    M32SearchSolver,
    M32Topology,
    MiningIntelligenceChooser,
    build_header,
    check_pow,
    compact_target,
    sha256d,
)

ACTIVE_FILES = (
    ROOT / "main.py",
    PYTHON_ROOT / "control_api.py",
    PYTHON_ROOT / "mining_runtime.py",
    PYTHON_ROOT / "manifold_pool_coordinator.py",
    ROOT / "chronus" / "mla1517" / "mining" / "chooser.py",
    ROOT / "chronus" / "mla1517" / "mining" / "coordinator.py",
    ROOT / "chronus" / "mla1517" / "mining" / "geometry.py",
    ROOT / "chronus" / "mla1517" / "mining" / "lane.py",
    ROOT / "chronus" / "mla1517" / "mining" / "pow.py",
    ROOT / "chronus" / "mla1517" / "mining" / "solver.py",
)
FORBIDDEN_ACTIVE_TEXT = (
    "TypeScript server",
    "Research/simulation",
    "Simulated tensor",
    "accepted += 1",
    "fixed hashrate",
)


def check_active_path() -> None:
    missing = [str(path.relative_to(ROOT)) for path in ACTIVE_FILES if not path.is_file()]
    assert not missing, f"active canonical files missing: {missing}"
    violations: list[str] = []
    for path in ACTIVE_FILES:
        text = path.read_text(encoding="utf-8")
        for needle in FORBIDDEN_ACTIVE_TEXT:
            if needle in text:
                violations.append(f"{path.relative_to(ROOT)}: {needle}")
    assert not violations, "active-path simulation/stale-backend text: " + "; ".join(violations)


def check_m32_coverage() -> None:
    topology = M32Topology()
    assert topology.connected(), "M32 graph is disconnected"
    solver = M32SearchSolver(topology)
    candidates = list(solver.candidates(start_nonce=7, budget=32))
    nonces = [nonce for nonce, _lane in candidates]
    lanes = [lane for _nonce, lane in candidates]
    assert nonces[0] == 7, "arbitrary start nonce was skipped"
    assert len(set(nonces)) == 32, "M32 candidate allocation overlaps"
    assert sorted(lanes) == list(range(32)), "M32 allocation does not cover all lanes"


def check_sha256d_boundary() -> None:
    # Construct a real 80-byte header and derive a deterministic target equal
    # to its real double-SHA256 digest. This tests header construction, hashing,
    # and the target predicate without depending on a lucky probabilistic hit.
    header = build_header(1, "00" * 32, "11" * 32, 1, 0x207FFFFF, 0)
    assert len(header) == 80, "Bitcoin header is not 80 bytes"
    digest = int.from_bytes(sha256d(header), byteorder="little")
    assert check_pow(header, digest), "real SHA256d proof was rejected"
    assert compact_target(0x207FFFFF) > 0, "compact target decoder failed"


def check_measured_chooser() -> None:
    chooser = MiningIntelligenceChooser()
    decision = chooser.choose(
        has_job=True,
        candidate_window=[1, 1, 2, 3, 5, 8],
        budget=32,
    )
    assert decision.lead == "m32_structured"
    assert chooser.accepted_count == 0 and chooser.rejected_count == 0
    chooser.learn(accepted=True, lead=decision.lead, job_id="observed-job")
    assert chooser.accepted_count == 1


def main() -> int:
    checks = (
        ("active canonical path", check_active_path),
        ("M32 complete coverage", check_m32_coverage),
        ("real SHA256d proof boundary", check_sha256d_boundary),
        ("measured chooser", check_measured_chooser),
    )
    for name, check in checks:
        check()
        print(f"PASS {name}")
    print("PASS behavioral claim gate")
    print("NOTE hardware, OpenCL, pool acceptance, and hashrate require the live deployment gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
