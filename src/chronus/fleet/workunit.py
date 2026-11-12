# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
# Chronus is a HYBA Data product.
"""Work units: what callers submit to the fleet.

A work unit names a kernel, its parameters and its input bytes, plus how it
should run: the requested route (``auto`` or one device route), the resident
lattice rung that stripes it into tiles, and the pool it draws capacity from
(spec 2.1, P3). ``prefer`` (``ours`` or ``host``) steers ``auto`` on every
worker for this unit; left unset, each worker's own ``--prefer`` applies. The
fleet itself knows nothing about what the kernel means.
"""

from __future__ import annotations

from dataclasses import dataclass, field


class _FrozenDict(dict):
    def _immutable(self, *args, **kwargs):
        raise TypeError("work unit parameters are immutable")
    __setitem__ = __delitem__ = clear = pop = popitem = setdefault = update = __ior__ = _immutable


class _FrozenList(list):
    def _immutable(self, *args, **kwargs):
        raise TypeError("work unit parameters are immutable")
    __setitem__ = __delitem__ = append = extend = insert = pop = remove = clear = sort = reverse = __iadd__ = __imul__ = _immutable


def _snapshot(value):
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise KernelError("params keys must be strings at every level")
        return _FrozenDict((key, _snapshot(item)) for key,item in value.items())
    if isinstance(value, (list,tuple)):
        return _FrozenList(_snapshot(item) for item in value)
    return value

from typing import Any, Mapping

from chronus.fleet.backends import PREFERENCES
from chronus.fleet.canonical import b64decode, b64encode, canonical_json, digest_json, sha256_hex
from chronus.fleet.errors import KernelError
from chronus.fleet.kernels import DEVICE_ROUTES
from chronus.fleet.lattice import DEFAULT_VIRTUAL_UNITS, require_rung

ROUTE_AUTO = "auto"
POOL_PREFILL = "prefill"
POOL_DECODE = "decode"
POOLS = (POOL_PREFILL, POOL_DECODE)
MAX_LABEL_CHARS = 200


@dataclass(frozen=True)
class WorkUnit:
    kernel: str
    payload: bytes = b""
    params: Mapping[str, Any] = field(default_factory=dict)
    route: str = ROUTE_AUTO
    virtual_units: int = DEFAULT_VIRTUAL_UNITS
    pool: str = POOL_DECODE
    kernel_version: str | None = None
    label: str = ""
    prefer: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.kernel, str) or not self.kernel:
            raise KernelError("work unit needs a kernel name")
        if not isinstance(self.payload, (bytes, bytearray)):
            raise KernelError("payload must be bytes")
        object.__setattr__(self, "payload", bytes(self.payload))
        if not isinstance(self.params, Mapping):
            raise KernelError("params must be a mapping")
        object.__setattr__(self, "params", _snapshot(self.params))
        try:
            canonical_json(dict(self.params))
        except (TypeError, ValueError) as exc:
            raise KernelError(f"params must be JSON-serialisable without NaN or infinity: {exc}") from exc
        if self.route != ROUTE_AUTO and self.route not in DEVICE_ROUTES:
            raise KernelError(f"route must be auto or one of {', '.join(DEVICE_ROUTES)}")
        require_rung(self.virtual_units)
        if self.pool not in POOLS:
            raise KernelError(f"pool must be one of {POOLS}")
        if not isinstance(self.label, str) or len(self.label) > MAX_LABEL_CHARS:
            raise KernelError(f"label must be a string of at most {MAX_LABEL_CHARS} characters")
        if self.prefer is not None and self.prefer not in PREFERENCES:
            raise KernelError("prefer must be ours or host")

    @property
    def payload_sha256(self) -> str:
        return sha256_hex(self.payload)

    def identity(self) -> dict[str, Any]:
        """Everything that determines the result, with the payload by digest."""
        identity = {
            "kernel": self.kernel,
            "kernel_version": self.kernel_version,
            "params": dict(self.params),
            "payload_sha256": self.payload_sha256,
            "payload_bytes": len(self.payload),
            "route": self.route,
            "virtual_units": self.virtual_units,
            "pool": self.pool,
        }
        if self.prefer is not None:
            identity["prefer"] = self.prefer
        return identity

    def digest(self) -> str:
        return digest_json(self.identity())

    def to_wire(self) -> dict[str, Any]:
        return {
            "kernel": self.kernel,
            "kernel_version": self.kernel_version,
            "params": dict(self.params),
            "payload_b64": b64encode(self.payload),
            "route": self.route,
            "virtual_units": self.virtual_units,
            "pool": self.pool,
            "label": self.label,
            "prefer": self.prefer,
        }

    @classmethod
    def from_wire(cls, data: Mapping[str, Any]) -> "WorkUnit":
        if not isinstance(data, Mapping):
            raise KernelError("work_unit must be an object")
        allowed = {"kernel", "kernel_version", "params", "payload_b64", "route", "virtual_units", "pool", "label", "prefer"}
        extra = set(data) - allowed
        if extra:
            raise KernelError(f"unexpected work_unit fields: {sorted(extra)}")
        try:
            payload = b64decode(data.get("payload_b64", ""))
        except ValueError as exc:
            raise KernelError(str(exc)) from exc
        return cls(
            kernel=data.get("kernel", ""),
            payload=payload,
            params=data.get("params") or {},
            route=data.get("route", ROUTE_AUTO),
            virtual_units=data.get("virtual_units", DEFAULT_VIRTUAL_UNITS),
            pool=data.get("pool", POOL_DECODE),
            kernel_version=data.get("kernel_version"),
            label=data.get("label", ""),
            prefer=data.get("prefer"),
        )
