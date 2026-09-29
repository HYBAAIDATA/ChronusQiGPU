"""Release tagging, pinning, checksum and upgrade policy."""

from __future__ import annotations
import hashlib
import re
from pathlib import Path
from .promotion_pipeline import PromotionRejected

TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?$")


def parse_tag(tag: str) -> tuple[int, int, int, str | None]:
    match = TAG.fullmatch(tag)
    if not match:
        raise ValueError("invalid release tag")
    a, b, c, pre = match.groups()
    return int(a), int(b), int(c), pre


def is_release_tag(tag: str) -> bool:
    return bool(TAG.fullmatch(tag))


def is_prerelease(tag: str) -> bool:
    return parse_tag(tag)[3] is not None


def pin(repo_kind: str, version: str) -> str:
    major, minor, patch, pre = parse_tag(version if version.startswith("v") else "v" + version)
    plain = f"{major}.{minor}.{patch}" + (f"-{pre}" if pre else "")
    if repo_kind in {"PYTHIA", "ENTERPRISE"}:
        return f"mla1517-core=={plain}"
    if repo_kind == "STAGING":
        return f"mla1517-core>={major}.{minor},<{major+1}.0"
    raise ValueError(repo_kind)


def classify_upgrade(current: str, new: str) -> str:
    c = parse_tag("v" + current.lstrip("v"))
    n = parse_tag("v" + new.lstrip("v"))
    if n[:3] <= c[:3]:
        raise PromotionRejected("upgrade must increase version")
    return "MAJOR" if n[0] != c[0] else "MINOR" if n[1] != c[1] else "PATCH"


def authorize_upgrade(repo_kind, current, new, manual_major_approval=False) -> str:
    level = classify_upgrade(current, new)
    if level == "MAJOR" and not manual_major_approval:
        raise PromotionRejected("major upgrade requires manual approval")
    return pin(repo_kind, new)


def sha256s(paths):
    return {Path(p).name: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths}


def check_version_consistency(expected: str, values: dict[str, str]) -> None:
    mismatched = {k: v for k, v in values.items() if v != expected}
    if mismatched:
        raise PromotionRejected(f"version mismatch: {mismatched}")
