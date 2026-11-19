#!/usr/bin/env python3
"""Fail-closed repository surface, root-allowlist, and IP-boundary gate."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from fnmatch import fnmatchcase
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from typing import Dict, List, Set

MAX_SCAN_BYTES = 2 * 1024 * 1024  # 2 MiB per tracked text file


@dataclass(frozen=True)
class Violation:
    rule_id: str
    path: str
    detail: str


def git_tracked_files(repo_root: Path) -> List[str]:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "-z"],
        check=True,
        capture_output=True,
    )
    raw = proc.stdout.decode("utf-8", errors="strict")
    return [entry for entry in raw.split("\0") if entry]


def matches_glob(rel_path: str, pattern: str) -> bool:
    posix = PurePosixPath(rel_path)
    if pattern.endswith("/**"):
        prefix = pattern[:-3].rstrip("/")
        return rel_path == prefix or rel_path.startswith(prefix + "/")
    if pattern.startswith("**/"):
        sub = pattern[3:]
        return fnmatchcase(rel_path, sub) or fnmatchcase(posix.name, sub)
    return fnmatchcase(rel_path, pattern) if "/" in pattern else "/" not in rel_path and fnmatchcase(rel_path, pattern)


def validate_policy(policy: object) -> None:
    """Validate the policy as a policy, not as qualification evidence."""
    if not isinstance(policy, dict):
        raise ValueError("hygiene policy is not a JSON object")
    if policy.get("schema_version") != "1.0.0" or policy.get("policy") != "fail_closed_public_surface":
        raise ValueError("unknown hygiene policy or schema version")
    for name in ("allowed_root_dirs", "allowed_root_files", "forbidden_path_globs", "content_scan_exclude_paths"):
        items = policy.get(name, [] if name == "content_scan_exclude_paths" else None)
        if not isinstance(items, list) or (not items and name != "content_scan_exclude_paths") or any(
            not isinstance(item, str) or not item.strip() for item in items
        ):
            raise ValueError(f"invalid hygiene policy list: {name}")
        if len(items) != len(set(items)):
            raise ValueError(f"duplicate hygiene policy entry: {name}")
    rules = policy.get("forbidden_content_regexes")
    if not isinstance(rules, list) or not rules:
        raise ValueError("forbidden_content_regexes must be a non-empty list")
    ids = set()
    for rule in rules:
        if not isinstance(rule, dict) or any(
            not isinstance(rule.get(key), str) or not rule[key].strip() for key in ("id", "pattern")
        ):
            raise ValueError("invalid content regex rule")
        if rule["id"] in ids:
            raise ValueError("duplicate content regex rule ID")
        ids.add(rule["id"])
        re.compile(rule["pattern"])


def evaluate_hygiene(repo_root: Path, allowlist_path: Path) -> List[Violation]:
    policy = json.loads(allowlist_path.read_text(encoding="utf-8"))
    validate_policy(policy)
    allowed_dirs: Set[str] = set(policy["allowed_root_dirs"])
    allowed_files: Set[str] = set(policy["allowed_root_files"])
    banned_globs: List[str] = list(policy["forbidden_path_globs"])
    exclude_content: Set[str] = set(policy.get("content_scan_exclude_paths", []))
    compiled_regexes = [
        (item["id"], re.compile(item["pattern"]))
        for item in policy["forbidden_content_regexes"]
    ]

    tracked = git_tracked_files(repo_root)
    violations: List[Violation] = []
    checked_roots: Set[str] = set()

    for rel in tracked:
        parts = PurePosixPath(rel).parts
        if not parts:
            continue
        top = parts[0]

        # 1. Strict Root Allowlist Check
        if top not in checked_roots:
            checked_roots.add(top)
            if len(parts) == 1:
                if top not in allowed_files:
                    violations.append(
                        Violation(
                            rule_id="ROOT_FILE_NOT_ALLOWLISTED",
                            path=top,
                            detail="Top-level file is absent from manifests/public_root_allowlist.json",
                        )
                    )
            else:
                if top not in allowed_dirs:
                    violations.append(
                        Violation(
                            rule_id="ROOT_DIR_NOT_ALLOWLISTED",
                            path=top + "/",
                            detail="Top-level directory is absent from manifests/public_root_allowlist.json",
                        )
                    )

        # 2. Banned Path / Scratch / Private-Tier Globs
        for glob_pat in banned_globs:
            if matches_glob(rel, glob_pat):
                violations.append(
                    Violation(
                        rule_id="BANNED_PATH_PATTERN",
                        path=rel,
                        detail=f"Matched banned pattern '{glob_pat}'",
                    )
                )
                break

        # 3. IP & Credential Boundary Content Scan
        if rel in exclude_content:
            continue
        abs_path = repo_root / rel
        if abs_path.is_symlink():
            violations.append(Violation("SYMLINK_REVIEW_REQUIRED", rel, "Tracked link requires owner review"))
            continue
        if not abs_path.is_file():
            violations.append(Violation("FILE_READ_ERROR", rel, "Tracked path is missing or not a file"))
            continue
        try:
            size = abs_path.stat().st_size
            if size == 0 or size > MAX_SCAN_BYTES:
                continue
            raw_bytes = abs_path.read_bytes()
            if b"\x00" in raw_bytes[:4096]:
                continue  # Binary artifact
            text = raw_bytes.decode("utf-8", errors="ignore")
        except OSError as exc:
            violations.append(
                Violation(
                    rule_id="FILE_READ_ERROR",
                    path=rel,
                    detail=str(exc),
                )
            )
            continue

        for rule_id, regex in compiled_regexes:
            match = regex.search(text)
            if match is not None:
                line_no = text.count("\n", 0, match.start()) + 1
                violations.append(
                    Violation(
                        rule_id=rule_id,
                        path=f"{rel}:{line_no}",
                        detail="Matched restricted IP or credential boundary pattern",
                    )
                )

    return sorted(violations, key=lambda v: (v.path, v.rule_id, v.detail))


def main() -> int:
    parser = argparse.ArgumentParser(description="ChronusQiGPU repo hygiene & IP boundary gate")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument(
        "--allowlist",
        type=Path,
        default=Path("manifests/public_root_allowlist.json"),
    )
    parser.add_argument("--report", type=Path, default=Path("artifacts/repo_hygiene_report.json"))
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    allowlist_path = (
        args.allowlist if args.allowlist.is_absolute() else (repo_root / args.allowlist)
    )
    if not allowlist_path.is_file():
        print(f"FATAL: Missing allowlist manifest: {allowlist_path}", file=sys.stderr)
        return 2

    try:
        commit_sha = subprocess.check_output(["git", "-C", str(repo_root), "rev-parse", "HEAD"], text=True).strip()
        violations = evaluate_hygiene(repo_root, allowlist_path)
    except (OSError, subprocess.CalledProcessError, ValueError, KeyError, TypeError, re.error) as exc:
        print(f"FATAL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    report: Dict[str, object] = {
        "commit_sha": commit_sha,
        "gate": "REPO_HYGIENE_AND_IP_BOUNDARY",
        "status": "PASS" if not violations else "FAIL",
        "violation_count": len(violations),
        "violations": [asdict(v) for v in violations],
    }

    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    if violations:
        print(f"HYGIENE GATE FAILED ({len(violations)} violations):", file=sys.stderr)
        for v in violations:
            print(f"  [{v.rule_id}] {v.path} — {v.detail}", file=sys.stderr)
        return 1

    print("HYGIENE GATE PASSED: root allowlist and IP boundary clean.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
