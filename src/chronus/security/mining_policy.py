"""AL HARAS local mining policy: explicit endpoints, arming and bounded shares.

This policy is an operator configuration boundary, not remote attestation.
"""
from __future__ import annotations

import base64
import json
import hashlib
from decimal import Decimal
import os
from collections import deque
from pathlib import Path
import time
from uuid import uuid4

from chronus.stratum.endpoint import PoolEndpoint, parse_endpoint


MAX_POOL_FRAME_BYTES = 1024 * 1024 + 1  # stream limit excludes the terminating LF


def _reject_constant(value):
    raise ValueError("non-finite JSON constant")


def _unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("duplicate JSON key")
        obj[key] = value
    return obj


def parse_pool_frame(frame: bytes) -> dict:
    """One strict UTF-8 and JSON decoder for admission and custody."""
    if not isinstance(frame, bytes) or not frame.endswith(b"\n") or len(frame) > MAX_POOL_FRAME_BYTES:
        raise ValueError("invalid bounded pool response frame")
    value = json.loads(frame.decode("utf-8"), parse_float=Decimal,
                       parse_constant=_reject_constant, object_pairs_hook=_unique_object)
    if not isinstance(value, dict):
        raise ValueError("pool response must be an object")
    return value


def _same_json(left, right):
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(_same_json(left[k], right[k]) for k in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(_same_json(a, b) for a, b in zip(left, right))
    return left == right


class MiningSubmissionPolicy:
    def __init__(self):
        self.armed = False
        self.approval_reference = None
        self.accepted_share_target = None
        self.accepted = 0
        self.pending: set[int] = set()
        self._last_authorized_rpc_id = 0
        self.events = deque(maxlen=256)
        self._custody = None
        self._key = None
        self._tenant = None
        self.session_id = str(uuid4())

    @staticmethod
    def check_endpoint(endpoint: PoolEndpoint) -> None:
        raw = os.getenv("CHRONUS_ALLOWED_POOL_ENDPOINTS", "[]")
        try:
            values = json.loads(raw)
            if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
                raise ValueError
            allowed = {parse_endpoint(value) for value in values}
        except (ValueError, TypeError) as exc:
            raise PermissionError("CHRONUS_ALLOWED_POOL_ENDPOINTS must be a JSON array of endpoints") from exc
        if endpoint not in allowed:
            raise PermissionError("Pool endpoint is not in the operator allowlist")

    def arm(self, approval_reference: str, accepted_share_target: int) -> None:
        if not isinstance(approval_reference, str) or not approval_reference.strip():
            raise ValueError("operator approval reference is required")
        if type(accepted_share_target) is not int or accepted_share_target < 1:
            raise ValueError("accepted_share_target must be a positive integer")
        if self.pending:
            raise RuntimeError("cannot arm with unresolved submissions")
        from chronus.storage.durable import DurableTheseusService
        try:
            self._tenant = os.environ["CHRONUS_MINING_TENANT_ID"]
            self._key = Path(os.environ["CHRONUS_MINING_KEY_FILE"]).read_bytes()
            if not self._tenant.strip() or len(self._key) != 32:
                raise ValueError("invalid custody identity or key")
            self._custody = DurableTheseusService(os.environ["CHRONUS_MINING_CUSTODY_PATH"])
        except (KeyError, OSError, ValueError) as exc:
            raise PermissionError("Encrypted mining custody and local identity must be configured before arming") from exc
        self._record("MINING_SUBMISSION_ARMED", {"approval_reference": approval_reference,
                                               "accepted_share_target": accepted_share_target})
        self.approval_reference = approval_reference
        self.accepted_share_target = accepted_share_target
        self.accepted = 0
        self.armed = True
        self.events.append("SUBMISSION_ARMED")

    def _record(self, event: str, record: dict) -> None:
        from chronus.execution.authority import _seal
        record = {"producer": "CHRONUS", "schema_version": 1, "timestamp_ns": time.time_ns(),
                  "session_id": self.session_id, "tenant_id": self._tenant, **record}
        sealed = _seal(record, self._key, self._tenant)
        return self._custody.append_journal_event(self._tenant, event, sealed)

    def authorize(self, rpc_id: int, evidence: dict | None = None) -> None:
        if not self.armed:
            raise PermissionError("Share submission is not armed")
        if type(rpc_id) is not int or rpc_id <= self._last_authorized_rpc_id:
            raise PermissionError("Submission RPC id must be new and increasing")
        if self.accepted + len(self.pending) >= self.accepted_share_target:
            raise PermissionError("Share target capacity is exhausted or awaiting acknowledgement")
        self._record("MINING_SUBMIT_AUTHORIZED", {"rpc_id": rpc_id, "candidate": evidence})
        self.pending.add(rpc_id)
        self._last_authorized_rpc_id = rpc_id

    def observe(self, response: dict, *, wire_frame: bytes | None = None) -> None:
        """Persist a correlated verdict before advancing local counters.

        The gateway supplies the original bounded frame. Direct policy callers
        without a wire frame have decoded-record evidence only.
        """
        rpc_id = response.get("id")
        if type(rpc_id) is not int or rpc_id not in self.pending:
            return
        if response.get("result") is not True and response.get("result") is not False and not response.get("error"):
            return
        if "method" in response:
            return
        decoded = json.dumps(response, sort_keys=True, default=str, allow_nan=False)
        record = {
            "rpc_id": rpc_id, "accepted": response.get("result") is True and not response.get("error"),
            "response_sha256": hashlib.sha256(decoded.encode()).hexdigest(),
            "decoded_response_json": decoded,
            "response_evidence_class": "DECODED_RESPONSE_ONLY",
        }
        if wire_frame is not None:
            literal = parse_pool_frame(wire_frame)
            if not _same_json(literal, response):
                raise ValueError("Pool response frame does not match decoded response")
            record.update({
                "response_evidence_class": "RECEIVED_STRATUM_FRAME",
                "wire_frame_sha256": hashlib.sha256(wire_frame).hexdigest(),
            })
            # Small frames preserve the existing record shape. Large frames are
            # encrypted in independently content-addressed chunks; the final
            # acknowledgement commits the ordered chunk object IDs and full hash.
            from chronus.config import runtime_bounds
            max_payload = runtime_bounds()["max_payload_bytes"]
            chunk_size = min(128 * 1024, max_payload // 8)
            if chunk_size < 1024:
                raise ValueError("custody payload budget too small for pool evidence")
            if len(wire_frame) <= chunk_size and len(decoded.encode()) <= chunk_size:
                record["wire_frame_b64"] = base64.b64encode(wire_frame).decode("ascii")
            else:
                # Retain the original bytes, not a second expanded decoded copy.
                record.pop("decoded_response_json")
                parts = []
                for offset in range(0, len(wire_frame), chunk_size):
                    fragment = wire_frame[offset:offset + chunk_size]
                    entry = self._record("MINING_POOL_RESPONSE_FRAGMENT", {
                        "rpc_id": rpc_id, "offset": offset,
                        "frame_sha256": record["wire_frame_sha256"],
                        "data_b64": base64.b64encode(fragment).decode("ascii"),
                    })
                    parts.append(entry.object_id)
                record["wire_frame_parts"] = parts
                record["wire_frame_bytes"] = len(wire_frame)
        self._record("MINING_POOL_ACKNOWLEDGEMENT", record)
        self.pending.remove(rpc_id)
        if response.get("result") is True and not response.get("error"):
            self.accepted += 1
            if self.accepted >= self.accepted_share_target:
                self.disarm("AUTO_DISARMED_TARGET_REACHED")

    def disarm(self, reason="SUBMISSION_DISARMED") -> None:
        self.armed = False
        self.events.append(reason)
        if self._custody is not None:
            self._record(reason, {"shares_accepted": self.accepted, "pending_submissions": len(self.pending)})

    def end_connection(self, reason: str) -> None:
        """Never reclassify or silently erase unanswered submissions."""
        self.disarm(reason)
        if self.pending:
            self._record("MINING_SUBMISSIONS_UNRESOLVED", {
                "rpc_ids": sorted(self.pending), "reason": reason,
                "verdict": "UNRESOLVED",
            })
            self.pending.clear()

    def status(self) -> dict:
        return {"share_submit_armed": self.armed,
                "accepted_share_target": self.accepted_share_target,
                "shares_accepted": self.accepted,
                "pending_submissions": len(self.pending),
                "approval_reference": self.approval_reference}
