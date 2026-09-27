#!/usr/bin/env python3
"""Fail-closed repository guard for production handover surfaces.

This gate is deliberately dependency-light. It checks invariants that must hold
on every push and pull request, without contacting a mining pool or pretending
that a hosted runner has the target iGPU.
"""
from __future__ import annotations

import ast
import hashlib
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True
    )
    return [item for item in result.stdout.decode().split("\0") if item]


def fail(message: str) -> None:
    raise SystemExit(f"FAIL — {message}")


def check_secret_boundaries(files: list[str]) -> None:
    forbidden_paths = [
        p for p in files
        if Path(p).name in {".env", ".env.local", ".env.production"}
        or p.endswith((".pem", ".key"))
    ]
    if forbidden_paths:
        fail(f"credential-bearing files are tracked: {forbidden_paths}")
    private_key = re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----")
    credential_literal = re.compile(
        r"(?i)(?:password|passwd|secret|client[_-]?secret|access[_-]?token)"
        r"\s*[:=]\s*['\"][^'\"]{12,}['\"]"
    )
    for relative in files:
        path = ROOT / relative
        if path.stat().st_size > 2_000_000:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if private_key.search(text):
            fail(f"private key material found in {relative}")
        if credential_literal.search(text) and relative not in {
            ".env.example",
            "docs/PRODUCTION_MINING_RUNBOOK.md",
        }:
            fail(f"credential-like literal found in {relative}")


def check_kernel_identity() -> None:
    candidates = [
        ROOT / "kernels" / "bitcoin_sha256d.cl",
        ROOT / "iGPU_Accelerator_JV" / "kernels" / "bitcoin_sha256d.cl",
    ]
    existing = [path for path in candidates if path.is_file()]
    if not existing:
        fail("canonical bitcoin_sha256d.cl kernel is missing")
    digests = {hashlib.sha256(path.read_bytes()).hexdigest() for path in existing}
    if len(digests) != 1:
        fail("duplicate bitcoin_sha256d.cl kernels diverge")
    print(f"PASS — canonical kernel identity ({next(iter(digests))[:16]})")


def check_python_syntax(files: list[str]) -> None:
    for relative in files:
        if not relative.endswith(".py"):
            continue
        path = ROOT / relative
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        except SyntaxError as exc:
            fail(f"syntax error in {relative}: {exc}")
    print("PASS — every tracked Python file parses")


def check_production_call_graph() -> None:
    miner = (ROOT / "mining" / "production_miner.py").read_text(encoding="utf-8")
    stack = (ROOT / "Intelligence" / "four_layer_stack.py").read_text(encoding="utf-8")
    toe = (ROOT / "toe.py").read_text(encoding="utf-8")
    registry = (ROOT / "Intelligence" / "registry.py").read_text(encoding="utf-8")
    required_miner = (
        "AethelExecutionAdapter",
        "FourLayerMiningStack",
        "PYTHIA_EXECUTION_PATH",
        "mining.subscribe",
        "mining.authorize",
        "mining.notify",
        "mining.submit",
        "_dsha256",
        "reference_digest",
        "certify_work_window",
        "verify_certificate",
        "strict_quantum",
    )
    required_stack = (
        "AethelStore",
        "TensorFoldEngine",
        "TuringLayer",
        "HashPipeline",
        "PYTHIA_HASH_BACKEND",
        "winning_hash",
        "consensus_rule",
        "strict_quantum",
        "PYTHIA_SCORE_ORDER_LIMIT",
        "preordered=True",
        "disabled-large-window",
        "deterministic-turing",
        "ordering_mode_for_window",
        "schedule_fingerprint",
    )
    required_toe = ("strict_quantum_work_certificate", "Intelligence.strict_quantum")
    required_registry = ("strict_quantum_control", "Intelligence.strict_quantum")
    for fragment in required_miner:
        if fragment not in miner:
            fail(f"production miner contract missing: {fragment}")
    for fragment in required_stack:
        if fragment not in stack:
            fail(f"AETHEL stack contract missing: {fragment}")
    for fragment in required_toe:
        if fragment not in toe:
            fail(f"TOE strict contract missing: {fragment}")
    for fragment in required_registry:
        if fragment not in registry:
            fail(f"strict quantum registry contract missing: {fragment}")
    print("PASS — production call graph contracts present")


def main() -> int:
    files = tracked_files()
    check_secret_boundaries(files)
    check_kernel_identity()
    check_python_syntax(files)
    check_production_call_graph()
    print("IRONCLAD REPOSITORY GUARD: GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
