"""Canonical production composition for Chronus, OVID and THESEUS."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from chronus.ovid.transform import OvidRepresentation, OvidTransformService
from chronus.storage.durable import DurableTheseusService
from chronus.storage.protected import ProtectedReceipt, ProtectedTheseusService


@dataclass(frozen=True)
class TriadReceipt:
    tenant_id: str
    representation_object_id: str
    receipt_object_id: str
    source_sha256: str
    representation_sha256: str
    contract_id: str
    contract_version: int

    def to_dict(self) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "representation_object_id": self.representation_object_id,
            "receipt_object_id": self.receipt_object_id,
            "source_sha256": self.source_sha256,
            "representation_sha256": self.representation_sha256,
            "contract_id": self.contract_id,
            "contract_version": self.contract_version,
        }


class ProductionTriad:
    """Production-shaped triad: transform -> durable custody -> verified materialisation."""

    def __init__(self, state_path: str) -> None:
        if not state_path:
            raise ValueError("state_path is required for production triad custody")
        self.ovid = OvidTransformService()
        self.theseus = DurableTheseusService(state_path)

    def put(self, tenant_id: str, payload: bytes) -> TriadReceipt:
        representation = self.ovid.fold(payload)
        stored = self.theseus.store(tenant_id, representation.payload)
        envelope = {
            **representation.envelope(),
            "tenant_id": tenant_id,
            "representation_object_id": stored.object_id,
        }
        receipt_bytes = json.dumps(
            envelope, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        receipt_record = self.theseus.store(tenant_id, receipt_bytes)
        self.theseus.append_journal_event(
            tenant_id, "TRIAD_REPRESENTATION_COMMITTED", receipt_bytes
        )
        return TriadReceipt(
            tenant_id=tenant_id,
            representation_object_id=stored.object_id,
            receipt_object_id=receipt_record.object_id,
            source_sha256=representation.source_sha256,
            representation_sha256=representation.representation_sha256,
            contract_id=representation.contract_id,
            contract_version=representation.contract_version,
        )

    def materialise(self, receipt: TriadReceipt) -> bytes:
        receipt_bytes = self.theseus.reconstruct(
            receipt.tenant_id, receipt.receipt_object_id
        )
        envelope = json.loads(receipt_bytes.decode("utf-8"))
        if envelope["representation_object_id"] != receipt.representation_object_id:
            raise ValueError("triad receipt/object mismatch")
        if envelope["source_sha256"] != receipt.source_sha256:
            raise ValueError("triad source digest mismatch")
        encoded = self.theseus.reconstruct(
            receipt.tenant_id, receipt.representation_object_id
        )
        representation = OvidRepresentation(
            contract_id=envelope["contract_id"],
            contract_version=int(envelope["contract_version"]),
            source_sha256=envelope["source_sha256"],
            representation_sha256=envelope["representation_sha256"],
            original_length=int(envelope["original_length"]),
            payload=encoded,
        )
        return self.ovid.materialise(representation)

    def verify(self, receipt: TriadReceipt) -> bool:
        payload = self.materialise(receipt)
        if hashlib.sha256(payload).hexdigest() != receipt.source_sha256:
            return False
        return self.theseus.verify_journal_continuity(receipt.tenant_id)

    def protect_payload(
        self, tenant_id: str, payload: bytes, shard_root: str | Path,
        *, shard_count: int = 4,
    ) -> ProtectedReceipt:
        """Commit redundant immutable shards under THESEUS custody.

        Optional resilience surface: does not alter OVID transformation contracts
        or the normal put/materialise API. The parity-bearing manifest is
        recorded in the same canonical THESEUS journal.
        """
        return ProtectedTheseusService(self.theseus, shard_root).store(
            tenant_id, payload, shard_count=shard_count,
        )

    def recover_protected_payload(
        self, receipt: ProtectedReceipt, shard_root: str | Path,
    ) -> bytes:
        """Reopen custodied shards and reconstruct at most one unavailable shard."""
        return ProtectedTheseusService(self.theseus, shard_root).reconstruct(receipt)

    def exact_grover_search(
        self, tenant_id: str, header_prefix: bytes, target: int, window_base: int,
        *, num_generators: int = 12, k: int = 32, epoch_step: int | None = None,
        artifact_id: str | None = None,
    ) -> dict:
        """Exact two-amplitude Grover over 2^num_generators nonces from window_base.

        CHRONUS builds FoldedRegisterN over (Z/2^32)^2 (lane 0 = header ntime,
        lane 1 = nonce), OVID folds/materialises the GL2 frames with this
        triad's OvidTransformService, THESEUS custodies every version and
        receipt in this triad's DurableTheseusService (SQLite WAL).  The
        SHA-256d oracle is evaluated on every materialised state (counted)."""
        from chronus.kernels.gl2_transform import FoldedRegisterN
        from chronus.ovid.folded_custody import OvidAdapter, OvidFoldedAdapter, TheseusAdapter
        from chronus.execution.sha256d_oracle import Sha256dTargetOracle
        from chronus.quantum.triad_grover import run_triad_exact_grover_search

        if k != 32:
            raise ValueError("header search packs (ntime, nonce) in (Z/2^32)^2: k must be 32")
        oracle = Sha256dTargetOracle(header_prefix, target)
        register = FoldedRegisterN.from_domain_offset(
            (oracle.ntime << 32) | (window_base & 0xFFFFFFFF), num_generators=num_generators, k=32,
        )
        theseus = TheseusAdapter(self.theseus, tenant_id)
        adapter = OvidFoldedAdapter(OvidAdapter(self.ovid), theseus)
        if artifact_id is None:
            # One identity per (header, window, width, schedule epoch): runs that can
            # select different winners never share versioned shard ids.
            artifact_id = (f"grover/{hashlib.sha256(oracle.prefix).hexdigest()[:32]}/"
                           f"{window_base & 0xFFFFFFFF:08x}/n{num_generators}/"
                           f"e{0 if epoch_step is None else epoch_step}")
        handle = adapter.stage_domain(artifact_id, register)
        # Fresh full-header SHA-256d check runs before any collapse commit or
        # GROVER_TARGET_VERIFIED receipt is written.
        checked: dict = {}

        def fresh_check(value: int) -> bool:
            ok, digest = oracle.verify(value)
            checked[value] = (ok, digest)
            return ok

        result = run_triad_exact_grover_search(
            adapter=adapter, handle=handle, oracle_predicate=oracle, epoch_step=epoch_step,
            winner_verifier=fresh_check,
        )
        verified, digest_hex = (False, None)
        if result.found:
            verified, digest_hex = checked[result.winner_value]
            if not verified:
                raise ArithmeticError("winner failed fresh SHA-256d verification")
        return {
            "result": result,
            "nonce": None if result.winner_value is None else result.winner_value & 0xFFFFFFFF,
            "verified": verified,
            "digest": digest_hex,
            "oracle_evaluations": oracle.evaluations,
            "oracle_compressions": oracle.compressions,
            "confirm_compressions": 3 if result.found else 0,
            "custody": theseus.counters,
        }

    def production_posture(self) -> dict:
        evidence = self.theseus.evidence()
        return {
            "triad": "Chronus-OVID-THESEUS",
            "chronus_role": "execution",
            "ovid_role": "versioned representation transformation/materialisation",
            "theseus_role": "durable custody/integrity/continuity/recovery/provenance",
            "durable_custody": evidence,
            "ovid": self.ovid.manifest(),
            "production_admission": "EVIDENCE_GATED",
        }


def open_production_triad(root: str | Path, name: str = "triad") -> ProductionTriad:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    return ProductionTriad(str(root / f"{name}.sqlite3"))
