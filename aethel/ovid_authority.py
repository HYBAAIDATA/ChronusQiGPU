"""Legacy Ovid-root storage (ovid-authority/v1), not enterprise Theseus custody.

OVID owns sealed folded objects. THESEUS rebuilds query/index projections
from this root and may be deleted without destroying authoritative state.
Chronus is not consulted and must not be required for put/get/verify.
"""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from .ovid import (
    OWNER_ID,
    FoldedWorkingForm,
    Ovid,
    TransformLineage,
    open_ovid,
    working_form_digest,
)
from .encoding import fold
from .zeckendorf import apply_zeckendorf_compression
from .storage import _atomic_write as _durable_write

SCHEMA = "ovid-authority/v1"
CLAIM_BOUNDARY = (
    "In the legacy-ovid-root/v1 profile only, OVID is the durable root. "
    "THESEUS projections are rebuildable from OVID and are not required "
    "to establish object existence or integrity. Chronus is execution-only "
    "and cannot decide storage correctness."
)


class OvidAuthorityError(RuntimeError):
    """Fail-closed OVID authority error."""


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _durable_write(path, text.encode("utf-8"))


@dataclass(frozen=True)
class OvidObject:
    """One sealed authoritative object."""

    object_id: str
    digest: str
    working_digest: str
    raw_len: int
    folded_units: int
    lineage: Optional[TransformLineage] = None


@dataclass
class OvidAuthority:
    """Disk-backed authoritative store of folded working forms."""

    root: Path
    ovid: Ovid = field(default_factory=open_ovid)
    _lock: threading.RLock = field(default_factory=threading.RLock)
    _index: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.root = Path(self.root)
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "objects").mkdir(parents=True, exist_ok=True)
        self._load_index()

    @property
    def claim_boundary(self) -> str:
        return CLAIM_BOUNDARY

    def _index_path(self) -> Path:
        return self.root / "ovid_index.json"

    def _object_path(self, object_id: str) -> Path:
        if not isinstance(object_id, str) or len(object_id) != 64:
            raise OvidAuthorityError("object_id must be a 64-char hex digest")
        bytes.fromhex(object_id)
        return self.root / "objects" / f"{object_id}.json"

    def _load_index(self) -> None:
        path = self._index_path()
        if not path.is_file():
            self._index = {}
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OvidAuthorityError(f"unreadable OVID index: {exc}") from exc
        if data.get("schema") != SCHEMA or data.get("owner") != OWNER_ID:
            raise OvidAuthorityError("OVID index schema/owner mismatch")
        records = data.get("records")
        if not isinstance(records, dict):
            raise OvidAuthorityError("OVID index has no record table")
        self._index = records

    def _save_index_locked(self) -> None:
        payload = {
            "schema": SCHEMA,
            "owner": OWNER_ID,
            "records": self._index,
        }
        _atomic_write(self._index_path(), json.dumps(payload, indent=2, sort_keys=True))

    def put(self, payload: bytes, *, parents: tuple[str, ...] = ()) -> OvidObject:
        if not isinstance(payload, (bytes, bytearray)):
            raise TypeError("OVID authority requires bytes")
        data = bytes(payload)
        form = self.ovid.metamorphose(data, parents=parents)
        if not form.verify():
            raise OvidAuthorityError("folded working form failed verify")
        object_id = form.digest
        record = {
            "object_id": object_id,
            "digest": form.digest,
            "working_digest": working_form_digest(form.vector),
            "raw_len": form.raw_len,
            "folded_units": form.folded_units,
            "owner": form.owner,
            "working_form": json.loads(
                json.dumps(
                    {
                        "kind": "zeckendorf_vector_v1",
                        "blocks": [[int(o), int(m)] for o, m in form.vector.blocks],
                        "total_bytes": int(form.vector.total_bytes),
                        "folded_units": int(form.vector.folded_units),
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                )
            ),
            "lineage": form.lineage.to_dict() if form.lineage is not None else None,
            "payload_sha256": form.digest,
            "payload_b64": __import__("base64").b64encode(data).decode("ascii"),
        }
        with self._lock:
            _atomic_write(
                self._object_path(object_id),
                json.dumps(record, indent=2, sort_keys=True),
            )
            self._index[object_id] = {
                "object_id": object_id,
                "digest": form.digest,
                "working_digest": record["working_digest"],
                "raw_len": form.raw_len,
                "folded_units": form.folded_units,
            }
            self._save_index_locked()
        return OvidObject(
            object_id=object_id,
            digest=form.digest,
            working_digest=record["working_digest"],
            raw_len=form.raw_len,
            folded_units=form.folded_units,
            lineage=form.lineage,
        )

    def _load_record(self, object_id: str) -> Dict[str, Any]:
        path = self._object_path(object_id)
        if not path.is_file():
            raise OvidAuthorityError(f"missing OVID object {object_id}")
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OvidAuthorityError(
                f"unreadable OVID object {object_id}: {exc}"
            ) from exc
        if not isinstance(record, dict):
            raise OvidAuthorityError("OVID object must be an object")
        if record.get("digest") != object_id or record.get("owner") != OWNER_ID:
            raise OvidAuthorityError(f"OVID object {object_id} failed identity bind")
        return record

    def get_bytes(self, object_id: str) -> bytes:
        record = self._load_record(object_id)
        item = self._index.get(object_id)
        fields = ("object_id", "digest", "working_digest", "raw_len", "folded_units")
        if not isinstance(item, dict) or any(
            item.get(k) != record.get(k) for k in fields
        ):
            raise OvidAuthorityError("OVID object/index metadata mismatch")
        if (
            record.get("object_id") != object_id
            or record.get("payload_sha256") != object_id
        ):
            raise OvidAuthorityError("OVID object identity mismatch")
        try:
            data = __import__("base64").b64decode(record["payload_b64"], validate=True)
        except (KeyError, TypeError, ValueError) as exc:
            raise OvidAuthorityError("OVID payload encoding is invalid") from exc
        if hashlib.sha256(data).hexdigest() != record["digest"]:
            raise OvidAuthorityError(f"OVID object {object_id} digest mismatch")
        form = self.reconstruct_form(record, data)
        if not form.verify():
            raise OvidAuthorityError(
                f"OVID object {object_id} working form failed verify"
            )
        materialised = self.ovid.materialise(form)
        if materialised != data:
            raise OvidAuthorityError(f"OVID object {object_id} materialise mismatch")
        return data

    def reconstruct_form(
        self, record: Dict[str, Any], data: bytes
    ) -> FoldedWorkingForm:
        vector = fold(data, max_fold_len=self.ovid.max_fold_len)
        sparse = apply_zeckendorf_compression(data)
        working = record.get("working_form") or {}
        expected_working = {
            "kind": "zeckendorf_vector_v1",
            "blocks": [[int(o), int(m)] for o, m in vector.blocks],
            "total_bytes": len(data),
            "folded_units": vector.folded_units,
        }
        if json.dumps(working, sort_keys=True) != json.dumps(
            expected_working, sort_keys=True
        ):
            raise OvidAuthorityError(
                "stored folded representation differs from verified payload"
            )
        if (
            type(record.get("raw_len")) is not int
            or record["raw_len"] != len(data)
            or type(record.get("folded_units")) is not int
            or record["folded_units"] != vector.folded_units
        ):
            raise OvidAuthorityError("stored folded metadata mismatch")
        if working_form_digest(vector) != record.get("working_digest"):
            raise OvidAuthorityError("folded working digest mismatch")
        lineage = None
        if record.get("lineage"):
            try:
                lineage = TransformLineage.from_dict(record["lineage"])
            except (KeyError, TypeError, ValueError) as exc:
                raise OvidAuthorityError("stored transform lineage is invalid") from exc
            if (
                lineage.input_sha256 != record["digest"]
                or lineage.input_bytes != len(data)
                or lineage.folded_units != vector.folded_units
                or lineage.producer != OWNER_ID
            ):
                raise OvidAuthorityError("stored transform lineage binding mismatch")
        return FoldedWorkingForm(
            vector=vector,
            sparse=sparse,
            digest=record["digest"],
            raw_len=int(record["raw_len"]),
            folded_units=int(record["folded_units"]),
            owner=OWNER_ID,
            lineage=lineage,
        )

    def get_form(self, object_id: str) -> FoldedWorkingForm:
        with self._lock:
            data = self.get_bytes(object_id)
            return self.reconstruct_form(self._load_record(object_id), data)

    def list_ids(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._index))

    def objects(self) -> Iterable[OvidObject]:
        with self._lock:
            items = list(self._index.values())
        for item in items:
            yield OvidObject(
                object_id=str(item["object_id"]),
                digest=str(item["digest"]),
                working_digest=str(item["working_digest"]),
                raw_len=int(item["raw_len"]),
                folded_units=int(item["folded_units"]),
            )

    def verify(self) -> bool:
        try:
            for object_id in self.list_ids():
                self.get_bytes(object_id)
            return True
        except OvidAuthorityError:
            return False

    def health(self) -> Dict[str, Any]:
        ok = self.verify()
        return {
            "owner": OWNER_ID,
            "status": "ok" if ok else "fail",
            "schema": SCHEMA,
            "storage_profile": "legacy-ovid-root/v1",
            "component": "aethel.ovid_authority.OvidAuthority",
            "records": len(self._index),
            "claim_boundary": CLAIM_BOUNDARY,
            "production_surface": True,
            "chronus_required": False,
            "theseus_required": False,
        }


def open_ovid_authority(
    root: str | Path, *, ovid: Optional[Ovid] = None
) -> OvidAuthority:
    kwargs: Dict[str, Any] = {"root": Path(root)}
    if ovid is not None:
        kwargs["ovid"] = ovid
    return OvidAuthority(**kwargs)


__all__ = [
    "SCHEMA",
    "CLAIM_BOUNDARY",
    "OvidAuthorityError",
    "OvidObject",
    "OvidAuthority",
    "open_ovid_authority",
]
