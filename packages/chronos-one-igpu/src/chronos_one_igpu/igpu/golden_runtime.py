"""Solve-first composition with immutable lease/target and replayable CPU evidence."""
from dataclasses import asdict
from itertools import islice
import hashlib
import json
import platform
import time
import uuid
import hmac
import threading
import numpy as np
from ..golden_quantum import (
    GoldenConstants, MathematicalQuantumState, HamiltonianEngine,
    AdvancedMathematicalOracles, GoldenTransform, DataFoldingEngine,
    TransfiniteMemoryMapper, QuantumCoherenceAnalyzer, MandelbrotResonanceEngine,
    GoldenQuantumInfinityFold, GoldenQuantumComputer, GoldenRatioMining,
    OmniscienceKernel, SuperGPU, ClusterInventory,
)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def verify_evidence(events, key=None, expected_head=None):
    previous = "0" * 64
    for event in events:
        body = dict(event); digest = body.pop("digest"); signature=body.get("signature"); body["signature"]=None
        if signature is not None and(key is None or not hmac.compare_digest(signature,hmac.new(key,digest.encode(),hashlib.sha256).hexdigest())):raise ValueError("signed evidence requires matching verification key")
        if body["previous"] != previous or hashlib.sha256(canonical(body)).hexdigest() != digest:
            raise ValueError("evidence hash-chain mismatch")
        previous = digest
    if expected_head is not None and previous!=expected_head:raise ValueError("evidence head mismatch or truncation")
    return True


class GoldenRuntime:
    MAX_CANDIDATES = 128
    def __init__(self, db=None, enabled=True, max_candidates=64, evidence_key=None):
        if type(max_candidates) is not int or not 1 <= max_candidates <= self.MAX_CANDIDATES:
            raise ValueError("bounded candidate quota required")
        if evidence_key is not None and(not isinstance(evidence_key,bytes)or len(evidence_key)<32):raise ValueError("evidence key must be at least 32 bytes")
        self.evidence_key=evidence_key;self._evidence_lock=threading.RLock()
        self.enabled = bool(enabled); self.db = db; self.max_candidates = max_candidates
        self.constants = GoldenConstants(); self.transform = GoldenTransform()
        self.folding = DataFoldingEngine(); self.memory = TransfiniteMemoryMapper()
        self.coherence = QuantumCoherenceAnalyzer(); self.fractal = MandelbrotResonanceEngine()
        self.infinity_fold = GoldenQuantumInfinityFold(); self.computer = GoldenQuantumComputer()
        self.miner = GoldenRatioMining(); self.uci = OmniscienceKernel()
        self.fabric = None; self.inventory = None; self.events = []; self.session_id = str(uuid.uuid4())
        from .solver_cache import DeterministicSolverCache
        self.solver_cache=DeterministicSolverCache()

    def attest(self, operation, started, partition=None, details=None, execution=None, scale_index=15):
        with self._evidence_lock:
            execution=execution or {"backend":"cpu_reference","device":platform.machine(),"capability":operation}
            body = {"schema": "chronos_golden_evidence_v1", "session_id": self.session_id, "sequence": len(self.events),
                    "previous": self.events[-1]["digest"] if self.events else "0"*64,
                    "operation": operation, "logical_device":"chronos_igpu", "backend": execution["backend"], "device": execution["device"],
                    "capability": execution["capability"], "lucas_rung": scale_index, "lucas_value": self.constants.lucas(scale_index),
                    "partition": partition, "duration_seconds": time.perf_counter()-started,
                    "clock": "perf_counter", "truth_class": "measured_"+execution["backend"],
                    "power_watts": None, "signature": None, "details": details or {}}
            event = {**body, "digest": hashlib.sha256(canonical(body)).hexdigest()}
            if self.evidence_key is not None:event["signature"]=hmac.new(self.evidence_key,event["digest"].encode(),hashlib.sha256).hexdigest()
            if self.db is not None:
                # Sequence count is bounded separately from mathematical indices.
                self.db.put(event, 1, family="golden_evidence")
            self.events.append(event)
            return event

    def checkpoint(self, data, index=0):
        if self.db is None: raise RuntimeError("checkpoint requires a PrimeDB path")
        start = time.perf_counter(); obj = self.memory.checkpoint(self.db, data, index)
        self.attest("checkpoint", start, details={"object_id": obj.object_id})
        return obj

    def restore(self, object_id):
        if self.db is None: raise RuntimeError("restore requires a PrimeDB path")
        start = time.perf_counter(); out = self.memory.restore(self.db, object_id)
        self.attest("restore", start, details={"object_id": object_id})
        return out

    def _validate_advice(self, advice, lease):
        values = list(islice(advice, self.max_candidates+1))
        if len(values) > self.max_candidates or len(values) != len(set(values)):
            raise ValueError("candidate quota/duplicate violation")
        if any(type(n) is not int or not lease.start <= n < lease.stop for n in values):
            raise ValueError("advice outside authorised lease")
        return values

    def plan(self, lease, solver=None, checkpoint_id=None,scale_index=15):
        from .scaled_plan import LADDER
        if scale_index not in LADDER:raise ValueError("undeclared Lucas rung")
        started = time.perf_counter(); path = []; reason = None; solver_evidence=None
        if not self.enabled:
            return {"order": (), "path": ("F3_classical",), "integration_mode": "classical_baseline", "reason": "explicit classical baseline selected"}
        candidates = list(range(lease.start, min(lease.stop, lease.start+self.max_candidates)))
        if not candidates:
            return {"order": (), "path": ("F3_classical",), "integration_mode": "solve_first", "reason": "empty lease"}
        try:
            # S1: reversible physical folding and numerical preconditioning.
            from .exact_fold import ExactFoldState
            pair_fold=ExactFoldState.fold(candidates)
            if pair_fold.unfold()!=tuple(candidates):raise ValueError("exact pair fold round-trip failure")
            raw = canonical({"job_id": lease.job_id, "epoch": lease.epoch, "candidates": candidates, "exact_fold":pair_fold.to_dict()})
            if self.folding.unfold(self.folding.fold(raw)) != raw: raise ValueError("fold round-trip failure")
            folded_state = self.transform.forward(np.ones(len(candidates)))
            path.append("S1_fold_transform")
            # S2: restore only explicit, job-bound checkpoint suggestions; never mutate lease.
            if checkpoint_id is not None:
                restored = json.loads(self.restore(checkpoint_id))
                if restored["job_id"] != lease.job_id or restored["epoch"] != lease.epoch:
                    raise ValueError("stale checkpoint")
                candidates = self._validate_advice(restored["candidates"], lease)
                if not candidates: raise ValueError("empty checkpoint candidates")
                folded_state = self.transform.forward(np.ones(len(candidates)))
            self.memory.address(0); path.append("S2_prime_checkpoint")
            state = MathematicalQuantumState(folded_state)
            gate = self.coherence.analyze(state); path.append("S3_coherence")
            if not gate["high_quality"]: raise ValueError("low-quality numerical regime")
            candidates = self.fractal.rank(candidates); path.append("S4_mandelbrot")
            candidates = self.infinity_fold.rank(candidates); path.append("S5_infinity_fold")
            if solver is None:
                positions,solver_evidence=self.solver_cache.rank(state.amplitudes,self.constants.phi)
                candidates = [candidates[i] for i in positions]
            else:
                candidates = self._validate_advice(solver(tuple(candidates)), lease)
            path.append("S6_chronos_solver")
            if not candidates: raise ValueError("solver returned no candidates")
        except Exception as exc:
            reason = f"{type(exc).__name__}: {exc}"
            # Explicit F1 finite ordering; full Grover simulation is a separate API.
            candidates = self.computer.prioritize(range(lease.start, min(lease.stop, lease.start+self.max_candidates)))
            path.append("F1_golden_quantum_fallback")
            if not candidates:
                candidates = self.miner.prioritize(range(lease.start, min(lease.stop, lease.start+self.max_candidates)))
                path.append("F2_golden_nonce")
        candidates = self._validate_advice(candidates, lease)
        path.append("F3_classical_remainder")
        self.attest("solve_first_plan", started, asdict(lease), {"path": path, "reason": reason, "candidate_count": len(candidates), "solver":solver_evidence},scale_index=scale_index)
        return {"order": tuple(candidates), "path": tuple(path), "integration_mode": "solve_first", "reason": reason}

    def mine(self, header_prefix, target, lease, max_evaluations=65536, solver=None,
             checkpoint_id=None, current_epoch=None, deadline=None,scale_index=15):
        from .scaled_plan import LADDER
        if scale_index not in LADDER:raise ValueError("undeclared Lucas rung")
        # Admit before candidate planning or checkpoint IO.
        if not isinstance(header_prefix, bytes) or len(header_prefix) != 76: raise ValueError("76-byte header prefix required")
        AdvancedMathematicalOracles.accepts(bytes(32), target)
        if type(max_evaluations) is not int or not 0 <= max_evaluations <= 1000000: raise ValueError("invalid evaluation budget")
        if current_epoch is not None and current_epoch != lease.epoch: raise ValueError("stale lease")
        if deadline is not None and (not np.isfinite(deadline) or time.perf_counter() >= deadline): raise ValueError("expired or invalid deadline")
        started = time.perf_counter()
        plan = self.plan(lease, solver, checkpoint_id,scale_index) if max_evaluations else {"order": (), "path": ("F3_classical",)}
        order = plan["order"][:max_evaluations]
        if self.fabric is not None and self.fabric.has_sha256d_executor():
            result = self.fabric.scan_sha256d(header_prefix,target,lease,order,max_evaluations,current_epoch,deadline)
        elif "F1_golden_quantum_fallback" in plan["path"] and max_evaluations:
            from ..golden_quantum import MiningResult, NonceLease
            size=min(self.max_candidates,max_evaluations,lease.stop-lease.start)
            digests=[]
            def oracle(index):
                if deadline is not None and time.perf_counter()>=deadline:raise TimeoutError("golden fallback deadline")
                digest=AdvancedMathematicalOracles.nonce_digest(header_prefix,lease.start+index)
                digests.append(digest);return AdvancedMathematicalOracles.accepts(digest,target)
            if size:
                phase_started=time.perf_counter();search_result=self.computer.simulate_golden_feedback(size,oracle)
                self.attest("golden_phase_feedback",phase_started,asdict(lease),{"oracle_sha256d_evaluations":len(digests),"phase_iterations":4,"success":search_result.success})
                if search_result.success:
                    nonce=lease.start+search_result.candidate;digest=digests[search_result.candidate]
                    elapsed=time.perf_counter()-started
                    result=MiningResult(nonce,digest.hex(),True,len(digests),elapsed,len(digests)/elapsed if elapsed else 0,"cpu_reference",plan["path"])
                else:
                    remainder=NonceLease(lease.start+size,lease.stop,lease.job_id,lease.epoch)
                    remaining_budget=max_evaluations-size
                    priority=self.miner.prioritize(range(remainder.start,min(remainder.stop,remainder.start+min(self.max_candidates,remaining_budget))))
                    result=self.miner.scan(header_prefix,target,remainder,priority,remaining_budget,current_epoch,deadline)
                    from dataclasses import replace
                    result=replace(result,sha256d_evaluations=result.sha256d_evaluations+size)
                    plan={**plan,"path":plan["path"]+("F2_golden_nonce",)}
            else:
                result=self.miner.scan(header_prefix,target,lease,(),max_evaluations,current_epoch,deadline)
        else:
            result = self.miner.scan(header_prefix, target, lease, order, max_evaluations, current_epoch, deadline)
        from dataclasses import replace
        elapsed = time.perf_counter()-started
        result = replace(result, path=plan["path"], elapsed_seconds=elapsed,
                         hashrate=result.sha256d_evaluations/elapsed if elapsed else 0)
        if result.verified:
            verify_start = time.perf_counter()
            digest = AdvancedMathematicalOracles.nonce_digest(header_prefix, result.nonce)
            if digest.hex() != result.digest_hex or not AdvancedMathematicalOracles.accepts(digest, target):
                raise ValueError("host proof verification failed")
            self.attest("host_sha256d_verify", verify_start, asdict(lease), {"verification_hashes": 1, "valid": True},scale_index=scale_index)
        elapsed = time.perf_counter()-started
        result = replace(result, elapsed_seconds=elapsed,
                         hashrate=result.sha256d_evaluations/elapsed if elapsed else 0,
                         verification_sha256d_evaluations=result.verification_sha256d_evaluations+int(result.verified))
        self.attest("sha256d_scan", started, asdict(lease),
                    {**asdict(result), "target": str(target), "header_prefix_sha256": hashlib.sha256(header_prefix).hexdigest(),
                     "verification_sha256d_evaluations": result.verification_sha256d_evaluations}, execution={"backend":result.backend,"device":self.fabric.route("sha256d").bound_device if self.fabric is not None else platform.machine(),"capability":"sha256d"},scale_index=scale_index)
        return result

    def search(self, candidates, predicate, max_evaluations=4096, scale_index=15):
        start = time.perf_counter()
        result = self.computer.search(candidates, predicate, max_evaluations)
        self.attest("search", start, details={"success": result.success, "evaluations": result.evaluations},scale_index=scale_index)
        return result

    def evolve(self, amplitudes, hamiltonian, time_value=1.0):
        start = time.perf_counter()
        from .exact_quantum import exact_hamiltonian_evolution
        result = exact_hamiltonian_evolution(amplitudes,hamiltonian,time_value,legacy_encoding=True)
        self.attest("state_evolution", start, details={"dimension": len(result.amplitudes),
            "execution_receipt":result.evidence})
        return result
