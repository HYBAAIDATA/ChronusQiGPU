#!/usr/bin/env python3
"""Static and dependency-light startup wiring gate."""
from __future__ import annotations

import ast
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent if Path(__file__).resolve().parent.name == "scripts" else Path(__file__).resolve().parent
CANON = ROOT / "mla1517_platform_v3.4" / "python"
if str(CANON) not in sys.path:
    sys.path.insert(0, str(CANON))

PRODUCTION = (
    CANON / "control_api.py",
    CANON / "mining_runtime.py",
    CANON / "salamander_engine.py",
    ROOT / "main.py",
)
_BANNED_IMPORT_PREFIXES = (
    "Intelligence.agentic_mining",
    "papers.discovery",
    "toe",
)


def main() -> int:
    for path in PRODUCTION:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for name in names:
                if any(
                    name == prefix or name.startswith(prefix + ".")
                    for prefix in _BANNED_IMPORT_PREFIXES
                ):
                    raise SystemExit(
                        f"production module imports segregated research surface {name}: {path}"
                    )

    control = (CANON / "control_api.py").read_text(encoding="utf-8")
    required = (
        "resolve_stratum_identity", "BootLock", "AppendOnlyAudit", "WorkerRecord",
        "HeartbeatReader", "agentic-mining", "salamander", "schema_version",
        "/healthz", "/readyz", "/ready-to-mine", "/metrics",
        "PYTHIA_ALIAS_POLICY", "identity_hmac_status", "fs_selfcheck",
    )
    missing = [fragment for fragment in required if fragment not in control]
    if missing:
        raise SystemExit(f"startup contract missing: {missing}")
    worker = (CANON / "worker_lifecycle.py").read_text(encoding="utf-8")
    runtime = (CANON / "mining_runtime.py").read_text(encoding="utf-8")
    if "HEARTBEAT_STRUCT" not in worker or "compare_digest" not in worker:
        raise SystemExit("heartbeat authentication contract missing")
    if 'PYTHIA_DIR_FSYNC_POLICY", "STRICT"' not in worker:
        raise SystemExit("strict fsync code default missing")
    if "PYTHIA_POOL_PROFILE" not in runtime:
        raise SystemExit("runtime pool profile selection missing")
    if "docker.sock" in control:
        raise SystemExit("control plane must not mount docker.sock")
    for path in PRODUCTION:
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
    print("STARTUP CONTRACT: GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
