"""Minimal stubs for staging cluster — self-contained, no euclid deps."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Set, Tuple, Optional
import random, math, time

PHI_I = 0.618034

@dataclass
class NetworkLinkProfile:
    latency_sec: float = 0.0; packet_loss_rate: float = 0.0; partition_id: int = 1

class ProbationaryRecoveryManager:
    def __init__(self, reputations: Dict[str, float], active_threshold: float = 0.3):
        self.reputations = reputations
        self.active_threshold = active_threshold
        self.probation_progress: Dict[str, int] = {}
        self.suspended: Set[str] = set()

class SimulatedNetwork:
    def __init__(self):
        self.nodes: Dict[str, Any] = {}
        self.topology: Dict[Tuple[str, str], NetworkLinkProfile] = {}
        self.node_partitions: Dict[str, int] = {}

    def register_node(self, peer_id, node, partition_id=1):
        self.nodes[peer_id] = node; self.node_partitions[peer_id] = partition_id

    def set_link_profile(self, sender, receiver, profile):
        self.topology[(sender, receiver)] = profile
        self.topology[(receiver, sender)] = profile
