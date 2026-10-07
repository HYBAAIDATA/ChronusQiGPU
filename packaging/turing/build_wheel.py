"""Build and inspect the standalone TURING 1.0.0 wheel and sdist.

The build is staged from the TURING source tree only.  It validates PyPI
metadata, records archive manifests and SHA-256 digests, and fails on obvious
secret/local-path leakage.  Clean-install and cross-version execution are
performed by packaging/verify_release_candidates.py against these exact
artefacts.
"""

from __future__ import annotations

import email
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
SOURCE = REPO / "turing_universal_quantum_computer"
DIST = HERE / "dist"
PRODUCT = "turing-universal-quantum-computer"
VERSION = "1.0.0"
REPOSITORY = "QuantumPhiRedux/PhiMiner"

_SECRET_PATTERNS = (
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"ghp_[A-Za-z0-9]{30,}"),
    re.compile(rb"github_pat_[A-Za-z0-9_]{40,}"),
    re.compile(rb"pypi-AgEI[A-Za-z0-9_-]{20,}"),
    re.compile(rb"AKIA[0-9A-Z]{16}"),
)
_FORBIDDEN_NAMES = ("/.git/", "/__pycache__/", ".pyc", ".pyo", ".pypirc", "/.env")


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


def stage(root: Path) -> Path:
    staged = root / "src"
    staged.mkdir(parents=True)
    for name in ("pyproject.toml", "README.md", "LICENSE"):
        shutil.copy2(SOURCE / name, staged / name)
    shutil.copytree(
        SOURCE / "turing_universal_quantum_computer",
        staged / "turing_universal_quantum_computer",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )
    return staged


def members(path: Path):
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as zf:
            for info in zf.infolist():
                if not info.is_dir():
                    yield info.filename, zf.read(info)
        return
    with tarfile.open(path, "r:*") as tf:
        for info in tf.getmembers():
            if info.isfile():
                fh = tf.extractfile(info)
                if fh is not None:
                    yield info.name, fh.read()


def scan(path: Path) -> dict:
    local = {
        str(REPO).encode(),
        str(REPO).replace("\\", "/").encode(),
    }
    findings = []
    names = []
    for name, data in members(path):
        names.append(name)
        if any(part in "/" + name for part in _FORBIDDEN_NAMES):
            findings.append({"file": name, "reason": "forbidden path"})
        for pattern in _SECRET_PATTERNS:
            if pattern.search(data):
                findings.append({"file": name, "reason": "secret pattern"})
        if any(token and token in data for token in local):
            findings.append({"file": name, "reason": "local repository path embedded"})
    if findings:
        raise RuntimeError(f"{path.name} failed release scan: {findings[:10]}")
    return {
        "file": path.name,
        "sha256": sha256(path),
        "files": sorted(names),
        "file_count": len(names),
        "findings": findings,
    }


def inspect_wheel(wheel: Path) -> dict:
    files = dict(members(wheel))
    names = sorted(files)
    dist_infos = {name.split("/", 1)[0] for name in names if ".dist-info/" in name}
    if len(dist_infos) != 1:
        raise RuntimeError(f"expected one dist-info directory, got {sorted(dist_infos)}")
    dist_info = next(iter(dist_infos))
    leaked = [
        name for name in names
        if not (
            name.startswith("turing_universal_quantum_computer/")
            or name.startswith(dist_info + "/")
        )
    ]
    if leaked:
        raise RuntimeError(f"wheel leaks outside TURING boundary: {leaked[:20]}")
    required = {
        "turing_universal_quantum_computer/__init__.py",
        "turing_universal_quantum_computer/product_registry.py",
        "turing_universal_quantum_computer/certificates.py",
        "turing_universal_quantum_computer/pipeline.py",
        "turing_universal_quantum_computer/backends/mps.py",
        "turing_universal_quantum_computer/py.typed",
    }
    missing = sorted(required - set(names))
    if missing:
        raise RuntimeError(f"wheel missing required files: {missing}")

    metadata_name = dist_info + "/METADATA"
    entry_name = dist_info + "/entry_points.txt"
    if metadata_name not in files or entry_name not in files:
        raise RuntimeError("wheel metadata or console entry-point metadata is missing")
    metadata = email.message_from_bytes(files[metadata_name])
    license_value = metadata.get("License-Expression") or metadata.get("License")
    requires = metadata.get_all("Requires-Dist") or []
    project_urls = metadata.get_all("Project-URL") or []
    checks = {
        "name": metadata.get("Name") == PRODUCT,
        "version": metadata.get("Version") == VERSION,
        "author": metadata.get("Author") == "HYBA Software Limited",
        "license": license_value == "MIT",
        "requires_python": metadata.get("Requires-Python") == ">=3.11",
        "kellogg_dependency": any(r.lower().startswith("kellogg-tensor") for r in requires),
        "canonical_repository": any(
            "https://github.com/QuantumPhiRedux/PhiMiner" in url for url in project_urls
        ),
        "old_repository_absent": not any("QuantumPhi2/PhiMiner" in url for url in project_urls),
        "console_entry_point": (
            "turing-vqc = turing_universal_quantum_computer.console:main"
            in files[entry_name].decode("utf-8")
        ),
    }
    failed = sorted(name for name, ok in checks.items() if not ok)
    if failed:
        raise RuntimeError(f"wheel metadata checks failed: {failed}")
    return {"metadata_checks": checks, "license": license_value, "requires": requires, "project_urls": project_urls}


def main() -> int:
    shutil.rmtree(DIST, ignore_errors=True)
    DIST.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix="turing-build-") as tmp:
        staged = stage(Path(tmp))
        subprocess.run(
            [
                sys.executable,
                "-m",
                "build",
                "--wheel",
                "--sdist",
                "--outdir",
                str(DIST),
                str(staged),
            ],
            check=True,
        )

    wheels = sorted(DIST.glob(f"turing_universal_quantum_computer-{VERSION}-*.whl"))
    sdists = sorted(DIST.glob(f"turing_universal_quantum_computer-{VERSION}.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise RuntimeError(f"expected one wheel and one sdist; got {wheels}, {sdists}")
    wheel, sdist = wheels[0], sdists[0]

    subprocess.run([sys.executable, "-m", "twine", "check", str(wheel), str(sdist)], check=True)
    wheel_scan = scan(wheel)
    sdist_scan = scan(sdist)
    metadata = inspect_wheel(wheel)

    (DIST / "wheel-manifest.json").write_text(
        json.dumps(wheel_scan, indent=2, sort_keys=True), encoding="utf-8"
    )
    (DIST / "sdist-manifest.json").write_text(
        json.dumps(sdist_scan, indent=2, sort_keys=True), encoding="utf-8"
    )
    verdict = {
        "product": PRODUCT,
        "version": VERSION,
        "repository": REPOSITORY,
        "git_sha": git_sha(),
        "wheel": {"file": wheel.name, "sha256": wheel_scan["sha256"]},
        "sdist": {"file": sdist.name, "sha256": sdist_scan["sha256"]},
        "wheel_built": True,
        "sdist_built": True,
        "metadata_valid": True,
        "artifact_secret_scan_passed": True,
        "package_boundary_archive_verified": True,
        "metadata": metadata,
        "published": False,
    }
    (DIST / "artifact-build.json").write_text(
        json.dumps(verdict, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(verdict, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
