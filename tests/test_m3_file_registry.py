from __future__ import annotations

import json

import pytest

from hyba_db import AccessDenied, OntologyStore, Quota


KEY = b"m3-file-registry-test-key-32-bytes!"


def _store(tmp_path):
    return OntologyStore(tmp_path / "ontology.db", KEY)


def _client(store, name="alpha"):
    return store.provision_client(name, Quota(10_000, 10_000_000))


def test_file_versions_are_content_addressed_custodied_linked_and_reconciled(tmp_path):
    with _store(tmp_path) as store:
        client = _client(store)
        job = store.files.record_mining(
            client.tenant_id, "job", {"job_id": "job-1", "generation": 1},
            producer="stratum", evidence_state="SOURCE_PRESENT", custody_record_id="custody-job-1",
        )
        root = tmp_path / "objects"
        object_id, version_id = store.files.put_file(
            client.tenant_id, root,
            logical_name="job-1.json", file_class="stratum_source",
            semantic_owner="pythia", domain="job", content=b'{"job":1}',
            producer="stratum", custody_record_id="custody-file-1",
            links=(("mining", job, "describes"),),
        )
        assert object_id.startswith("fo_")
        assert version_id.startswith("fv_")
        report = store.files.reconcile_files(client.tenant_id, root)
        assert report.passed, report.to_dict()
        assert store.verify_database(client.tenant_id).passed


def test_versions_are_immutable_and_conflicts_fail(tmp_path):
    with _store(tmp_path) as store:
        client = _client(store)
        obj = store.files.create_object(client.tenant_id, "x.json", "report", "theseus", "audit")
        first = store.files.register_version(
            client.tenant_id, obj, b"one", storage_uri="file:///tmp/one", logical_path="/tmp/one",
            producer="theseus", custody_record_id="custody-1",
        )
        assert first
        second = store.files.register_version(
            client.tenant_id, obj, b"two", storage_uri="file:///tmp/two", logical_path="/tmp/two",
            producer="theseus", custody_record_id="custody-2",
        )
        assert second != first
        with pytest.raises(Exception):
            store.files.register_version(
                client.tenant_id, obj, b"three", storage_uri="file:///tmp/three", logical_path="/tmp/three",
                producer="theseus", custody_record_id="custody-3", previous_version_id=first,
            )


def test_cross_tenant_links_and_orphans_fail_closed(tmp_path):
    with _store(tmp_path) as store:
        a = _client(store, "alpha")
        b = _client(store, "bravo")
        record = store.files.record_mining(
            a.tenant_id, "job", {"job_id": "a-job"}, producer="stratum",
            custody_record_id="custody-a",
        )
        obj, version = store.files.put_file(
            a.tenant_id, tmp_path / "objects", logical_name="a.json", file_class="report",
            semantic_owner="theseus", domain="job", content=b"a", producer="theseus",
            custody_record_id="custody-a-file", links=(("mining", record, "describes"),),
        )
        with pytest.raises(AccessDenied):
            store.files.link(b.tenant_id, version, "mining", record)
        orphan = tmp_path / "objects" / "orphan.bin"
        orphan.write_bytes(b"orphan")
        report = store.files.reconcile_files(a.tenant_id, tmp_path / "objects")
        assert str(orphan.resolve()) in report.orphan_files
        assert not report.passed


def test_mining_chain_requires_verified_proof_before_submission(tmp_path):
    with _store(tmp_path) as store:
        client = _client(store)
        job = store.files.record_mining(client.tenant_id, "job", {"job_id": "j"}, producer="stratum", custody_record_id="c-job")
        plan = store.files.record_mining(client.tenant_id, "search_plan", {"plan_id": "p"}, parent_ids=(job,), producer="pythia", custody_record_id="c-plan")
        lease = store.files.record_mining(client.tenant_id, "lease", {"lease_id": "l"}, parent_ids=(plan,), producer="pythia", custody_record_id="c-lease")
        execution = store.files.record_mining(client.tenant_id, "execution", {"execution_id": "e", "hashes_attempted": 10}, parent_ids=(lease,), producer="chronus", custody_record_id="c-exec")
        candidate = store.files.record_mining(client.tenant_id, "candidate_verification", {"sha256d_valid": True, "target_met": True}, parent_ids=(execution,), evidence_state="PASS", producer="sha256d", custody_record_id="c-candidate")
        proof = store.files.record_mining(client.tenant_id, "verified_proof", {"target_met": True, "host_verified": True}, parent_ids=(candidate,), evidence_state="PASS", producer="sha256d", custody_record_id="c-proof")
        submission = store.files.record_mining(client.tenant_id, "submission", {"attempt": 1}, parent_ids=(proof,), producer="stratum", custody_record_id="c-submit")
        outcome = store.files.record_mining(client.tenant_id, "pool_outcome", {"response": "UNAVAILABLE"}, parent_ids=(submission,), evidence_state="UNAVAILABLE", producer="pool", custody_record_id="c-outcome")
        learning = store.files.record_mining(client.tenant_id, "learning", {"outcome": outcome}, parent_ids=(outcome,), producer="pythia", custody_record_id="c-learning")
        assert learning and store.files.verify_mining(client.tenant_id)
        assert store.verify_database(client.tenant_id).passed
        with pytest.raises(Exception):
            store.files.record_mining(client.tenant_id, "submission", {"attempt": 2}, parent_ids=(candidate,), producer="stratum", custody_record_id="bad")
