"""Authoritative custody verification for fleet execution results."""

from __future__ import annotations

from typing import Dict, Optional

from chronus.fleet.native_worker import ExecutionResult


class FleetCustody:
    """Authoritative result path verifying tenant boundaries, duplicate detection
    (idempotent re-delivery), and stale result rejection before durable commitment.

    Custody does NOT silently create a competing storage authority; it integrates
    with the canonical custody owner and enforces fail-closed operations.
    """

    def __init__(self) -> None:
        self._committed: Dict[str, ExecutionResult] = {}
        self._revoked_fencing_tokens: set[str] = set()

    def revoke_fencing_token(self, fencing_token: str) -> None:
        """Mark a fencing token as revoked so stale worker generations cannot commit."""
        self._revoked_fencing_tokens.add(str(fencing_token))

    def check_duplicate(self, work_id: str, output_digest: str) -> bool:
        """Return True if work_id is already committed with the identical output_digest."""
        existing = self._committed.get(work_id)
        if existing is None:
            return False
        return existing.output_digest == output_digest

    def check_stale(self, work_id: str, output_digest: str) -> bool:
        """Return True if work_id is already committed with a DIFFERENT output_digest."""
        existing = self._committed.get(work_id)
        if existing is None:
            return False
        return existing.output_digest != output_digest

    def verify_and_commit(
        self,
        result: ExecutionResult,
        expected_tenant: str,
        *,
        expected_fencing_token: Optional[str] = None,
    ) -> bool:
        """Verify a result before durable commitment.

        Returns True if the result passes all custody checks and is committed.
        Returns False otherwise (result rejected, not committed).

        Checks:
        1. Tenant boundary: result.tenant must match expected_tenant
        2. Revoked or mismatched fencing token rejection
        3. Duplicate detection: same output_digest for same work_id = idempotent, accept
        4. Stale/conflicting digest rejection: different output_digest for same work_id = reject
        """
        if result.tenant != expected_tenant:
            return False

        if result.fencing_token in self._revoked_fencing_tokens:
            return False

        if expected_fencing_token is not None and result.fencing_token != expected_fencing_token:
            return False

        work_id = result.work_id
        existing = self._committed.get(work_id)
        if existing is not None:
            if existing.output_digest == result.output_digest:
                return True
            return False

        self._committed[work_id] = result
        return True

    def reject_stale(self, result: ExecutionResult, expected_tenant: str) -> bool:
        """Explicitly reject a stale or cross-tenant result."""
        if result.tenant != expected_tenant or result.fencing_token in self._revoked_fencing_tokens:
            if result.work_id in self._committed and self._committed[result.work_id] is result:
                del self._committed[result.work_id]
            return True
        if self.check_stale(result.work_id, result.output_digest):
            return True
        return False

    def get_committed(self, work_id: str) -> Optional[ExecutionResult]:
        """Retrieve a previously committed result by work_id."""
        return self._committed.get(work_id)

    @property
    def committed_count(self) -> int:
        return len(self._committed)
