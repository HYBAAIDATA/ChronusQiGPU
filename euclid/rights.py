"""Creator-scoped rights ledger and provider boundary checks."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .evidence import EvidenceChain


@dataclass(frozen=True)
class ProviderManifest:
    provider_id: str
    identity: str
    modalities: frozenset[str]
    deployment: str


class RightsLedger:
    def __init__(self, creator_id: str, evidence: EvidenceChain) -> None:
        if not creator_id:
            raise ValueError("creator_id is required")
        self.creator_id = creator_id
        self.evidence = evidence
        self._grants: set[tuple[str, str, str, str]] = set()

    def grant(self, creator: str, subject: str, asset: str, action: str) -> None:
        key = (creator, subject, asset, action)
        if not all(key):
            raise ValueError("rights fields must be non-empty")
        if creator != self.creator_id:
            raise PermissionError("only the runtime creator may grant rights")
        self._grants.add(key)
        self.evidence.append("right-granted", {"creator": creator, "subject": subject,
                                               "asset": asset, "action": action})

    def revoke(self, creator: str, subject: str, asset: str, action: str) -> None:
        if creator != self.creator_id:
            raise PermissionError("only the runtime creator may revoke rights")
        self._grants.discard((creator, subject, asset, action))
        self.evidence.append("right-revoked", {"creator": creator, "subject": subject,
                                               "asset": asset, "action": action})

    def permits(self, creator: str, subject: str, asset: str, action: str) -> bool:
        return (
            creator == self.creator_id
            and (creator, subject, asset, action) in self._grants
        )

    def require(self, creator: str, subject: str, asset: str, action: str) -> None:
        if not self.permits(creator, subject, asset, action):
            self.evidence.append("right-denied", {"creator": creator, "subject": subject,
                                                  "asset": asset, "action": action})
            raise PermissionError("no active creator-scoped grant")

    def snapshot(self) -> dict[str, Any]:
        return {
            "schema": "euclid.rights/1",
            "creator_id": self.creator_id,
            "grants": [list(item) for item in sorted(self._grants)],
        }

    @classmethod
    def restore(
        cls,
        evidence: EvidenceChain,
        payload: dict[str, Any],
        *,
        creator_id: str | None = None,
    ) -> "RightsLedger":
        if payload.get("schema") != "euclid.rights/1":
            raise ValueError("unsupported rights schema")
        persisted_creator = str(payload.get("creator_id") or creator_id or "")
        if creator_id is not None and persisted_creator != creator_id:
            raise ValueError("persisted rights creator mismatch")
        ledger = cls(persisted_creator, evidence)
        for item in payload.get("grants", []):
            if not isinstance(item, list) or len(item) != 4 or not all(item):
                raise ValueError("invalid persisted rights grant")
            if str(item[0]) != persisted_creator:
                raise ValueError("persisted grant is outside the creator scope")
            ledger._grants.add(tuple(str(value) for value in item))
        return ledger


def require_provider(
    actual: ProviderManifest,
    *,
    provider_id: str,
    identity: str,
    modality: str,
    deployment: str,
) -> None:
    checks = (
        actual.provider_id == provider_id,
        actual.identity == identity,
        modality in actual.modalities,
        actual.deployment == deployment,
    )
    if not all(checks):
        raise PermissionError("provider manifest mismatch")
