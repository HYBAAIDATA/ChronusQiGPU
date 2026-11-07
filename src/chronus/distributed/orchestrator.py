"""Cluster Orchestrator for Chronus Distributed Systems."""

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class ClusterState(str, Enum):
    INITIALIZING = "INITIALIZING"
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    RECOVERING = "RECOVERING"
    MAINTENANCE = "MAINTENANCE"
    CRITICAL = "CRITICAL"


@dataclass
class NodeInfo:
    node_id: str
    hostname: str
    region: str
    status: str = "ACTIVE"
    last_heartbeat: Optional[datetime] = None
    workloads_assigned: int = 0
    capacity: int = 100
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "hostname": self.hostname,
            "region": self.region,
            "status": self.status,
            "last_heartbeat": (
                self.last_heartbeat.isoformat() if self.last_heartbeat else None
            ),
            "workloads_assigned": self.workloads_assigned,
            "capacity": self.capacity,
            "metadata": self.metadata,
        }


@dataclass
class WorkloadAssignment:
    workload_id: str
    node_id: str
    assigned_at: datetime = field(default_factory=datetime.utcnow)
    status: str = "ASSIGNED"
    result: Optional[Dict[str, Any]] = None


class ClusterOrchestrator:
    def __init__(self, cluster_size: int = 72) -> None:
        self.cluster_size = cluster_size
        self._nodes: Dict[str, NodeInfo] = {}
        self._workloads: Dict[str, WorkloadAssignment] = {}
        self._cluster_state = ClusterState.INITIALIZING
        self._scheduler_algorithm = "round_robin"
    def assign_workload(
        self, workload_id: str, preferred_region: Optional[str] = None
    ) -> Optional[str]:
        active_nodes = [
            n for n in self._nodes.values() if n.status == "ACTIVE"
        ]

        if not active_nodes:
            return None

        if preferred_region:
            region_nodes = [n for n in active_nodes if n.region == preferred_region]
            if region_nodes:
                active_nodes = region_nodes

        selected_node = min(active_nodes, key=lambda n: n.workloads_assigned)

        if selected_node.workloads_assigned >= selected_node.capacity:
            available = [
                n
                for n in active_nodes
                if n.workloads_assigned < n.capacity
            ]
            if not available:
                return None
            selected_node = min(available, key=lambda n: n.workloads_assigned)

        selected_node.workloads_assigned += 1
        assignment = WorkloadAssignment(
            workload_id=workload_id,
            node_id=selected_node.node_id,
        )
        self._workloads[workload_id] = assignment
        self._total_workloads += 1

        return selected_node.node_id

    def complete_workload(
        self, workload_id: str, result: Optional[Dict[str, Any]] = None
    ) -> bool:
        if workload_id not in self._workloads:
            return False

        assignment = self._workloads[workload_id]
        assignment.status = "COMPLETED"
        assignment.result = result

        node = self._nodes.get(assignment.node_id)
        if node and node.workloads_assigned > 0:
            node.workloads_assigned -= 1

        self._completed_workloads += 1
        return True

    def fail_workload(self, workload_id: str) -> bool:
        if workload_id not in self._workloads:
            return False

        assignment = self._workloads[workload_id]
        assignment.status = "FAILED"

        node = self._nodes.get(assignment.node_id)
        if node and node.workloads_assigned > 0:
            node.workloads_assigned -= 1

        self._failed_workloads += 1
        return True

    def get_node(self, node_id: str) -> Optional[NodeInfo]:
        return self._nodes.get(node_id)

    def get_all_nodes(self) -> List[NodeInfo]:
        return list(self._nodes.values())

    def get_workload_assignment(self, workload_id: str) -> Optional[WorkloadAssignment]:
        return self._workloads.get(workload_id)

    def get_cluster_state(self) -> ClusterState:
        return self._cluster_state

    def get_stats(self) -> Dict[str, Any]:
        active_nodes = sum(
            1 for n in self._nodes.values() if n.status == "ACTIVE"
        )
        return {
            "cluster_state": self._cluster_state.value,
            "cluster_size": self.cluster_size,
            "active_nodes": active_nodes,
            "total_nodes": len(self._nodes),
            "total_workloads": self._total_workloads,
            "completed_workloads": self._completed_workloads,
            "failed_workloads": self._failed_workloads,
            "scheduler_algorithm": self._scheduler_algorithm,
            "failover_enabled": self._failover_enabled,
        }


class ConsensusProtocol:
    def __init__(self, quorum_size: int = 3) -> None:
        self.quorum_size = quorum_size
        self._proposals: Dict[str, Dict[str, Any]] = {}
        self._votes: Dict[str, Dict[str, bool]] = {}
        self._decided: Dict[str, bool] = {}

    def propose(
        self, proposal_id: str, proposal: Dict[str, Any], proposer: str
    ) -> bool:
        if proposal_id in self._proposals:
            return False

        self._proposals[proposal_id] = {
            "proposal": proposal,
            "proposer": proposer,
            "created_at": time.time(),
        }
        self._votes[proposal_id] = {}
        self._decided[proposal_id] = False
        return True

    def vote(
        self, proposal_id: str, voter: str, approve: bool
    ) -> bool:
        if proposal_id not in self._proposals:
            return False
        if self._decided.get(proposal_id, False):
            return False

        self._votes[proposal_id][voter] = approve

        votes = self._votes[proposal_id]
        approve_count = sum(1 for v in votes.values() if v)
        total_votes = len(votes)

        if approve_count >= self.quorum_size:
            self._decided[proposal_id] = True
        elif total_votes - approve_count >= self.quorum_size:
            self._decided[proposal_id] = True

        return True

    def is_decided(self, proposal_id: str) -> bool:
        return self._decided.get(proposal_id, False)

    def get_proposal_result(self, proposal_id: str) -> Optional[bool]:
        if not self._decided.get(proposal_id, False):
            return None

        votes = self._votes.get(proposal_id, {})
        approve_count = sum(1 for v in votes.values() if v)
        return approve_count >= self.quorum_size
        self._failover_enabled = True
        self._total_workloads = 0
        self._completed_workloads = 0
        self._failed_workloads = 0

    def register_node(
        self, hostname: str, region: str, capacity: int = 100
    ) -> str:
        node_id = f"node-{uuid.uuid4().hex[:8]}"
        node = NodeInfo(
            node_id=node_id,
            hostname=hostname,
            region=region,
            capacity=capacity,
            last_heartbeat=datetime.utcnow(),
        )
        self._nodes[node_id] = node

        if len(self._nodes) >= self.cluster_size:
            self._cluster_state = ClusterState.HEALTHY
        elif len(self._nodes) > 0:
            self._cluster_state = ClusterState.DEGRADED

        return node_id

    def heartbeat(self, node_id: str) -> bool:
        if node_id not in self._nodes:
            return False

        self._nodes[node_id].last_heartbeat = datetime.utcnow()
        self._nodes[node_id].status = "ACTIVE"
        return True