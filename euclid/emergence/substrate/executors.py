"""Measured in-process and fresh-process substrates; signatures are host custody, not attestation."""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import math
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Sequence

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from ..models.candidate import ReproductionProtocol
from ..models.manifest import CapabilityManifest
from ..models.substrate import SubstrateProperties, SubstrateExecutionResult
from ..models.telemetry import TelemetryRecord, NoveltyReport
from . import engine


@dataclass
class ReproductionEvidence:
    observed: bool
    executor_id: str
    substrate_id: str
    reproduction_rate: float
    observed_behaviors: List[str]
    signed_journal_hash: str
    execution_metrics: Dict[str, float]
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        from dataclasses import asdict
        return asdict(self)

    def signing_body(self):
        body = self.to_dict()
        body['details'].pop('custody_signature', None)
        return engine.canonical(body)


class BaseExecutor:
    backend = 'unavailable'

    def __init__(self, properties: SubstrateProperties, executor_id: Optional[str] = None,
                 *, signing_key: Optional[Ed25519PrivateKey] = None, repetitions: int = 5,
                 timeout_seconds: float = 10):
        if signing_key is not None and not isinstance(signing_key, Ed25519PrivateKey):
            raise TypeError('explicit host-owned Ed25519 signing key required')
        if type(repetitions) is not int or not 2 <= repetitions <= 1000:
            raise ValueError('2..1000 repetitions required')
        if not engine.finite_number(timeout_seconds) or not 0 < timeout_seconds <= 60:
            raise ValueError('bounded positive worker timeout required')
        self.properties, self.substrate_id = properties, properties.compute_id()
        self.executor_id = executor_id or secrets.token_hex(16)
        self.state_store = {}
        self.signing_key, self.repetitions, self.timeout_seconds = signing_key, repetitions, timeout_seconds

    def reproduce(self, protocol: ReproductionProtocol, *, challenge=None, stress_factor=1.0,
                  candidate_fingerprint='', expanded_envelope=None):
        start = time.perf_counter_ns()
        challenge = challenge or secrets.token_hex(32)
        if not engine.finite_number(stress_factor) or stress_factor < 1:
            raise ValueError('finite stress factor >= 1 required')
        repetitions = math.ceil(self.repetitions * stress_factor)
        details = {'execution_kind': 'UNAVAILABLE', 'backend': self.backend,
                   'protocol_hash': protocol.compute_protocol_hash(), 'challenge': challenge,
                   'candidate_fingerprint': candidate_fingerprint, 'stress_factor': stress_factor,
                   'base_repetitions': self.repetitions, 'repetitions': repetitions,
                   'properties': json.loads(self.properties.canonical_json()),
                   'expanded_envelope': expanded_envelope, 'parent_pid': os.getpid(),
                   'run_id': secrets.token_hex(32), 'timestamp': time.time(),
                   'independent_attestation': False}
        result = ReproductionEvidence(False, self.executor_id, self.substrate_id, 0, [], '', {}, details)
        try:
            if self.signing_key is None:
                raise ValueError('host substrate signing key unavailable')
            if self.backend not in ('in_process', 'isolated_worker'):
                raise ValueError('measured backend unavailable')
            from dataclasses import asdict
            request = {'protocol': asdict(protocol), 'repetitions': repetitions}
            # Canonical roundtrip detaches all caller-owned nested protocol state.
            request = json.loads(engine.canonical(request))
            if self.backend == 'in_process':
                payload = engine.execute_request(request)
            else:
                # -I ignores environment/PYTHONPATH; a new interpreter gets JSON only, no keys.
                completed = subprocess.run([sys.executable, '-I', str(Path(engine.__file__).resolve())],
                    input=engine.canonical(request), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    timeout=self.timeout_seconds, check=False, cwd=Path(engine.__file__).parent)
                if completed.returncode:
                    raise ValueError('worker failed: ' + completed.stderr.decode(errors='replace')[:500])
                payload = json.loads(completed.stdout)
            summary = engine.summarize(request['protocol'], payload['trials'], repetitions)
            details.update(payload)
            details['execution_kind'] = 'MEASURED'
            result.observed, result.reproduction_rate = summary['observed'], summary['reproduction_rate']
            result.observed_behaviors = summary['observed_behaviors']
            result.execution_metrics = {k: summary[k] for k in ('latency_ms', 'stability', 'entropy')}
            details['telemetry'] = [self._record(protocol, details, trial, i).to_dict()
                                    for i, trial in enumerate(payload['trials'])]
            self.state_store = json.loads(engine.canonical(payload['trials'][-1]['state']))
        except (ValueError, TypeError, KeyError, ArithmeticError, OSError, subprocess.TimeoutExpired) as exc:
            details['error'] = type(exc).__name__ + ': ' + str(exc)
            result.observed = False
        details['elapsed_ms'] = (time.perf_counter_ns() - start) / 1e6
        result.signed_journal_hash = engine.digest(details)
        if self.signing_key is not None:
            details['custody_signature'] = self.signing_key.sign(result.signing_body()).hex()
        return result

    def execute_reproduction(self, protocol, iterations=None, stress_factor=1.0):
        if iterations is not None and iterations != self.repetitions:
            raise ValueError('configure repetitions on the host-owned executor')
        return self.reproduce(protocol, stress_factor=stress_factor)

    def _record(self, protocol, details, trial, index):
        return TelemetryRecord(details['run_id'], self.substrate_id, index, protocol.task_signature,
            tuple(trial['actions']), NoveltyReport(), tuple(trial['invariant_violations']),
            {'started': details['timestamp'], 'duration_ms': trial['duration_ms']},
            {'seed': trial['seed']}, details['environment_hash']).with_computed_hash()

    def execute_run(self, architecture: Any, task_suite: Sequence[str], iterations: int,
                    telemetry_module: Any, manifest: CapabilityManifest) -> SubstrateExecutionResult:
        # Generic architecture discovery requires actual observations; never manufacture obs/task strings.
        if self.backend != 'in_process':
            raise ValueError('arbitrary architecture objects cannot enter JSON-isolated worker; use reproduce')
        if type(iterations) is not int or iterations < 2 or not task_suite:
            raise ValueError('nonempty tasks and >=2 iterations required')
        if not all(callable(getattr(architecture, name, None)) for name in ('decide', 'act', 'observe')):
            raise TypeError('real decide/act/observe architecture required')
        from ..telemetry.sink import TelemetryStream
        run_id = secrets.token_hex(16)
        stream = TelemetryStream(run_id)
        records, behaviors, trajectories = [], set(), []
        for i in range(iterations):
            task = task_suite[i % len(task_suite)]
            decisions = architecture.decide(task, iteration=i)
            actions = architecture.act(decisions)
            observation = architecture.observe()
            if type(observation) is not dict or not observation or not all(engine.finite_number(v) for v in observation.values()):
                raise ValueError('numeric measured observation dictionary required')
            trajectories.append([observation[k] for k in sorted(observation)])
            rec, _ = telemetry_module.on_iteration(agent_id=self.executor_id, task_signature=task,
                actions=actions, observations=[observation], decisions=decisions,
                run_id=run_id, substrate_id=self.substrate_id, iteration_index=i,
                manifest=manifest, telemetry_stream=stream)
            records.append(rec)
            behaviors.update(rec.novel_elements.unattributed)
        result = SubstrateExecutionResult(self.substrate_id, self.properties, iterations,
            {'novel_behavior_count': float(len(behaviors)), 'stability': engine.stability(trajectories)},
            records, sorted(behaviors))
        result.run_hash = result.compute_run_hash()
        return result


class StandardSyncExecutor(BaseExecutor):
    backend = 'in_process'


class AsyncIsolatedExecutor(BaseExecutor):
    """Fresh interpreter and disjoint state; not container/hostile-code isolation."""
    backend = 'isolated_worker'


RealSubstrateExecutor = StandardSyncExecutor
