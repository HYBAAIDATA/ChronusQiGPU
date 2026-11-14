"""Load and validate the claim audit. Fails closed: a malformed audit is a 500,
never a silently permissive one."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import date

import yaml

from chronus.service.api.errors import ApiError

_DISPOSITIONS = {"supported", "unverified", "withdrawn"}
_ID = re.compile(r"[a-z0-9][a-z0-9-]{2,63}")
_cache: "Audit | None" = None


@dataclass(frozen=True)
class Claim:
    id: str
    statement: str
    disposition: str
    reviewer: str | None
    evidence: tuple[dict, ...]
    notes: str | None


@dataclass(frozen=True)
class Blocker:
    id: str
    description: str
    status: str


@dataclass(frozen=True)
class Audit:
    reviewed_at: date
    commit: str
    claims: tuple[Claim, ...]
    blockers: tuple[Blocker, ...]

    @property
    def posture(self) -> str:
        # Honest by construction: anything not supported blocks qualification.
        if self.claims and all(c.disposition == "supported" for c in self.claims):
            return "qualified"
        return "not_qualified"


def reset_cache() -> None:
    global _cache
    _cache = None


def _fail(detail: str) -> ApiError:
    return ApiError(500, "claim_audit_invalid", "Claim audit is invalid", detail)


def load_audit() -> Audit:
    global _cache
    if _cache is not None:
        return _cache

    path = os.getenv("CHRONUS_CLAIM_AUDIT", "docs/claim-audit.yaml")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            raw = yaml.safe_load(handle)
    except FileNotFoundError:
        raise _fail(f"{path} not found.")
    except yaml.YAMLError as exc:
        raise _fail(f"{path} is not valid YAML: {exc}")

    if not isinstance(raw, dict) or raw.get("version") != 1:
        raise _fail("Top level must be a mapping with version: 1.")

    claims: list[Claim] = []
    seen: set[str] = set()
    for entry in raw.get("claims") or []:
        if not isinstance(entry, dict):
            raise _fail("Each claim must be a mapping.")
        claim_id = str(entry.get("id", ""))
        if not _ID.fullmatch(claim_id):
            raise _fail(f"Bad claim id {claim_id!r}.")
        if claim_id in seen:
            raise _fail(f"Duplicate claim id {claim_id!r}.")
        seen.add(claim_id)

        disposition = entry.get("disposition")
        if disposition not in _DISPOSITIONS:
            raise _fail(f"Claim {claim_id!r} has disposition {disposition!r}.")
        evidence = tuple(entry.get("evidence") or ())
        reviewer = entry.get("reviewer")

        # The rule that makes "supported" mean something.
        if disposition == "supported":
            if not evidence:
                raise _fail(f"Claim {claim_id!r} is supported but has no evidence.")
            if not reviewer:
                raise _fail(f"Claim {claim_id!r} is supported but has no reviewer.")
            for item in evidence:
                if not isinstance(item, dict) or not item.get("ref"):
                    raise _fail(f"Claim {claim_id!r} has an evidence entry without ref.")

        claims.append(Claim(claim_id, str(entry.get("statement", "")),
                            disposition, reviewer, evidence, entry.get("notes")))

    blockers = tuple(
        Blocker(str(b.get("id")), str(b.get("description", "")), str(b.get("status", "open")))
        for b in (raw.get("blockers") or []) if isinstance(b, dict)
    )

    try:
        reviewed_at = date.fromisoformat(str(raw["reviewed_at"]))
    except (KeyError, ValueError):
        raise _fail("reviewed_at must be an ISO date.")

    _cache = Audit(reviewed_at, str(raw.get("commit", "")), tuple(claims), blockers)
    return _cache
