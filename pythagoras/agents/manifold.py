"""
PYTHAGORAS 11D Entangled Manifold Architecture
===============================================
Dodecahedron–Icosahedron dual Platonic overlay over an 11-dimensional state space.
Integrates EUCLID, SALAMANDER, AL HARAS and PYTHIA.

v12.1: every coordinate is a measured property of the code (all in [0, 1]):
    0 phi_score                  5 function_balance           10 audit_clearance (AL HARAS)
    1 golden_growth_resonance    6 integrity
    2 annotation_coherence       7 lucas_x_normalised  x/(1+x)
    3 depth_balance              8 lucas_lock (Pisot proximity)
    4 complexity_balance         9 integration (λ₂/n, Tononi substrate)

Dual symmetry coherence is measured: the 11D state is projected to 3D along eleven
icosahedral vertex directions (after centring at 0.5), and coherence is the mean of
its best cosine alignment with the icosahedron's 12 vertices and the dodecahedron's
20 vertices (the dodecahedron's vertices sit at the icosahedron's 20 face centres).
"""
import itertools
import math
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

PHI = (1.0 + math.sqrt(5.0)) / 2.0

STATE_AXES = [
    "phi_score", "golden_growth_resonance", "annotation_coherence", "depth_balance",
    "complexity_balance", "function_balance", "integrity", "lucas_x_normalised",
    "lucas_lock", "integration", "audit_clearance",
]


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


def _unit(v):
    n = math.sqrt(sum(x * x for x in v))
    return [x / n for x in v]


def _cyclic(v):
    a, b, c = v
    return [(a, b, c), (c, a, b), (b, c, a)]


def _icosahedron() -> List[List[float]]:
    pts = set()
    for s1, s2 in itertools.product((1, -1), repeat=2):
        for p in _cyclic((0.0, s1 * 1.0, s2 * PHI)):
            pts.add(p)
    return [_unit(p) for p in sorted(pts)]


def _dodecahedron() -> List[List[float]]:
    pts = set(itertools.product((1.0, -1.0), repeat=3))
    for s1, s2 in itertools.product((1, -1), repeat=2):
        for p in _cyclic((0.0, s1 / PHI, s2 * PHI)):
            pts.add(p)
    return [_unit(p) for p in sorted(pts)]


ICOSAHEDRON = _icosahedron()    # 12 vertices
DODECAHEDRON = _dodecahedron()  # 20 vertices
assert len(ICOSAHEDRON) == 12 and len(DODECAHEDRON) == 20


@dataclass
class DodecahedronIcosahedron11DOverlay:
    dimensions: int = 11
    dodecahedron_vertices: int = 20
    icosahedron_vertices: int = 12

    def project_11d_coordinates(self, agent_id: str, phi_score: float,
                                state_vector: Optional[List[float]] = None) -> List[float]:
        """Returns the measured 11D state. Without a state vector only the φ axis is known;
        the remaining axes are reported as 0.0 rather than synthesised."""
        if state_vector is not None:
            if len(state_vector) != 11:
                raise ValueError("state_vector must have 11 components")
            return [round(float(x), 6) for x in state_vector]
        return [round(float(phi_score), 6)] + [0.0] * 10

    def project_3d(self, state: List[float]) -> List[float]:
        centred = [x - 0.5 for x in state]
        return [sum(c * ICOSAHEDRON[i][k] for i, c in enumerate(centred)) for k in range(3)]

    def dual_coherence(self, state: List[float]) -> Optional[float]:
        p = self.project_3d(state)
        norm = math.sqrt(sum(x * x for x in p))
        if norm < 1e-12:
            return None
        u = [x / norm for x in p]
        ico = max(sum(a * b for a, b in zip(u, v)) for v in ICOSAHEDRON)
        dod = max(sum(a * b for a, b in zip(u, v)) for v in DODECAHEDRON)
        return round((ico + dod) / 2.0, 6)


@dataclass
class AgentMessage:
    sender: AgentID
    payload_type: PayloadType
    payload: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)


class SharedEntangledManifold:
    def __init__(self):
        self.overlay_11d = DodecahedronIcosahedron11DOverlay()
        self.message_bus: List[AgentMessage] = []
        self.agent_11d_states: Dict[str, List[float]] = {}
        self.topological_mapped_files: List[str] = []
        self.active_search_strategies: Dict[str, Any] = {}
        self.security_audit_log: List[Any] = []
        self.optimization_records: List[Any] = []

    def broadcast(self, sender: AgentID, payload_type: PayloadType, payload_obj: Any):
        payload_dict = asdict(payload_obj) if hasattr(payload_obj, "__dataclass_fields__") else payload_obj
        self.message_bus.append(AgentMessage(sender=sender, payload_type=payload_type, payload=payload_dict))

        state = payload_dict.get("state_11d")
        phi_ref = payload_dict.get("optimized_phi", payload_dict.get("initial_phi"))
        if state is not None or phi_ref is not None:
            self.agent_11d_states[sender.value] = self.overlay_11d.project_11d_coordinates(
                sender.value, phi_ref or 0.0, state)

        if payload_type == PayloadType.DIRECTIVE:
            f = payload_dict.get("target_file")
            if f and f not in self.topological_mapped_files:
                self.topological_mapped_files.append(f)
        elif payload_type == PayloadType.SECURITY_AUDIT:
            self.security_audit_log.append(payload_dict)
        elif payload_type == PayloadType.OPTIMIZATION:
            self.optimization_records.append(payload_dict)
        elif payload_type == PayloadType.SEARCH_STRATEGY:
            self.active_search_strategies[payload_dict.get("search_space_id", "default_search_space")] = payload_dict

    def measured_dual_coherence(self) -> Optional[float]:
        vals = [self.overlay_11d.dual_coherence(s) for s in self.agent_11d_states.values()]
        vals = [v for v in vals if v is not None]
        return round(sum(vals) / len(vals), 6) if vals else None

    def get_snapshot(self) -> Dict[str, Any]:
        return {
            "manifold_geometry": "11D Dodecahedron-Icosahedron Dual Platonic Overlay",
            "spatial_dimensions": 11,
            "state_axes": STATE_AXES,
            "dodecahedron_nodes": 20,
            "icosahedron_faces": 20,
            "dual_symmetry_coherence": self.measured_dual_coherence(),
            "agent_11d_projections": self.agent_11d_states,
            "topological_mapped_files_count": len(self.topological_mapped_files),
            "active_search_strategies_count": len(self.active_search_strategies),
            "security_audits_count": len(self.security_audit_log),
            "total_entanglement_events": len(self.message_bus),
        }
