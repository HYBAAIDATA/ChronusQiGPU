# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""Durable THESEUS record of miner pool switches. Fails closed when configured.

Enabled by two environment variables: HYBA_MINE_CUSTODY_PATH (the THESEUS store
file) and HYBA_MINE_TENANT_ID (the tenant the records belong to). Set neither
and custody is off. Set only one and the miner refuses to start.

When custody is on, a pool switch is refused unless its request is recorded in
THESEUS first. A record never carries a pool login.

This is an audit record. It is not AL HARAS admission: the local console has no
operator identity to admit.
"""

from __future__ import annotations

import json
import os
from typing import Any, Mapping, Optional

ENV_PATH = "HYBA_MINE_CUSTODY_PATH"
ENV_TENANT = "HYBA_MINE_TENANT_ID"
SCHEMA = "hyba-mine.pool-switch/1"
EVENT_REQUESTED = "HYBA_MINE_POOL_SWITCH_REQUESTED"
EVENT_APPLIED = "HYBA_MINE_POOL_SWITCH_APPLIED"
EVENT_REFUSED = "HYBA_MINE_POOL_SWITCH_REFUSED"


class CustodyError(RuntimeError):
    """A pool-switch record could not be written to THESEUS."""


class PoolSwitchCustody:
    def __init__(self, service: Any, tenant_id: str) -> None:
        if not isinstance(tenant_id, str) or not tenant_id.strip():
            raise CustodyError("the tenant id must be a non-empty string")
        self._service = service
        self._tenant = tenant_id

    def record(self, event: str, data: Mapping[str, Any]) -> None:
        body = {"schema": SCHEMA, "event": event, **data}
        payload = json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
        try:
            self._service.append_journal_event(self._tenant, event, payload)
        except Exception as exc:  # any failure to write means the switch is not recorded
            raise CustodyError(f"{type(exc).__name__}: {exc}") from exc


def custody_from_environment(env: Optional[Mapping[str, str]] = None) -> Optional[PoolSwitchCustody]:
    env = os.environ if env is None else env
    path = env.get(ENV_PATH, "").strip()
    tenant = env.get(ENV_TENANT, "").strip()
    if not path and not tenant:
        return None
    if not path or not tenant:
        raise CustodyError(f"set both {ENV_PATH} and {ENV_TENANT}, or neither")
    from chronus.storage.durable import DurableTheseusService  # imported only when custody is on

    return PoolSwitchCustody(DurableTheseusService(path), tenant)
