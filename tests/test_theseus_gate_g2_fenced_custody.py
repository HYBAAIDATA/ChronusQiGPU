"""Gate G2 deterministic chaos, fencing, and RFC 6962 non-malleability suite.

Runs completely deterministically with zero wall-clock sleeps by injecting a
VirtualClock and an atomic in-memory etcd v3 CAS/lease simulator.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
import sqlite3
import threading
from typing import Any, Dict, List, Optional, Sequence, Tuple

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.exceptions import InvalidSignature
import pytest

pytestmark = pytest.mark.simulated

from chronus.storage.durable import (
    AnchorCommitUncertainError,
    Blake3MerkleTree,
    QuorumUnavailableError,
    ChainIntegrityError,
    CustodyError,
    CustodyHaltError,
    CustodyHealth,
    CustodyWatermarks,
    EtcdAnchorQuorumClient,
    EtcdLeaseFencer,
    FencedReceiptEnvelope,
    FencedTheseusEdgeStore,
    LeaseLostError,
    LocalSingleNodeFencer,
    StaleFencingEpochError,
    merkle_leaf_hash,
    merkle_node_hash,
)


# ---------------------------------------------------------------------------
# Deterministic Virtual Clock & Software CI Signer
# ---------------------------------------------------------------------------
class VirtualClock:
    """Thread-safe deterministic nanosecond clock."""

    def __init__(self, start_ns: int = 1_760_000_000_000_000_000) -> None:
        self._lock = threading.Lock()
        self._now_ns = start_ns

    def now_ns(self) -> int:
        with self._lock:
            return self._now_ns

    def advance_s(self, seconds: int) -> int:
        with self._lock:
            self._now_ns += seconds * 1_000_000_000
            return self._now_ns


class DeterministicTestSigner:
    """Deterministic Ed25519 software key explicitly marked non-hardware."""

    def __init__(self, key_id: str = "ci-ephemeral-key-01", secret: bytes = b"A" * 32) -> None:
        if len(secret) != 32:
            raise ValueError("Ed25519 requires exactly 32-byte seed")
        self._key_id = key_id
        self._key = Ed25519PrivateKey.from_private_bytes(secret)

    @property
    def key_id(self) -> str:
        return self._key_id

    @property
    def hardware_backed(self) -> bool:
        return False

    def sign(self, message: bytes) -> bytes:
        return self._key.sign(message)

    def verify(self, message: bytes, signature: bytes) -> bool:
        try:
            self._key.public_key().verify(signature, message)
        except InvalidSignature:
            return False
        return True


# ---------------------------------------------------------------------------
# Faithful In-Memory etcd v3 CAS + Lease Simulator
# ---------------------------------------------------------------------------
@dataclasses.dataclass(frozen=True)
class _FakeHeader:
    revision: int


@dataclasses.dataclass(frozen=True)
class _FakeResponse:
    header: _FakeHeader
    value: Optional[bytes] = None


@dataclasses.dataclass
class _FakeKVEntry:
    value: bytes
    create_revision: int
    mod_revision: int
    lease_id: Optional[int]


@dataclasses.dataclass
class _FakeLeaseRecord:
    lease_id: int
    ttl_s: int
    expiry_ns: int
    revoked: bool = False


class _FakeLeaseHandle:
    def __init__(self, cluster: "FakeEtcdCluster", lease_id: int) -> None:
        self._cluster = cluster
        self.id = lease_id

    def refresh(self):
        ttl = self._cluster._refresh_lease(self.id)

        class _KeepAliveResp:
            TTL = ttl

        yield _KeepAliveResp()

    def revoke(self) -> None:
        self._cluster._revoke_lease(self.id)


class _CompareOp:
    def __init__(self, field: str, key: str, expected: Any) -> None:
        self.field = field
        self.key = key
        self.expected = expected


class _KeySelector:
    def __init__(self, field: str, key: str) -> None:
        self._field = field
        self._key = key

    def __eq__(self, other: Any) -> _CompareOp:  # type: ignore[override]
        return _CompareOp(self._field, self._key, other)


class _TxBuilder:
    def create(self, key: str) -> _KeySelector:
        return _KeySelector("create", key)

    def mod(self, key: str) -> _KeySelector:
        return _KeySelector("mod", key)

    def value(self, key: str) -> _KeySelector:
        return _KeySelector("value", key)

    def put(self, key: str, value: Any, lease: Any = None) -> Tuple[str, str, bytes, Optional[int]]:
        raw = value.encode("utf-8") if isinstance(value, str) else bytes(value)
        lease_id = int(lease.id) if lease is not None else None
        return ("put", key, raw, lease_id)

    def get(self, key: str) -> Tuple[str, str, bytes, Optional[int]]:
        return ("get", key, b"", None)


class FakeEtcdCluster:
    """Atomic in-memory Raft/etcd v3 simulator with virtual-clock lease expiry."""

    def __init__(self, clock: VirtualClock) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._revision = 0
        self._next_lease_id = 100
        self._kv: Dict[str, _FakeKVEntry] = {}
        self._leases: Dict[int, _FakeLeaseRecord] = {}
        self.transactions = _TxBuilder()
        self.partitioned = False

    def _expire_leases_locked(self) -> None:
        now_ns = self._clock.now_ns()
        expired_ids = {
            lid
            for lid, rec in self._leases.items()
            if rec.revoked or now_ns >= rec.expiry_ns
        }
        if not expired_ids:
            return
        for key in list(self._kv.keys()):
            if self._kv[key].lease_id in expired_ids:
                del self._kv[key]

    def lease(self, ttl: int) -> _FakeLeaseHandle:
        with self._lock:
            if self.partitioned:
                raise ConnectionError("Simulated etcd quorum partition")
            self._expire_leases_locked()
            lid = self._next_lease_id
            self._next_lease_id += 1
            self._leases[lid] = _FakeLeaseRecord(
                lease_id=lid,
                ttl_s=ttl,
                expiry_ns=self._clock.now_ns() + ttl * 1_000_000_000,
            )
            return _FakeLeaseHandle(self, lid)

    def _refresh_lease(self, lease_id: int) -> int:
        with self._lock:
            if self.partitioned:
                raise ConnectionError("Simulated etcd quorum partition")
            self._expire_leases_locked()
            rec = self._leases.get(lease_id)
            if rec is None or rec.revoked or self._clock.now_ns() >= rec.expiry_ns:
                return 0
            rec.expiry_ns = self._clock.now_ns() + rec.ttl_s * 1_000_000_000
            return rec.ttl_s

    def _revoke_lease(self, lease_id: int) -> None:
        with self._lock:
            rec = self._leases.get(lease_id)
            if rec is not None:
                rec.revoked = True
            self._expire_leases_locked()

    def get(self, key: str) -> Tuple[Optional[bytes], Optional[_FakeKVEntry]]:
        with self._lock:
            if self.partitioned:
                raise ConnectionError("Simulated etcd quorum partition")
            self._expire_leases_locked()
            entry = self._kv.get(key)
            if entry is None:
                return None, None
            return entry.value, entry

    def transaction(
        self,
        compare: Sequence[_CompareOp],
        success: Sequence[Tuple[str, str, bytes, Optional[int]]],
        failure: Sequence[Tuple[str, str, bytes, Optional[int]]],
    ) -> Tuple[bool, List[_FakeResponse]]:
        with self._lock:
            if self.partitioned:
                raise ConnectionError("Simulated etcd quorum partition")
            self._expire_leases_locked()

            passed = True
            for cmp_op in compare:
                entry = self._kv.get(cmp_op.key)
                if cmp_op.field == "create":
                    actual = 0 if entry is None else entry.create_revision
                elif cmp_op.field == "mod":
                    actual = 0 if entry is None else entry.mod_revision
                elif cmp_op.field == "value":
                    actual = b"" if entry is None else entry.value
                else:
                    raise ValueError(f"Unsupported compare field: {cmp_op.field}")
                if actual != cmp_op.expected:
                    passed = False
                    break

            ops = success if passed else failure
            mutated = any(op[0] == "put" for op in ops)
            if mutated:
                self._revision += 1

            responses: List[_FakeResponse] = []
            for kind, key, raw_val, lease_id in ops:
                if kind == "put":
                    existing = self._kv.get(key)
                    create_rev = existing.create_revision if existing else self._revision
                    self._kv[key] = _FakeKVEntry(
                        value=raw_val,
                        create_revision=create_rev,
                        mod_revision=self._revision,
                        lease_id=lease_id,
                    )
                    responses.append(_FakeResponse(header=_FakeHeader(revision=self._revision)))
                elif kind == "get":
                    entry = self._kv.get(key)
                    responses.append(
                        _FakeResponse(
                            header=_FakeHeader(revision=self._revision),
                            value=entry.value if entry else None,
                        )
                    )
            return passed, responses


# ---------------------------------------------------------------------------
# Test 1: Zombie Fence Rejection & Split-Brain Fail-Closed Guarantees
# ---------------------------------------------------------------------------
def test_zombie_fence_rejection_and_handover(tmp_path: Path) -> None:
    clock = VirtualClock()
    etcd = FakeEtcdCluster(clock)
    quorum = EtcdAnchorQuorumClient(etcd, verify_anchor=lambda a: a.signer_key_id == signer_a.key_id and signer_a.verify(a.signing_preimage(), a.signature))
    signer_a = DeterministicTestSigner(key_id="ci-software-node-a", secret=b"A" * 32)

    lease_lost_reasons: List[str] = []
    fencer_a = EtcdLeaseFencer(
        etcd_client=etcd,
        node_id="node-a",
        slot_id="gpu-slot-0",
        ttl_s=12,
        safety_margin_s=3,
        on_lease_lost=lease_lost_reasons.append,
        clock_ns=clock.now_ns,
    )
    token_a = fencer_a.acquire()
    assert token_a.epoch >= 1

    store_a = FencedTheseusEdgeStore(
        db_path=tmp_path / "node_a.db",
        node_id="node-a",
        slot_id="gpu-slot-0",
        fencer=fencer_a,
        signer=signer_a,
        quorum=quorum,
        clock_ns=clock.now_ns,
        monotonic_ns=clock.now_ns,
    )
    assert store_a.reconcile_recovery_tail() is None

    # Contention while Node A holds valid lease must fail closed.
    fencer_b = EtcdLeaseFencer(
        etcd_client=etcd,
        node_id="node-b",
        slot_id="gpu-slot-0",
        ttl_s=12,
        safety_margin_s=3,
        clock_ns=clock.now_ns,
    )
    with pytest.raises(StaleFencingEpochError):
        fencer_b.acquire()

    # Normal write and anchor on Node A.
    env_1 = store_a.append_receipt(
        tenant_id="tenant-alpha",
        event_type="SHARE_VERIFIED",
        payload={"nonce": 42, "difficulty_bits": 32},
    )
    assert env_1.seq == 1
    anchor_a = store_a.seal_pending_epoch()
    assert anchor_a is not None
    assert anchor_a.fencing_epoch == token_a.epoch
    assert signer_a.verify(anchor_a.signing_preimage(), anchor_a.signature)

    # Stop keepalive updates by partitioning briefly, then advance past safety margin (9s of 12s TTL).
    etcd.partitioned = True
    clock.advance_s(9)
    with pytest.raises(LeaseLostError):
        store_a.append_receipt(
            tenant_id="tenant-alpha",
            event_type="SHARE_VERIFIED",
            payload={"nonce": 43},
        )

    # Advance past full TTL (12s+), heal quorum: Node B acquires strictly higher epoch.
    clock.advance_s(5)
    etcd.partitioned = False
    token_b = fencer_b.acquire()
    assert token_b.epoch > token_a.epoch

    # Even if zombie Node A bypasses its local check and pushes a stale anchor directly to Raft,
    # Tier-2 CAS MUST reject it atomically.
    assert lease_lost_reasons
    with pytest.raises(StaleFencingEpochError):
        quorum.commit_anchor(anchor_a)

    # Cleanup background threads cleanly.
    fencer_a.release()
    fencer_b.release()
    store_a.close()


# ---------------------------------------------------------------------------
# Test 2: RFC 6962 BLAKE3 Merkle Non-Malleability & Tamper Sensitivity
# ---------------------------------------------------------------------------
def test_rfc6962_merkle_non_malleability_and_proofs() -> None:
    leaves_3 = [b"leaf-0", b"leaf-1", b"leaf-2"]
    leaves_4_dup = [b"leaf-0", b"leaf-1", b"leaf-2", b"leaf-2"]

    # CVE-2012-2459 immunity: duplicating trailing odd leaf MUST produce a distinct root.
    tree_3 = Blake3MerkleTree(leaves_3)
    tree_4 = Blake3MerkleTree(leaves_4_dup)
    assert tree_3.root != tree_4.root

    # Domain separation: hashing concatenation of two leaf hashes as a leaf != internal node hash.
    h0 = merkle_leaf_hash(b"A")
    h1 = merkle_leaf_hash(b"B")
    assert merkle_leaf_hash(h0 + h1) != merkle_node_hash(h0, h1)

    # Exhaustive inclusion proof verification across power-of-2 and awkward tree cardinalities.
    for size in (1, 2, 3, 4, 5, 7, 8, 9, 15, 16, 17, 33):
        batch = [f"receipt-{i:04d}".encode("ascii") for i in range(size)]
        tree = Blake3MerkleTree(batch)
        for idx, leaf in enumerate(batch):
            proof = tree.proof_for(idx)
            assert proof.verify(leaf, tree.root) is True
            # Wrong leaf rejected.
            assert proof.verify(leaf + b"x", tree.root) is False

            # Mutating any sibling hash byte or side direction must fail verification.
            if proof.steps:
                sib_hash, side = proof.steps[0]
                flipped_hash = bytes([sib_hash[0] ^ 0x01]) + sib_hash[1:]
                tampered_hash_proof = dataclasses.replace(
                    proof, steps=((flipped_hash, side),) + proof.steps[1:]
                )
                assert tampered_hash_proof.verify(leaf, tree.root) is False

                flipped_side = "L" if side == "R" else "R"
                tampered_side_proof = dataclasses.replace(
                    proof, steps=((sib_hash, flipped_side),) + proof.steps[1:]
                )
                assert tampered_side_proof.verify(leaf, tree.root) is False


# ---------------------------------------------------------------------------
# Test 3: Gate G2 Crash-Tail Recovery & WAL Tamper Detection
# ---------------------------------------------------------------------------
def test_gate_g2_crash_tail_recovery_and_wal_tamper_detection(tmp_path: Path) -> None:
    clock = VirtualClock()
    etcd = FakeEtcdCluster(clock)
    quorum = EtcdAnchorQuorumClient(etcd, verify_anchor=lambda a: signer.verify(a.signing_preimage(), a.signature))
    signer = DeterministicTestSigner(key_id="ci-software-node-c", secret=b"C" * 32)
    db_file = tmp_path / "theseus_g2.db"

    # --- Run 1: Anchor 100 receipts, then write 150 unanchored receipts and crash ---
    fencer_1 = EtcdLeaseFencer(
        etcd_client=etcd,
        node_id="node-c",
        slot_id="gpu-slot-7",
        ttl_s=12,
        safety_margin_s=3,
        clock_ns=clock.now_ns,
    )
    tok_1 = fencer_1.acquire()
    store_1 = FencedTheseusEdgeStore(
        db_path=db_file,
        node_id="node-c",
        slot_id="gpu-slot-7",
        fencer=fencer_1,
        signer=signer,
        quorum=quorum,
        clock_ns=clock.now_ns,
        monotonic_ns=clock.now_ns,
    )
    store_1.reconcile_recovery_tail()

    for i in range(1, 101):
        store_1.append_receipt(
            tenant_id="tenant-g2",
            event_type="KERNEL_COMMIT",
            payload={"step": i, "flops_exact": i * 1024},
        )
    regular_anchor = store_1.seal_pending_epoch()
    assert regular_anchor is not None
    assert (regular_anchor.seq_start, regular_anchor.seq_end) == (1, 100)
    assert regular_anchor.anchor_kind == "REGULAR"

    for i in range(101, 251):
        store_1.append_receipt(
            tenant_id="tenant-g2",
            event_type="KERNEL_COMMIT",
            payload={"step": i, "flops_exact": i * 1024},
        )

    # Simulate abrupt crash before anchoring 101..250.
    store_1.close()
    fencer_1.release()

    # --- Run 2: Fresh restart, acquire new epoch, seal RECOVERY_TAIL ---
    fencer_2 = EtcdLeaseFencer(
        etcd_client=etcd,
        node_id="node-c",
        slot_id="gpu-slot-7",
        ttl_s=12,
        safety_margin_s=3,
        clock_ns=clock.now_ns,
    )
    tok_2 = fencer_2.acquire()
    assert tok_2.epoch > tok_1.epoch

    store_2 = FencedTheseusEdgeStore(
        db_path=db_file,
        node_id="node-c",
        slot_id="gpu-slot-7",
        fencer=fencer_2,
        signer=signer,
        quorum=quorum,
        clock_ns=clock.now_ns,
        monotonic_ns=clock.now_ns,
    )

    # Fail-closed before recovery runs.
    with pytest.raises(CustodyError, match="reconcile_recovery_tail"):
        store_2.seal_pending_epoch()
    with pytest.raises(CustodyError, match="reconcile_recovery_tail"):
        store_2.append_receipt(
            tenant_id="tenant-g2",
            event_type="KERNEL_COMMIT",
            payload={"step": 251},
        )

    recovery_anchor = store_2.reconcile_recovery_tail()
    assert recovery_anchor is not None
    assert recovery_anchor.anchor_kind == "RECOVERY_TAIL"
    assert (recovery_anchor.seq_start, recovery_anchor.seq_end) == (101, 250)
    assert recovery_anchor.fencing_epoch == tok_2.epoch
    assert quorum.last_anchored_seq("node-c", "gpu-slot-7") == 250

    # Verify independent O(log K) inclusion proofs across both REGULAR and RECOVERY_TAIL epochs.
    for target_seq in (1, 50, 100, 101, 175, 250):
        env, anc, proof = store_2.inclusion_proof_for_seq(target_seq)
        assert env.seq == target_seq
        assert signer.verify(anc.signing_preimage(), anc.signature)
        assert proof.verify(env.canonical_leaf_bytes(), anc.merkle_root)

    # New writes now succeed under tok_2.
    env_251 = store_2.append_receipt(
        tenant_id="tenant-g2",
        event_type="KERNEL_COMMIT",
        payload={"step": 251},
    )
    assert env_251.seq == 251
    assert env_251.fencing_epoch == tok_2.epoch
    store_2.close()
    fencer_2.release()

    # --- Run 3: Tamper unanchored row 251 in SQLite and confirm fail-closed detection ---
    conn = sqlite3.connect(str(db_file))
    conn.execute(
        "UPDATE theseus_fenced_receipts SET payload_digest = ? WHERE seq = 251;",
        (b"\xff" * 32,),
    )
    conn.commit()
    conn.close()

    fencer_3 = EtcdLeaseFencer(
        etcd_client=etcd,
        node_id="node-c",
        slot_id="gpu-slot-7",
        ttl_s=12,
        safety_margin_s=3,
        clock_ns=clock.now_ns,
    )
    fencer_3.acquire()
    store_3 = FencedTheseusEdgeStore(
        db_path=db_file,
        node_id="node-c",
        slot_id="gpu-slot-7",
        fencer=fencer_3,
        signer=signer,
        quorum=quorum,
        clock_ns=clock.now_ns,
        monotonic_ns=clock.now_ns,
    )
    with pytest.raises(ChainIntegrityError):
        store_3.reconcile_recovery_tail()

    store_3.close()
    fencer_3.release()


# ---------------------------------------------------------------------------
# Test 4: Hard Watermark Custody Halt & Exact-Arithmetic Float Rejection
# ---------------------------------------------------------------------------
def test_hard_watermark_custody_halt_and_exact_arithmetic_guard(tmp_path: Path) -> None:
    clock = VirtualClock()
    etcd = FakeEtcdCluster(clock)
    quorum = EtcdAnchorQuorumClient(etcd, verify_anchor=lambda a: signer.verify(a.signing_preimage(), a.signature))
    signer = DeterministicTestSigner(key_id="ci-software-node-d", secret=b"D" * 32)
    fencer = LocalSingleNodeFencer(tmp_path / "fences.db", node_id="node-d", slot_id="gpu-0")
    token = fencer.acquire()
    # Register matching fence in FakeEtcdCluster so quorum CAS succeeds when unpartitioned.
    tx = etcd.transactions
    ok, resps = etcd.transaction(
        compare=[tx.create("/chronus/theseus/fences/gpu-0") == 0],
        success=[tx.put("/chronus/theseus/fences/gpu-0", "node-d")],
        failure=[],
    )
    assert ok and resps[0].header.revision == token.epoch

    store = FencedTheseusEdgeStore(
        db_path=tmp_path / "node_d.db",
        node_id="node-d",
        slot_id="gpu-0",
        fencer=fencer,
        signer=signer,
        quorum=quorum,
        watermarks=CustodyWatermarks(
            warn_unanchored_s=10,
            halt_unanchored_s=30,
            warn_unanchored_records=5,
            halt_unanchored_records=10,
        ),
        clock_ns=clock.now_ns,
        monotonic_ns=clock.now_ns,
    )
    store.reconcile_recovery_tail()

    # Exact-arithmetic guard: reject floats at top-level or nested paths.
    with pytest.raises(TypeError, match="Floating-point value forbidden"):
        store.append_receipt(
            tenant_id="tenant-exact",
            event_type="TELEMETRY",
            payload={"hashrate_mh": 42.5},
        )
    with pytest.raises(TypeError, match="Floating-point value forbidden"):
        store.append_receipt(
            tenant_id="tenant-exact",
            event_type="TELEMETRY",
            payload={"nested": [{"temp_c": float("nan")}]},
        )

    # Write 1 receipt so backlog > 0, then partition quorum and advance clock.
    store.append_receipt(
        tenant_id="tenant-exact",
        event_type="TELEMETRY",
        payload={"hashrate_h_per_s": 42_500_000},
    )
    assert store.health_status() is CustodyHealth.HEALTHY

    etcd.partitioned = True
    clock.advance_s(12)
    assert store.health_status() is CustodyHealth.UNANCHORED_WARN

    # Soft watermark still allows local buffering.
    store.append_receipt(
        tenant_id="tenant-exact",
        event_type="TELEMETRY",
        payload={"hashrate_h_per_s": 43_000_000},
    )

    # Hard watermark triggers fail-closed CustodyHaltError.
    clock.advance_s(20)
    assert store.health_status() is CustodyHealth.CUSTODY_HALT
    with pytest.raises(CustodyHaltError):
        store.append_receipt(
            tenant_id="tenant-exact",
            event_type="TELEMETRY",
            payload={"hashrate_h_per_s": 43_500_000},
        )

    # Heal quorum, anchor pending backlog, confirm HEALTHY recovery and resumed writes.
    etcd.partitioned = False
    anchor = store.seal_pending_epoch()
    assert anchor is not None and anchor.leaf_count == 2
    assert store.health_status() is CustodyHealth.HEALTHY

    resumed = store.append_receipt(
        tenant_id="tenant-exact",
        event_type="TELEMETRY",
        payload={"hashrate_h_per_s": 44_000_000},
    )
    assert resumed.seq == 3
    store.close()
    fencer.release()

def test_local_fencer_rejects_superseded_epoch(tmp_path: Path) -> None:
    a = LocalSingleNodeFencer(tmp_path / "fences.db", "a", "slot")
    b = LocalSingleNodeFencer(tmp_path / "fences.db", "b", "slot")
    first = a.acquire()
    assert b.acquire().epoch > first.epoch
    with pytest.raises(StaleFencingEpochError):
        a.current_valid_token()
    a.release()
    b.release()


def test_exact_receipt_envelope() -> None:
    from chronus.storage.fenced_custody import GENESIS_HASH
    env, _ = FencedReceiptEnvelope.create(
        node_id="node", slot_id="slot", tenant_id="tenant", fencing_epoch=1,
        seq=1, ts_ns=0, event_type="test", payload={"n": 1},
        prev_hash=GENESIS_HASH)
    env.verify_link(GENESIS_HASH, 1)
    with pytest.raises(TypeError):
        dataclasses.replace(env, seq=1.0)


@pytest.mark.parametrize("count", [1, 2, 3, 4, 5, 7, 8, 9, 15, 16, 33])
def test_merkle_cardinalities(count: int) -> None:
    leaves = [str(i).encode("ascii") for i in range(count)]
    tree = Blake3MerkleTree(leaves)
    for i, leaf in enumerate(leaves):
        proof = tree.proof_for(i)
        assert proof.verify(leaf, tree.root)
        assert not dataclasses.replace(proof, steps=proof.steps + ((tree.root, "R"),)).verify(leaf, tree.root)

def test_remote_ack_recovery_and_exact_250_receipt_tail(tmp_path: Path) -> None:
    clock = VirtualClock()
    etcd = FakeEtcdCluster(clock)
    signer = DeterministicTestSigner()
    quorum = EtcdAnchorQuorumClient(etcd, verify_anchor=lambda a: signer.verify(a.signing_preimage(), a.signature))
    fencer = EtcdLeaseFencer(etcd_client=etcd, node_id="n", slot_id="s", clock_ns=clock.now_ns)
    db = tmp_path / "tail.db"
    fencer.acquire()
    store = FencedTheseusEdgeStore(db_path=db, node_id="n", slot_id="s",
        fencer=fencer, signer=signer, quorum=quorum,
        clock_ns=clock.now_ns, monotonic_ns=clock.now_ns)
    store.reconcile_recovery_tail()
    for i in range(250):
        store.append_receipt(tenant_id="t", event_type="receipt", payload={"i": i})
    store.close()
    fencer.release()
    fencer = EtcdLeaseFencer(etcd_client=etcd, node_id="n", slot_id="s", clock_ns=clock.now_ns)
    fencer.acquire()
    store = FencedTheseusEdgeStore(db_path=db, node_id="n", slot_id="s",
        fencer=fencer, signer=signer, quorum=quorum,
        clock_ns=clock.now_ns, monotonic_ns=clock.now_ns)
    with pytest.raises(CustodyError):
        store.append_receipt(tenant_id="t", event_type="receipt", payload={"i": 250})
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TRIGGER deny_anchor BEFORE INSERT ON theseus_epoch_anchors BEGIN SELECT RAISE(ABORT, 'injected local commit failure'); END")
    with pytest.raises(sqlite3.IntegrityError):
        store.reconcile_recovery_tail()
    assert quorum.last_anchored_seq("n", "s") == 250
    with pytest.raises(CustodyError):
        store.append_receipt(tenant_id="t", event_type="receipt", payload={"i": 250})
    with sqlite3.connect(db) as conn:
        conn.execute("DROP TRIGGER deny_anchor")
    assert store.reconcile_recovery_tail() is None
    for seq in (1, 125, 250):
        env, anchor, proof = store.inclusion_proof_for_seq(seq)
        assert (anchor.seq_start, anchor.seq_end, anchor.anchor_kind) == (1, 250, "RECOVERY_TAIL")
        assert proof.verify(env.canonical_leaf_bytes(), anchor.merkle_root)
    store.close()
    fencer.release()


@pytest.mark.parametrize("column,value", [
    ("ts_ns", 0.5),
    ("fencing_epoch", 1.5),
    ("payload_digest", "not-a-blob"),
])
def test_recovery_rejects_sqlite_storage_type_tampering(tmp_path: Path, column, value) -> None:
    clock = VirtualClock(0)
    etcd = FakeEtcdCluster(clock)
    signer = DeterministicTestSigner()
    quorum = EtcdAnchorQuorumClient(etcd, verify_anchor=lambda a: signer.verify(a.signing_preimage(), a.signature))
    fencer = EtcdLeaseFencer(etcd_client=etcd, node_id="n", slot_id="s", clock_ns=clock.now_ns)
    db = tmp_path / "tampered.db"
    fencer.acquire()
    try:
        store = FencedTheseusEdgeStore(db_path=db, node_id="n", slot_id="s",
            fencer=fencer, signer=signer, quorum=quorum,
            clock_ns=clock.now_ns, monotonic_ns=clock.now_ns)
        try:
            store.reconcile_recovery_tail()
            store.append_receipt(tenant_id="t", event_type="receipt", payload={"i": 0})
        finally:
            store.close()
        with sqlite3.connect(db) as conn:
            # Column comes exclusively from the parametrized literal test cases.
            if column == "ts_ns":
                conn.execute("UPDATE theseus_fenced_receipts SET ts_ns = ?", (value,))
            elif column == "fencing_epoch":
                conn.execute("UPDATE theseus_fenced_receipts SET fencing_epoch = ?", (value,))
            else:
                conn.execute("UPDATE theseus_fenced_receipts SET payload_digest = ?", (value,))
        store = FencedTheseusEdgeStore(db_path=db, node_id="n", slot_id="s",
            fencer=fencer, signer=signer, quorum=quorum,
            clock_ns=clock.now_ns, monotonic_ns=clock.now_ns)
        try:
            with pytest.raises(ChainIntegrityError, match="field type"):
                store.reconcile_recovery_tail()
            with pytest.raises(CustodyError, match="reconcile_recovery_tail"):
                store.append_receipt(tenant_id="t", event_type="receipt", payload={"i": 1})
        finally:
            store.close()
    finally:
        fencer.release()


def test_merkle_rejects_malformed_step_without_throwing() -> None:
    tree = Blake3MerkleTree([b"A", b"B"])
    proof = tree.proof_for(0)
    for steps in (((),), ((tree.root,),), ((tree.root, "R", "extra"),)):
        assert not dataclasses.replace(proof, steps=steps).verify(b"A", tree.root)


def test_quorum_outage_and_lost_acknowledgement_are_distinct(tmp_path: Path) -> None:
    class AckLossCluster(FakeEtcdCluster):
        drop_ack = False

        def transaction(self, compare, success, failure):
            result = super().transaction(compare, success, failure)
            if self.drop_ack:
                self.drop_ack = False
                raise ConnectionError("Injected loss after committed CAS")
            return result

    clock = VirtualClock()
    etcd = AckLossCluster(clock)
    signer = DeterministicTestSigner()
    quorum = EtcdAnchorQuorumClient(etcd, verify_anchor=lambda a: signer.verify(a.signing_preimage(), a.signature))
    fencer = EtcdLeaseFencer(etcd_client=etcd, node_id="n", slot_id="s", clock_ns=clock.now_ns)
    fencer.acquire()
    store = FencedTheseusEdgeStore(db_path=tmp_path / "uncertain.db", node_id="n", slot_id="s",
        fencer=fencer, signer=signer, quorum=quorum,
        clock_ns=clock.now_ns, monotonic_ns=clock.now_ns)
    try:
        store.reconcile_recovery_tail()
        store.append_receipt(tenant_id="t", event_type="r", payload={"i": 1})
        etcd.partitioned = True
        try:
            with pytest.raises(QuorumUnavailableError):
                store.seal_pending_epoch()
            store.append_receipt(tenant_id="t", event_type="r", payload={"i": 2})
        finally:
            etcd.partitioned = False
        etcd.drop_ack = True
        with pytest.raises(AnchorCommitUncertainError):
            store.seal_pending_epoch()
        assert quorum.last_anchored_seq("n", "s") == 2
        with pytest.raises(CustodyError, match="reconcile_recovery_tail"):
            store.append_receipt(tenant_id="t", event_type="r", payload={"i": 3})
        assert store.reconcile_recovery_tail() is None
        env, anchor, proof = store.inclusion_proof_for_seq(2)
        assert proof.verify(env.canonical_leaf_bytes(), anchor.merkle_root)
        assert store.append_receipt(tenant_id="t", event_type="r", payload={"i": 3}).seq == 3
    finally:
        store.close()
        fencer.release()


def test_persisted_anchor_timestamp_cannot_be_coerced(tmp_path: Path) -> None:
    clock = VirtualClock(0)
    etcd = FakeEtcdCluster(clock)
    signer = DeterministicTestSigner()
    quorum = EtcdAnchorQuorumClient(etcd, verify_anchor=lambda a: signer.verify(a.signing_preimage(), a.signature))
    fencer = EtcdLeaseFencer(etcd_client=etcd, node_id="n", slot_id="s", clock_ns=clock.now_ns)
    fencer.acquire()
    db = tmp_path / "anchor.db"
    store = FencedTheseusEdgeStore(db_path=db, node_id="n", slot_id="s",
        fencer=fencer, signer=signer, quorum=quorum,
        clock_ns=clock.now_ns, monotonic_ns=clock.now_ns)
    try:
        store.reconcile_recovery_tail()
        store.append_receipt(tenant_id="t", event_type="r", payload={"i": 1})
        store.seal_pending_epoch()
        with sqlite3.connect(db) as conn:
            conn.execute("UPDATE theseus_epoch_anchors SET anchored_ts_ns = ?", (0.5,))
        with pytest.raises(ChainIntegrityError, match="field type"):
            store.inclusion_proof_for_seq(1)
    finally:
        store.close()
        fencer.release()
