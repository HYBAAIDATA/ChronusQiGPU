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
    def __init__(self, evidence: EvidenceChain) -> None:
        self.evidence = evidence
        self._grants: set[tuple[str, str, str, str]] = set()

    def grant(self, creator: str, subject: str, asset: str, action: str) -> None:
        key = (creator, subject, asset, action)
        if not all(key):
            raise ValueError("rights fields must be non-empty")
        self._grants.add(key)
        self.evidence.append("right-granted", {"creator": creator, "subject": subject,
                                               "asset": asset, "action": action})

    def revoke(self, creator: str, subject: str, asset: str, action: str) -> None:
        self._grants.discard((creator, subject, asset, action))
        self.evidence.append("right-revoked", {"creator": creator, "subject": subject,
                                               "asset": asset, "action": action})

    def require(self, creator: str, subject: str, asset: str, action: str) -> None:
        if (creator, subject, asset, action) not in self._grants:
            self.evidence.append("right-denied", {"creator": creator, "subject": subject,
                                                  "asset": asset, "action": action})
            raise PermissionError("no active creator-scoped grant")

    def snapshot(self) -> dict[str, Any]:
        return {
            "schema": "euclid.rights/1",
            "grants": [list(item) for item in sorted(self._grants)],
        }

    @classmethod
    def restore(
        cls, evidence: EvidenceChain, payload: dict[str, Any]
    ) -> "RightsLedger":
        if payload.get("schema") != "euclid.rights/1":
            raise ValueError("unsupported rights schema")
        ledger = cls(evidence)
        for item in payload.get("grants", []):
            if not isinstance(item, list) or len(item) != 4 or not all(item):
                raise ValueError("invalid persisted rights grant")
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
