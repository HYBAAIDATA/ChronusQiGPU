"""Native, read-only Python review adapter. No LLM, imports, shell or schedules.

Inputs are an explicit host-approved path/hash manifest, not instructions from
source documents. Findings are bounded syntactic evidence, NOT repair approval
or a semantic correctness/security verdict. POSIX no-follow descriptor traversal
is required; unsupported hosts refuse rather than weakening confinement.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ReviewRejected(ValueError):
    """No review receipt is issued for refused or incomplete input."""


@dataclass(frozen=True)
class ReviewPolicy:
    expected_files: tuple[tuple[str, str], ...]
    max_file_bytes: int = 262144
    max_total_bytes: int = 1048576
    max_findings: int = 128

    def __post_init__(self) -> None:
        for name, ceiling in (
            ("max_file_bytes", 262144),
            ("max_total_bytes", 1048576),
            ("max_findings", 128),
        ):
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= ceiling:
                raise ReviewRejected(f"{name}: exact positive integer within {ceiling} required")
        if type(self.expected_files) is not tuple or not 1 <= len(self.expected_files) <= 64:
            raise ReviewRejected("expected_files: immutable manifest of 1..64 files required")
        seen = set()
        for item in self.expected_files:
            if type(item) is not tuple or len(item) != 2:
                raise ReviewRejected("manifest entries must be path/digest tuples")
            path, digest = item
            if not _safe_path(path) or path in seen:
                raise ReviewRejected("manifest requires distinct safe relative Python paths")
            if (
                type(digest) is not str
                or len(digest) != 64
                or any(c not in "0123456789abcdef" for c in digest)
            ):
                raise ReviewRejected("manifest requires lowercase SHA256 digests")
            seen.add(path)


def _safe_path(path: Any) -> bool:
    if type(path) is not str or not path.endswith(".py") or "\\" in path or "\0" in path:
        return False
    parts = path.split("/")
    return all(part and part not in (".", "..") and not part.startswith(".") for part in parts)


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def _directory_fd(parts: tuple[str, ...], parent: int) -> int:
    fd = os.dup(parent)
    try:
        for part in parts:
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        return fd
    except BaseException:
        os.close(fd)
        raise


def _read_file(root_fd: int, path: str, limit: int) -> bytes:
    parts = tuple(path.split("/"))
    parent = _directory_fd(parts[:-1], root_fd)
    try:
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
    finally:
        os.close(parent)
    with os.fdopen(fd, "rb") as handle:
        before = os.fstat(handle.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
            raise ReviewRejected("nonregular or oversized review input")
        data = handle.read(limit + 1)
        after = os.fstat(handle.fileno())
        if len(data) > limit or (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ):
            raise ReviewRejected("review input exceeded its bound or changed during reading")
        return data


def _findings(data: bytes, path: str) -> list[dict[str, Any]]:
    try:
        # Passing bytes honours the Python source encoding declaration.
        tree = ast.parse(data, filename=path)
    except SyntaxError as exc:
        return [{"code": "PYTHON_SYNTAX_ERROR", "line": exc.lineno or 0}]
    except (ValueError, RecursionError) as exc:
        raise ReviewRejected("source cannot be parsed within the adapter contract") from exc
    findings = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in ("eval", "exec"):
                findings.append({"code": "DYNAMIC_CODE_CALL_REVIEW", "line": node.lineno})
    # This is a review candidate, not proof that redefinition is erroneous:
    # properties, overloads and deliberate rebinding need semantic assessment.
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            seen = set()
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    if child.name in seen:
                        findings.append({"code": "REDEFINED_BINDING_REVIEW", "line": child.lineno})
                    seen.add(child.name)
    return sorted(findings, key=lambda f: (f["line"], f["code"]))


def _read_file_windows(root: Path, path: str, limit: int) -> bytes:
    if not root.is_dir():
        raise ReviewRejected("review root is not an existing directory")
    st = os.lstat(root)
    if stat.S_ISLNK(st.st_mode) or (
        getattr(st, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    ):
        raise ReviewRejected("symlink root rejected")
    parts = tuple(path.split("/"))
    curr = root
    for part in parts[:-1]:
        curr = curr / part
        st = os.lstat(curr)
        if stat.S_ISLNK(st.st_mode) or (
            getattr(st, "st_file_attributes", 0)
            & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        ):
            raise ReviewRejected("symlink in path rejected")
        if not stat.S_ISDIR(st.st_mode):
            raise ReviewRejected("parent is not a directory")
    file_path = curr / parts[-1]
    st = os.lstat(file_path)
    if stat.S_ISLNK(st.st_mode) or (
        getattr(st, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    ):
        raise ReviewRejected("symlink file rejected")
    if not stat.S_ISREG(st.st_mode) or st.st_size > limit:
        raise ReviewRejected("nonregular or oversized review input")
    try:
        file_path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ReviewRejected("path escapes repository root") from exc
    fd = os.open(str(file_path), os.O_RDONLY | getattr(os, "O_BINARY", 0))
    with os.fdopen(fd, "rb") as handle:
        before = os.fstat(handle.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
            raise ReviewRejected("nonregular or oversized review input")
        data = handle.read(limit + 1)
        after = os.fstat(handle.fileno())
        if len(data) > limit or (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ):
            raise ReviewRejected("review input exceeded its bound or changed during reading")
        return data


def review_repository(*, repo_root: str | Path, policy: ReviewPolicy) -> dict[str, Any]:
    """Read only declared bytes and return deterministic source-bound evidence.

    The host chooses root and hashes. This is not a user-authentication layer,
    complete repository audit, current git-state attestation or wall-time bound.
    No findings means only that these syntactic checks found no candidates.
    """
    if type(policy) is not ReviewPolicy:
        raise ReviewRejected("an explicit ReviewPolicy is required")
    has_posix_descriptors = all(
        hasattr(os, name) for name in ("O_NOFOLLOW", "O_DIRECTORY", "O_NONBLOCK")
    ) and (os.open in getattr(os, "supports_dir_fd", set()))
    is_windows = os.name == "nt"
    if not has_posix_descriptors and not is_windows:
        raise ReviewRejected("host lacks required no-follow descriptor support")
    if not isinstance(repo_root, (str, Path)) or not str(repo_root):
        raise ReviewRejected("explicit repository root required")
    root = Path(repo_root).absolute()
    if ".." in root.parts:
        raise ReviewRejected("repository root cannot contain parent traversal")
    records = []
    total = 0
    count = 0
    try:
        if has_posix_descriptors:
            start = os.open(root.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                root_fd = _directory_fd(tuple(root.parts[1:]), start)
            finally:
                os.close(start)
            try:
                for path, expected in sorted(policy.expected_files):
                    data = _read_file(root_fd, path, policy.max_file_bytes)
                    total += len(data)
                    if total > policy.max_total_bytes:
                        raise ReviewRejected("total review byte budget exceeded")
                    actual = hashlib.sha256(data).hexdigest()
                    if actual != expected:
                        raise ReviewRejected("review input does not match approved manifest")
                    findings = _findings(data, path)
                    count += len(findings)
                    if count > policy.max_findings:
                        raise ReviewRejected("finding budget exceeded; no partial receipt")
                    records.append(
                        {"path": path, "sha256": actual, "bytes": len(data), "findings": findings}
                    )
            finally:
                os.close(root_fd)
        else:
            for path, expected in sorted(policy.expected_files):
                data = _read_file_windows(root, path, policy.max_file_bytes)
                total += len(data)
                if total > policy.max_total_bytes:
                    raise ReviewRejected("total review byte budget exceeded")
                actual = hashlib.sha256(data).hexdigest()
                if actual != expected:
                    raise ReviewRejected("review input does not match approved manifest")
                findings = _findings(data, path)
                count += len(findings)
                if count > policy.max_findings:
                    raise ReviewRejected("finding budget exceeded; no partial receipt")
                records.append(
                    {"path": path, "sha256": actual, "bytes": len(data), "findings": findings}
                )
    except OSError as exc:
        # No absolute paths or source text in externally returned errors.
        raise ReviewRejected("review path is missing, unsafe or unreadable") from exc
    result = {
        "schema": "euclid.repository-review/1",
        "skill": "repository-review",
        "status": "REVIEWED_READ_ONLY",
        "semantic_verdict": "NOT_ESTABLISHED",
        "manifest_sha256": _digest(sorted(policy.expected_files)),
        "policy": {
            "max_file_bytes": policy.max_file_bytes,
            "max_total_bytes": policy.max_total_bytes,
            "max_findings": policy.max_findings,
        },
        "files": records,
        "total_bytes": total,
        "finding_count": count,
    }
    result["receipt_sha256"] = _digest(result)
    return result
