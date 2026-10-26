"""Preserve corrupt custody evidence and latch access closed pending manual quorum.

This module deliberately has no automatic clear/reseal API. A quarantine latch
is an incident, not a failed cache entry; restoring files is insufficient to
clear it. Quorum-authorized recovery must retain the incident and issue a new
custody generation through the deployment's authority owner.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import tempfile
import time
from pathlib import Path


class CustodyQuarantine:
    def __init__(self, tenant_root: Path, key: bytes):
        self.root, self.key = Path(tenant_root) / "quarantine", key

    def _incident(self, record_id: str) -> Path:
        # Record ids need never become path components.
        return self.root / hashlib.sha256(record_id.encode()).hexdigest()

    def blocked(self, record_id: str) -> bool:
        # Any retained incident blocks, even a damaged or partially written manifest.
        return self._incident(record_id).exists()

    def capture(self, record_id: str, sides: dict[str, Path]) -> dict:
        folder = self._incident(record_id)
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        files = {}
        for side, source in sides.items():
            if side not in {"primary", "replica"}:
                raise ValueError("unknown custody side")
            data = Path(source).read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            name = f"{side}-{digest}.bin"
            path = folder / name
            # Never overwrite retained corruption evidence.
            try:
                fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                    raise RuntimeError("quarantine evidence integrity failure")
            else:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
            files[name] = digest
        manifest = {"schema_version": "hyba.custody.quarantine/1", "record_id": record_id,
                    "severity": "SEV-1", "status": "QUARANTINED", "at": time.time(),
                    "files": files, "release": "MANUAL_QUORUM_RESEAL_REQUIRED"}
        body = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
        manifest["hmac_sha256"] = hmac.new(self.key, body, hashlib.sha256).hexdigest()
        fd, temp = tempfile.mkstemp(prefix="incident-", dir=folder)
        with os.fdopen(fd, "w") as stream:
            json.dump(manifest, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, folder / "incident.json")
        return manifest
