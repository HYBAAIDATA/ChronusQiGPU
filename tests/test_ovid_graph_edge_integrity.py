"""OVID ontology-store graph reads verify edge integrity (review finding R09).

The 2026-10-04 production review found that ``traverse``, ``topology`` and
``_components`` read ``to_node``/``kind`` straight from SQL, so a modified
edge row steered navigation before ``verify_database`` ran. Each test
tampers one edge row the way an attacker with database-file access would
(bypassing any append-only trigger) and asserts the read refuses it.
"""

from __future__ import annotations

import sqlite3

import pytest

from hyba_db import EdgeKind, IntegrityFailure, NodeKind, OntologyStore, Quota
from hyba_db.theseus_custody import TheseusFileCustody

KEY = b"ovid-r09-edge-integrity-key-32bytes!"
CUSTODY_KEY = b"ovid-r09-custody-key-32-bytes!!!!!!"


@pytest.fixture
def graph(tmp_path):
    custody = TheseusFileCustody(tmp_path / "custody", hmac_key=CUSTODY_KEY)
    path = tmp_path / "ontology.db"
    with OntologyStore(path, KEY, custody=custody) as store:
        tenant = store.provision_client("alpha", Quota(100, 100_000))
        gpu = store.add_node(tenant.tenant_id, NodeKind.GPU, {"name": "GPU0"})
        kernel = store.add_node(
            tenant.tenant_id,
            NodeKind.KERNEL,
            {"name": "fold"},
            connect_from=gpu.id,
            edge_kind=EdgeKind.DISPATCHES,
        )
        decoy = store.add_node(tenant.tenant_id, NodeKind.KERNEL, {"name": "decoy"})
        yield store, path, tenant.tenant_id, gpu, kernel, decoy


def _tamper(path, sql, params):
    db = sqlite3.connect(path)
    try:
        for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type='trigger'").fetchall():
            db.execute(f'DROP TRIGGER IF EXISTS "{name}"')
        db.execute(sql, params)
        db.commit()
    finally:
        db.close()


def test_untampered_graph_still_traverses(graph):
    store, _path, tenant, gpu, kernel, _decoy = graph
    reached = {node.id for node in store.traverse(tenant, gpu.id)}
    assert kernel.id in reached
    assert store.topology(tenant)["edges"] >= 1


def test_redirected_edge_is_refused_by_traverse(graph):
    store, path, tenant, gpu, kernel, decoy = graph
    _tamper(
        path,
        "UPDATE edges SET to_node=? WHERE tenant_id=? AND from_node=? AND to_node=?",
        (decoy.id, tenant, gpu.id, kernel.id),
    )
    with pytest.raises(IntegrityFailure):
        store.traverse(tenant, gpu.id)


def test_relabelled_edge_kind_is_refused_by_traverse(graph):
    store, path, tenant, gpu, kernel, _decoy = graph
    _tamper(
        path,
        "UPDATE edges SET kind=? WHERE tenant_id=? AND from_node=? AND to_node=?",
        ("connects", tenant, gpu.id, kernel.id),
    )
    with pytest.raises(IntegrityFailure):
        store.traverse(tenant, gpu.id, edge_kinds=["connects"])


def test_tampered_edge_is_refused_by_topology(graph):
    store, path, tenant, gpu, kernel, decoy = graph
    _tamper(
        path,
        "UPDATE edges SET to_node=? WHERE tenant_id=? AND from_node=? AND to_node=?",
        (decoy.id, tenant, gpu.id, kernel.id),
    )
    with pytest.raises(IntegrityFailure):
        store.topology(tenant)


def test_verify_database_reports_tampered_edge(graph):
    store, path, tenant, gpu, kernel, decoy = graph
    _tamper(
        path,
        "UPDATE edges SET to_node=? WHERE tenant_id=? AND from_node=? AND to_node=?",
        (decoy.id, tenant, gpu.id, kernel.id),
    )
    report = store.verify_database(tenant)
    assert report["passed"] is False if isinstance(report, dict) else not report.passed
