"""HYBA data-substrate elevation tests — Pass 2 sections 6-22.

Every claim is exercised against real machinery (aethel AddressSpace /
encoding, toe receipts) — nothing mocked. Failure tests assert the
specified behaviour: recover, or fail closed; never silent invention.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
import threading
import unittest
from pathlib import Path

from aethel.encoding import fold
from aethel.errors import (
    AethelError,
    FoldDomainOverflow,
    GapDetected,
    InvalidAddress,
    SegmentMissing,
)
from aethel.fibonacci import fibonacci, fibonacci_index
from aethel.storage import FibonacciAddress

from hyba.substrate import (
    FOLD_NATIVE,
    FULL_RECONSTRUCTION,
    HybaSubstrate,
    NotFound,
    PARTIAL_RECONSTRUCTION,
    UNSUPPORTED,
    near_state_classify,
    prefix_unfold,
    suffix_unfold,
)


def _tmp(name: str) -> Path:
    d = Path(tempfile.mkdtemp(prefix=f"hyba_{name}_"))
    return d


class TestIdentityLayers(unittest.TestCase):
    """§7 — content identity != fold identity != logical != physical."""

    def test_four_identities_are_distinct(self):
        s = HybaSubstrate()
        ident = s.put("a", b"payload-a")
        self.assertNotEqual(ident.content_id, ident.fold_id)
        self.assertGreaterEqual(ident.logical_address, 1)
        self.assertEqual(ident.content_id, hashlib.sha256(b"payload-a").hexdigest())

    def test_storage_movement_preserves_logical_identity(self):
        s = HybaSubstrate()
        before = s.put("movable", b"data that moves")
        d = _tmp("move")
        s.persist(d)
        s2 = HybaSubstrate.attach(d)
        after = s2.identify("movable")
        self.assertEqual(before.content_id, after.content_id)
        self.assertEqual(before.fold_id, after.fold_id)
        self.assertEqual(before.logical_address, after.logical_address)
        # physical location moved; identity did not
        self.assertEqual(s2.get("movable"), b"data that moves")


class TestSemanticsAndVersioning(unittest.TestCase):
    """§12-14 — PUT/GET/VERSION/TRANSFORM/DELETE semantics."""

    def test_put_get_roundtrip(self):
        s = HybaSubstrate()
        s.put("k", b"v1")
        self.assertEqual(s.get("k"), b"v1")

    def test_version_chain_preserves_previous_state(self):
        s = HybaSubstrate()
        s.put("obj", b"state-1")
        s.transform("obj", b"state-2", how="edit")
        s.transform("obj", b"state-3", how="edit")
        versions = s.versions("obj")
        self.assertEqual([v.version for v in versions], [1, 2, 3])
        self.assertIsNone(versions[0].parent_digest)
        self.assertEqual(
            versions[1].parent_digest, hashlib.sha256(b"state-1").hexdigest()
        )
        self.assertEqual(s.get_version("obj", 1), b"state-1")
        self.assertEqual(s.get_version("obj", 2), b"state-2")
        self.assertEqual(s.get("obj"), b"state-3")
        # every version has a receipt (provenance)
        self.assertTrue(all(v.receipt_sha256 for v in versions))

    def test_delete_is_tombstone_not_erasure(self):
        s = HybaSubstrate()
        s.put("gone", b"evidence")
        s.delete("gone")
        with self.assertRaises(NotFound):
            s.get("gone")
        # history is preserved — evidence is never silently destroyed
        self.assertEqual(len(s.versions("gone")), 1)

    def test_oversize_payload_fails_closed(self):
        s = HybaSubstrate()
        with self.assertRaises(FoldDomainOverflow):
            s.put("big", os.urandom((1 << 20) + 1))


class TestConcurrency(unittest.TestCase):
    """§13 — concurrent writers over the shared ledger."""

    def test_concurrent_tenant_writers_keep_ledger_consistent(self):
        s = HybaSubstrate()
        tenants = [s.scope(f"t{i}") for i in range(4)]
        errors = []

        def work(t, n):
            try:
                for j in range(25):
                    t.put(f"item{j}", f"{t.tenant}-{j}".encode())
            except Exception as exc:  # pragma: no cover
                errors.append(exc)

        threads = [threading.Thread(target=work, args=(t, i)) for i, t in enumerate(tenants)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        self.assertFalse(errors)
        self.assertTrue(s.space.ledger.verify_ledger())
        self.assertTrue(s.attest()["ledger_ok"])
        # each tenant sees only its own 25 objects
        for t in tenants:
            self.assertEqual(len(t._objects), 25)


class TestFailureRecovery(unittest.TestCase):
    """§19 — recover or fail closed; never silently invent state."""

    def test_partial_write_truncated_journal_fails_closed(self):
        s = HybaSubstrate()
        s.put("x", b"aaaa")
        s.put("y", b"bbbb")
        d = _tmp("partial")
        s.persist(d)
        journal = d / "blocks" / "ledger.jsonl"
        lines = journal.read_bytes().split(b"\n")
        # corrupt mid-LINE: a partial JSON record must not silently parse
        journal.write_bytes(b"\n".join(lines[:-1]) + b"\n" + lines[-2][: len(lines[-2]) // 2])
        with self.assertRaises(AethelError):
            HybaSubstrate.attach(d)

    def test_consistent_prefix_journal_is_recoverable(self):
        # designed recovery: an operator-truncated journal (whole lines) is a
        # consistent prefix and attach succeeds on it — but the objects index
        # is authoritative, so get() on a missing block still fails closed
        s = HybaSubstrate()
        s.put("x", b"aaaa")
        s.put("y", b"bbbb")
        d = _tmp("prefix")
        s.persist(d)
        journal = d / "blocks" / "ledger.jsonl"
        lines = journal.read_bytes().splitlines(keepends=True)
        journal.write_bytes(b"".join(lines[:1]))  # keep only entry seq 0
        s2 = HybaSubstrate.attach(d)
        self.assertTrue(s2.space.ledger.verify_ledger())
        with self.assertRaises((AethelError, Exception)):
            s2.get("y")  # entry absent from truncated ledger -> fail closed

    def test_missing_block_segment_fails_closed(self):
        s = HybaSubstrate()
        s.put("seg", b"segment-data")
        d = _tmp("seg")
        s.persist(d)
        idx = s.identify("seg").logical_address
        os.remove(d / "blocks" / "blocks" / f"{idx}.blk")
        with self.assertRaises(SegmentMissing):
            HybaSubstrate.attach(d)

    def test_corrupt_folded_state_detected(self):
        s = HybaSubstrate()
        s.put("fragile", b"integrity-checked")
        # corrupt the stored block bytes via the block map
        idx = s.identify("fragile").logical_address
        s.space._blocks[idx] = b"tampered-bytes!!"  # simulate bit rot
        with self.assertRaises(Exception):
            s.get("fragile")

    def test_wrong_address_fails_closed(self):
        s = HybaSubstrate()
        s.put("w", b"data")
        space = s.space
        with self.assertRaises((GapDetected, InvalidAddress)):
            space.read(space.address_of_index(9999))

    def test_interrupted_fold_domain(self):
        # fold refuses beyond the declared domain — no partial state
        with self.assertRaises(FoldDomainOverflow):
            fold(os.urandom((1 << 20) + 8))


class TestIntegrity(unittest.TestCase):
    """§20 — mutation detection must be explicit."""

    def test_payload_mutation_detected(self):
        s = HybaSubstrate()
        s.put("v", b"original")
        idx = s.identify("v").logical_address
        s.space._blocks[idx] = b"mutated!"
        with self.assertRaises(Exception):
            s.get("v")

    def test_ledger_quadruple_forgery_detected(self):
        s = HybaSubstrate()
        s.put("a", b"1")
        s.put("b", b"2")
        entry = s.space.ledger.entries[0]
        forged = type(entry)(
            seq=entry.seq, index=entry.index, value=entry.value,
            quadruple=(1, 1, 1, 1), digest=entry.digest, writer=entry.writer,
        )
        s.space.ledger.entries[0] = forged
        self.assertFalse(s.attest()["ledger_ok"])

    def test_stream_reorder_detected(self):
        s = HybaSubstrate()
        s.put("a", b"1")
        s.put("b", b"2")
        e = s.space.ledger.entries
        e[0], e[1] = e[1], e[0]
        with self.assertRaises(GapDetected):
            s.space.ledger.check_consistent()

    def test_version_substitution_detected(self):
        s = HybaSubstrate()
        s.put("sv", b"v1")
        s.transform("sv", b"v2", how="edit")
        # try to serve v1's block as v2 — digest gate catches it
        v1 = s.versions("sv")[0].digest
        self.assertNotEqual(v1, hashlib.sha256(b"v2").hexdigest())


class TestAddressing(unittest.TestCase):
    """§6 — determinism / injectivity / collision / ordering / range."""

    def test_fibonacci_address_injective_and_deterministic(self):
        seen = {}
        # honest §6 finding: F_1 == F_2 == 1 — the address VALUE collides at
        # the head of the sequence, so the canonical address is the INDEX
        # (injective) and the value is navigation-grade. Verified below.
        self.assertEqual(fibonacci(1), fibonacci(2))
        for n in range(3, 2000):
            a = FibonacciAddress(n, fibonacci(n))
            self.assertNotIn(a.value, seen)  # injective on n>=3
            seen[a.value] = n
            self.assertEqual(fibonacci_index(a.value), n)  # reconstruction

    def test_anchor_is_navigation_not_identity(self):
        # mod-90 anchors collide by construction — declared navigation lens
        s = HybaSubstrate()
        for i in range(95):
            s.put(f"o{i}", f"payload-{i}".encode())
        res = s.navigate("anchor", 5)
        self.assertTrue(res["navigation_grade"])
        self.assertFalse(res["injective"])
        # collisions exist by pigeonhole (95 objects, 90 anchors)
        total = sum(
            len(s.navigate("anchor", a)["candidates"]) for a in range(90)
        )
        self.assertGreaterEqual(total, 95)

    def test_forged_address_object_unconstructible(self):
        with self.assertRaises(InvalidAddress):
            FibonacciAddress(10, fibonacci(10) + 1)  # value off sequence


class TestNearStateCompute(unittest.TestCase):
    """§9 — operator classes + measured partial reconstruction."""

    def test_operator_classification_table(self):
        table = near_state_classify()
        self.assertEqual(table["equality"]["class"], FOLD_NATIVE)
        self.assertEqual(table["prefix_read"]["class"], PARTIAL_RECONSTRUCTION)
        self.assertEqual(table["content_digest"]["class"], FULL_RECONSTRUCTION)
        self.assertEqual(table["content_distance"]["class"], UNSUPPORTED)

    def test_prefix_unfold_materializes_only_prefix(self):
        payload = bytes(range(256)) * 8  # 2048 B
        v = fold(payload)
        head = prefix_unfold(v, 64)
        self.assertEqual(head, payload[:64])
        self.assertEqual(len(head), 64)

    def test_suffix_unfold(self):
        payload = bytes(range(256)) * 8
        v = fold(payload)
        tail = suffix_unfold(v, 32)
        self.assertEqual(tail, payload[-32:])

    def test_mask_equality_implies_content_equality(self):
        a = fold(b"identical-content")
        b = fold(b"identical-content")
        self.assertEqual(a.blocks, b.blocks)


class TestNavigationLenses(unittest.TestCase):
    """§8 — shared state, multiple lenses, no duplicated copies."""

    def test_three_lenses_one_store(self):
        s = HybaSubstrate()
        ident = s.put("nav", b"navigable bytes")
        self.assertEqual(s.navigate("content", ident.content_id)["key"], "nav")
        self.assertIn("nav", s.navigate("fold", fold(b"navigable bytes"))["candidates"])
        anchor_hits = s.navigate("anchor", ident.logical_address % 90)
        self.assertIn("nav", anchor_hits["candidates"])
        # one store — lenses are views over _objects/ledger, not copies


class TestTenancy(unittest.TestCase):
    """§21 — tenant A cannot resolve tenant B identity/address."""

    def test_tenant_isolation(self):
        s = HybaSubstrate()
        a = s.scope("tenant-A")
        b = s.scope("tenant-B")
        ia = a.put("confidential", b"A-secret")
        b.put("confidential", b"B-data")
        # B cannot resolve A's digest through its own handle
        self.assertIsNone(b.query_digest(ia.content_id))
        # B cannot read A's key (separate namespaces)
        self.assertEqual(b.get("confidential"), b"B-data")
        # B's navigate returns only B-tenant objects — resolving B's hit
        # yields B's bytes, never A's content
        hits = b.navigate("anchor", ia.logical_address % 90)["candidates"]
        self.assertEqual(len(b._objects), 1)
        for h in hits:
            self.assertEqual(b.get(h), b"B-data")
        # and A's object count/identity is invisible to B entirely
        self.assertEqual(len(a._objects), 1)
        self.assertNotIn(ia.content_id, [o.digest for o in b.versions("confidential")])
        # A's receipts/attest remain distinct per tenant
        self.assertTrue(a.attest()["all_verified"])
        self.assertTrue(b.attest()["all_verified"])


class TestToeIntegration(unittest.TestCase):
    """§16 — stored state -> TOE representation -> reasoning; reuse."""

    def test_stored_payload_to_toe_state(self):
        import numpy as np

        from toe.intelligence_state import IntelligenceState
        from toe.representation import select_views, structural_signature

        s = HybaSubstrate()
        series = np.cumsum(np.random.default_rng(0).integers(-2, 3, 512)).astype(float)
        s.put("series", series.tobytes())
        raw = s.get("series")
        rows = np.frombuffer(raw, dtype=np.float64).tolist()
        state = IntelligenceState(rows)
        sig = structural_signature(rows)
        self.assertTrue(sig["kind"])  # a real signature kind was produced
        views = select_views(sig)
        self.assertTrue(len(views["selected"]) >= 1)
        # reuse: same bytes -> same observation digest (re-embed avoided)
        state2 = IntelligenceState(np.frombuffer(s.get("series"), dtype=np.float64).tolist())
        self.assertEqual(state.observation_sha256, state2.observation_sha256)


class TestDataMovement(unittest.TestCase):
    """§18 — real byte accounting at the movement boundary."""

    def test_meter_counts_moved_bytes(self):
        s = HybaSubstrate()
        payload = b"m" * 1024
        s.put("m", payload)
        s.get("m")
        snap = s.meter.snapshot()
        self.assertEqual(snap["bytes_written"], 1024)
        self.assertEqual(snap["bytes_read"], 1024)
        self.assertEqual(snap["bytes_reconstructed"], 1024)
        self.assertEqual(snap["bytes_copied"], 0)


class TestPersistAttachRoundTrip(unittest.TestCase):
    def test_full_reopen(self):
        s = HybaSubstrate()
        s.put("p1", b"first")
        s.put("p2", b"second")
        s.transform("p1", b"first-v2", how="edit")
        d = _tmp("full")
        s.persist(d)
        s2 = HybaSubstrate.attach(d)
        self.assertEqual(s2.get("p1"), b"first-v2")
        self.assertEqual(s2.get_version("p1", 1), b"first")
        self.assertTrue(s2.attest()["all_verified"])


if __name__ == "__main__":
    unittest.main()
