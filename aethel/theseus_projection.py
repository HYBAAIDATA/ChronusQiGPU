"""THESEUS rebuildable projection over an OVID authority root.

THESEUS here is not the durable source of truth. Deleting this projection
must not destroy OVID objects. Rebuild compares query outputs against the
OVID generation/digest set.
"""
from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from .ovid_authority import OvidAuthority, OvidObject


SCHEMA = "theseus-projection/v1"
CLAIM_BOUNDARY = (
    "THESEUS is a rebuildable query/index/lineage projection bound to an "
    "OVID object generation and source digest. It is not required to "
    "establish authoritative stored-state existence or integrity."
)


class TheseusProjectionError(RuntimeError):
    """Fail-closed THESEUS projection error."""


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


@dataclass(frozen=True)
class ProjectionRow:
    object_id: str
    digest: str
    working_digest: str
    raw_len: int
    folded_units: int
    ovid_generation: str


@dataclass
class TheseusProjection:
    root: Path
    ovid: OvidAuthority
    _lock: threading.RLock = field(default_factory=threading.RLock)
    _rows: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    generation: str = ""

    def __post_init__(self) -> None:
        self.root = Path(self.root)
        self.root.mkdir(parents=True, exist_ok=True)

    @property
    def claim_boundary(self) -> str:
        return CLAIM_BOUNDARY

    def _index_path(self) -> Path:
        return self.root / "theseus_projection.json"

    def rebuild(self) -> str:
        """Rebuild the entire projection from OVID. Returns generation digest."""
        import hashlib

        rows: Dict[str, Dict[str, Any]] = {}
        for obj in self.ovid.objects():
            payload = self.ovid.get_bytes(obj.object_id)
            if hashlib.sha256(payload).hexdigest() != obj.digest:
                raise TheseusProjectionError(f"OVID digest failed for {obj.object_id}")
            rows[obj.object_id] = {
                "object_id": obj.object_id,
                "digest": obj.digest,
                "working_digest": obj.working_digest,
                "raw_len": obj.raw_len,
                "folded_units": obj.folded_units,
            }
        material = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
        generation = hashlib.sha256(material).hexdigest()
        for row in rows.values():
            row["ovid_generation"] = generation
        with self._lock:
            self._rows = rows
            self.generation = generation
            _atomic_write(
                self._index_path(),
                json.dumps(
                    {
                        "schema": SCHEMA,
                        "ovid_generation": generation,
                        "source": str(self.ovid.root),
                        "rows": rows,
                    },
                    indent=2,
                    sort_keys=True,
                ),
            )
        return generation

    def delete(self) -> None:
        """Drop the projection only. OVID objects remain."""
        with self._lock:
            self._rows = {}
            self.generation = ""
            path = self._index_path()
            if path.is_file():
                path.unlink()

    def lookup(self, object_id: str) -> ProjectionRow:
        with self._lock:
            row = self._rows.get(object_id)
            if row is None:
                raise TheseusProjectionError(f"projection miss: {object_id}")
            return ProjectionRow(
                object_id=str(row["object_id"]),
                digest=str(row["digest"]),
                working_digest=str(row["working_digest"]),
                raw_len=int(row["raw_len"]),
                folded_units=int(row["folded_units"]),
                ovid_generation=str(row["ovid_generation"]),
            )

    def query_ids(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._rows))

    def compare_to_ovid(self) -> Dict[str, Any]:
        ovid_ids = set(self.ovid.list_ids())
        with self._lock:
            proj_ids = set(self._rows)
            generation = self.generation
        missing = sorted(ovid_ids - proj_ids)
        extra = sorted(proj_ids - ovid_ids)
        digest_mismatch = []
        for oid in sorted(ovid_ids & proj_ids):
            if self._rows[oid]["digest"] != oid:
                digest_mismatch.append(oid)
        return {
            "equal": not missing and not extra and not digest_mismatch,
            "ovid_generation": generation,
            "ovid_count": len(ovid_ids),
            "projection_count": len(proj_ids),
            "missing_from_projection": missing,
            "extra_in_projection": extra,
            "digest_mismatch": digest_mismatch,
        }

    def health(self) -> Dict[str, Any]:
        cmp = self.compare_to_ovid()
        return {
            "owner": "theseus",
            "status": "ok" if cmp["equal"] else "stale",
            "schema": SCHEMA,
            "claim_boundary": CLAIM_BOUNDARY,
            "rebuildable": True,
            "authoritative": False,
            "comparison": cmp,
        }


def open_theseus_projection(root: str | Path, ovid: OvidAuthority) -> TheseusProjection:
    return TheseusProjection(root=Path(root), ovid=ovid)


__all__ = [
    "SCHEMA",
    "CLAIM_BOUNDARY",
    "TheseusProjectionError",
    "ProjectionRow",
    "TheseusProjection",
    "open_theseus_projection",
]
