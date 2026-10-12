"""Uniform, commit-bound file-backed gate result library.

Digests establish integrity, not producer authenticity or production certification.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Callable


class Status(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"
    NOT_RUN = "NOT_RUN"
    ERROR = "ERROR"


@dataclass(frozen=True)
class Outcome:
    status: Status
    reason: str
    artifacts: tuple[str, ...] = ()


@dataclass(frozen=True)
class GateResult:
    gate: str
    status: Status
    reason: str
    artifacts: tuple[str, ...]
    started_at: int
    finished_at: int
    source_commit: str = ""
    execution: str = ""
    artifact_digests: dict[str, str] | None = None
    evidence_digest: str = ""
    schema_version: int = 2


def canonical_digest(payload: dict) -> str:
    body = {k: v for k, v in payload.items() if k != "evidence_digest"}
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def current_commit(root: Path) -> str:
    proc = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    )
    sha = proc.stdout.strip()
    if re.fullmatch(r"[0-9a-f]{40}", sha) is None:
        raise ValueError("invalid checkout commit")
    return sha


def artifact_digest(root: Path, name: str) -> str:
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("artifact must be a file inside the checkout")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _clean_tracked_tree(root: Path, exclude: tuple[str, ...] = ()) -> None:
    pathspec = ["."] + [f":(exclude){p}" for p in exclude]
    subprocess.run(
        ["git", "-C", str(root), "diff", "--quiet", "HEAD", "--", *pathspec],
        check=True, capture_output=True,
    )


def run(name: str, fn: Callable[[Path], Outcome], repo_root: Path) -> GateResult:
    if re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) is None:
        raise ValueError("invalid gate name")
    root = repo_root.resolve()
    start = time.time_ns()
    sha = ""
    execution = f"{fn.__module__}:{fn.__qualname__}"
    artifacts: tuple[str, ...] = ()
    digests: dict[str, str] = {}
    try:
        sha = current_commit(root)
        _clean_tracked_tree(root)
        outcome = fn(root)
        if not isinstance(outcome, Outcome) or not isinstance(outcome.status, Status):
            raise TypeError("gate did not return a typed Outcome")
        artifacts = tuple(
            (root / p).resolve().relative_to(root).as_posix() for p in outcome.artifacts
        )
        if len(set(artifacts)) != len(artifacts):
            raise ValueError("duplicate artifacts")
        digests = {p: artifact_digest(root, p) for p in artifacts}
        if current_commit(root) != sha:
            raise ValueError("checkout changed during gate")
        # The gate's declared artifacts are evidence it produced this run —
        # they are digested above, not tampering. A gate whose artifact is a
        # tracked manifest (e.g. reports/REPO_FILE_OWNERSHIP.json) would
        # otherwise fail-closed on its own output every run.
        _clean_tracked_tree(root, exclude=artifacts)
        status, reason = outcome.status, outcome.reason
    except Exception as exc:
        # Do not persist exception messages: dependencies may include credentials.
        status, reason = Status.ERROR, f"gate execution error: {type(exc).__name__}"
        artifacts, digests = (), {}
    result = GateResult(
        name, status, reason, artifacts, start, time.time_ns(), sha, execution, digests
    )
    payload = asdict(result)
    payload["evidence_digest"] = canonical_digest(payload)
    result = GateResult(**payload)
    path = root / "results" / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as tmp:
            tmp_name = tmp.name
            json.dump(payload, tmp, sort_keys=True, indent=2, allow_nan=False)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp_name, path)
    finally:
        if tmp_name is not None and Path(tmp_name).exists():
            Path(tmp_name).unlink()
    return result
