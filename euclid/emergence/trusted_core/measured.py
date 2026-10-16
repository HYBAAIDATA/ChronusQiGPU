"""Public-key substrate registration and challenge-bound local execution verification."""
from dataclasses import asdict, dataclass
import json
import math
import os
from types import MappingProxyType

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from ..models.substrate import SubstrateProperties
from ..models.telemetry import TelemetryRecord, NoveltyReport
from ..substrate.executors import ReproductionEvidence
from ..substrate import engine
from .custody import CandidateCustodyError


@dataclass(frozen=True)
class RegisteredSubstrate:
    properties: SubstrateProperties
    public_key: Ed25519PublicKey
    backend: str
    artifact_hash: str
    environment_hash: str
    manifest_hash: str
    repetitions: int = 5

    def __post_init__(self):
        if (type(self.properties) is not SubstrateProperties
                or not all(type(v) is str and v for v in
                    (self.artifact_hash, self.environment_hash, self.manifest_hash))
                or not isinstance(self.public_key, Ed25519PublicKey)
                or self.backend not in ('in_process', 'isolated_worker')
                or type(self.repetitions) is not int or self.repetitions < 2):
            raise ValueError('explicit measured substrate binding required')


class MeasuredEvidenceVerifier:
    def __init__(self, registrations=None):
        bindings = {}
        for substrate_id, registration in (registrations or {}).items():
            if type(registration) is not RegisteredSubstrate or substrate_id != registration.properties.compute_id():
                raise ValueError('registry identity/properties mismatch')
            bindings[substrate_id] = registration
        raw_keys = [b.public_key.public_bytes(serialization.Encoding.Raw,
                    serialization.PublicFormat.Raw) for b in bindings.values()]
        if len(set(raw_keys)) != len(raw_keys):
            raise ValueError('each registered substrate requires a distinct custody key')
        self.registrations = MappingProxyType(bindings)

    def verify(self, result, protocol, *, fingerprint, challenge, factor=1.0, envelope=None):
        try:
            if type(result) is not ReproductionEvidence:
                raise ValueError('typed execution evidence required')
            # Detach the evidence immediately; later caller mutation cannot rewrite accepted custody.
            result = ReproductionEvidence(**json.loads(engine.canonical(result.to_dict())))
            binding = self.registrations.get(result.substrate_id)
            if binding is None:
                raise ValueError('unregistered substrate')
            if (protocol.manifest_hash != binding.manifest_hash
                    or protocol.environment_snapshot_hash != binding.environment_hash):
                raise ValueError('protocol manifest/environment differs from registered execution')
            d = result.details
            binding.public_key.verify(bytes.fromhex(d['custody_signature']), result.signing_body())
            unsigned = dict(d)
            unsigned.pop('custody_signature')
            if result.signed_journal_hash != engine.digest(unsigned):
                raise ValueError('journal digest mismatch')
            checks = {'execution_kind': 'MEASURED', 'backend': binding.backend,
                'properties': json.loads(binding.properties.canonical_json()),
                'artifact_hash': binding.artifact_hash, 'environment_hash': binding.environment_hash,
                'protocol_hash': protocol.compute_protocol_hash(), 'candidate_fingerprint': fingerprint,
                'challenge': challenge, 'stress_factor': factor, 'base_repetitions': binding.repetitions,
                'repetitions': math.ceil(binding.repetitions * factor), 'expanded_envelope': envelope}
            if any(d.get(key) != value for key, value in checks.items()):
                raise ValueError('execution scope/provenance mismatch')
            repetitions = checks['repetitions']
            summary = engine.summarize(asdict(protocol), d['trials'], repetitions)
            if (result.observed != summary['observed'] or result.reproduction_rate != summary['reproduction_rate']
                    or result.observed_behaviors != summary['observed_behaviors']
                    or result.execution_metrics != {k: summary[k] for k in ('latency_ms', 'stability', 'entropy')}):
                raise ValueError('derived execution measurements mismatch')
            if not engine.finite_number(d['elapsed_ms']) or d['elapsed_ms'] <= 0:
                raise ValueError('missing elapsed measurement')
            if binding.backend == 'isolated_worker':
                if any(t['pid'] == d['parent_pid'] for t in d['trials']):
                    raise ValueError('worker process separation absent')
            elif any(t['pid'] != d['parent_pid'] for t in d['trials']):
                raise ValueError('in-process execution identity mismatch')
            records = []
            for i, trial in enumerate(d['trials']):
                rec = TelemetryRecord(d['run_id'], result.substrate_id, i, protocol.task_signature,
                    tuple(trial['actions']), NoveltyReport(), tuple(trial['invariant_violations']),
                    {'started': d['timestamp'], 'duration_ms': trial['duration_ms']},
                    {'seed': trial['seed']}, d['environment_hash']).with_computed_hash()
                records.append(rec)
            if d['telemetry'] != [r.to_dict() for r in records]:
                raise ValueError('incomplete or changed telemetry window')
            return result, tuple(records)
        except (InvalidSignature, KeyError, TypeError, ValueError, ArithmeticError) as exc:
            raise CandidateCustodyError('lacks measured reproduction: ' + str(exc)) from exc
