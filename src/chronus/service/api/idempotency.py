"""Idempotent POST support via the Idempotency-Key header."""

from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass

from fastapi import Depends, Request
from fastapi.responses import JSONResponse

from chronus.service.api import state, store
from chronus.service.api.errors import ApiError
from chronus.service.api.schemas import Workload, WorkloadCreate
from chronus.service.api.security import Principal, current_principal

_KEY_PATTERN = re.compile(r"[A-Za-z0-9._:-]{8,255}")
_TTL_SECONDS = 24 * 60 * 60


def reset_idempotency_store() -> None:
    state.reset_idempotency()


@dataclass
class Guard:
    tenant_id: str
    key: str
    body_hash: str

    def _record(self, conn=None) -> dict | None:
        record = state.get_idempotency(self.tenant_id, self.key, conn)
        if record is None:
            return None
        if record["expires"] < time.time():
            state.delete_idempotency(self.tenant_id, self.key, conn)
            return None
        if record["body_hash"] != self.body_hash:
            raise ApiError(
                409, "idempotency_conflict", "Idempotency key reused",
                "This key was used with a different request body.",
            )
        return record

    def replay(self) -> JSONResponse | None:
        record = self._record()
        if record is None:
            return None
        return JSONResponse(record["body"], status_code=record["status"],
                            headers={**record["headers"], "Idempotent-Replay": "true"})

    def remember(self, status: int, body: dict, headers: dict[str, str]) -> None:
        state.put_idempotency(self.tenant_id, self.key, {
            "body_hash": self.body_hash, "status": status,
            "body": body, "headers": headers, "expires": time.time() + _TTL_SECONDS,
        })

    def create_workload(self, payload: WorkloadCreate) -> tuple[Workload, bool]:
        """Create once across workers; return the workload and whether it is a replay."""
        with state.atomic() as conn:
            record = self._record(conn)
            if record is not None:
                return Workload.model_validate(record["body"]), True
            workload = store.create_workload(self.tenant_id, payload, conn)
            body = workload.model_dump(mode="json")
            headers = {"Location": f"/v1/workloads/{workload.id}"}
            state.put_idempotency(
                self.tenant_id,
                self.key,
                {
                    "body_hash": self.body_hash,
                    "status": 202,
                    "body": body,
                    "headers": headers,
                    "expires": time.time() + _TTL_SECONDS,
                },
                conn,
            )
            return workload, False


async def idempotency_guard(
    request: Request,
    principal: Principal = Depends(current_principal),
) -> Guard:
    key = request.headers.get("Idempotency-Key", "").strip()
    if not key:
        raise ApiError(428, "idempotency_key_required", "Idempotency-Key required",
                       "Send a unique Idempotency-Key header so retries are safe.")
    if not _KEY_PATTERN.fullmatch(key):
        raise ApiError(400, "invalid_idempotency_key", "Invalid Idempotency-Key",
                       "Use 8-255 characters from [A-Za-z0-9._:-].")
    body = await request.body()
    return Guard(principal.tenant_id, key, hashlib.sha256(body).hexdigest())
