"""Versioned, integrity-checked offline data checkpoints.

Single trusted writer only. A checkpoint is not a write-ahead log, an
idempotency ledger, an authenticated backup, or live-write durability.
Recovery creates a NEW layer; it never overwrites an active instance.
"""
from __future__ import annotations

import base64
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
import zlib

from .data_layer import Policy, Record, UnifiedDataLayer, _canonical, _digest, detached_payload

SCHEMA = 'toe.unified.data-checkpoint/v1'
FIELDS = {
    'records', 'policies', 'audit', 'batch', 'by_entity', 'blobs', 'raw_bytes',
    'stored_bytes', 'index_visits', 'scan_visits', 'row_audit', 'batch_payloads',
}


def save_checkpoint(layer: UnifiedDataLayer, path: str | Path) -> str:
    """Atomic file replacement and fsync; caller must authorize and own the path."""
    path = Path(path)
    # Serialize writes from this layer in order, including file publication.
    with layer._lock:
        state = {
            'records': [asdict(record) for record in layer._records.values()],
            'policies': [asdict(policy) for policy in layer._policies.values()],
            'audit': deepcopy(layer.audit), 'batch': layer._batch,
            'by_entity': deepcopy(layer._by_entity),
            'blobs': {key: base64.b64encode(value).decode('ascii') for key, value in layer._blobs.items()},
            'raw_bytes': layer.raw_bytes, 'stored_bytes': layer.stored_bytes,
            'index_visits': layer.index_visits, 'scan_visits': layer.scan_visits,
            'row_audit': list(layer.row_audit), 'batch_payloads': deepcopy(layer._batch_payloads),
        }
        # asdict emits a tuple for lineage; JSON is the on-disk contract.
        state = json.loads(_canonical(state))
        checksum = hashlib.sha256(_canonical(state).encode()).hexdigest()
        encoded = _canonical({'schema': SCHEMA, 'sha256': checksum, 'state': state}).encode()
        fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
            directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return checksum


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate checkpoint JSON key')
        result[key] = value
    return result


def load_checkpoint(path: str | Path) -> UnifiedDataLayer:
    """Reject missing/corrupt/inconsistent state; never invent an empty success."""
    envelope = json.loads(Path(path).read_text(), object_pairs_hook=_unique_object)
    if not isinstance(envelope, dict) or set(envelope) != {'schema', 'sha256', 'state'}:
        raise ValueError('invalid checkpoint envelope')
    if envelope['schema'] != SCHEMA:
        raise ValueError('unsupported checkpoint schema')
    state = envelope['state']
    if hashlib.sha256(_canonical(state).encode()).hexdigest() != envelope['sha256']:
        raise ValueError('checkpoint checksum mismatch')
    if not isinstance(state, dict) or set(state) != FIELDS:
        raise ValueError('incomplete checkpoint state')
    state = detached_payload(state)
    for key in ('batch', 'raw_bytes', 'stored_bytes', 'index_visits', 'scan_visits'):
        if type(state[key]) is not int or state[key] < 0:
            raise ValueError('invalid checkpoint counter: ' + key)
    expected_batches = {f'b{i}' for i in range(1, state['batch'] + 1)}
    if set(state['batch_payloads']) != expected_batches:
        raise ValueError('checkpoint batch ledger mismatch')
    for payloads in state['batch_payloads'].values():
        if not isinstance(payloads, list):
            raise ValueError('invalid batch payloads')
        for payload in payloads:
            detached_payload(payload)
    layer = UnifiedDataLayer()
    by_entity = {}
    for entry in state['records']:
        entry['lineage'] = tuple(detached_payload(item) for item in entry['lineage'])
        record = Record(**entry)
        if not record.source or not isinstance(record.source, str) or not record.entity or not isinstance(record.entity, str):
            raise ValueError('invalid record identity')
        if type(record.quarantined) is not bool:
            raise ValueError('invalid quarantine flag')
        if type(record.ingested_at) not in (int, float) or not math.isfinite(record.ingested_at) or record.ingested_at < 0:
            raise ValueError('invalid ingestion time')
        if not isinstance(record.operator_digest, str) or not record.operator_digest:
            raise ValueError('missing operator lineage')
        if record.batch_id not in expected_batches or not re.fullmatch(r'b[1-9][0-9]*', record.batch_id):
            raise ValueError('invalid record batch')
        payload = detached_payload(record.payload)
        digest = _digest({'source': record.source, 'entity': record.entity, 'payload': payload})
        if digest != record.digest or digest in layer._records:
            raise ValueError('invalid or duplicate record digest')
        blob = base64.b64decode(state['blobs'][digest], validate=True)
        if zlib.decompress(blob) != json.dumps(payload, sort_keys=True, allow_nan=False).encode():
            raise ValueError('checkpoint blob/payload mismatch')
        if payload not in state['batch_payloads'][record.batch_id]:
            raise ValueError('record missing from receiving batch')
        layer._records[digest] = record
        layer._blobs[digest] = blob
        layer.raw_bytes += len(zlib.decompress(blob))
        layer.stored_bytes += len(blob)
        by_entity.setdefault(record.entity.casefold(), []).append(digest)
    if set(state['blobs']) != set(layer._records) or by_entity != state['by_entity']:
        raise ValueError('checkpoint index mismatch')
    if state['row_audit'] != list(layer._records):
        raise ValueError('checkpoint row audit mismatch')
    if (layer.raw_bytes, layer.stored_bytes) != (state['raw_bytes'], state['stored_bytes']):
        raise ValueError('checkpoint byte accounting mismatch')
    for entry in state['policies']:
        policy = Policy(**entry)
        if policy.entity in layer._policies:
            raise ValueError('duplicate checkpoint policy')
        layer._policies[policy.entity] = policy
    if not isinstance(state['audit'], list):
        raise ValueError('invalid checkpoint audit')
    layer.audit = state['audit']
    layer._batch = state['batch']
    layer._batch_payloads = state['batch_payloads']
    layer._by_entity = by_entity
    layer.row_audit = state['row_audit']
    layer.index_visits = state['index_visits']
    layer.scan_visits = state['scan_visits']
    return layer
