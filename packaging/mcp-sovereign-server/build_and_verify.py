#!/usr/bin/env python3
"""Build and verify standalone hyba-mcp-sovereign-server 1.0.0 artefacts.

Artefact-first, like KELLOGG's script:

    stage only what MCP sovereign-server owns → build wheel + sdist → twine check
    → inspect the wheel boundary + secret scan
    → clean venv: install the exact hyba-mcp-sovereign-server wheel
      → import hyba_mcp, exercise tools/list + tools/call lucas
      → verify Cassini invariants: L15=1364 (Cassini -4), L20=15127 (Cassini +4)
    → rebuild a wheel from the sdist and verify it the same way
    → machine-readable evidence in packaging/mcp-sovereign-server/dist/

Nothing is published. ``publishable`` stays false while any owner decision
in OWNER_DECISIONS.md is open.

Usage: python packaging/mcp-sovereign-server/build_and_verify.py
       (extra --python interpreters re-run the installed check on the
       same artefacts for cross-version evidence)
"""

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
DIST = HERE / "dist"
REPOSITORY = "PhiEnterprise1/EuclidPhiEnterprise"
PRODUCT = "hyba-mcp-sovereign-server"
VERSION = "1.0.0"

# The sovereign MCP does NOT vendor these namespaces into the wheel.
_EXCLUDED = (
    "aethel",
    "chronus",
    "euclid",
    "Intelligence",
    "mining",
    "toe",
    "turing_universal_quantum_computer",
)

# Cassini invariant verification targets: L_n with Cassini index
_LUCAS_Cassini_CHECKS = (
    {"n": 15, "expected_L": 1364, "expected_cassini": -4, "desc": "L15 = 1364 (Cassini: -4)"},
    {"n": 20, "expected_L": 15127, "expected_cassini": 4, "desc": "L20 = 15127 (Cassini: +4)"},
)
def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "UNAVAILABLE"

def _secret_scan(wheel_path: Path, sdist_path: Path) -> list[dict[str, Any]]:
    """Scan built archives for secret patterns (no third-party scanners)."""
    findings: list[dict[str, Any]] = []
    patterns = {
        "private_key": rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
        "github_pat": rb"ghp_[A-Za-z0-9]{30,}",
        "github_token": rb"github_pat_[A-Za-z0-9_]{40,}",
        "pypi_token": rb"pypi-AgEI[A-Za-z0-9_-]{20,}",
        "aws_key": rb"AKIA[0-9A-Z]{16}",
    }
    for archive in [wheel_path, sdist_path]:
        data = archive.read_bytes()
        for name, pattern in patterns.items():
            matches = pattern.findall(data)
            if matches:
                findings.append(
                    {
                        "archive": archive.name,
                        "pattern": name,
                        "count": len(matches),
                        "snippet": str(matches[0])[:80],
                    }
                )
    return findings