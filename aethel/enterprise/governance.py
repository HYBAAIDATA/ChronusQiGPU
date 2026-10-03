"""Quotas and resource governance for enterprise custody."""
from __future__ import annotations

from dataclasses import dataclass

from .errors import ResourceExhausted


@dataclass
class Quotas:
    max_payload: int = 1_048_576  # 1 MiB default
    max_records: int = 100_000
    max_tenant_bytes: int = 64 * 1_048_576  # 64 MiB default per tenant

    def check_payload(self, size: int) -> None:
        if size > self.max_payload:
            raise ResourceExhausted(
                f"payload {size} exceeds max_payload {self.max_payload}"
            )

    def check_records(self, count: int) -> None:
        if count > self.max_records:
            raise ResourceExhausted(
                f"records {count} exceeds max_records {self.max_records}"
            )

    def check_tenant_bytes(self, used: int, incoming: int = 0) -> None:
        total = used + incoming
        if total > self.max_tenant_bytes:
            raise ResourceExhausted(
                f"tenant bytes {total} exceeds max_tenant_bytes {self.max_tenant_bytes}"
            )


__all__ = ["Quotas"]
