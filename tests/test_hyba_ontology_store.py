from __future__ import annotations

import sqlite3

import pytest

from hyba_db import (
    AccessDenied, EdgeKind, IntegrityFailure, NodeKind, OntologyStore,
    ProofStatus, Quota, QuotaExceeded,
)
from hyba_db.theseus_custody import TheseusFileCustody

KEY = b"hyba-test-integrity-key-32-bytes!!"
CUSTODY_KEY = b"hyba-test-custody-key-32-bytes!!!!"
VECTOR = tuple((i - 5) / 7 for i in range(11))


@pytest.fixture
def store(tmp_path):
    custody = TheseusFileCustody(tmp_path / "custody", hmac_key=CUSTODY_KEY)
    with OntologyStore(tmp_path / "ontology.db", KEY, custody=custody) as value:
        yield value


def client(store, name="alpha", records=100, blob=100_000):
    return store.provision_client(name, Quota(records, blob))


def test_tenant_isolation_and_namespace_uniqueness(store):
    a = client(store, "alpha")
    b = client(store, "bravo")
    fold = store.write_fold(a.tenant_id, VECTOR)
    with pytest.raises(AccessDenied):
        store.read_fold(b.tenant_id, fold.id)
    with pytest.raises(sqlite3.IntegrityError):
        client(store, "alpha")


def test_quota_is_transactional(store):
    c = client(store, records=1)
    with pytest.raises(QuotaExceeded):
        store.write_fold(c.tenant_id, VECTOR)
    assert store.verify_database(c.tenant_id).passed


def test_fold_certificate_parent_and_physical_block(store):
    c = client(store)
    first = store.write_fold(c.tenant_id, VECTOR)
    second = store.write_fold(c.tenant_id, tuple(-x for x in VECTOR), parent_id=first.id)
    assert store.verify_certificate(c.tenant_id, first.certificate.id, VECTOR)
    assert store.children_of(c.tenant_id, first.id) == (second.id,)
    block = store.write_physical_block(c.tenant_id, 144, b"immutable", first.id)
    assert store.read_physical_block(c.tenant_id, block) == b"immutable"


def test_tensor_network_roundtrip(store):
    c = client(store)
    fold = store.write_fold(c.tenant_id, VECTOR)
    tensor = store.write_tensor(c.tenant_id, "mps", fold.id, b"safe-binary", dimensions=(2, 3, 2), norm=1.0, entropy=0.2, invariants={"canonical": True})
    loaded = store.read_tensor(c.tenant_id, tensor.id)
    assert loaded.payload == b"safe-binary"
    assert loaded.dimensions == (2, 3, 2)
    assert loaded.invariants["canonical"] is True


def test_graph_topology_and_traversal(store):
    c = client(store)
    gpu = store.add_node(c.tenant_id, NodeKind.GPU, {"name": "GPU0"}, betti=(1, 0), persistence=0.9)
    kernel = store.add_node(c.tenant_id, NodeKind.KERNEL, {"name": "fold"}, connect_from=gpu.id, edge_kind=EdgeKind.DISPATCHES)
    reached = {n.id for n in store.traverse(c.tenant_id, c.root_node_id)}
    assert {gpu.id, kernel.id} <= reached
    assert store.topology(c.tenant_id)["components"] == 1


def test_semantic_layer_and_attestation_evidence(store):
    c = client(store)
    evidence = store.attest(c.tenant_id, "test:normalization", {"passed": True})
    inv = store.register_invariant(c.tenant_id, "T1", 2, "MPS norm is one", ProofStatus.TESTED, evidence.id)
    row = store.query_by_invariant(c.tenant_id, "T1")
    assert row["evidence_attestation_id"] == evidence.id
    contract = store.register_contract(c.tenant_id, "tensor-write", {"required": ["fold_id"]}, [inv])
    term = store.register_term(c.tenant_id, "fold", "An immutable 11D state", {"certified_by": "Zeckendorf"})
    computation = store.materialize(c.tenant_id, "norm", [inv], {"value": 1.0})
    assert all(x for x in (contract, term, computation))


def test_mining_projection(store):
    c = client(store)
    pool = store.store_pool_connection(c.tenant_id, "stratum+tcp://pool.example:3333")
    job = store.store_job(c.tenant_id, pool.id, "job-1", "0000ffff")
    share = store.store_share(c.tenant_id, job.id, "0000000f", VECTOR, nonce=7, accepted=True)
    assert [x.id for x in store.find_shares(c.tenant_id, "000000ff")] == [share.id]
    assert [x.id for x in store.pool_to_shares(c.tenant_id, pool.id)] == [share.id]


def test_tamper_detection_and_full_verification(store):
    c = client(store)
    fold = store.write_fold(c.tenant_id, VECTOR)
    assert store.verify_database(c.tenant_id).passed
    store._db.execute("UPDATE certificates SET digest='bad' WHERE tenant_id=? AND id=?", (c.tenant_id, fold.certificate.id))
    with pytest.raises(IntegrityFailure):
        store.read_fold(c.tenant_id, fold.id)
    report = store.verify_database(c.tenant_id)
    assert not report.passed and not report.certificates_ok
