"""Reconstructed PHILOS contracts, not recovered historical source.

Hashes bind canonical content; they confer no execution authority or certification.
"""
from __future__ import annotations
import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from types import MappingProxyType


def plain(value):
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {f.name: plain(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, Mapping):
        if any(not isinstance(k, str) for k in value):
            raise TypeError("canonical mapping keys must be strings")
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, (set, frozenset)):
        return sorted((plain(v) for v in value), key=canonical)
    if isinstance(value, (tuple, list)):
        return [plain(v) for v in value]
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    raise ValueError("unsupported or non-finite canonical value")


def canonical(value):
    return json.dumps(plain(value), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def digest(domain, value):
    return hashlib.sha256(domain.encode() + b"\0" + canonical(value).encode()).hexdigest()


def freeze(value):
    if isinstance(value, Mapping):
        plain(value)  # Validate before freezing; never coerce unknown objects.
        return MappingProxyType({k: freeze(v) for k, v in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(freeze(v) for v in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(freeze(v) for v in value)
    plain(value)
    return value


def finite(value, name, minimum=0):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(name + " must be numeric")
    if not math.isfinite(value) or value < minimum:
        raise ValueError(name + " must be finite and within bounds")


def count(value, name):
    if type(value) is not int or value < 0:
        raise ValueError(name + " must be a nonnegative integer")


def names(values, name):
    result = tuple(values)
    if any(not isinstance(v, str) or not v.strip() for v in result):
        raise ValueError(name + " requires nonempty strings")
    return result


@dataclass(frozen=True)
class CapabilityManifest:
    declared_actions: frozenset[str] = frozenset()
    declared_compositions: frozenset[tuple[str, ...]] = frozenset()
    declared_strategies: frozenset[str] = frozenset()

    def __post_init__(self):
        object.__setattr__(self, "declared_actions", frozenset(names(self.declared_actions, "actions")))
        object.__setattr__(self, "declared_strategies", frozenset(names(self.declared_strategies, "strategies")))
        object.__setattr__(self, "declared_compositions", frozenset(
            names(c, "composition") for c in self.declared_compositions))

    def to_dict(self):
        return plain(self)

    def compute_hash(self):
        return digest("philos.reconstructed.manifest.v1", self)
