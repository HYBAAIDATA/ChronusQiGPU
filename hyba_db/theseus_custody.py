"""THESEUS custody boundary for the hyba_db file plane.

``TheseusFileCustody`` adapts :class:`aethel.enterprise.EnterpriseCustody` — the
canonical durable custody substrate — to the ``FileRegistry`` adapter protocol:

    put_record(tenant_id, record)  -> custody record id
    verify(tenant_id, record_id)   -> bool (record exists and authenticates)
    has_custody()                  -> True

Custody is partitioned per tenant: each tenant maps to its own
``EnterpriseCustody`` under ``<root>/<tenant>``, so a custody identity from one
tenant can never verify inside another. A custody_record_id that does not
resolve to an admitted OperationalRecord fails closed.

The adapter never adjudicates record semantics — it verifies contract admission
(registered producer, supported schema window, explicit evidence state, digest
binding, verifiable dependencies) and stores the record durably. Semantic
revalidation after recovery remains the producer's job, per THESEUS's own
boundary.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Iterable

from aethel.enterprise.custody import EnterpriseCustody
from aethel.enterprise.records import (
    CANONICAL_PRODUCERS,
    OperationalRecord,
    ProducerContract,
    ProducerRegistry,
)

# Producers the file plane legitimately admits beyond the canonical subsystem
# names: the stratum boundary, the SHA256d verifier, the pool, and THESEUS
# itself when it writes custody/reconciliation receipts.
FILE_PLANE_PRODUCERS = (
    "theseus",
    "stratum",
    "pool",
    "sha256d",
    "hyba_db",
    "kellogg",
)


class TheseusFileCustody:
    """Per-tenant THESEUS custody adapter for the file registry."""

    def __init__(
        self,
        root: str | Path,
        *,
        hmac_key: bytes,
        key_id: str = "k1",
        extra_producers: Iterable[str] = (),
        require_authenticity: bool = True,
        allow_insecure_dev_key: bool = False,
        **custody_kwargs: Any,
    ) -> None:
        if not hmac_key:
            raise ValueError("hmac_key is required for THESEUS file custody")
        self.root = Path(root)
        self.hmac_key = bytes(hmac_key)
        self.key_id = str(key_id)
        self.require_authenticity = bool(require_authenticity)
        self.allow_insecure_dev_key = bool(allow_insecure_dev_key)
        self._custody_kwargs = dict(custody_kwargs)
        producers = set(CANONICAL_PRODUCERS) | set(FILE_PLANE_PRODUCERS)
        producers.update(str(p).strip().lower() for p in extra_producers)
        self._producer_registry = ProducerRegistry(
            ProducerContract(name=p) for p in sorted(producers)
        )
        self._stores: dict[str, EnterpriseCustody] = {}
        self._lock = threading.Lock()

    def has_custody(self) -> bool:
        return True

    def _for(self, tenant_id: str) -> EnterpriseCustody:
        with self._lock:
            store = self._stores.get(tenant_id)
            if store is None:
                store = EnterpriseCustody(
                    self.root,
                    tenant=tenant_id,
                    hmac_key=self.hmac_key,
                    key_id=self.key_id,
                    require_authenticity=self.require_authenticity,
                    allow_insecure_dev_key=self.allow_insecure_dev_key,
                    producer_registry=self._producer_registry,
                    **self._custody_kwargs,
                )
                self._stores[tenant_id] = store
            return store

    def put_record(self, tenant_id: str, record: OperationalRecord) -> str:
        """Admit one record into THIS tenant's THESEUS custody."""
        env = self._for(tenant_id).put_record(record, idempotency_key=record.record_id)
        return str(env.record_id)

    def verify(self, tenant_id: str, record_id: str) -> bool:
        """True only when the record exists in this tenant's custody and its
        envelope authenticates (HMAC + digest verified on load)."""
        try:
            self._for(tenant_id).get_record(str(record_id))
        except Exception:
            return False
        return True

    def open_tenant(self, tenant_id: str) -> EnterpriseCustody:
        """Expose the underlying THESEUS store for replay/checkpoint callers."""
        return self._for(tenant_id)

    def close(self) -> None:
        with self._lock:
            stores = list(self._stores.values())
            self._stores.clear()
        for store in stores:
            close = getattr(store, "close", None)
            if callable(close):
                close()


__all__ = ["TheseusFileCustody", "FILE_PLANE_PRODUCERS"]
