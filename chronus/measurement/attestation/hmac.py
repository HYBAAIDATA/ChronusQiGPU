"""HMAC attestation of a measurement artifact.

Invariants:
    HM1: every attestation is an HMAC-SHA256 over the artifact digest.
    HM2: the key is never stored with the artifact — it comes from the
         CHRONUS_MEASUREMENT_HMAC_KEY env var or a per-call ephemeral key.
"""

from __future__ import annotations

import hashlib
import hmac as _hmac
import os

from .artifact import MeasurementArtifact

ENV_KEY = "CHRONUS_MEASUREMENT_HMAC_KEY"


def load_hmac_key() -> bytes:
    """Env hex key when set; else an ephemeral key (attestation marked so)."""
    raw = os.environ.get(ENV_KEY, "").strip()
    if raw:
        try:
            return bytes.fromhex(raw)
        except ValueError:
            return raw.encode("utf-8")
    return os.urandom(32)


def attest_artifact(artifact: MeasurementArtifact, key: bytes) -> str:
    """HMAC-SHA256 over the content digest."""
    return _hmac.new(key, artifact.digest.encode("ascii"), hashlib.sha256).hexdigest()
