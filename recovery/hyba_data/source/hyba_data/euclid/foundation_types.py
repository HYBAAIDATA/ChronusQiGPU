"""Minimal types stub for simulation and schema_negotiation imports."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Set, Tuple, Optional
import hashlib, hmac, json, time, random

class VetoCategory(Enum):
    CONFIDENCE_FAILURE = "confidence_failure"
    COHERENCE_FAILURE = "coherence_failure"
    TRUTH_FAILURE = "truth_failure"
    CAUSAL_FAILURE = "causal_failure"
    FEEDBACK_FAILURE = "feedback_failure"
    NO_CANDIDATES = "no_candidates"

class IOPMessageType(Enum):
    NEGOTIATE = "negotiate"
    DISPATCH = "dispatch"
    RESOLVE = "resolve"
    VETO = "veto"
    ADVERTISE = "advertise"
    ACKNOWLEDGE = "acknowledge"

class IOPState(Enum):
    PROPOSED = "proposed"; ACTIVE = "active"; RUNNING = "running"
    COMPLETED = "completed"; BREACHED = "breached"; TERMINATED = "terminated"

_TRANS = {
    IOPState.PROPOSED: {IOPState.ACTIVE, IOPState.TERMINATED},
    IOPState.ACTIVE: {IOPState.RUNNING, IOPState.TERMINATED},
    IOPState.RUNNING: {IOPState.COMPLETED, IOPState.BREACHED, IOPState.TERMINATED},
}

@dataclass
class IOPExecutionTracker:
    state: IOPState = IOPState.PROPOSED
    events: List[Dict[str, Any]] = field(default_factory=list)
    start_time: float = 0.0
    def transition(self, to, reason=""):
        if to not in _TRANS.get(self.state, set()):
            return (False, f"Bad: {self.state.value}->{to.value}")
        self.state = to
        if to == IOPState.RUNNING: self.start_time = time.time()
        self.events.append({"from": self.state.value, "to": to.value, "reason": reason})
        return (True, f"ok")
    def has_timed_out(self, max_lat):
        return self.start_time > 0 and (time.time() - self.start_time) > max_lat

@dataclass
class IOPEnvelope:
    message_id: str = ""; sender_id: str = ""; receiver_id: str = ""
    message_type: IOPMessageType = IOPMessageType.DISPATCH
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time); signature: str = ""
    def serialize(self):
        ps = json.dumps(self.payload, sort_keys=True, default=str)
        return f"{self.message_id}:{self.sender_id}:{self.receiver_id}:{self.message_type.value}:{ps}:{self.timestamp}"
    def sign(self, secret):
        self.signature = hmac.new(secret.encode(), self.serialize().encode(), hashlib.sha256).hexdigest()
    def verify(self, secret):
        e = hmac.new(secret.encode(), self.serialize().encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(self.signature, e)

class TelemetryConsensusEngine:
    def __init__(self, threshold=0.67):
        self.threshold = threshold; self.peer_reputations: Dict[str, float] = {}; self.peer_secrets: Dict[str, str] = {}
    def register_peer(self, pid, secret, rep=0.7):
        self.peer_secrets[pid] = secret; self.peer_reputations[pid] = rep
    def resolve_state(self, key, claims):
        valid, tw = [], 0.0
        for c in claims:
            pid = c.get("peer_id", ""); s = self.peer_secrets.get(pid)
            if not s: continue
            p = f"{key}:{str(c.get('observed_value',''))}:{c.get('timestamp',0)}"
            e = hmac.new(s.encode(), p.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(str(c.get('signature','')), e): continue
            w = self.peer_reputations.get(pid, 0.0)
            if w > 0.3: valid.append((pid, c["observed_value"], w)); tw += w
        if not valid: return (False, None, "No valid claims.")
        g: Dict[str, Tuple[Any, float]] = {}
        for pid, v, w in valid:
            kk = str(v); g[kk] = (v, g[kk][1] + w) if kk in g else (v, w)
        bk = max(g, key=lambda kk: g[kk][1])
        wv, ww = g[bk]; r = ww / tw if tw > 0 else 0
        if r < self.threshold: return (False, wv, f"No consensus: {r:.3f}<{self.threshold}")
        return (True, wv, f"Consensus: {r:.3f}")

class SimpleIOPRouter:
    def __init__(self, oid, secret="test"):
        self.oid = oid; self.secret = secret; self.peers: Dict[str, str] = {}; self._log: List[str] = []
    def register_peer(self, pid, sec): self.peers[pid] = sec
    def handle_inbound_envelope(self, env):
        s = self.peers.get(env.sender_id, "")
        if not s or not env.verify(s): return IOPEnvelope(message_id=f"v_{env.message_id}", sender_id=self.oid, receiver_id=env.sender_id, message_type=IOPMessageType.VETO, payload={"reason":"Bad sig"})
        self._log.append(f"rx:{env.sender_id}:{env.message_type.value}")
        if env.message_type == IOPMessageType.DISPATCH:
            return IOPEnvelope(message_id=f"r_{env.message_id}", sender_id=self.oid, receiver_id=env.sender_id, message_type=IOPMessageType.RESOLVE, payload={"task_id": env.payload.get("task_id"), "status": "accepted"})
        return None

@dataclass
class NetworkLinkProfile:
    latency_sec: float = 0.0; packet_loss_rate: float = 0.0; partition_id: int = 1
