"""Replay verification — recompute the digest from the payload.

Invariants:
    RPL1: replay recomputes the digest from the payload.
    RPL2: forgery fails replay.
"""

from __future__ import annotations

import hashlib

from .._common import canonical_json
from .artifact import MeasurementArtifact


def replay_artifact(artifact: MeasurementArtifact) -> bool:
    """Recompute sha256 over the canonical payload; compare to the digest."""
    expected = hashlib.sha256(canonical_json(artifact.payload()).encode("utf-8")).hexdigest()
    return expected == artifact.digest
