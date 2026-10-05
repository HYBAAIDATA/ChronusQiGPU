"""Integrity-verified checkpoints for enterprise custody.

A checkpoint is an immutable, self-describing snapshot of one tenant's
custody root: primary + replica + journal + provenance, plus a manifest
listing every record's (id, generation, content_digest) and the digest of
every copied file. The manifest carries an HMAC under the custody key, so a
forged or truncated checkpoint fails verification rather than rolling back
garbage.

Crash discipline: the checkpoint is staged under ``<id>.tmp`` and the
manifest is written LAST via atomic rename; a directory without a manifest
is an interrupted checkpoint — reported UNAVAILABLE and never usable for
rollback (fail closed).

This module never imports custody — the caller passes plain values.
"""

from __future__ import annotations

import json
import os
import shutil
import time
import uuid
from pathlib import Path
from typing import Any, Iterable, Optional

from .authenticity import content_digest, mac_create, mac_verify
from .errors import EnterpriseCustodyError


class CheckpointIntegrityError(EnterpriseCustodyError):
    """Checkpoint manifest or payload failed verification — refuse to trust."""


class CheckpointUnavailableError(EnterpriseCustodyError):
    """Checkpoint absent or interrupted — nothing to verify or roll back to."""


MANIFEST_NAME = "manifest.json"
MANIFEST_TMP = "manifest.json.tmp"
CHECKPOINT_FORMAT = 1


def _copy_tree(src: Path, dst: Path) -> dict[str, str]:
    """Copy ``src`` into ``dst``; return {relative path: sha256} of files."""
    digests: dict[str, str] = {}
    if not src.exists():
        return digests
    for item in sorted(src.rglob("*")):
        rel = item.relative_to(src).as_posix()
        target = dst / rel
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        if item.name.endswith(".lock"):
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, target)
        digests[rel] = content_digest(target.read_bytes())
    return digests


class CheckpointManager:
    """Create/verify/list checkpoints under ``<tenant_root>/checkpoints``."""

    def __init__(self, tenant_root: Path | str) -> None:
        self.tenant_root = Path(tenant_root)
        self.checkpoints_dir = self.tenant_root / "checkpoints"
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)

    # -- creation -----------------------------------------------------------

    def create(
        self,
        *,
        key: bytes,
        records: Iterable[dict[str, Any]],
        tenant: str,
        label: str = "",
    ) -> dict[str, Any]:
        """Snapshot tenant_root durable state + write a verified manifest.

        ``records`` is the caller's current verified record index:
        ``{"record_id", "generation", "content_digest"}`` per entry.
        """
        checkpoint_id = f"ckpt-{int(time.time())}-{uuid.uuid4().hex[:12]}"
        staging = self.checkpoints_dir / f"{checkpoint_id}.tmp"
        final = self.checkpoints_dir / checkpoint_id
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir(parents=True)

        # Copy the durable subtrees that make up custody state.
        file_digests: dict[str, str] = {}
        for name in ("primary", "replica", "journal", "provenance"):
            src = self.tenant_root / name
            file_digests.update(
                {f"{name}/{r}": d for r, d in _copy_tree(src, staging / name).items()}
            )
        meta_src = self.tenant_root / "meta.json"
        if meta_src.exists():
            shutil.copy2(meta_src, staging / "meta.json")
            file_digests["meta.json"] = content_digest((staging / "meta.json").read_bytes())

        record_list = sorted((dict(r) for r in records), key=lambda r: r["record_id"])
        manifest = {
            "checkpoint_format": CHECKPOINT_FORMAT,
            "checkpoint_id": checkpoint_id,
            "tenant": tenant,
            "label": label,
            "created_ts": time.time(),
            "records": record_list,
            "record_count": len(record_list),
            "file_digests": file_digests,
            "mac": "",
        }
        manifest["mac"] = mac_create(key, self._canonical(manifest))

        tmp_manifest = staging / MANIFEST_TMP
        with open(tmp_manifest, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(manifest, sort_keys=True, indent=2))
            fh.flush()
            os.fsync(fh.fileno())
        # Manifest lands last; directory renames publish the checkpoint.
        os.replace(tmp_manifest, staging / MANIFEST_NAME)
        os.replace(staging, final)
        return {
            "checkpoint_id": checkpoint_id,
            "path": str(final),
            "records": manifest["record_count"],
            "created_ts": manifest["created_ts"],
        }

    @staticmethod
    def _canonical(manifest: dict[str, Any]) -> bytes:
        data = {k: v for k, v in manifest.items() if k != "mac"}
        return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")

    # -- verification --------------------------------------------------------

    def _load_manifest(self, checkpoint_id: str) -> dict[str, Any]:
        cdir = self.checkpoints_dir / checkpoint_id
        mpath = cdir / MANIFEST_NAME
        if not cdir.is_dir() or not mpath.is_file():
            raise CheckpointUnavailableError(
                f"checkpoint {checkpoint_id} absent or interrupted " f"(no manifest) — UNAVAILABLE"
            )
        try:
            manifest = json.loads(mpath.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CheckpointIntegrityError(
                f"checkpoint {checkpoint_id} manifest unreadable: {exc}"
            ) from exc
        if int(manifest.get("checkpoint_format", -1)) != CHECKPOINT_FORMAT:
            raise CheckpointIntegrityError(
                f"checkpoint {checkpoint_id} unsupported format "
                f"{manifest.get('checkpoint_format')}"
            )
        return manifest

    def verify(self, checkpoint_id: str, *, key: bytes) -> dict[str, Any]:
        """Re-verify a checkpoint: manifest MAC + every file digest.

        Returns an explicit evidence dict — ``status`` is PASS or FAIL, never
        silently optimistic. Raises CheckpointUnavailableError when there is
        nothing to verify.
        """
        manifest = self._load_manifest(checkpoint_id)
        cdir = self.checkpoints_dir / checkpoint_id
        result: dict[str, Any] = {
            "checkpoint_id": checkpoint_id,
            "mac": "MISSING",
            "files_checked": 0,
            "files_failed": [],
            "status": "FAIL",
        }
        mac = str(manifest.get("mac", ""))
        result["mac"] = "PASS" if mac_verify(key, self._canonical(manifest), mac) else "FAIL"
        failed: list[str] = []
        checked = 0
        for rel, expected in sorted((manifest.get("file_digests") or {}).items()):
            target = cdir / rel
            checked += 1
            if not target.is_file() or content_digest(target.read_bytes()) != expected:
                failed.append(rel)
        result["files_checked"] = checked
        result["files_failed"] = failed
        result["status"] = "PASS" if result["mac"] == "PASS" and not failed else "FAIL"
        return result

    # -- enumeration ---------------------------------------------------------

    def list(self) -> list[dict[str, Any]]:
        """All complete checkpoints (interrupted .tmp dirs excluded)."""
        out: list[dict[str, Any]] = []
        for child in sorted(self.checkpoints_dir.iterdir()):
            if child.name.endswith(".tmp") or not child.is_dir():
                continue
            mpath = child / MANIFEST_NAME
            if not mpath.is_file():
                continue
            try:
                manifest = json.loads(mpath.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                manifest = {}
            out.append(
                {
                    "checkpoint_id": child.name,
                    "created_ts": manifest.get("created_ts"),
                    "record_count": manifest.get("record_count"),
                    "label": manifest.get("label", ""),
                }
            )
        return out

    def latest(self) -> Optional[str]:
        entries = self.list()
        if not entries:
            return None
        return max(entries, key=lambda e: e.get("created_ts") or 0)["checkpoint_id"]

    def checkpoint_dir(self, checkpoint_id: str) -> Path:
        return self.checkpoints_dir / checkpoint_id


__all__ = [
    "CheckpointIntegrityError",
    "CheckpointUnavailableError",
    "CheckpointManager",
    "CHECKPOINT_FORMAT",
]
