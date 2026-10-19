"""Qualify the exact wheel and sdist in separate external environments.

Requires uv on PATH and locked build/test tools in this interpreter. Never
publishes, approves a release, edits the checkout, or trusts a supplied commit.
"""

from __future__ import annotations
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
from time import perf_counter
from uuid import uuid4
import zipfile

PROJECT = Path(__file__).resolve().parents[1]


def file_hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def wheel_content(path: Path) -> dict[str, str]:
    with zipfile.ZipFile(path) as archive:
        return {
            name: sha256(archive.read(name)).hexdigest()
            for name in archive.namelist()
            if not name.endswith("/")
        }


def container_metadata(path: Path) -> dict:
    with zipfile.ZipFile(path) as archive:
        return {
            item.filename: {
                "date_time": item.date_time,
                "external_attr": item.external_attr,
                "compress_type": item.compress_type,
                "create_system": item.create_system,
                "extra_hex": item.extra.hex(),
                "comment_hex": item.comment.hex(),
            }
            for item in archive.infolist()
        }


def unpack_sdist(path: Path, destination: Path) -> Path:
    with tarfile.open(path) as archive:
        for entry in archive:
            target = destination / entry.name
            if not target.resolve().is_relative_to(destination.resolve()):
                raise ValueError("Unsafe sdist path")
            if entry.isdir():
                target.mkdir(parents=True, exist_ok=True)
            elif entry.isfile():
                target.parent.mkdir(parents=True, exist_ok=True)
                stream = archive.extractfile(entry)
                if stream is None:
                    raise ValueError("Unreadable sdist member")
                with stream, target.open("wb") as output:
                    shutil.copyfileobj(stream, output)
            else:
                raise ValueError("Links and special files are not allowed in qualification sdists")
    roots = list(destination.iterdir())
    if len(roots) != 1 or not roots[0].is_dir():
        raise ValueError("Expected one sdist root")
    return roots[0]


def one(directory: Path, pattern: str) -> Path:
    matches = list(directory.glob(pattern))
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one artifact matching {pattern}")
    return matches[0].resolve()


def qualify(dist_dir: Path, requirements: Path, output: Path) -> Path:
    output.mkdir(parents=True, exist_ok=True)
    report_path = output / ("artifact_qualification_" + uuid4().hex + ".json")
    report = {
        "schema": "turing.artifact_qualification.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "running",
        "release_approved": False,
        "python": sys.version,
        "source_date_epoch": os.environ.get("SOURCE_DATE_EPOCH"),
        "lock_sha256": file_hash(PROJECT / "uv.lock"),
        "requirements_sha256": file_hash(requirements),
        "steps": [],
    }
    # Read observed source identity; this is not a parameter a caller can invent.
    from run_experiment import source_identity

    report["source"] = source_identity(PROJECT.parent)
    report["evidence_scope"] = (
        "commit_bound_candidate" if report["source"]["state"] == "clean" else "development_only"
    )
    failure = None

    def command(label, args, cwd):
        before = perf_counter()
        result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=180)
        report["steps"].append(
            {
                "name": label,
                "exit_code": result.returncode,
                "duration_seconds": perf_counter() - before,
            }
        )
        # Do not persist subprocess output: installers/consumers can expose
        # private index URLs or user payloads. JUnit is separately reviewed.
        if result.returncode:
            raise RuntimeError(
                f"{label} failed with exit code {result.returncode}; rerun that step locally for private diagnostics"
            )

    try:
        wheel = one(dist_dir, "hyba_turing_vqc-*.whl")
        sdist = one(dist_dir, "hyba_turing_vqc-*.tar.gz")
        dependency = one(dist_dir, "hyba_kellogg_tensor-*.whl")
        report["artifacts"] = [
            {"filename": p.name, "sha256": file_hash(p)} for p in (wheel, sdist, dependency)
        ]
        with tempfile.TemporaryDirectory(prefix="turing-artifact-qualification-") as temporary:
            work = Path(temporary)
            extracted = unpack_sdist(sdist, work / "source")
            for needed in (
                "uv.lock",
                "CITATION.cff",
                "mypy.ini",
                "TURING-qualification.md",
                "docs/mathematical-contracts.md",
                "experiments/run_experiment.py",
            ):
                if not (extracted / needed).is_file():
                    raise ValueError("sdist missing required qualification asset: " + needed)
            rebuilt_dir = work / "rebuilt"
            command(
                "build-wheel-from-sdist",
                [
                    sys.executable,
                    "-m",
                    "build",
                    "--wheel",
                    "--no-isolation",
                    str(extracted),
                    "--outdir",
                    str(rebuilt_dir),
                ],
                work,
            )
            rebuilt = one(rebuilt_dir, "hyba_turing_vqc-*.whl")
            report["sdist_rebuilt_wheel_sha256"] = file_hash(rebuilt)
            report["wheel_sdist_normalized_file_parity"] = wheel_content(wheel) == wheel_content(
                rebuilt
            )
            report["wheel_sdist_byte_identity"] = file_hash(wheel) == file_hash(rebuilt)
            original_meta, rebuilt_meta = container_metadata(wheel), container_metadata(rebuilt)
            report["wheel_container_metadata_differences"] = {
                name: [
                    key
                    for key in original_meta[name]
                    if original_meta[name][key] != rebuilt_meta.get(name, {}).get(key)
                ]
                for name in original_meta
                if original_meta[name] != rebuilt_meta.get(name)
            }
            if not report["wheel_sdist_normalized_file_parity"]:
                raise ValueError("Wheel rebuilt from sdist has different package/metadata contents")
            for label, candidate in [("wheel", wheel), ("sdist", rebuilt)]:
                sandbox = work / label
                sandbox.mkdir()
                environment = sandbox / "environment"
                python = environment / (
                    "Scripts/python.exe" if sys.platform == "win32" else "bin/python"
                )
                command(
                    label + "-venv",
                    ["uv", "venv", "--python", sys.executable, str(environment)],
                    sandbox,
                )
                command(
                    label + "-locked-dependencies",
                    [
                        "uv",
                        "pip",
                        "install",
                        "--python",
                        str(python),
                        "-r",
                        str(requirements.resolve()),
                    ],
                    sandbox,
                )
                command(
                    label + "-install",
                    [
                        "uv",
                        "pip",
                        "install",
                        "--python",
                        str(python),
                        "--no-deps",
                        str(dependency),
                        str(candidate),
                    ],
                    sandbox,
                )
                command(
                    label + "-dependency-consistency",
                    ["uv", "pip", "check", "--python", str(python)],
                    sandbox,
                )
                tests = sandbox / "tests"
                tests.mkdir()
                # Run consumers from the released source distribution, not an
                # independently edited test tree or a repository import path.
                for name in ("test_public_api_dropin.py", "test_release_qualification.py"):
                    shutil.copy2(extracted / "tests" / name, tests / name)
                junit = output.resolve() / (report_path.stem + "-" + label + ".xml")
                command(
                    label + "-installed-consumer-tests",
                    [
                        str(python),
                        "-I",
                        "-m",
                        "pytest",
                        str(tests),
                        "-q",
                        "--junitxml=" + str(junit),
                    ],
                    sandbox,
                )
                report.setdefault("consumer_reports", []).append(
                    {"target": label, "junit_file": junit.name, "sha256": file_hash(junit)}
                )
                example = sandbox / "consumer.py"
                shutil.copy2(extracted / "examples/turing_pipeline.py", example)
                command(label + "-installed-example", [str(python), "-I", str(example)], sandbox)
        report["status"] = "passed"
    except Exception as error:
        failure = error
        report["status"] = "failed"
        report["failure_type"] = type(error).__name__
        report["failure_summary"] = (
            str(error)
            if isinstance(error, (ValueError, RuntimeError))
            else "Qualification infrastructure failed; inspect privately"
        )
    report["manifest_digest"] = sha256(
        json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    with report_path.open("x") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    if failure:
        raise RuntimeError(
            "Artifact qualification failed; report: " + str(report_path)
        ) from failure
    return report_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist-dir", type=Path, required=True)
    parser.add_argument("--requirements", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(qualify(args.dist_dir, args.requirements, args.output))
