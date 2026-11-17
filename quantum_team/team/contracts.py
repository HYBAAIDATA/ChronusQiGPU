"""Frozen interface artifacts and deterministic schema registry.

Every contract is hashed over its canonical JSON representation; drift
in any field, type, or version produces a distinct SHA-256 digest.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from typing import Any


def canonical_json(obj: Any) -> bytes:
    """RFC 8785 / JCS-compatible deterministic JSON encoding (UTF-8)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


@dataclasses.dataclass(frozen=True)
class Contract:
    name: str
    version: int
    schema: dict
    digest: str


# ---------------------------------------------------------------------
# Canonical frozen schemas for the wire protocol
# ---------------------------------------------------------------------

TASK_SCHEMA_V1: dict = {
    "type": "object",
    "required": ["task_id", "generation", "specialty", "module",
                 "description", "required_digests", "parent_patches"],
    "properties": {
        "task_id": {"type": "integer", "minimum": 0},
        "generation": {"type": "integer", "minimum": 0},
        "specialty": {"type": "string",
                      "enum": ["api", "connectivity", "tests"]},
        "module": {"type": "string",
                   "pattern": r"^[a-zA-Z_][a-zA-Z0-9_]*$"},
        "description": {"type": "string", "minLength": 1},
        "required_digests": {"type": "array",
                             "items": {"type": "string",
                                       "pattern": r"^[0-9a-f]{64}$"}},
        "parent_patches": {"type": "array",
                           "items": {"type": "string",
                                     "pattern": r"^[0-9a-f]{64}$"}},
    },
    "additionalProperties": False,
}

PATCH_SCHEMA_V1: dict = {
    "type": "object",
    "required": ["patch_id", "task_id", "agent_id", "parent_ids",
                 "files", "declares", "tests_passed", "tests_total",
                 "files_changed_conflicts"],
    "properties": {
        "patch_id": {"type": "string", "pattern": r"^[0-9a-f]{64}$"},
        "task_id": {"type": "integer", "minimum": 0},
        "agent_id": {"type": "string", "minLength": 1},
        "parent_ids": {"type": "array",
                       "items": {"type": "string",
                                 "pattern": r"^[0-9a-f]{64}$"}},
        "files": {"type": "object",
                  "additionalProperties": {"type": "string"}},
        "declares": {"type": "array",
                     "items": {"type": "string",
                               "pattern": r"^[0-9a-f]{64}$"}},
        "tests_passed": {"type": "integer", "minimum": 0},
        "tests_total": {"type": "integer", "minimum": 0},
        "files_changed_conflicts": {"type": "array",
                                    "items": {"type": "string"}},
    },
    "additionalProperties": False,
}

FITNESS_REPORT_SCHEMA_V1: dict = {
    "type": "object",
    "required": ["patch_id", "task_id", "conforms", "missing_digests",
                 "extra_digests", "pass_ratio", "conflict_penalty",
                 "raw_score", "normalized_phase_angle"],
    "properties": {
        "patch_id": {"type": "string", "pattern": r"^[0-9a-f]{64}$"},
        "task_id": {"type": "integer", "minimum": 0},
        "conforms": {"type": "boolean"},
        "missing_digests": {"type": "array", "items": {"type": "string"}},
        "extra_digests": {"type": "array", "items": {"type": "string"}},
        "pass_ratio": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "conflict_penalty": {"type": "number", "minimum": 0.0},
        "raw_score": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "normalized_phase_angle": {"type": "number", "minimum": 0.0,
                                   "maximum": 3.141592653589793},
    },
    "additionalProperties": False,
}

CONTRACT_SYNC_SCHEMA_V1: dict = {
    "type": "object",
    "required": ["contracts"],
    "properties": {
        "contracts": {"type": "array", "items": {"type": "object"}},
    },
    "additionalProperties": False,
}


class ContractRegistry:
    def __init__(self) -> None:
        self._current: dict = {}
        self._history: list = []

    def freeze(self, name: str, schema: dict, version: int = 1) -> Contract:
        if name in self._current and self._current[name].version >= version:
            raise ValueError(
                f"Contract {name!r} v{self._current[name].version} already "
                "frozen; bump version explicitly to evolve schema.")
        payload = canonical_json({"name": name, "version": version,
                                  "schema": schema})
        digest = hashlib.sha256(payload).hexdigest()
        contract = Contract(name=name, version=version, schema=schema,
                            digest=digest)
        self._current[name] = contract
        self._history.append(contract)
        return contract

    def get(self, name: str) -> Contract:
        return self._current[name]

    def live_digests(self) -> frozenset:
        return frozenset(c.digest for c in self._current.values())

    def conforms(self, declared: frozenset) -> bool:
        """Hard gate: True iff declared digests match the exact live set."""
        return declared == self.live_digests()

    def diff_digests(self, declared: frozenset):
        """(missing_digests, extra_digests) for audit reporting."""
        live = self.live_digests()
        return (tuple(sorted(live - declared)),
                tuple(sorted(declared - live)))

    def export(self) -> tuple:
        """Serializable snapshot for CONTRACT_SYNC frames."""
        return tuple({"name": c.name, "version": c.version,
                      "digest": c.digest, "schema": c.schema}
                     for c in self._current.values())
