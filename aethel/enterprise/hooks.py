"""Security hooks — AL HARAS optional adapter (evidence forward only).

Access doctrine: a stored record does not create authority to access it.
``before_put``/``before_get``/``before_delete`` are the admission surfaces;
when a hook does not implement the get/delete surface custody treats access
policy as unsupplied and reports ``access_contract: none`` in health — it is
declared, never silently open or silently closed.
"""

from __future__ import annotations

from typing import Any, Optional, Protocol, runtime_checkable


@runtime_checkable
class SecurityHook(Protocol):
    def before_put(self, tenant: str, record_id: str, payload: bytes, meta: dict) -> bool:
        """Return True to allow, False to deny."""
        ...

    def before_get(self, tenant: str, record_id: str, meta: dict) -> bool:
        """Return True to allow read, False to deny (fail closed)."""
        ...

    def before_delete(self, tenant: str, record_id: str, meta: dict) -> bool:
        """Return True to allow delete, False to deny (fail closed)."""
        ...

    def after_put(self, tenant: str, record_id: str, envelope: dict, meta: dict) -> None: ...

    def after_get(self, tenant: str, record_id: str, meta: dict) -> None: ...

    def after_heal(self, tenant: str, record_id: str, detail: dict) -> None: ...


class AllowAllHook:
    """Default permissive hook (no security authority attached)."""

    def before_put(self, tenant: str, record_id: str, payload: bytes, meta: dict) -> bool:
        return True

    def before_get(self, tenant: str, record_id: str, meta: dict) -> bool:
        return True

    def before_delete(self, tenant: str, record_id: str, meta: dict) -> bool:
        return True

    def after_put(self, tenant: str, record_id: str, envelope: dict, meta: dict) -> None:
        return None

    def after_get(self, tenant: str, record_id: str, meta: dict) -> None:
        return None

    def after_heal(self, tenant: str, record_id: str, detail: dict) -> None:
        return None


class DenyingHook:
    """Test hook that denies all custody operations."""

    def before_put(self, tenant: str, record_id: str, payload: bytes, meta: dict) -> bool:
        return False

    def before_get(self, tenant: str, record_id: str, meta: dict) -> bool:
        return False

    def before_delete(self, tenant: str, record_id: str, meta: dict) -> bool:
        return False

    def after_put(self, tenant: str, record_id: str, envelope: dict, meta: dict) -> None:
        return None

    def after_get(self, tenant: str, record_id: str, meta: dict) -> None:
        return None

    def after_heal(self, tenant: str, record_id: str, detail: dict) -> None:
        return None


class AlHarasEvidenceAdapter:
    """Optional AL HARAS adapter — forwards evidence only; no embedded policy.

    ``forward`` receives structured evidence dicts. Policy packs stay outside Theseus.
    ``before_put`` delegates to optional ``gate`` callable; default allow.
    """

    def __init__(
        self,
        forward: Optional[Any] = None,
        gate: Optional[Any] = None,
    ) -> None:
        self._forward = forward
        self._gate = gate
        self.evidence: list[dict[str, Any]] = []

    def before_put(self, tenant: str, record_id: str, payload: bytes, meta: dict) -> bool:
        if self._gate is not None:
            return bool(self._gate(tenant, record_id, payload, meta))
        return True

    def before_get(self, tenant: str, record_id: str, meta: dict) -> bool:
        if self._gate is not None:
            return bool(self._gate(tenant, record_id, b"", meta))
        return True

    def before_delete(self, tenant: str, record_id: str, meta: dict) -> bool:
        if self._gate is not None:
            return bool(self._gate(tenant, record_id, b"", meta))
        return True

    def after_get(self, tenant: str, record_id: str, meta: dict) -> None:
        evt = {
            "kind": "after_get",
            "tenant": tenant,
            "record_id": record_id,
            "meta": dict(meta or {}),
        }
        self.evidence.append(evt)
        if self._forward is not None:
            self._forward(evt)

    def after_put(self, tenant: str, record_id: str, envelope: dict, meta: dict) -> None:
        evt = {
            "kind": "after_put",
            "tenant": tenant,
            "record_id": record_id,
            "content_digest": envelope.get("content_digest", ""),
            "generation": envelope.get("generation"),
            "meta": dict(meta or {}),
        }
        self.evidence.append(evt)
        if self._forward is not None:
            self._forward(evt)

    def after_heal(self, tenant: str, record_id: str, detail: dict) -> None:
        evt = {
            "kind": "after_heal",
            "tenant": tenant,
            "record_id": record_id,
            "detail": dict(detail or {}),
        }
        self.evidence.append(evt)
        if self._forward is not None:
            self._forward(evt)


__all__ = [
    "SecurityHook",
    "AllowAllHook",
    "DenyingHook",
    "AlHarasEvidenceAdapter",
]
