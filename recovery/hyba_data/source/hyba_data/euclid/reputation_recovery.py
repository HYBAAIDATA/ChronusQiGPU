"""Reputation Recovery — Probationary Recovery Path. 19 July 2026."""
from typing import Dict, Set, Tuple

PHI_I = 0.618034

class ProbationaryRecoveryManager:
    def __init__(self, peer_reputations: Dict[str, float], active_threshold: float = 0.3):
        self.peer_reputations = peer_reputations
        self.active_threshold = active_threshold
        self.probation_progress: Dict[str, int] = {}
        self.suspended_nodes: Set[str] = set()

    def evaluate_node_health(self, peer_id: str) -> str:
        if peer_id in self.suspended_nodes:
            return "SUSPENDED"
        if self.peer_reputations.get(peer_id, 0.5) < self.active_threshold:
            return "PROBATIONARY"
        return "HEALTHY"

    def initiate_probation(self, peer_id: str, required_tests: int = 3) -> bool:
        if peer_id in self.suspended_nodes:
            return False
        if self.peer_reputations.get(peer_id, 0.5) >= self.active_threshold:
            return False
        self.probation_progress[peer_id] = required_tests
        return True

    def record_test_result(self, peer_id: str, success: bool) -> Tuple[str, float]:
        cr = self.peer_reputations.get(peer_id, 0.0)
        if not success:
            nr = max(0.0, cr - 0.40)
            self.peer_reputations[peer_id] = nr
            self.suspended_nodes.add(peer_id)
            self.probation_progress.pop(peer_id, None)
            return ("SUSPENDED", nr)
        nr = min(1.0, cr + 0.05 * PHI_I)
        self.peer_reputations[peer_id] = nr
        if peer_id in self.probation_progress:
            self.probation_progress[peer_id] -= 1
            r = self.probation_progress[peer_id]
            if r <= 0 and nr >= self.active_threshold:
                self.probation_progress.pop(peer_id, None)
                return ("HEALTHY", nr)
            return ("PROBATIONARY", nr)
        return ("PROBATIONARY", nr)
