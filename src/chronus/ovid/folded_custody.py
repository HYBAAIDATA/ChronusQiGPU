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
    ``load_shard`` resolves the latest such record.
  - Committed versions are immutable: a second write to ``{artifact_id}:v{n}``
    with a different frame or provenance is rejected, a byte-identical retry
    reuses the committed record, and restore loads the shard by the selected
    receipt's object id.  Versions are claimed with compare-and-swap appends on
    the durable journal tip, so concurrent adapters cannot both commit one
    version; each adapter's index is refreshed incrementally before lookups.
Exact integer/byte arithmetic only.
"""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from typing import Callable, Iterable, List, Optional, Protocol, Sequence, Tuple

from chronus.kernels.gl2_transform import FoldedRegisterN, crc32c, hensellift_m15, invert_gl2_mod2k
from chronus.ovid.transform import OvidRepresentation, OvidTransformService
from chronus.storage.durable import CustodyConflictError, DurableTheseusService

EVENT_SHARD = "OVID_SHARD_COMMITTED"
EVENT_STAGE = "OVID_FOLDED_STAGE"
EVENT_COLLAPSE = "OVID_GENERATOR_COLLAPSE"
RECEIPT_SCHEMA = "chronus.ovid-folded-register/1"
# Reference full reconstruction materialises 2^N values; bounded like the
# scheduler's MAX_ACTIVE_DIM so a 64-generator register cannot request 2^64.
MAX_FULL_RECONSTRUCT_GENERATORS = 24


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


def shard_id(artifact_id: str, version: int) -> str:
    return f"{artifact_id}:v{version}"


class OvidServiceProtocol(Protocol):
    def register_working_representation(self, artifact_id: str, version: int, wire_frame: bytes) -> OvidRepresentation: ...
    def materialise(self, representation: OvidRepresentation) -> bytes: ...


class TheseusServiceProtocol(Protocol):
    def persist_shard(self, shard_id: str, representation: OvidRepresentation) -> dict: ...
    def load_shard(self, shard_id: str) -> OvidRepresentation: ...
    def append_audit_receipt(self, event_type: str, receipt: dict) -> str: ...
    def committed_receipt(self, artifact_id: str, version: int) -> Optional[dict]: ...
    def latest_receipt(self, artifact_id: str) -> Optional[dict]: ...
    def load_shard_object(self, shard_id: str, object_id: str) -> OvidRepresentation: ...
    def journal_receipts(self, event_types: Iterable[str]) -> List[Tuple[str, dict]]: ...
    def receipt_entry_hash(self, event_type: str, receipt: dict) -> Optional[str]: ...
    def commit_version(self, artifact_id: str, version: int, event_type: str, shard_id: str,
                       representation: OvidRepresentation,
                       build_receipt: Callable[[dict], dict]) -> Tuple[dict, dict, bool]: ...


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
    """TheseusServiceProtocol over the real ``DurableTheseusService``.

    The journal index is refreshed incrementally (entries after the last indexed
    sequence) before every lookup, so a version committed through another adapter
    or process is never hidden by a cached miss.  ``commit_version`` claims a
    version atomically: the shard mapping and the receipt are appended with
    compare-and-swap on the journal tip, and a moved tip forces a re-read and a
    re-check instead of a blind write.  Cached receipts are stored and returned
    as detached copies."""

    MAX_CLAIM_ATTEMPTS = 16

    def __init__(self, custody: DurableTheseusService, tenant_id: str) -> None:
        if not isinstance(custody, DurableTheseusService):
            raise TypeError("DurableTheseusService custody is required")
        if not tenant_id:
            raise ValueError("tenant_id is required")
        self.custody = custody
        self.tenant_id = tenant_id
        self.counters = CustodyCounters()
        self._shards: dict = {}      # (shard_id, object_id) -> ref, insertion = journal order
        self._versions: dict = {}    # (artifact_id, version) -> list of receipts in journal order
        self._tip = -1               # newest journal sequence folded into the index

    def _refresh(self) -> int:
        for e in self.custody.get_journal(self.tenant_id, after_sequence=self._tip):
            if e.event_type in (EVENT_SHARD, EVENT_STAGE, EVENT_COLLAPSE):
                rec = json.loads(self.custody.reconstruct(self.tenant_id, e.object_id))
                self._index_add(e.event_type, rec)
            self._tip = e.sequence
        return self._tip

    def _index_add(self, event_type: str, rec: dict) -> None:
        rec = copy.deepcopy(rec)
        if event_type == EVENT_SHARD:
            key = (rec["shard_id"], rec["object_id"])
            self._shards.pop(key, None)
            self._shards[key] = rec
        else:
            self._versions.setdefault((rec["artifact_id"], rec["version"]), []).append(rec)

    def _append(self, event_type: str, payload: dict, expected_last_sequence: Optional[int]):
        entry = self.custody.append_journal_event(self.tenant_id, event_type, canonical_json(payload),
                                                  expected_last_sequence=expected_last_sequence)
        if expected_last_sequence is not None and entry.sequence == self._tip + 1:
            # The CAS proved nothing was appended in between: index it directly.
            if event_type in (EVENT_SHARD, EVENT_STAGE, EVENT_COLLAPSE):
                self._index_add(event_type, payload)
            self._tip = entry.sequence
        return entry

    def _store_shard(self, representation: OvidRepresentation) -> Tuple[str, bool]:
        object_id = hashlib.sha256(representation.payload).hexdigest()
        try:
            self.custody.get_record(self.tenant_id, object_id)
            reused = True
        except KeyError:
            reused = False
        rec = self.custody.store(self.tenant_id, representation.payload)
        return rec.object_id, reused

    def persist_shard(self, shard_id: str, representation: OvidRepresentation) -> dict:
        object_id, reused = self._store_shard(representation)
        ref = {"shard_id": shard_id, "object_id": object_id, **representation.envelope()}
        self.custody.append_journal_event(self.tenant_id, EVENT_SHARD, canonical_json(ref))
        self.counters.shards_persisted += 1
        self.counters.shards_reused += int(reused)
        self.counters.shard_bytes += len(representation.payload)
        return {**ref, "reused": reused}

    def commit_version(self, artifact_id: str, version: int, event_type: str, shard_id: str,
                       representation: OvidRepresentation,
                       build_receipt: Callable[[dict], dict]) -> Tuple[dict, dict, bool]:
        """Atomically claim (artifact_id, version).  Returns (receipt, shard_ref, claimed):
        claimed=False means another writer already holds the version and its
        receipt is returned unchanged for the caller to compare."""
        for _ in range(self.MAX_CLAIM_ATTEMPTS):
            tip = self._refresh()
            prior = self._versions.get((artifact_id, version))
            if prior:
                return copy.deepcopy(prior[0]), {}, False
            object_id, reused = self._store_shard(representation)
            ref = {"shard_id": shard_id, "object_id": object_id, **representation.envelope()}
            try:
                shard_entry = self._append(EVENT_SHARD, ref, tip)
            except CustodyConflictError:
                continue
            receipt = build_receipt(ref)
            try:
                self._append(event_type, receipt, shard_entry.sequence)
            except CustodyConflictError:
                continue          # the orphan shard mapping is inert: restore follows receipts
            self.counters.shards_persisted += 1
            self.counters.shards_reused += int(reused)
            self.counters.shard_bytes += len(representation.payload)
            self.counters.receipts_appended += 1
            return copy.deepcopy(receipt), {**ref, "reused": reused}, True
        raise CustodyConflictError(f"could not claim {artifact_id!r} v{version}: journal tip kept moving")

    def _records(self, event_types: Iterable[str]) -> List[Tuple[str, dict]]:
        wanted = set(event_types)
        out = []
        for e in self.custody.get_journal(self.tenant_id):
            if e.event_type in wanted:
                out.append((e.event_type, json.loads(self.custody.reconstruct(self.tenant_id, e.object_id))))
        return out

    def load_shard(self, shard_id: str) -> OvidRepresentation:
        """Latest mapping for shard_id (prefer ``load_shard_object`` when the
        committing receipt is known)."""
        self._refresh()
        refs = [ref for (sid, _oid), ref in self._shards.items() if sid == shard_id]
        if not refs:
            raise KeyError(shard_id)
        return self._representation(refs[-1])

    def load_shard_object(self, shard_id: str, object_id: str) -> OvidRepresentation:
        self._refresh()
        ref = self._shards.get((shard_id, object_id))
        if ref is None:
            raise KeyError(f"{shard_id} -> {object_id}")
        return self._representation(ref)

    def _representation(self, ref: dict) -> OvidRepresentation:
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

    def committed_receipt(self, artifact_id: str, version: int) -> Optional[dict]:
        """First committed receipt for (artifact_id, version), or None (fresh read)."""
        self._refresh()
        recs = self._versions.get((artifact_id, version))
        return copy.deepcopy(recs[0]) if recs else None

    def latest_receipt(self, artifact_id: str) -> Optional[dict]:
        """Committed receipt at the highest version of artifact_id (fresh read)."""
        self._refresh()
        best = None
        for (aid, ver), recs in self._versions.items():
            if aid == artifact_id and (best is None or ver > best["version"]):
                best = recs[0]
        return copy.deepcopy(best) if best is not None else None

    def journal_receipts(self, event_types: Iterable[str]) -> List[Tuple[str, dict]]:
        return self._records(event_types)

    def receipt_entry_hash(self, event_type: str, receipt: dict) -> Optional[str]:
        """Journal entry hash of the first ``event_type`` entry carrying exactly ``receipt``."""
        for entry in self.custody.get_journal(self.tenant_id):
            if entry.event_type == event_type and json.loads(
                    self.custody.reconstruct(self.tenant_id, entry.object_id)) == receipt:
                return entry.entry_hash
        return None


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

        def matches(body: dict) -> bool:
            # Same frame, same event and same provenance (collapsed generator, bit,
            # previous frame): a different collapse that happens to produce the
            # same frame is a conflict, not a retry.
            return (body["frame_sha256"] == digest and body["event"] == event
                    and all(body.get(key) == value for key, value in extra.items()))

        def reuse(body: dict) -> FoldedWorkingHandle:
            if not matches(body):
                raise ValueError(f"version {version} of {artifact_id!r} is already committed with a different frame")
            self.theseus.load_shard_object(body["shard_id"], body["object_id"])
            return FoldedWorkingHandle(artifact_id, version, folded, frame, digest,
                                       {"shard_id": body["shard_id"], "object_id": body["object_id"],
                                        "reused": True})

        prior = self.theseus.committed_receipt(artifact_id, version)
        if prior is not None:
            return reuse(verify_attested(prior))
        rep = self.ovid.register_working_representation(artifact_id, version, frame)
        sid = shard_id(artifact_id, version)

        def build(ref: dict) -> dict:
            return attest({
                "schema": RECEIPT_SCHEMA, "event": event, "artifact_id": artifact_id, "version": version,
                "shard_id": sid, "object_id": ref["object_id"], "k": folded.k,
                "num_generators": folded.num_generators, "resolved_mask": folded.resolved_mask,
                "resolved_bits": folded.resolved_bits, "frame_sha256": digest,
                "frame_crc32c": frame[-4:].hex(), "ovid_contract_id": rep.contract_id,
                "ovid_representation_sha256": rep.representation_sha256, **extra,
            })

        receipt, ref, claimed = self.theseus.commit_version(artifact_id, version, event, sid, rep, build)
        if not claimed:
            return reuse(verify_attested(receipt))
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
        if reg.num_generators > MAX_FULL_RECONSTRUCT_GENERATORS:
            raise ValueError(f"full_reconstruct is bounded to {MAX_FULL_RECONSTRUCT_GENERATORS} generators "
                             f"(2^{MAX_FULL_RECONSTRUCT_GENERATORS} states); use materialise_indices")
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
        best = self.theseus.latest_receipt(artifact_id)
        if best is None:
            raise KeyError(artifact_id)
        body = verify_attested(best)
        frame = self.ovid.materialise(self.theseus.load_shard_object(body["shard_id"], body["object_id"]))
        if hashlib.sha256(frame).hexdigest() != body["frame_sha256"]:
            raise ValueError("restored frame SHA-256 mismatch")
        reg = FoldedRegisterN.from_wire_bytes(frame)
        if (reg.resolved_mask, reg.resolved_bits) != (body["resolved_mask"], body["resolved_bits"]):
            raise ValueError("restored register disagrees with receipt")
        return FoldedWorkingHandle(artifact_id, body["version"], reg, frame, body["frame_sha256"],
                                   {"shard_id": body["shard_id"], "object_id": body["object_id"]})
