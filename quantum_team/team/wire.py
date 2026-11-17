"""Binary/JSON wire protocol between Leader and Specialist agents.

Frame layout:
    [2B magic b'QT'][1B version][1B kind][4B BE len][8B sha256 prefix]
    [folded blob: 4B BE original-payload-length + folded payload bytes]

Order of operations, and why:
  encode: canonical JSON -> fold -> blob -> SHA256(blob)[:8] -> header
  decode: header checks -> SHA256(blob) check -> unfold -> canonical
          self-check -> schema validation -> typed message

The digest covers the transmitted bytes, so corruption is rejected
BEFORE any parsing. After unfold, the payload is re-canonicalized and
compared byte-for-byte: a sender using non-canonical JSON is rejected,
not tolerated. Payload integrity (content addressing) is a separate
hash: PatchMessage.patch_id commits to the logical content.
"""

from __future__ import annotations

import dataclasses
import enum
import hashlib
import json
import re
import struct
from typing import Any

from .contracts import (CONTRACT_SYNC_SCHEMA_V1, FITNESS_REPORT_SCHEMA_V1,
                        PATCH_SCHEMA_V1, TASK_SCHEMA_V1, canonical_json)
from .fold import fold as _fold
from .fold import from_wire as _fold_from_wire
from .fold import to_wire as _fold_to_wire
from .fold import unfold as _unfold

HEADER_STRUCT = struct.Struct(">2sBBI8s")
MAGIC = b"QT"
WIRE_VERSION = 1


class MessageKind(enum.IntEnum):
    CONTRACT_SYNC = 1
    TASK = 2
    PATCH = 3
    FITNESS_REPORT = 4


# ---------------------------------------------------------------------
# Typed messages
# ---------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class ContractSyncMessage:
    contracts: tuple

    def to_dict(self) -> dict:
        return {"contracts": [dict(c) for c in self.contracts]}

    @classmethod
    def from_dict(cls, d: dict) -> "ContractSyncMessage":
        return cls(contracts=tuple(dict(c) for c in d["contracts"]))


@dataclasses.dataclass(frozen=True)
class TaskMessage:
    task_id: int
    generation: int
    specialty: str
    module: str
    description: str
    required_digests: tuple
    parent_patches: tuple = ()

    def to_dict(self) -> dict:
        return {"task_id": self.task_id, "generation": self.generation,
                "specialty": self.specialty, "module": self.module,
                "description": self.description,
                "required_digests": sorted(self.required_digests),
                "parent_patches": list(self.parent_patches)}

    @classmethod
    def from_dict(cls, d: dict) -> "TaskMessage":
        return cls(task_id=int(d["task_id"]), generation=int(d["generation"]),
                   specialty=str(d["specialty"]), module=str(d["module"]),
                   description=str(d["description"]),
                   required_digests=tuple(d["required_digests"]),
                   parent_patches=tuple(d["parent_patches"]))


@dataclasses.dataclass(frozen=True)
class PatchMessage:
    task_id: int
    agent_id: str
    parent_ids: tuple
    files: dict
    declares: frozenset
    tests_passed: int
    tests_total: int
    files_changed_conflicts: tuple = ()
    patch_id: str = ""

    def __post_init__(self) -> None:
        if self.tests_passed < 0 or self.tests_total < 0 \
                or self.tests_passed > self.tests_total:
            raise ValueError(
                f"Invalid test counts: {self.tests_passed}/{self.tests_total}")
        computed = self._compute_id()
        if self.patch_id and self.patch_id != computed:
            raise ValueError(f"patch_id mismatch: expected {computed}, "
                             f"got {self.patch_id}")
        object.__setattr__(self, "patch_id", computed)

    def _compute_id(self) -> str:
        body = {"task_id": self.task_id, "agent_id": self.agent_id,
                "parent_ids": list(self.parent_ids), "files": self.files,
                "declares": sorted(self.declares),
                "tests_passed": self.tests_passed,
                "tests_total": self.tests_total,
                "files_changed_conflicts": list(self.files_changed_conflicts)}
        return hashlib.sha256(canonical_json(body)).hexdigest()

    def to_dict(self) -> dict:
        return {"patch_id": self.patch_id, "task_id": self.task_id,
                "agent_id": self.agent_id,
                "parent_ids": list(self.parent_ids),
                "files": dict(sorted(self.files.items())),
                "declares": sorted(self.declares),
                "tests_passed": self.tests_passed,
                "tests_total": self.tests_total,
                "files_changed_conflicts": list(self.files_changed_conflicts)}

    @classmethod
    def from_dict(cls, d: dict) -> "PatchMessage":
        return cls(patch_id=str(d["patch_id"]), task_id=int(d["task_id"]),
                   agent_id=str(d["agent_id"]),
                   parent_ids=tuple(d["parent_ids"]),
                   files=dict(d["files"]),
                   declares=frozenset(d["declares"]),
                   tests_passed=int(d["tests_passed"]),
                   tests_total=int(d["tests_total"]),
                   files_changed_conflicts=tuple(d["files_changed_conflicts"]))


@dataclasses.dataclass(frozen=True)
class FitnessReportMessage:
    patch_id: str
    task_id: int
    conforms: bool
    missing_digests: tuple
    extra_digests: tuple
    pass_ratio: float
    conflict_penalty: float
    raw_score: float
    normalized_phase_angle: float          # theta_i = pi * f_i in [0, pi]

    def to_dict(self) -> dict:
        return {"patch_id": self.patch_id, "task_id": self.task_id,
                "conforms": self.conforms,
                "missing_digests": list(self.missing_digests),
                "extra_digests": list(self.extra_digests),
                "pass_ratio": round(self.pass_ratio, 8),
                "conflict_penalty": round(self.conflict_penalty, 8),
                "raw_score": round(self.raw_score, 8),
                "normalized_phase_angle": round(self.normalized_phase_angle, 8)}

    @classmethod
    def from_dict(cls, d: dict) -> "FitnessReportMessage":
        return cls(patch_id=str(d["patch_id"]), task_id=int(d["task_id"]),
                   conforms=bool(d["conforms"]),
                   missing_digests=tuple(d["missing_digests"]),
                   extra_digests=tuple(d["extra_digests"]),
                   pass_ratio=float(d["pass_ratio"]),
                   conflict_penalty=float(d["conflict_penalty"]),
                   raw_score=float(d["raw_score"]),
                   normalized_phase_angle=float(d["normalized_phase_angle"]))


MessageUnion = (ContractSyncMessage | TaskMessage | PatchMessage
                | FitnessReportMessage)

_KIND_TO_CLS = {
    MessageKind.CONTRACT_SYNC: ContractSyncMessage,
    MessageKind.TASK: TaskMessage,
    MessageKind.PATCH: PatchMessage,
    MessageKind.FITNESS_REPORT: FitnessReportMessage,
}
_CLS_TO_KIND = {v: k for k, v in _KIND_TO_CLS.items()}

_PAYLOAD_SCHEMAS = {
    MessageKind.CONTRACT_SYNC: CONTRACT_SYNC_SCHEMA_V1,
    MessageKind.TASK: TASK_SCHEMA_V1,
    MessageKind.PATCH: PATCH_SCHEMA_V1,
    MessageKind.FITNESS_REPORT: FITNESS_REPORT_SCHEMA_V1,
}


# ---------------------------------------------------------------------
# Minimal structural schema validator — supports exactly the constructs
# used by the frozen schemas above, nothing speculative
# ---------------------------------------------------------------------

def _validate(obj: Any, schema: dict, path: str = "payload") -> None:
    t = schema.get("type")
    if t == "object":
        if not isinstance(obj, dict):
            raise ValueError(f"{path}: expected object")
        props = schema.get("properties", {})
        ap = schema.get("additionalProperties", True)
        if ap is False:
            extra = set(obj) - set(props)
            if extra:
                raise ValueError(f"{path}: unknown properties {sorted(extra)}")
        for key in schema.get("required", []):
            if key not in obj:
                raise ValueError(f"{path}: missing required {key!r}")
        for key, val in obj.items():
            if key in props:
                _validate(val, props[key], f"{path}.{key}")
            elif isinstance(ap, dict):
                _validate(val, ap, f"{path}.{key}")
    elif t == "array":
        if not isinstance(obj, list):
            raise ValueError(f"{path}: expected array")
        items = schema.get("items")
        if items:
            for i, val in enumerate(obj):
                _validate(val, items, f"{path}[{i}]")
    elif t == "string":
        if not isinstance(obj, str):
            raise ValueError(f"{path}: expected string")
        if "minLength" in schema and len(obj) < schema["minLength"]:
            raise ValueError(f"{path}: shorter than minLength")
        if "pattern" in schema and not re.fullmatch(schema["pattern"], obj):
            raise ValueError(f"{path}: fails pattern {schema['pattern']!r}")
    elif t == "integer":
        if not isinstance(obj, int) or isinstance(obj, bool):
            raise ValueError(f"{path}: expected integer")
    elif t == "number":
        if isinstance(obj, bool) or not isinstance(obj, (int, float)):
            raise ValueError(f"{path}: expected number")
    elif t == "boolean":
        if not isinstance(obj, bool):
            raise ValueError(f"{path}: expected boolean")
    if "enum" in schema and obj not in schema["enum"]:
        raise ValueError(f"{path}: not in enum {schema['enum']}")
    if "minimum" in schema and obj < schema["minimum"]:
        raise ValueError(f"{path}: below minimum")
    if "maximum" in schema and obj > schema["maximum"]:
        raise ValueError(f"{path}: above maximum")


# ---------------------------------------------------------------------
# Frame codec
# ---------------------------------------------------------------------

def encode_frame(msg: MessageUnion) -> bytes:
    kind = _CLS_TO_KIND[type(msg)]
    payload = canonical_json(msg.to_dict())
    blob = _fold_to_wire(_fold(payload))
    digest_prefix = hashlib.sha256(blob).digest()[:8]
    header = HEADER_STRUCT.pack(MAGIC, WIRE_VERSION, int(kind), len(blob),
                                digest_prefix)
    return header + blob


def decode_frame(frame: bytes):
    if len(frame) < HEADER_STRUCT.size:
        raise ValueError(f"Truncated frame: {len(frame)} < {HEADER_STRUCT.size}")
    magic, version, kind_int, length, digest_prefix = \
        HEADER_STRUCT.unpack(frame[:HEADER_STRUCT.size])
    if magic != MAGIC:
        raise ValueError(f"Invalid wire magic: {magic!r}")
    if version != WIRE_VERSION:
        raise ValueError(f"Unsupported wire version: {version}")
    blob = frame[HEADER_STRUCT.size:]
    if len(blob) != length:
        raise ValueError(f"Frame length mismatch: header={length}, "
                         f"actual={len(blob)}")
    if hashlib.sha256(blob).digest()[:8] != digest_prefix:
        raise ValueError("Wire frame corrupted: SHA-256 prefix mismatch")

    payload = _unfold(_fold_from_wire(blob))
    if not payload:
        raise ValueError("Empty payload after unfold")

    data = json.loads(payload.decode("utf-8"))
    if canonical_json(data) != payload:                    # canonical self-check
        raise ValueError("Payload is not canonical JSON")

    kind = MessageKind(kind_int)
    _validate(data, _PAYLOAD_SCHEMAS[kind])
    return kind, _KIND_TO_CLS[kind].from_dict(data)
