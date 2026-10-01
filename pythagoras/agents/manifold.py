"""PYTHAGORAS v12 shared 11-dimensional coordination manifold.

The manifold is a coordination/state projection surface. Values are derived
from supplied execution data; it does not manufacture Mining telemetry.
"""

from __future__ import annotations

import math
import time
from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class AgentID(str, Enum):
    EUCLID = "EUCLID_REPO_INTELLIGENCE"
    SALAMANDER = "SALAMANDER_SELF_HEALER"
    AL_HARAS = "AL_HARAS_SECURITY_GUARD"
    PYTHIA = "PYTHIA_SEARCH_ORACLE"


class PayloadType(str, Enum):
    DIRECTIVE = "EUCLID_DIRECTIVE"
    OPTIMIZATION = "SALAMANDER_OPTIMIZATION"
    SECURITY_AUDIT = "AL_HARAS_AUDIT"
    SEARCH_STRATEGY = "PYTHIA_ORACLE_STRATEGY"


@dataclass
class DodecahedronIcosahedron11DOverlay:
    dimensions: int = 11
    dodecahedron_vertices: int = 20
    icosahedron_vertices: int = 12
    dual_symmetry_coherence: Optional[float] = None

    def project_11d_coordinates(self, agent_id: str, phi_score: float) -> List[float]:
        """Project a measured structural score into the shared 11D coordinate basis."""
        del agent_id
        golden_ratio = (1.0 + math.sqrt(5.0)) / 2.0
        return [
            round(
                math.sin(float(phi_score) * index * golden_ratio)
                * math.cos(index / golden_ratio),
                6,
            )
            for index in range(1, self.dimensions + 1)
        ]


@dataclass
class AgentMessage:
    sender: AgentID
    payload_type: PayloadType
    payload: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)


class SharedEntangledManifold:
    """In-process state/message surface shared by the v12 agents."""

    def __init__(self) -> None:
        self.overlay_11d = DodecahedronIcosahedron11DOverlay()
        self.message_bus: List[AgentMessage] = []
        self.agent_11d_states: Dict[str, List[float]] = {}
        self.topological_mapped_files: List[str] = []
        self.active_search_strategies: Dict[str, Any] = {}
        self.security_audit_log: List[Any] = []
        self.optimization_records: List[Any] = []

    def broadcast(
        self,
        sender: AgentID,
        payload_type: PayloadType,
        payload_obj: Any,
    ) -> AgentMessage:
        if is_dataclass(payload_obj):
            payload_dict = asdict(payload_obj)
        elif isinstance(payload_obj, dict):
            payload_dict = dict(payload_obj)
        else:
            raise TypeError("payload_obj must be a dataclass instance or dict")

        message = AgentMessage(
            sender=sender,
            payload_type=payload_type,
            payload=payload_dict,
        )
        self.message_bus.append(message)

        phi_ref = payload_dict.get(
            "optimized_phi",
            payload_dict.get("initial_phi", payload_dict.get("phi_score", 0.0)),
        )
        try:
            phi_value = float(phi_ref)
        except (TypeError, ValueError):
            phi_value = 0.0
        self.agent_11d_states[sender.value] = self.overlay_11d.project_11d_coordinates(
            sender.value,
            phi_value,
        )

        if payload_type == PayloadType.DIRECTIVE:
            target = payload_dict.get("target_file")
            if target and target not in self.topological_mapped_files:
                self.topological_mapped_files.append(str(target))
        elif payload_type == PayloadType.SECURITY_AUDIT:
            self.security_audit_log.append(payload_dict)
        elif payload_type == PayloadType.OPTIMIZATION:
            self.optimization_records.append(payload_dict)
        elif payload_type == PayloadType.SEARCH_STRATEGY:
            search_id = str(payload_dict.get("search_space_id", "default_search_space"))
            self.active_search_strategies[search_id] = payload_dict

        return message

    def get_snapshot(self) -> Dict[str, Any]:
        return {
            "manifold_geometry": "11D Dodecahedron-Icosahedron Dual Platonic Overlay",
            "spatial_dimensions": self.overlay_11d.dimensions,
            "dodecahedron_nodes": self.overlay_11d.dodecahedron_vertices,
            "icosahedron_nodes": self.overlay_11d.icosahedron_vertices,
            "dual_symmetry_coherence": self.overlay_11d.dual_symmetry_coherence,
            "dual_symmetry_coherence_source": "not_measured",
            "agent_11d_projections": dict(self.agent_11d_states),
            "topological_mapped_files_count": len(self.topological_mapped_files),
            "active_search_strategies_count": len(self.active_search_strategies),
            "security_audits_count": len(self.security_audit_log),
            "optimization_records_count": len(self.optimization_records),
            "total_entanglement_events": len(self.message_bus),
        }
