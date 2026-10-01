"""Validation for GPU evidence and provenance records."""

from __future__ import annotations

import re
from typing import Any, Mapping

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_ALLOWED_TRUTH = {"source_verified", "software_verified", "hardware_verified", "pool_verified"}
_PLACEHOLDER_PRS = {"test", "replay-test", "unknown", ""}


class ProvenanceError(ValueError):
    """A record cannot support a production claim."""


def validate_provenance(record: Mapping[str, Any], *, production: bool = False) -> dict[str, Any]:
    """Validate a provenance record and return a normalized copy.

    Production records require a real PR identifier, merge SHA, non-empty
    change bundles, replay pins and an explicit evidence truth class.
    """
    normalized = dict(record)
    problems: list[str] = []
    repo_sha = str(normalized.get("repo_sha", ""))
    if not _SHA40.fullmatch(repo_sha):
        problems.append("repo_sha must be a 40-character lowercase git SHA")
    replay = normalized.get("replay")
    if not isinstance(replay, Mapping):
        problems.append("replay metadata is required")
    else:
        for key in ("agent_versions", "seed", "substrate_freeze_sha"):
            if key not in replay:
                problems.append(f"replay.{key} is required")
    truth_class = str(normalized.get("truth_class", "source_verified"))
    if truth_class not in _ALLOWED_TRUTH:
        problems.append(f"unsupported truth_class: {truth_class}")
    if production:
        if str(normalized.get("pr", "")) in _PLACEHOLDER_PRS:
            problems.append("production provenance requires a real PR identifier")
        if not _SHA40.fullmatch(str(normalized.get("human_merge_sha", ""))):
            problems.append("production provenance requires human_merge_sha")
        bundles = normalized.get("change_bundles")
        if not isinstance(bundles, list) or not bundles:
            problems.append("production provenance requires non-empty change_bundles")
    if problems:
        raise ProvenanceError("; ".join(problems))
    normalized["truth_class"] = truth_class
    normalized["production_eligible"] = production
    return normalized
