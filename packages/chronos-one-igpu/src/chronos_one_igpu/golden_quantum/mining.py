"""Offline, budgeted SHA-256d reference execution. No Stratum transport."""
from dataclasses import dataclass
import math
import time
from .oracles import AdvancedMathematicalOracles as Oracle
@dataclass(frozen=True)
class NonceLease:
    start: int
    stop: int
    job_id: str = "offline"
    epoch: int = 0
    def __post_init__(self):
        if type(self.start) is not int or type(self.stop) is not int or not 0 <= self.start <= self.stop <= 2**32: raise ValueError("uint32 half-open lease required")
    def partition(self, weights):
        if not weights or any(not math.isfinite(w) or w <= 0 for w in weights): raise ValueError("positive measured weights required")
        # Largest remainder allocation, exact coverage, no duplicated intervals.
        total = self.stop-self.start; ratios = [w/max(weights) for w in weights]; denominator = sum(ratios)
        raw = [total*w/denominator for w in ratios]; widths = [int(v) for v in raw]
        for i in sorted(range(len(widths)), key=lambda i: (-(raw[i]-widths[i]), i))[:total-sum(widths)]: widths[i] += 1
        out = []; pos = self.start
        for width in widths:
            out.append(NonceLease(pos, pos+width, self.job_id, self.epoch)); pos += width
        return tuple(out)
@dataclass(frozen=True)
class MiningResult:
    nonce: object
    digest_hex: object
    verified: bool
    sha256d_evaluations: int
    elapsed_seconds: float
    hashrate: float
    backend: str
    path: tuple
    pool_accepted: object = None
    network_submitted: bool = False
    verification_sha256d_evaluations: int = 0
    @property
    def total_sha256d_evaluations(self): return self.sha256d_evaluations + self.verification_sha256d_evaluations
class GoldenRatioMining:
    def prioritize(self, candidates):
        from .search import GoldenQuantumComputer
        return GoldenQuantumComputer().prioritize(candidates)
    def scan(self, header_prefix, target, lease, order=(), max_evaluations=65536, current_epoch=None, deadline=None):
        if not isinstance(header_prefix, bytes) or len(header_prefix) != 76: raise ValueError("76-byte header prefix required")
        Oracle.accepts(bytes(32), target)
        if type(max_evaluations) is not int or not 0 <= max_evaluations <= 1000000: raise ValueError("bounded hash budget required")
        if current_epoch is not None and current_epoch != lease.epoch: raise ValueError("stale lease")
        if deadline is not None and not math.isfinite(deadline): raise ValueError("finite monotonic deadline required")
        priority = list(order)
        if len(priority) > max_evaluations or len(priority) != len(set(priority)) or any(type(n) is not int or not lease.start <= n < lease.stop for n in priority):
            raise ValueError("advice must be unique, bounded, and within the unchanged lease")
        def candidates():
            yield from priority
            seen = set(priority)
            for n in range(lease.start, lease.stop):
                if n not in seen: yield n
        start = time.perf_counter(); count = 0; found = None; digest = None
        for nonce in candidates():
            if count >= max_evaluations or (deadline is not None and time.perf_counter() >= deadline): break
            value = Oracle.nonce_digest(header_prefix, nonce); count += 1
            if Oracle.accepts(value, target): found = nonce; digest = value.hex(); break
        elapsed = time.perf_counter()-start
        return MiningResult(found, digest, found is not None, count, elapsed, count/elapsed if elapsed else 0,
                            "cpu_reference", ("priority", "F3_classical_remainder") if priority else ("F3_classical",))
