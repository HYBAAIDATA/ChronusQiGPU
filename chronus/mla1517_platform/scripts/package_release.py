#!/usr/bin/env python3
"""Build a complete, secret-free PYTHIA production source bundle."""
from __future__ import annotations

import hashlib
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
REQUIRED = (
    "README.md", "Makefile", "pyproject.toml", "build_manifest.json",
    "python/control_api.py", "python/mining_runtime.py",
    "../mla1517/mining/stratum_adapter.py",
    "../mla1517/mining/turing_adapter.py", "../mla1517/mining/toe_adapter.py",
    "host", "kernels", "rtl", "Dockerfile.production",
)
EXCLUDED_PARTS = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", "dist", "results", "logs", ".venv", "venv", "node_modules"}
SECRET_NAMES = re.compile(r"(^|[._-])(env|secret|token|credential|password|apikey)([._-]|$)", re.I)


def included(path: Path) -> bool:
    return not any(part in EXCLUDED_PARTS for part in path.parts)


def main() -> int:
    missing = [name for name in REQUIRED if not (ROOT / name).exists()]
    if missing:
        raise SystemExit("missing release inputs: " + ", ".join(missing))
    RESULTS.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive = RESULTS / f"pythia-production-mining-{stamp}.zip"
    entries = []
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(ROOT.rglob("*")):
            if not path.is_file() or not included(path):
                continue
            relative = path.relative_to(ROOT)
            if SECRET_NAMES.search(relative.name) and relative.name != ".env.example":
                raise SystemExit(f"refusing to package secret-looking file: {relative}")
            data = path.read_bytes()
            archive_path = relative.as_posix()
            bundle.writestr(archive_path, data)
            entries.append({"path": archive_path, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        package = ROOT.parent / "mla1517"
        for path in sorted(package.rglob("*")):
            if not path.is_file() or not included(path):
                continue
            relative = path.relative_to(package)
            data = path.read_bytes()
            archive_path = (Path("python/chronus/mla1517") / relative).as_posix()
            bundle.writestr(archive_path, data)
            entries.append({"path": archive_path, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    manifest = {
        "product": "PYTHIA", "bundle": archive.name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_tree": "chronus/mla1517_platform", "files": entries,
        "hardware_execution": "not measured by packaging",
        "pool_acceptance": "not measured by packaging", "production_ready": False,
        "reason": "Packaging proves bundle completeness only; runtime and physical gates must pass separately.",
    }
    (RESULTS / "release_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(archive.suffix + ".sha256").write_text(f"{checksum}  {archive.name}\n", encoding="utf-8")
    print(json.dumps({"archive": str(archive), "sha256": checksum, "files": len(entries)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
