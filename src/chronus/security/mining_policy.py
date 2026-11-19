"""AL HARAS local mining policy: explicit endpoints, arming and bounded shares.

This policy is an operator configuration boundary, not remote attestation.
"""
from __future__ import annotations

import json
import hashlib
from decimal import Decimal
import os
from collections import deque
from pathlib import Path
import time
from uuid import uuid4

from chronus.config import runtime_bounds
from chronus.stratum.endpoint import PoolEndpoint, parse_endpoint

# AES-256-GCM binary blob overhead (nonce + tag). The sealed frame object must
# fit the durable custody payload limit, so the accepted frame is bounded by it.
_AEAD_OVERHEAD_BYTES = 12 + 16


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
        self._custody.append_journal_event(self._tenant, event, sealed)

    def _seal_frame_blob(self, wire_frame: bytes) -> bytes:
        """Seal the literal frame as raw AES-GCM bytes (no base64 expansion)."""
        if self._key is None:
            return wire_frame
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        nonce = os.urandom(12)
        aad = json.dumps({"tenant_id": self._tenant, "schema": "chronus-mining-wire-frame-v1"},
                         sort_keys=True, separators=(",", ":")).encode()
        return nonce + AESGCM(self._key).encrypt(nonce, wire_frame, aad)

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
            frame_limit = runtime_bounds()["max_payload_bytes"] - _AEAD_OVERHEAD_BYTES
            if (not isinstance(wire_frame, bytes) or not wire_frame.endswith(b"\n")
                    or len(wire_frame) > frame_limit):
                raise ValueError("Invalid bounded pool response frame")
            literal = json.loads(wire_frame.decode("utf-8"), parse_float=Decimal)
            if not isinstance(literal, dict) or json.dumps(
                    literal, sort_keys=True, default=str, allow_nan=False) != decoded:
                raise ValueError("Pool response frame does not match decoded response")
            # The literal frame is stored as its own sealed custody object and
            # linked by object id; the decoded JSON is derivable from it, so it is
            # not duplicated into the record (keeps the record within custody limits).
            frame_object = self._seal_frame_blob(wire_frame)
            stored = self._custody.store(self._tenant, frame_object)
            record.pop("decoded_response_json")
            record.update({
                "response_evidence_class": "RECEIVED_STRATUM_FRAME",
                "wire_frame_object_id": stored.object_id,
                "wire_frame_sha256": hashlib.sha256(wire_frame).hexdigest(),
                "wire_frame_bytes": len(wire_frame),
            })
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
tatus(self) -> dict:
        return {"share_submit_armed": self.armed,
                "accepted_share_target": self.accepted_share_target,
                "shares_accepted": self.accepted,
                "pending_submissions": len(self.pending),
                "approval_reference": self.approval_reference}
