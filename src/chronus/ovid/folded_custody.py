"""OVID folded working representations of FoldedRegisterN under THESEUS custody.

* The register is held folded by the Hensel-lifted M_k and serialised as a
  lossless ``GL2\\x01`` v2 frame with CRC-32C (``chronus.kernels.gl2_transform``).
* OVID: the frame goes through the real ``OvidTransformService.fold`` /
  ``materialise`` (``chronus/ovid/transform.py``), which checks source and
  representation SHA-256 on the way back.
* THESEUS: the OVID representation bytes are stored with the real
  ``DurableTheseusService.store`` (``chronus/storage/durable.py``, SQLite WAL,
  content-addressed) and indexed by shard id ``"{artifact_id}:v{version}"``
  through a hash-chained journal event; audit receipts are canonical JSON with
  their own CRC-32C and SHA-256, appended with ``append_journal_event``.

API mismatches with the owner's protocol names, handled by thin adapters:
  - OVID has no per-artifact registry: ``register_working_representation``
    returns the ``OvidRepresentation``; version lives in the shard id.
  - THESEUS has no named keys: ``persist_shard`` stores the payload and appends
    an ``OVID_SHARD_COMMITTED`` journal record mapping shard id -> object id;
    ``load_shard`` resolves the latest such record (journal scan).
Exact integer/byte arithmetic only.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Protocol, Sequence, Tuple

from chronus.kernels.gl2_transform import FoldedRegisterN, crc32c, hensellift_m15, invert_gl2_mod2k
from chronus.ovid.transform import OvidRepresentation, OvidTransformService
from chronus.storage.durable import DurableTheseusService

EVENT_SHARD = "OVID_SHARD_COMMITTED"
EVENT_STAGE = "OVID_FOLDED_STAGE"
EVENT_COLLAPSE = "OVID_GENERATOR_COLLAPSE"
RECEIPT_SCHEMA = "chronus.ovid-folded-register/1"


def canonical_json(obj: dict) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def attest(body: dict) -> dict:
    """body + CRC-32C and SHA-256 of its canonical JSON bytes."""
    raw = canonical_json(body)
    return {**body, "body_crc32c": f"{crc32c(raw):08x}", "body_sha256": hashlib.sha256(raw).hexdigest()}


def verify_attested(receipt: dict) -> dict:
    body = {k: v for k, v in receipt.items() if k not in ("body_crc32c", "body_sha256")}
    raw = canonical_json(body)
    if receipt.get("body_crc32c") != f"{crc32c(raw):08x}":
        raise ValueError("receipt CRC-32C mismatch")
    if receipt.get("body_sha256") != hashlib.sha256(raw).hexdigest():
        raise ValueError("receipt SHA-256 mismatch")
    return body


def shard_id(artifact_id: str, version: int, frame_sha256: str) -> str:
    # Content-bound: repeated runs for the same artifact/version with different frames
    # get distinct shard ids, so load_shard cannot return a later run's frame for an
    # earlier receipt.
    return f"{artifact_id}:v{version}:{frame_sha256}"


class OvidServiceProtocol(Protocol):
    def register_working_representation(self, artifact_id: str, version: int, wire_frame: bytes) -> OvidRepresentation: ...
    def materialise(self, representation: OvidRepresentation) -> bytes: ...


class TheseusServiceProtocol(Protocol):
    def persist_shard(self, shard_id: str, representation: OvidRepresentation) -> dict: ...
    def load_shard(self, shard_id: str) -> OvidRepresentation: ...
    def append_audit_receipt(self, event_type: str, receipt: dict) -> str: ...


class OvidAdapter:
    """OvidServiceProtocol over the real ``OvidTransformService``."""

    def __init__(self, service: Optional[OvidTransformService] = None) -> None:
        self.service = service or OvidTransformService()

    def register_working_representation(self, artifact_id: str, version: int, wire_frame: bytes) -> OvidRepresentation:
        return self.service.fold(wire_frame)

    def materialise(self, representation: OvidRepresentation) -> bytes:
        return self.service.materialise(representation)


@dataclass
class CustodyCounters:
    shards_persisted: int = 0
    shards_reused: int = 0      # representation bytes already custodied (content-address hit)
    receipts_appended: int = 0
    shard_bytes: int = 0
    shards_loaded: int = 0


class TheseusAdapter:
    """TheseusServiceProtocol over the real ``DurableTheseusService``."""

    def __init__(self, custody: DurableTheseusService, tenant_id: str) -> None:
        if not isinstance(custody, DurableTheseusService):
            raise TypeError("DurableTheseusService custody is required")
        if not tenant_id:
            raise ValueError("tenant_id is required")
        self.custody = custody
        self.tenant_id = tenant_id
        self.counters = CustodyCounters()

    def persist_shard(self, shard_id: str, representation: OvidRepresentation) -> dict:
        object_id = hashlib.sha256(representation.payload).hexdigest()
        try:
            self.custody.get_record(self.tenant_id, object_id)
            reused = True
        except KeyError:
            reused = False
        rec = self.custody.store(self.tenant_id, representation.payload)
        ref = {"shard_id": shard_id, "object_id": rec.object_id, **representation.envelope()}
        self.custody.append_journal_event(self.tenant_id, EVENT_SHARD, canonical_json(ref))
        self.counters.shards_persisted += 1
        self.counters.shards_reused += int(reused)
        self.counters.shard_bytes += len(representation.payload)
        return {**ref, "reused": reused}

    def _records(self, event_types: Iterable[str]) -> List[Tuple[str, dict]]:
        wanted = set(event_types)
        out = []
        for e in self.custody.get_journal(self.tenant_id):
            if e.event_type in wanted:
                out.append((e.event_type, json.loads(self.custody.reconstruct(self.tenant_id, e.object_id))))
        return out

    def load_shard(self, shard_id: str) -> OvidRepresentation:
        ref = None
        for _e, rec in self._records((EVENT_SHARD,)):
            if rec.get("shard_id") == shard_id:
                ref = rec
        if ref is None:
            raise KeyError(shard_id)
        payload = self.custody.reconstruct(self.tenant_id, ref["object_id"])
        self.counters.shards_loaded += 1
        return OvidRepresentation(
            contract_id=ref["contract_id"], contract_version=int(ref["contract_version"]),
            source_sha256=ref["source_sha256"], representation_sha256=ref["representation_sha256"],
            original_length=int(ref["original_length"]), payload=payload,
        )

    def append_audit_receipt(self, event_type: str, receipt: dict) -> str:
        entry = self.custody.append_journal_event(self.tenant_id, event_type, canonical_json(receipt))
        self.counters.receipts_appended += 1
        return entry.entry_hash

    def journal_receipts(self, event_types: Iterable[str]) -> List[Tuple[str, dict]]:
        return self._records(event_types)


@dataclass(frozen=True)
class FoldedWorkingHandle:
    artifact_id: str
    version: int
    register: FoldedRegisterN     # held folded by M_k
    wire_frame: bytes             # GL2\x01 v2 frame of ``register``
    sha256_digest: str            # sha256(wire_frame)
    shard_ref: dict = field(default_factory=dict, compare=False)


class OvidFoldedAdapter:
    """Stage, selectively materialise, collapse and restore folded registers."""

    def __init__(self, ovid: OvidServiceProtocol, theseus: TheseusServiceProtocol) -> None:
        self.ovid = ovid
        self.theseus = theseus
        self.states_materialised = 0

    def _commit(self, artifact_id: str, version: int, folded: FoldedRegisterN, event: str,
                extra: dict) -> FoldedWorkingHandle:
        frame = folded.to_wire_bytes()
        digest = hashlib.sha256(frame).hexdigest()
        rep = self.ovid.register_working_representation(artifact_id, version, frame)
        sid = shard_id(artifact_id, version, digest)
        ref = self.theseus.persist_shard(sid, rep)
        body = {
            "schema": RECEIPT_SCHEMA, "event": event, "artifact_id": artifact_id, "version": version,
            "shard_id": sid, "object_id": ref["object_id"], "k": folded.k,
            "num_generators": folded.num_generators, "resolved_mask": folded.resolved_mask,
            "resolved_bits": folded.resolved_bits, "frame_sha256": digest,
            "frame_crc32c": frame[-4:].hex(), "ovid_contract_id": rep.contract_id,
            "ovid_representation_sha256": rep.representation_sha256, **extra,
        }
        self.theseus.append_audit_receipt(event, attest(body))
        return FoldedWorkingHandle(artifact_id, version, folded, frame, digest, ref)

    def stage_domain(self, artifact_id: str, register: FoldedRegisterN) -> FoldedWorkingHandle:
        """Fold the plain register by M_k once and custody the folded frame (version 0)."""
        return self._commit(artifact_id, 0, register.fold_mk(), EVENT_STAGE, {})

    def commit_collapse_step(self, handle: FoldedWorkingHandle, idx: int, bit_val: int) -> FoldedWorkingHandle:
        """Collapse generator idx on the folded register (fold and collapse commute)."""
        nxt = handle.register.collapse_generator(idx, bit_val)
        return self._commit(handle.artifact_id, handle.version + 1, nxt, EVENT_COLLAPSE,
                            {"collapsed_generator": idx, "bit_val": bit_val,
                             "prev_frame_sha256": handle.sha256_digest})

    def materialise_indices(self, handle: FoldedWorkingHandle, indices: Sequence[int]) -> List[int]:
        """Unfold once (Cayley-Hamilton inverse, N+1 matvecs) and evaluate only the
        requested indices, O(N) each; value = (hi << k) | lo.  No 2^N table."""
        plain = handle.register.unfold_mk()
        k = plain.k
        out = []
        for i in indices:
            hi, lo = plain.evaluate_index(i)
            out.append((hi << k) | lo)
        self.states_materialised += len(out)
        return out

    def full_reconstruct(self, handle: FoldedWorkingHandle) -> List[int]:
        """Reference: apply M_k^-1 to every one of the 2^N folded states separately."""
        reg = handle.register
        k, mask = reg.k, (1 << reg.k) - 1
        inv = invert_gl2_mod2k(hensellift_m15(k), k)
        out = []
        for i in range(1 << reg.num_generators):
            x, y = reg.evaluate_index(i)
            out.append((((inv[0][0] * x + inv[0][1] * y) & mask) << k) | ((inv[1][0] * x + inv[1][1] * y) & mask))
        return out

    def restore_from_theseus(self, artifact_id: str) -> FoldedWorkingHandle:
        """Latest handle for artifact_id after restart; verifies receipt CRC/SHA,
        OVID digests, frame SHA-256 and GL2 frame CRC-32C."""
        best = None
        for _e, rec in self.theseus.journal_receipts((EVENT_STAGE, EVENT_COLLAPSE)):
            if rec.get("artifact_id") == artifact_id and (best is None or rec["version"] > best["version"]):
                best = rec
        if best is None:
            raise KeyError(artifact_id)
        body = verify_attested(best)
        frame = self.ovid.materialise(self.theseus.load_shard(body["shard_id"]))
        if hashlib.sha256(frame).hexdigest() != body["frame_sha256"]:
            raise ValueError("restored frame SHA-256 mismatch")
        reg = FoldedRegisterN.from_wire_bytes(frame)
        if (reg.resolved_mask, reg.resolved_bits) != (body["resolved_mask"], body["resolved_bits"]):
            raise ValueError("restored register disagrees with receipt")
        return FoldedWorkingHandle(artifact_id, body["version"], reg, frame, body["frame_sha256"],
                                   {"shard_id": body["shard_id"], "object_id": body["object_id"]})
