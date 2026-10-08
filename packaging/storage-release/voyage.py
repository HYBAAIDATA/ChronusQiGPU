"""Installed canonical-components voyages, never a whole-platform certificate.

The parent creates private ephemeral keys; no key value is logged or retained in
release evidence. Each phase executes in a new interpreter outside the source.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path


def require(value, message):
    if not value:
        raise RuntimeError(message)


def theseus(root, phase):
    from aethel.enterprise import compose
    from aethel.enterprise.errors import EnterpriseCustodyError
    from aethel.enterprise.records import OperationalRecord, ProducerAdmissionError
    key = (root / "custody.key").read_bytes()
    require(compose.__module__ == "aethel.enterprise.custody", "noncanonical custody root")
    c = compose(root / "custody", hmac_key=key)
    payload = b"HYBA standalone THESEUS release fixture; not production observation"
    try:
        if phase == "write":
            record = OperationalRecord(record_id="release-fixture", producer="ovid",
                producer_version="1.0.0", schema_version=1, kind="publication-fixture",
                payload=payload, evidence_state="UNAVAILABLE")
            c.put_record(record, idempotency_key="release-fixture")
            c.put_record(record, idempotency_key="release-fixture")
        actual = c.get_record("release-fixture")
        require(actual.payload == payload and actual.evidence_state == "UNAVAILABLE", "custody altered bytes/evidence")
        replay = c.verify_replay()
        require(replay["match"] is True and replay["expected_records"] == 1,
                "custody replay diverged or retry duplicated a logical record")
        require(c.custody_evidence("release-fixture")["integrity"] == "PASS", "custody evidence failed")
        if phase == "negative":
            bad = OperationalRecord(record_id="bad", producer="unregistered-release-producer",
                producer_version="1", schema_version=1, kind="bad", payload=payload)
            try:
                c.put_record(bad)
            except ProducerAdmissionError:
                pass
            else:
                raise RuntimeError("unknown producer admitted")
            try:
                compose(root / "no-key", hmac_key=b"")
            except (ValueError, EnterpriseCustodyError):
                pass
            else:
                raise RuntimeError("missing key accepted")
            c.corrupt_for_test("release-fixture", side="primary")
            c.corrupt_for_test("release-fixture", side="replica")
            try:
                c.get_record("release-fixture")
            except EnterpriseCustodyError:
                pass
            else:
                raise RuntimeError("corrupted primary and replica accepted")
        return {"product":"THESEUS", "phase":phase, "payload_sha256":hashlib.sha256(payload).hexdigest(),
                "status":"PASS", "claim_scope":"single-root installed software fixture",
                "semantic_revalidation":"producer-owned; not self-awarded by release tooling"}
    finally:
        c.close()


def ovid(root, phase):
    from hyba_db import OntologyStore, TheseusFileCustody, Quota, AccessDenied
    from hyba_db.ovid_transform import OvidTransformPlane
    from hyba_db.rebuild import projection_fingerprint, restore_projection_from_custody
    c = TheseusFileCustody(root / "ovid-custody", hmac_key=(root / "custody.key").read_bytes())
    store = OntologyStore(root / "ovid.db", (root / "integrity.key").read_bytes(), custody=c)
    statefile = root / "state.json"
    try:
        if phase == "write":
            first = store.provision_client("release-a", Quota(100000,100000000))
            other = store.provision_client("release-b", Quota(100000,100000000))
            obj, version = store.files.put_file(first.tenant_id, root / "files", logical_name="release.bin",
                file_class="durable_evidence", semantic_owner="ovid", domain="publication-fixture",
                content=b"OVID installed release fixture", producer="ovid", producer_version="1.0.0",
                evidence_state="UNAVAILABLE", links=(("external:release-fixture", "source", "supports"),))
            transform = OvidTransformPlane(store.files).fold_into(first.tenant_id, root / "files", version)
            require(transform["equivalence"]["equivalent"] is True, "wrong transform exactness")
            state = {"tenant":first.tenant_id,"other":other.tenant_id,"version":version,
                     "fingerprint":json.loads(json.dumps(projection_fingerprint(store, first.tenant_id))),
                     "organisation_digest":store.ovid.organisation_digest(first.tenant_id)}
            statefile.write_text(json.dumps(state))
        state = json.loads(statefile.read_text())
        require(store.ovid.verify(state["tenant"])["passed"] is True, "OVID index verification failed")
        require(store.ovid.organisation_digest(state["tenant"]) == state["organisation_digest"], "restart organisation diverged")
        require(json.loads(json.dumps(projection_fingerprint(store,state["tenant"]))) == state["fingerprint"], "restart projection diverged")
        try:
            OvidTransformPlane(store.files).fold_into(state["other"],root / "files",state["version"])
        except AccessDenied:
            pass
        else:
            raise RuntimeError("cross-tenant version was accepted")
        if phase == "negative":
            # A separate new projection must be rebuildable from actual THESEUS custody.
            rebuild_custody = TheseusFileCustody(root / "ovid-custody", hmac_key=(root / "custody.key").read_bytes())
            rebuilt = OntologyStore(root / "rebuilt.db", (root / "integrity.key").read_bytes(),custody=rebuild_custody)
            try:
                result=restore_projection_from_custody(rebuilt,state["tenant"],root / "files")
                require(result["passed"] is True,"custody-to-projection rebuild failed")
                require(json.loads(json.dumps(projection_fingerprint(rebuilt,state["tenant"]))) == state["fingerprint"],"destructive readback diverged")
            finally:
                rebuilt.close(); rebuild_custody.close()
            unbound = OntologyStore(root / "ovid.db", (root / "integrity.key").read_bytes(), custody=None)
            try:
                require(unbound.verify_database(state["tenant"]).file_plane_ok is False,
                        "missing custody adapter was falsely green")
            finally:
                unbound.close()
            store._db.execute("DROP INDEX idx_file_versions_sha")
            require(store.ovid.verify(state["tenant"])["passed"] is False,"missing index was falsely green")
        return {"product":"OVID","phase":phase,"status":"PASS",
                "organisation_digest":state["organisation_digest"],
                "claim_scope":"installed projection + canonical THESEUS software composition",
                "semantic_revalidation":"producer-owned; full production gate not self-awarded"}
    finally:
        store.close();c.close()


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--product",choices=("theseus","ovid"),required=True)
    p.add_argument("--phase",choices=("write","restart","negative"),required=True)
    p.add_argument("--root",type=Path,required=True)
    args=p.parse_args()
    print(json.dumps((theseus if args.product=="theseus" else ovid)(args.root,args.phase),sort_keys=True))

if __name__=="__main__":
    main()
