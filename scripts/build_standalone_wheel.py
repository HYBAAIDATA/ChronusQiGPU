#!/usr/bin/env python3
"""Build the dedicated EUCLID enterprise artifact, never the mining umbrella.

Build tools must already be installed. --offline additionally resolves all
runtime dependency wheels only from the supplied wheelhouse. The output is a
platform/Python-specific wheelhouse, not a universal offline bundle.
"""

from __future__ import annotations

import argparse
import ast
from email.parser import BytesParser
import hashlib
import fnmatch
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import zipfile

REPO = Path(__file__).resolve().parent.parent
DIST = REPO / "dist" / "euclid-enterprise"
SEEDS = (
    "euclid",
    "Intelligence",
    "al_haras",
    "hyba_substrate",
    "resonance_intelligence",
    "toe",
    "aethel",
    "lucas",
    "hyba_toe_intelligence",
    "hyba_euclid_intelligence",
    "hyba_mcp",
)
DEPENDENCIES = (
    "numpy>=1.26,<3",
    "PyYAML>=6,<7",
    "cryptography>=46,<51",
    "sympy>=1.12,<2",
    "scipy>=1.11,<2",
    "pydantic>=2,<3",
    "hyba-turing-vqc==1.0.0",
    "hyba-kellogg-tensor==1.0.0",
)
EXTERNAL_ROOTS = {"kellogg", "turing_universal_quantum_computer"}
OWNED_PROJECTS = (
    ("hyba-kellogg-tensor", "packaging/kellogg-tensor"),
    ("hyba-turing-vqc", "turing_universal_quantum_computer"),
)
EXCLUDED = {"tests", "__pycache__", "var", ".git", ".venv", "node_modules"}
SECRET_PATTERNS = (
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    rb"ghp_[A-Za-z0-9]{30,}",
    rb"github_pat_[A-Za-z0-9_]{40,}",
    rb"pypi-AgEI[A-Za-z0-9_-]{20,}",
    rb"AKIA[0-9A-Z]{16}",
)


def sh(args, **kwargs):
    print("$", " ".join(map(str, args)), flush=True)
    return subprocess.run(list(map(str, args)), check=True, text=True, **kwargs)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_commit(expected=None):
    commit = sh(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True).stdout.strip()
    if expected and commit != expected:
        raise RuntimeError(f"source commit mismatch: expected {expected}, found {commit}")
    dirty = sh(
        ["git", "status", "--porcelain", "--untracked-files=normal"], cwd=REPO, capture_output=True
    ).stdout
    if dirty.strip():
        raise RuntimeError("source must be a clean committed checkout")
    return commit


def local_source(name, package_dirs):
    if not name.isidentifier() or name in {"tests", "legacy", "scripts"}:
        return None
    if name in package_dirs:
        candidate = REPO / package_dirs[name]
        if candidate.exists():
            return candidate
    if name == "turing_universal_quantum_computer":
        candidate = REPO / name / name
        if candidate.is_dir():
            return candidate
    for root in (REPO, REPO / "chronus/mla1517_platform/python"):
        directory, module = root / name, root / (name + ".py")
        if (directory / "__init__.py").is_file():
            return directory
        if module.is_file():
            return module
    return None


def imported_roots(path):
    # Include lazy literal imports, including the existing public-export tables.
    tree = ast.parse(path.read_bytes(), filename=str(path))
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            value = node.value
            if re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+", value):
                roots.add(value.split(".")[0])
    return roots


def stage(destination, tracked_files=None):
    destination.mkdir(parents=True, exist_ok=True)
    config = tomllib.loads((REPO / "pyproject.toml").read_text())
    package_dirs = config.get("tool", {}).get("setuptools", {}).get("package-dir", {})
    pending, copied = set(SEEDS) | {"turing_core", "pythia_turing_math"}, set()
    while pending:
        name = min(pending)
        pending.remove(name)
        if name in copied or name in EXTERNAL_ROOTS:
            continue
        source = local_source(name, package_dirs)
        if source is None:
            raise FileNotFoundError(f"required local package/module missing: {name}")
        target = destination / (name if source.is_dir() else name + ".py")
        ignored_patterns = ("*.pyc", "*.pyo", "*.key", ".env", ".env.*", "*.pem", "test_*.py")
        if source.is_dir():
            target.mkdir(parents=True)
            candidates = (
                sorted(
                    REPO / path for path in tracked_files if (REPO / path).is_relative_to(source)
                )
                if tracked_files is not None
                else sorted(source.rglob("*"))
            )
            for path in candidates:
                relative = path.relative_to(source)
                if set(relative.parts) & EXCLUDED or any(
                    fnmatch.fnmatch(part, pattern)
                    for part in relative.parts
                    for pattern in ignored_patterns
                ):
                    continue
                if path.is_symlink():
                    raise ValueError("symlinked source is not accepted in enterprise staging")
                if path.is_file():
                    staged = target / relative
                    staged.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, staged)
            files = sorted(target.rglob("*.py"))
        else:
            if source.is_symlink() or (
                tracked_files is not None
                and source.relative_to(REPO).as_posix() not in tracked_files
            ):
                raise ValueError("source module must be a tracked regular file")
            shutil.copy2(source, target)
            files = [target]
        copied.add(name)
        for path in files:
            for imported in imported_roots(path):
                if (
                    imported not in copied
                    and imported not in EXTERNAL_ROOTS
                    and local_source(imported, package_dirs) is not None
                ):
                    pending.add(imported)
    return sorted(copied)


def inspect_wheel(wheel):
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        metadata = [n for n in names if n.endswith(".dist-info/METADATA")]
        if len(metadata) != 1:
            raise RuntimeError("wheel must have exactly one distribution identity")
        identity = BytesParser().parsebytes(archive.read(metadata[0]))
        if identity["Name"] != "euclid-engine" or identity["Version"] != "1.0.0":
            raise RuntimeError("wrong enterprise distribution")
        for name in names:
            if any(re.search(pattern, archive.read(name)) for pattern in SECRET_PATTERNS):
                raise RuntimeError(f"credential-pattern scan rejected wheel member {name}")
        required = (
            "euclid/runtime.py",
            "Intelligence/capability_fabric.py",
            "euclid/capabilities/empirical_state_bridge.py",
            "euclid/capabilities/empirical_runtime.py",
            "euclid/capabilities/empirical_recovery.py",
            "al_haras/audit.py",
            "aethel/enterprise/lifecycle.py",
            "euclid/_artifact_provenance.json",
        )
        missing = sorted(set(required) - set(names))
        vendored = [n for n in names if n.split("/")[0] in EXTERNAL_ROOTS]
        if missing or vendored or any(set(Path(n).parts) & EXCLUDED for n in names):
            raise RuntimeError(f"wheel inspection rejected missing/forbidden members: {missing}")
        return {name: hashlib.sha256(archive.read(name)).hexdigest() for name in names}


def build_owned_wheels(work, built, tracked):
    """Build actual owner manifests, preserving their monorepo relative mapping.

    Never fetch a same-named owner release from an index or vendor its files into
    EUCLID. The snapshot contains tracked owner inputs only, not ambient files.
    """
    snapshot = work / "owner-source"
    prefixes = ("kellogg/", "packaging/kellogg-tensor/", "turing_universal_quantum_computer/")
    for relative in sorted(tracked):
        path = Path(relative)
        if not relative.startswith(prefixes) or set(path.parts) & EXCLUDED:
            continue
        source, target = REPO / path, snapshot / path
        if source.is_symlink():
            raise ValueError("symlinked owner source is not accepted")
        if source.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    result = {}
    for distribution, project in OWNED_PROJECTS:
        if distribution == "hyba-kellogg-tensor":
            if "LICENSE" not in tracked or (REPO / "LICENSE").is_symlink():
                raise ValueError("tracked repository license required for Kellogg staging")
            shutil.copy2(REPO / "LICENSE", snapshot / project / "LICENSE")
        sh(
            [
                sys.executable,
                "-m",
                "build",
                "--wheel",
                "--no-isolation",
                "--outdir",
                built,
                snapshot / project,
            ],
            cwd=work,
        )
        wheels = list(built.glob(distribution.replace("-", "_") + "-*.whl"))
        if len(wheels) != 1:
            raise RuntimeError(f"expected exactly one freshly built {distribution} wheel")
        wheel = wheels[0]
        with zipfile.ZipFile(wheel) as archive:
            names = archive.namelist()
            metadata = [n for n in names if n.endswith(".dist-info/METADATA")]
            if len(metadata) != 1:
                raise RuntimeError("invalid owner wheel identity")
            identity = BytesParser().parsebytes(archive.read(metadata[0]))
            if identity["Name"] != distribution or identity["Version"] != "1.0.0":
                raise RuntimeError("unexpected owner distribution/version")
            members = {}
            for name in names:
                raw = archive.read(name)
                if any(re.search(pattern, raw) for pattern in SECRET_PATTERNS):
                    raise RuntimeError(f"credential pattern in owner member: {name}")
                if name.endswith(".py"):
                    owner_root = (
                        snapshot if distribution == "hyba-kellogg-tensor" else snapshot / project
                    )
                    source = owner_root / name
                    if not source.is_file() or sha256(source) != hashlib.sha256(raw).hexdigest():
                        raise RuntimeError("owner Python differs from tracked source")
                members[name] = hashlib.sha256(raw).hexdigest()
        result[distribution] = {"wheel": wheel.name, "members": members}
    return result


def reject_wheel_overlaps(wheels):
    owners = {}
    for wheel in wheels:
        with zipfile.ZipFile(wheel) as archive:
            for name in archive.namelist():
                if name.endswith("/") or ".dist-info/" in name:
                    continue
                if name in owners:
                    raise RuntimeError(
                        f"wheel member overlap: {name}: {owners[name]} / {wheel.name}"
                    )
                owners[name] = wheel.name


def stage_and_build(*, expected_commit=None, output_dir=None, offline=False, wheelhouse=None):
    commit = source_commit(expected_commit)
    output = Path(output_dir or DIST).resolve()
    # Never let a later run mistake a previous PASS record for fresh evidence.
    output.mkdir(parents=True, exist_ok=True)
    for name in ("build-manifest.json", "verification.json"):
        (output / name).unlink(missing_ok=True)
    if any(output.glob("*.whl")):
        raise FileExistsError("choose a fresh output directory; existing wheels are never deleted")
    with tempfile.TemporaryDirectory(prefix="euclid-build-") as tmp:
        work = Path(tmp)
        project, source, built = work / "project", work / "project/src", work / "built"
        source.mkdir(parents=True)
        tracked = set(
            sh(["git", "ls-files", "--cached", "-z"], cwd=REPO, capture_output=True).stdout.split(
                "\0"
            )
        ) - {""}
        built.mkdir()
        owned = build_owned_wheels(work, built, tracked)
        modules = stage(source, tracked_files=tracked)
        module_names = sorted(p.stem for p in source.glob("*.py"))
        shutil.copy2(REPO / "LICENSE", project / "LICENSE")
        (project / "README.md").write_text("# EUCLID enterprise verification candidate\n")
        (source / "euclid/_artifact_provenance.json").write_text(
            json.dumps(
                {
                    "schema": "euclid.artifact-provenance/1",
                    "source_commit": commit,
                    "classification": "VERIFICATION_CANDIDATE_NOT_RELEASE_APPROVAL",
                },
                sort_keys=True,
            )
        )
        (project / "pyproject.toml").write_text(
            '[build-system]\nrequires = ["setuptools>=68", "wheel"]\n'
            'build-backend = "setuptools.build_meta"\n[project]\n'
            'name = "euclid-engine"\nversion = "1.0.0"\nrequires-python = ">=3.12"\n'
            'readme = "README.md"\n'
            f"dependencies = {json.dumps(DEPENDENCIES)}\n"
            "[tool.setuptools]\ninclude-package-data = true\n"
            f"py-modules = {json.dumps(module_names)}\n"
            'package-dir = {"" = "src"}\n'
            '[tool.setuptools.packages.find]\nwhere = ["src"]\n'
            'exclude = ["*.tests", "*.tests.*", "tests", "tests.*"]\n'
            '[tool.setuptools.package-data]\n"*" = ["*.json", "*.yaml", "*.yml", "*.toml", '
            '"*.md", "*.cl", "*.h", "py.typed", "**/*.json", "**/*.yaml", "**/*.yml", "**/*.cl", "**/*.h", "skills/**/*"]\n'
        )
        sh(
            [
                sys.executable,
                "-m",
                "build",
                "--wheel",
                "--no-isolation",
                "--outdir",
                built,
                project,
            ],
            cwd=work,
        )
        wheels = list(built.glob("euclid_engine-*.whl"))
        if len(wheels) != 1:
            raise RuntimeError("build did not produce exactly one enterprise wheel")
        members = inspect_wheel(wheels[0])
        source_python = {
            path.relative_to(source).as_posix(): sha256(path)
            for path in sorted(source.rglob("*.py"))
        }
        if any(members.get(name) != digest for name, digest in source_python.items()):
            raise RuntimeError("wheel Python sources differ from committed staged sources")
        owned["euclid-engine"] = {"wheel": wheels[0].name, "members": members}
        reject_wheel_overlaps(sorted(built.glob("*.whl")))
        # Resolve the full declared runtime closure while network is allowed;
        # the actual acceptance installation below will be offline.
        download = [
            sys.executable,
            "-m",
            "pip",
            "download",
            "--only-binary=:all:",
            "--dest",
            built,
            "--find-links",
            built,
        ]
        if offline:
            if wheelhouse is None:
                raise ValueError("--offline requires --wheelhouse")
            download += ["--no-index", "--find-links", Path(wheelhouse).resolve()]
        sh([*download, *(built / item["wheel"] for item in owned.values())], cwd=work)
        reject_wheel_overlaps(sorted(built.glob("*.whl")))
        if source_commit(expected_commit) != commit:
            raise RuntimeError("source changed during build")
        # Only this invocation's freshly built wheelhouse is published.
        for path in built.glob("*.whl"):
            shutil.copy2(path, output / path.name)
        wheel = output / wheels[0].name
        record = {
            "schema": "euclid.enterprise-build/1",
            "source_commit": commit,
            "wheel": wheel.name,
            "wheel_sha256": sha256(wheel),
            "members": members,
            "source_python": source_python,
            "owned_distributions": owned,
            "local_import_roots": modules,
            "dependency_wheels": {p.name: sha256(p) for p in sorted(output.glob("*.whl"))},
            "verifier_sha256": sha256(REPO / "scripts/verify_clean_install.py"),
            "classification": "BUILT_NOT_RUNTIME_VERIFIED",
        }
        (output / "build-manifest.json").write_text(json.dumps(record, indent=2, sort_keys=True))
        print(f"WHEEL={wheel}")
        return wheel


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-commit")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--wheelhouse", type=Path)
    stage_and_build(**vars(parser.parse_args()))
