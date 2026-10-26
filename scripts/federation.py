"""Authority-backed Lucas matrix federation handshake.

Nodes never coerce or negotiate capacities. They either share the exact
fingerprint, or a declared authority quorum supplies the canonical fingerprint.
Mismatch produces an actionable diagnostic and no scheduled work.
"""
from __future__ import annotations

import dataclasses
import hmac
from collections import Counter
from typing import Any, Mapping

try:
    from scripts.lucas_scale_matrix import LucasScaleMatrixEngine, MATRIX_VERSION, SCHEMA_VERSION
except ImportError:
    from lucas_scale_matrix import LucasScaleMatrixEngine, MATRIX_VERSION, SCHEMA_VERSION


@dataclasses.dataclass(frozen=True)
class FederationManifest:
    authority_ids: tuple[str, ...]
    threshold: int
    declared_fingerprints: dict[str, str]
    schema_version: str = SCHEMA_VERSION
    matrix_version: str = MATRIX_VERSION

    def __post_init__(self) -> None:
        if not self.authority_ids:
            raise ValueError("authority set must not be empty")
        if not 1 <= self.threshold <= len(self.authority_ids):
            raise ValueError("threshold must be within authority-set size")
        if set(self.declared_fingerprints) != set(self.authority_ids):
            raise ValueError("every authority must declare one fingerprint")
        for fingerprint in self.declared_fingerprints.values():
            if len(fingerprint) != 64 or any(c not in "0123456789abcdef" for c in fingerprint):
                raise ValueError("authority fingerprints must be full lowercase SHA-256 hex")

    def canonical_fingerprint(self) -> str | None:
        counts = Counter(self.declared_fingerprints.values())
        winners = [fingerprint for fingerprint, count in counts.items() if count >= self.threshold]
        return winners[0] if len(winners) == 1 else None


@dataclasses.dataclass(frozen=True)
class FederationDecision:
    accepted: bool
    status: str
    local_fingerprint: str
    observed_fingerprints: dict[str, str]
    canonical_fingerprint: str | None
    diagnostics: dict[str, Any]


def handshake(
    local_engine: LucasScaleMatrixEngine,
    peer_fingerprints: Mapping[str, str],
    manifest: FederationManifest,
) -> FederationDecision:
    local = local_engine.compute_fingerprint()
    observed = dict(peer_fingerprints)
    all_fingerprints = [local, *observed.values()]
    same_content = all(hmac.compare_digest(local, fingerprint) for fingerprint in all_fingerprints)
    namespace_ok = manifest.schema_version == SCHEMA_VERSION and manifest.matrix_version == MATRIX_VERSION
    canonical = manifest.canonical_fingerprint()
    authority_accepts = canonical is not None and hmac.compare_digest(local, canonical)
    accepted = namespace_ok and (same_content or authority_accepts)
    status = "ACCEPTED_EXACT_MATCH" if accepted and same_content else (
        "ACCEPTED_AUTHORITY_QUORUM" if accepted else "INCOMPATIBLE_MATRIX_FEDERATION"
    )
    return FederationDecision(
        accepted=accepted,
        status=status,
        local_fingerprint=local,
        observed_fingerprints=observed,
        canonical_fingerprint=canonical,
        diagnostics={
            "schema_version_local": SCHEMA_VERSION,
            "schema_version_manifest": manifest.schema_version,
            "matrix_version_local": MATRIX_VERSION,
            "matrix_version_manifest": manifest.matrix_version,
            "authority_ids": list(manifest.authority_ids),
            "threshold": manifest.threshold,
        },
    )
