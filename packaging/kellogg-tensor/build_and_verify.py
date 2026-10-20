"""Build and verify the standalone hyba-kellogg-tensor 1.0.0 release artefacts.

This script is deliberately artefact-first. It stages only the public Kellogg
package, builds wheel + sdist, validates metadata, inspects and secret-scans the
archives, installs the wheel outside the repository, imports every shipped
module, exercises the public verification surface, and proves the sdist can
rebuild a wheel that passes the same installed-package checks.

Nothing is published.
"""

from __future__ import annotations

import hashlib
import json
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import venv
import zipfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
DIST = HERE / "dist"
PRODUCT = "hyba-kellogg-tensor"
VERSION = "1.0.0"
REPOSITORY = "PhiEnterprise1/EuclidPhiEnterprise"

_REQUIRED_PUBLIC = (
    "attest",
    "verify_attestation",
    "verify_version",
    "ProofBoundary",
    "certify",
    "verify_certificate",
    "ResidentCustody",
    "default_custody",
    "REGISTRY",
    "verify_registry",
)
_FORBIDDEN_TOP_LEVEL = {
    "aethel",
    "chronus",
    "euclid",
    "Intelligence",
    "mining",
    "toe",
    "turing_core",
    "turing_universal_quantum_computer",
}
_SECRET_PATTERNS = (
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"ghp_[A-Za-z0-9]{30,}"),
    re.compile(rb"github_pat_[A-Za-z0-9_]{40,}"),
    re.compile(rb"pypi-AgEI[A-Za-z0-9_-]{20,}"),
    re.compile(rb"AKIA[0-9A-Z]{16}"),
)
_BAD_NAME_PARTS = (
    "/.git/",
    "/__pycache__/",
    ".pyc",
    ".pyo",
    ".pypirc",
    ".env",
    "/tests/",
    "/evidence/",
    "/benchmarks/",
)


def sh(cmd: list[Any], **kw: Any) -> subprocess.CompletedProcess[str]:
    print("$", " ".join(str(c) for c in cmd), flush=True)
    return subprocess.run([str(c) for c in cmd], check=True, text=True, **kw)


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
    src = root / "src"
    src.mkdir(parents=True)
    shutil.copytree(
        REPO / "kellogg",
        src / "kellogg",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )
    for name in ("pyproject.toml", "README.md"):
        shutil.copy2(HERE / name, src / name)
    shutil.copy2(REPO / "LICENSE", src / "LICENSE")
    # The live manifest maps back to the monorepo. The staged source and its
    # sdist must instead resolve Kellogg inside their own self-contained tree.
    manifest = src / "pyproject.toml"
    text = manifest.read_text(encoding="utf-8")
    original = 'package-dir = {"kellogg" = "../../kellogg"}'
    if text.count(original) != 1:
        raise RuntimeError("Kellogg package-dir contract changed; review staging")
    manifest.write_text(text.replace(original, 'package-dir = {"kellogg" = "kellogg"}'),
                        encoding="utf-8")
    return src


def _artifact_names(archive: Path) -> list[str]:
    if archive.suffix == ".whl":
        with zipfile.ZipFile(archive) as zf:
            return zf.namelist()
    with tarfile.open(archive, "r:*") as tf:
        return [m.name for m in tf.getmembers()]
    

def _artifact_members(archive: Path):
    if archive.suffix == ".whl":
        with zipfile.ZipFile(archive) as zf:
            for info in zf.infolist():
                if not info.is_dir():
                    yield info.filename, zf.read(info)
        return
    with tarfile.open(archive, "r:*") as tf:
        for member in tf.getmembers():
            if member.isfile():
                fh = tf.extractfile(member)
                if fh is not None:
                    yield member.name, fh.read()


def inspect_wheel(wheel: Path) -> dict[str, Any]:
    names = _artifact_names(wheel)
    dist_info_prefixes = {
        name.split("/", 1)[0] + "/"
        for name in names
        if ".dist-info/" in name
    }
    if len(dist_info_prefixes) != 1:
        raise RuntimeError(f"expected one dist-info directory, found {sorted(dist_info_prefixes)}")
    dist_info = next(iter(dist_info_prefixes))
    unexpected = [
        name
        for name in names
        if not (name.startswith("kellogg/") or name.startswith(dist_info))
    ]
    if unexpected:
        raise RuntimeError(f"wheel contains files outside Kellogg boundary: {unexpected[:20]}")
    required = {
        "kellogg/__init__.py",
        "kellogg/py.typed",
        "kellogg/CAPABILITY_MANIFEST.json",
    }
    missing = sorted(required - set(names))
    if missing:
        raise RuntimeError(f"wheel is missing required package data: {missing}")
    license_names = [
        name for name in names
        if name.startswith(dist_info) and name.upper().endswith("/LICENSE")
    ]
    if not license_names:
        raise RuntimeError("wheel is missing the repository licence")
    bad = [name for name in names if any(part in "/" + name for part in _BAD_NAME_PARTS)]
    if bad:
        raise RuntimeError(f"wheel contains release-forbidden paths: {bad[:20]}")
    manifest = {
        "product": PRODUCT,
        "version": VERSION,
        "wheel": wheel.name,
        "sha256": sha256(wheel),
        "files": sorted(names),
        "file_count": len(names),
    }
    (DIST / "wheel-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    return manifest


def scan_artifact(archive: Path) -> dict[str, Any]:
    repo_tokens = {
        str(REPO).encode("utf-8", errors="ignore"),
        str(REPO).replace("\\", "/").encode("utf-8", errors="ignore"),
    }
    findings: list[dict[str, str]] = []
    for name, data in _artifact_members(archive):
        if any(part in "/" + name for part in _BAD_NAME_PARTS):
            findings.append({"file": name, "reason": "forbidden path"})
        for pattern in _SECRET_PATTERNS:
            if pattern.search(data):
                findings.append({"file": name, "reason": f"secret pattern {pattern.pattern!r}"})
        if any(token and token in data for token in repo_tokens):
            findings.append({"file": name, "reason": "local repository path embedded"})
    if findings:
        raise RuntimeError(f"release artefact scan failed: {findings[:10]}")
    return {"artifact": archive.name, "sha256": sha256(archive), "findings": []}


_INSTALLED_CHECK = r"""
import importlib
import importlib.metadata
import json
import pkgutil
import sys

import kellogg

EXPECTED_VERSION = "1.0.0"
REQUIRED = (
    "attest", "verify_attestation", "verify_version", "ProofBoundary",
    "certify", "verify_certificate",
    "ResidentCustody", "default_custody", "REGISTRY", "verify_registry",
)
FORBIDDEN = {
    "aethel", "chronus", "euclid", "Intelligence", "mining", "toe",
    "turing_core", "turing_universal_quantum_computer",
}

assert "site-packages" in str(kellogg.__file__).replace("\\", "/"), kellogg.__file__
assert kellogg.__version__ == EXPECTED_VERSION, kellogg.__version__

metadata = importlib.metadata.metadata("hyba-kellogg-tensor")
assert metadata["Name"] == "hyba-kellogg-tensor"
assert metadata["Version"] == EXPECTED_VERSION
assert metadata["Requires-Python"] == ">=3.11"
assert metadata["Author"] == "HYBA Software Limited"
license_value = metadata.get("License-Expression") or metadata.get("License")
assert license_value == "MIT", license_value
requires = importlib.metadata.requires("hyba-kellogg-tensor") or []
hard_requires = [r for r in requires if "extra ==" not in r]
assert len(hard_requires) == 1 and hard_requires[0].lower().startswith("numpy"), hard_requires
project_urls = metadata.get_all("Project-URL") or []
assert any("https://github.com/PhiEnterprise1/EuclidPhiEnterprise" in u for u in project_urls), project_urls
assert not any(old in u for old in ("QuantumPhi2/PhiMiner", "QuantumPhiRedux/PhiMiner")
               for u in project_urls), project_urls

mods = sorted(m.name for m in pkgutil.iter_modules(kellogg.__path__))
failed = {}
for module in mods:
    try:
        importlib.import_module("kellogg." + module)
    except Exception as exc:
        failed[module] = f"{type(exc).__name__}: {exc}"
if failed:
    raise AssertionError(f"module import failures: {failed}")

missing = [name for name in REQUIRED if not hasattr(kellogg, name)]
if missing:
    raise AssertionError(f"missing public API: {missing}")

from importlib.resources import files
manifest = json.loads(files("kellogg").joinpath("CAPABILITY_MANIFEST.json").read_text())
assert manifest["distribution"] == "hyba-kellogg-tensor"
assert manifest["version"] == EXPECTED_VERSION
assert manifest["hard_dependencies"] == ["numpy"]

from kellogg.spec import verify_registry
registry = verify_registry()
assert registry["ok"], registry["problems"]

from kellogg.exact_tensor import canonical_digest
fixture = {
    "schema": "kellogg.release-fixture/v1",
    "version": EXPECTED_VERSION,
    "integers": [0, 1, 2, 3, 5, 8, 13],
    "nested": {"plane": "exact", "field": "Q(zeta8)"},
}
fixture_digest = canonical_digest(fixture)

from kellogg.certificate import (
    CertificateError,
    certificate_from_dict,
    certify,
    cex,
    verify_certificate,
    verify_merkle_proof,
    merkle_proof,
    merkle_root,
)
cert = certify(
    "release_fixture",
    "Q(zeta8)",
    "software",
    "0" * 64,
    fixture_digest,
    parameters={"count": 7},
    invariants={"exact": True},
)
assert verify_certificate(cert) is True
assert certificate_from_dict(cert.to_dict()).digest == cert.digest
try:
    cex({"diagnostic": 0.5})
except CertificateError:
    pass
else:
    raise AssertionError("CEX silently accepted a float as exact")

leaves = [fixture_digest, cert.digest, "1" * 64]
root = merkle_root(leaves)
assert verify_merkle_proof(leaves[1], merkle_proof(leaves, 1), root)
assert not verify_merkle_proof(leaves[1], merkle_proof(leaves, 1), "f" * 64)

from kellogg.attest import AttestationError, attest, verify_attestation
attestation = attest(fixture)
assert verify_attestation(fixture, attestation) is True
tampered = dict(fixture)
tampered["integers"] = [0, 1, 2, 4]
try:
    verify_attestation(tampered, attestation)
except AttestationError:
    pass
else:
    raise AssertionError("tampered attestation payload verified")

from kellogg.custody import ResidentCustody
from kellogg.cyclotomic import ONE8, Q8
from kellogg.exact_network import ExactTensorTrain, ghz_circuit
psi = ghz_circuit(8, custody=ResidentCustody())
assert psi.norm2() == ONE8
assert psi.ledger.verify_chain()
vals = [Q8(i) for i in range(8)]
tt = ExactTensorTrain.from_dense(vals, [2, 2, 2], custody=ResidentCustody())
assert tt.to_dense() == vals

from kellogg.benchmark import BENCHMARKS, run
benchmarks = {}
for bid, (axis, _) in BENCHMARKS.items():
    if axis in ("correctness", "meta") and bid != "cross_version_digest":
        result = run(bid, quick=True)
        benchmarks[bid] = result["passed"]
        if result["passed"] is not True:
            raise AssertionError(f"installed benchmark {bid} failed: {result.get('error') or result['result']}")

siblings_loaded = sorted(name for name in FORBIDDEN if name in sys.modules)
if siblings_loaded:
    raise AssertionError(f"standalone import loaded sibling products: {siblings_loaded}")

print(json.dumps({
    "product": "hyba-kellogg-tensor",
    "version": kellogg.__version__,
    "python": sys.version.split()[0],
    "modules": mods,
    "module_count": len(mods),
    "registry_ok": registry["ok"],
    "registry_items": registry["items"],
    "metadata": {
        "name": metadata["Name"],
        "version": metadata["Version"],
        "requires_python": metadata["Requires-Python"],
        "license": license_value,
        "project_urls": project_urls,
        "hard_requires": hard_requires,
    },
    "canonical_digest": fixture_digest,
    "certificate_digest": cert.digest,
    "attestation_digest": attestation["attestation_digest"],
    "benchmarks": benchmarks,
    "siblings_loaded": siblings_loaded,
}, sort_keys=True))
"""


def _python_in_venv(env_dir: Path) -> Path:
    return env_dir / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def installed_check(wheel: Path, workdir: Path, label: str) -> dict[str, Any]:
    env_dir = workdir / "venv"
    venv.EnvBuilder(with_pip=True, clear=True).create(env_dir)
    py = _python_in_venv(env_dir)
    sh([py, "-m", "pip", "install", "-q", "--disable-pip-version-check", str(wheel)])
    out = sh([py, "-I", "-c", _INSTALLED_CHECK], cwd=workdir, capture_output=True)
    record = json.loads(out.stdout.strip().splitlines()[-1])
    record["label"] = label
    record["import_file"] = subprocess.check_output(
        [str(py), "-I", "-c", "import kellogg; print(kellogg.__file__)"],
        cwd=workdir,
        text=True,
    ).strip()
    return record


def rebuild_from_sdist(sdist: Path, root: Path) -> tuple[Path, dict[str, Any]]:
    extract = root / "sdist"
    extract.mkdir()
    with tarfile.open(sdist, "r:*") as tf:
        tf.extractall(extract, filter="data")
    roots = [p for p in extract.iterdir() if p.is_dir()]
    if len(roots) != 1:
        raise RuntimeError(f"sdist extraction produced unexpected roots: {roots}")
    build_env = root / "build-venv"
    venv.EnvBuilder(with_pip=True, clear=True).create(build_env)
    py = _python_in_venv(build_env)
    sh([py, "-m", "pip", "install", "-q", "build"])
    rebuilt_dir = root / "rebuilt"
    rebuilt_dir.mkdir()
    sh([py, "-m", "build", "--wheel", "--outdir", rebuilt_dir, roots[0]])
    wheels = sorted(rebuilt_dir.glob("hyba_kellogg_tensor-*.whl"))
    if len(wheels) != 1:
        raise RuntimeError(f"sdist rebuild produced {len(wheels)} wheels")
    with tempfile.TemporaryDirectory(prefix="kellogg-sdist-install-") as tmp:
        record = installed_check(wheels[0], Path(tmp), "sdist-rebuilt-wheel")
    return wheels[0], record


def main() -> int:
    if not (REPO / "LICENSE").exists():
        raise RuntimeError("repository LICENSE is missing")
    shutil.rmtree(DIST, ignore_errors=True)
    DIST.mkdir(parents=True)

    with tempfile.TemporaryDirectory(prefix="kellogg-build-") as tmp:
        staged = stage(Path(tmp))
        sh([
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--sdist",
            "--outdir",
            DIST,
            staged,
        ])

    wheels = sorted(DIST.glob(f"hyba_kellogg_tensor-{VERSION}-*.whl"))
    sdists = sorted(DIST.glob(f"hyba_kellogg_tensor-{VERSION}.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise RuntimeError(
            f"expected one wheel and one sdist for {VERSION}; got wheels={wheels}, sdists={sdists}"
        )
    wheel, sdist = wheels[0], sdists[0]

    sh([sys.executable, "-m", "twine", "check", str(wheel), str(sdist)])
    wheel_manifest = inspect_wheel(wheel)
    scans = [scan_artifact(wheel), scan_artifact(sdist)]

    with tempfile.TemporaryDirectory(prefix="kellogg-wheel-install-") as tmp:
        wheel_record = installed_check(wheel, Path(tmp), "release-wheel")

    with tempfile.TemporaryDirectory(prefix="kellogg-sdist-rebuild-") as tmp:
        rebuilt, sdist_record = rebuild_from_sdist(sdist, Path(tmp))
        rebuilt_sha = sha256(rebuilt)

    if wheel_record["canonical_digest"] != sdist_record["canonical_digest"]:
        raise RuntimeError("sdist-rebuilt wheel changed the canonical deterministic fixture")
    if wheel_record["certificate_digest"] != sdist_record["certificate_digest"]:
        raise RuntimeError("sdist-rebuilt wheel changed the certificate fixture")
    if wheel_record["attestation_digest"] != sdist_record["attestation_digest"]:
        raise RuntimeError("sdist-rebuilt wheel changed the attestation fixture")

    evidence = {
        "product": PRODUCT,
        "version": VERSION,
        "repository": REPOSITORY,
        "git_sha": git_sha(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "wheel": {"file": wheel.name, "sha256": sha256(wheel)},
        "sdist": {"file": sdist.name, "sha256": sha256(sdist)},
        "rebuilt_wheel_sha256": rebuilt_sha,
        "package_metadata_valid": True,
        "standalone_boundary_verified": True,
        "registry_verified": bool(wheel_record["registry_ok"]),
        "installed_imports_verified": True,
        "public_api_verified": True,
        "attestation_verified": True,
        "certificate_verification_passed": True,
        "wheel_built": True,
        "wheel_clean_install_verified": True,
        "sdist_verified": True,
        "artifact_secret_scan_passed": all(not x["findings"] for x in scans),
        "canonical_digest": wheel_record["canonical_digest"],
        "certificate_digest": wheel_record["certificate_digest"],
        "attestation_digest": wheel_record["attestation_digest"],
        "module_count": wheel_record["module_count"],
        "quick_installed_benchmarks": wheel_record["benchmarks"],
        "wheel_manifest": wheel_manifest,
        "publishable": False,
        "published": False,
        "scope": "artefact verification; full test/benchmark/cross-version release gates run separately",
    }
    (DIST / "artifact-verdict.json").write_text(
        json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8"
    )
    (DIST / "canonical-fixture.json").write_text(
        json.dumps(
            {
                "product": PRODUCT,
                "version": VERSION,
                "git_sha": evidence["git_sha"],
                "python": evidence["python"],
                "canonical_digest": evidence["canonical_digest"],
                "certificate_digest": evidence["certificate_digest"],
                "attestation_digest": evidence["attestation_digest"],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    print(json.dumps(evidence, indent=2, sort_keys=True))
    print("VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
