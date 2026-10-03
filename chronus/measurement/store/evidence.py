"""Evidence store — content-addressed artifacts with replay verification.

Invariants:
    EV1: every artifact is stored under its digest (unique key).
    EV2: every artifact is replayable.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

from .._common import canonical_json
from ..attestation.artifact import MeasurementArtifact
from ..attestation.replay import replay_artifact

_PAYLOAD_KEYS = (
    "baseline",
    "topology",
    "profiling",
    "roofline",
    "workloads",
    "efficiency",
    "stability",
)


@dataclass
class EvidenceStore:
    """In-memory store; optional directory persistence as canonical JSON."""

    artifacts: Dict[str, MeasurementArtifact] = field(default_factory=dict)
    ledger: Dict[str, str] = field(default_factory=dict)
    directory: Optional[Path] = None

    def write(self, artifact: MeasurementArtifact) -> str:
        key = artifact.digest
        self.artifacts[key] = artifact
        self.ledger[key] = artifact.attestation
        if self.directory is not None:
            self.directory.mkdir(parents=True, exist_ok=True)
            path = self.directory / f"{key}.json"
            path.write_text(canonical_json(artifact.as_dict()), encoding="utf-8")
        return key

    def read(self, key: str) -> MeasurementArtifact:
        return self.artifacts[key]

    def verify(self, key: str) -> bool:
        return replay_artifact(self.artifacts[key])

    def load(self, path: Path) -> Dict[str, object]:
        """Load a persisted artifact dict and recompute its content digest.

        Merely containing a ``digest`` field is not evidence. The persisted
        payload must reproduce that digest byte-for-byte under canonical JSON.
        """
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        payload = {key: data.get(key, {}) for key in _PAYLOAD_KEYS}
        expected = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
        supplied = str(data.get("digest", "") or "")
        ok = bool(supplied) and hmac.compare_digest(expected, supplied)
        return {
            "ok": ok,
            "artifact": data,
            "expected_digest": expected,
            "supplied_digest": supplied,
        }
