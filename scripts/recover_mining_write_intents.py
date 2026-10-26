#!/usr/bin/env python3
"""Explicit, offline recovery of interrupted mining receipts. Never deletes evidence.

Stop the mining service first and snapshot its state. The caller supplies the
existing keys and quotas through PYTHIA_STORAGE_*; no keys are generated here.
Legacy receipt semantics must match a retained causal source event byte-for-byte
(after canonical JSON normalization). Unknown original context links stay unknown.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from aethel.enterprise.governance import Quotas
from hyba_db.models import IntegrityFailure
from hyba_db.store import OntologyStore
from hyba_db.theseus_custody import TheseusFileCustody


def stable(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), default=str)


def source_index(path):
    sources = set()
    for line in Path(path).read_text().splitlines():
        event = json.loads(line)
        if all(k in event for k in ('kind', 'seq', 'at', 'coordinate', 'detail')):
            sources.add(hashlib.sha256(stable(event).encode()).hexdigest())
    return sources


def legacy_receipt_request(files, tenant, intent, root, sources):
    obj = files.store._db.execute(
        'SELECT * FROM file_objects WHERE tenant_id=? AND file_object_id=?',
        (tenant, intent['file_object_id']),
    ).fetchone()
    path = Path(intent['final_uri'])
    try:
        path.resolve().relative_to(Path(root).resolve() / tenant)
    except ValueError as exc:
        raise IntegrityFailure('legacy receipt outside tenant root') from exc
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != intent['content_sha256']:
        raise IntegrityFailure('legacy receipt digest mismatch')
    body = json.loads(data)
    event = {k: v for k, v in body.items() if k != 'chain_records'}
    source_digest = hashlib.sha256(stable(event).encode()).hexdigest()
    if source_digest not in sources:
        raise IntegrityFailure('legacy receipt has no matching causal source event')
    if (obj is None or obj['semantic_owner'] != 'chronus'
        or obj['logical_name'] != f"receipt-{body['kind']}-seq{body['seq']}.json"
        or obj['domain'] != f"mining:{body['kind']}"):
        raise IntegrityFailure('legacy receipt object/source mismatch')
    chain = body.get('chain_records', [])
    for rid in chain:
        record = files.store._db.execute(
            'SELECT custody_record_id FROM mining_lifecycle WHERE tenant_id=? AND record_id=?',
            (tenant, rid),
        ).fetchone()
        if record is None or not files.custody.verify(tenant, record[0]):
            raise IntegrityFailure('legacy receipt refers to an unverified mining record')
    version = files.store._db.execute(
        'SELECT fv.*,fp.provenance_json FROM file_versions fv JOIN file_provenance fp '
        'USING(tenant_id,file_version_id) WHERE fv.tenant_id=? AND fv.file_object_id=? '
        'AND fv.content_sha256=? ORDER BY fv.version DESC LIMIT 1',
        (tenant, intent['file_object_id'], intent['content_sha256']),
    ).fetchone()
    links = []
    if version:
        provenance = json.loads(version['provenance_json'])
        links = [tuple(x) for x in files.store._db.execute(
            'SELECT domain_type,domain_id,relationship FROM file_links '
            'WHERE tenant_id=? AND file_version_id=?', (tenant, version['file_version_id']))]
    else:
        provenance = {
            'source_ids': chain, 'correlation_ids': body['coordinate'],
            'code_ref': body.get('software_revision') or 'UNAVAILABLE',
            'recovery_class': 'operator-reconstructed-legacy-causal-receipt',
            'recovery_source_event_sha256': source_digest,
            'backend': body['detail'].get('executed_route') or 'UNAVAILABLE',
            'device_identity': body['detail'].get('device_identity') or 'UNAVAILABLE',
        }
    if not links:
        # Do not invent the previous in-memory "context" head after a crash.
        links = [('mining', chain[-1], 'receipt')] if chain else [
            ('external:causal_ledger', source_digest, 'recovered_from')]
    return {
        'logical_name': obj['logical_name'], 'file_class': obj['file_class'],
        'semantic_owner': obj['semantic_owner'], 'domain': obj['domain'],
        'producer': version['producer'] if version else 'chronus',
        'producer_version': version['producer_version'] if version else body.get('software_revision') or 'UNAVAILABLE',
        'schema_version': version['schema_version'] if version else 1,
        'evidence_state': version['evidence_state'] if version else 'MEASURED',
        'provenance': provenance, 'links': links,
    }


def recover(*, apply=False, causal_path=None):
    if not os.getenv('PYTHIA_M3_ACTOR'):
        raise ValueError('explicit PYTHIA_M3_ACTOR required for operator recovery')
    names = {'max_payload': 'PAYLOAD_BYTES', 'max_records': 'RECORDS', 'max_tenant_bytes': 'TENANT_BYTES'}
    quotas = {field: int(os.environ['PYTHIA_STORAGE_CUSTODY_MAX_' + suffix])
              for field, suffix in names.items() if os.getenv('PYTHIA_STORAGE_CUSTODY_MAX_' + suffix)}
    custody = TheseusFileCustody(os.environ['PYTHIA_STORAGE_CUSTODY_ROOT'],
        hmac_key=bytes.fromhex(os.environ['PYTHIA_STORAGE_CUSTODY_KEY_HEX']), quotas=Quotas(**quotas))
    store = OntologyStore(os.environ['PYTHIA_STORAGE_DB'],
        bytes.fromhex(os.environ['PYTHIA_STORAGE_INTEGRITY_KEY_HEX']), custody=custody)
    try:
        from scripts.provision_m3_tenant import namespace_for
        tenant = store._db.execute('SELECT tenant_id FROM tenants WHERE namespace=?',
            (namespace_for(os.environ['PYTHIA_STORAGE_TENANT']),)).fetchone()
        if tenant is None:
            raise ValueError('existing admitted tenant required')
        tenant = tenant[0]
        root = Path(os.environ['PYTHIA_STORAGE_ROOT'])
        pending = store._db.execute("SELECT * FROM file_intents WHERE tenant_id=? AND state!='COMMITTED' ORDER BY rowid", (tenant,)).fetchall()
        sources = source_index(causal_path) if causal_path else set()
        requests = []
        # Validate ALL legacy sources before mutating any incomplete intent.
        for row in pending:
            detail = json.loads(row['detail_json'])
            req = None if detail.get('request') else legacy_receipt_request(store.files, tenant, row, root, sources)
            requests.append((row['intent_id'], req))
        results = []
        if apply:
            for iid, req in requests:
                results.append(store.files.resume_write_intent(tenant, iid, root, legacy_request=req))
        report = store.files.reconcile_files(tenant, root)
        return {'applied': apply, 'pending_at_start': len(pending), 'recovered': results,
                'reconciliation': report.to_dict(), 'database': store.files.verify_database(tenant),
                'mining_chain_valid': store.files.verify_mining(tenant)}
    finally:
        store.close()
        custody.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--apply', action='store_true')
    p.add_argument('--causal-log', type=Path)
    p.add_argument('--report', type=Path, required=True)
    args = p.parse_args()
    report = recover(apply=args.apply, causal_path=args.causal_log)
    args.report.write_text(json.dumps(report, indent=2))
    args.report.chmod(0o600)
    return 0 if report['reconciliation']['passed'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
