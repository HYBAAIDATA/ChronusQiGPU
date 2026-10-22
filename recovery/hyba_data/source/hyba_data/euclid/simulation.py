"""Byzantine and Partition Simulation Harness. 19 July 2026."""
from __future__ import annotations
import random, time, hashlib, hmac
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass, field
from euclid.foundation_types import (
    NetworkLinkProfile, IOPEnvelope, IOPMessageType, IOPState,
    IOPExecutionTracker, SimpleIOPRouter, TelemetryConsensusEngine,
)


class SimulatedNetwork:
    def __init__(self):
        self.nodes: Dict[str, Any] = {}
        self.topology: Dict[Tuple[str, str], NetworkLinkProfile] = {}
        self.node_partitions: Dict[str, int] = {}
        self.transmission_log: List[Dict[str, Any]] = []

    def register_node(self, peer_id: str, node_instance: Any, partition_id: int = 1):
        self.nodes[peer_id] = node_instance
        self.node_partitions[peer_id] = partition_id

    def set_link_profile(self, sender: str, receiver: str, profile: NetworkLinkProfile):
        self.topology[(sender, receiver)] = profile
        self.topology[(receiver, sender)] = profile

    def isolate_node(self, node_id: str, new_partition: int):
        self.node_partitions[node_id] = new_partition

    def transmit(self, envelope: IOPEnvelope) -> Tuple[bool, str, Optional[IOPEnvelope]]:
        sender, receiver = envelope.sender_id, envelope.receiver_id
        sp = self.node_partitions.get(sender, 1)
        rp = self.node_partitions.get(receiver, 1)
        if sp != rp:
            self._log(sender, receiver, False, "PARTITION_BLOCK")
            return (False, "TRANSMISSION_FAILED: Network partition block.", None)
        link = self.topology.get((sender, receiver), NetworkLinkProfile())
        if random.random() < link.packet_loss_rate:
            self._log(sender, receiver, False, "PACKET_DROPPED")
            return (False, "TRANSMISSION_FAILED: Packet dropped.", None)
        if link.latency_sec > 0.0:
            time.sleep(min(link.latency_sec, 0.05))
        router = self.nodes.get(receiver)
        if not router:
            self._log(sender, receiver, False, "NODE_OFFLINE")
            return (False, "TRANSMISSION_FAILED: Target offline.", None)
        response = router.handle_inbound_envelope(envelope)
        self._log(sender, receiver, True, "DELIVERED")
        return (True, "TRANSMISSION_SUCCESS", response)

    def _log(self, s, r, ok, reason):
        self.transmission_log.append({"sender": s, "receiver": r, "ok": ok, "reason": reason, "ts": time.time()})


class ByzantineNodeProxy:
    def __init__(self, peer_id: str, peer_secret: str = "byzantine"):
        self.peer_id = peer_id; self.peer_secret = peer_secret

    def generate_byzantine_telemetry(self, key: str, value: Any) -> Any:
        if isinstance(value, (int, float)): return value * 10.0
        return f"CORRUPTED_{value}"

    def sign_forged_claim(self, key: str, value: Any) -> Dict[str, Any]:
        corrupted = self.generate_byzantine_telemetry(key, value)
        ts = time.time()
        p = f"{key}:{str(corrupted)}:{ts}"
        sig = hmac.new(self.peer_secret.encode(), p.encode(), hashlib.sha256).hexdigest()
        return {"peer_id": self.peer_id, "observed_value": corrupted, "timestamp": ts, "signature": sig}

    def sign_honest_claim(self, key: str, value: Any) -> Dict[str, Any]:
        ts = time.time()
        p = f"{key}:{str(value)}:{ts}"
        sig = hmac.new(self.peer_secret.encode(), p.encode(), hashlib.sha256).hexdigest()
        return {"peer_id": self.peer_id, "observed_value": value, "timestamp": ts, "signature": sig}
