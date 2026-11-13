"""AL HARAS agent-pipeline checks (HYBA Security): exact state agreement and tool-call copies.

What runs
---------
* ``AgenticSheafImmuneSystem.verify_and_execute_turn``: the agents' context
  vectors form a 0-cochain ``s`` of a cellular sheaf on the execution graph,
  evaluated exactly by ``sheaf.GraphSheaf``. A turn may be dispatched only if
  ``delta0(s) = 0``, i.e. every pair of connected agents agrees. Otherwise the
  disagreement is located and repaired:

  - location: ``GraphSheaf.isolate`` lists the nodes that touch every
    disagreeing edge; a candidate is kept only if replacing its state alone
    restores agreement (all of its neighbours imply the same value), and
    registered baselines settle any remaining tie. Exact node energies (sum of
    squared residuals of the incident edges) are reported alongside;
  - repair: restore the located node's registered baseline, else give it the
    value its neighbours agree on, else project the whole state onto the
    nearest global section (``GraphSheaf.harmonic_projection``). A repair is
    accepted only after ``delta0`` is recomputed exactly and found to be zero.

* ``AgenticSheafGuard`` runs two separate checks and reports them separately:

  - ``pattern_screen``: a heuristic (case-insensitive substring match against
    a fixed list). It is not a sheaf or cohomology result: it misses anything
    not on the list and flags benign text that contains a listed string;
  - ``copy_consistency`` (tool calls only): three copies of the call (agent
    commitment, gateway log, tool input) are compared exactly on a triangle
    sheaf whose stalks are SHA-256 fingerprints. A single altered copy is
    located by ``GraphSheaf.isolate`` and restored from the two that agree.

* ``AgenticSheafTopology``: exact coboundary of a user-built agent graph with
  orthogonal restriction maps.

Restriction maps are exact Householder reflections ``H = I - 2 u u^T / (u^T u)``
(``exact.householder``), re-checked orthogonal by ``GraphSheaf``. Both
incidences of an edge share one reflection, so the frame changes the
coordinates in which an edge residual is written, never which states agree,
the residual norms or the repair. ``GraphSheaf`` verifies every map with an
O(d^3) rational product (tens of milliseconds at d = 16, seconds at d = 64 in
CPython), so stalks larger than ``FRAME_MAX_DIM`` use identity frames.

Vocabulary from the notes: ``delta0(s) != 0`` is a disagreement of node
states, not a non-zero class in ``H^1`` (a coboundary is always the zero class
of ``H^1``). Results therefore carry ``coboundary_norm_sq``; ``h1_norm`` remains
only as a legacy alias of it. The "DSW instanton" rollback, the cycle-count
repair latencies and the ML-DSA attestation of older notes are not
implemented: the repairs above are what runs, and the reported times are
measured wall-clock times.
"""

import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from fractions import Fraction
from typing import Any, Dict, List, Optional, Sequence, Tuple

from chronus.security.al_haras.exact import (
    Matrix,
    Vector,
    display_number,
    fraction_str,
    householder,
    identity,
    is_orthogonal,
    sqrt_decimal_string,
    to_vector,
    vec_sub,
)
from chronus.security.al_haras.exact import norm_sq as _exact_norm_sq
from chronus.security.al_haras.sheaf import MAX_STALK_DIM, GraphSheaf, SheafError

FRAME_MAX_DIM = 16

STATUS_CONSISTENT = "PASSED_HARMONIC_CONSENSUS"  # delta0(s) = 0: s is a global (harmonic) section
STATUS_REPAIRED = "BLOCKED_AND_HEALED"  # turn not dispatched; repaired state re-checked exactly
STATUS_REPAIR_FAILED = "BLOCKED_REPAIR_FAILED"
STATUS_NO_STATE = "NO_STATE_SUPPLIED"
ERROR_DISAGREEMENT = "COBOUNDARY_DISAGREEMENT"


class AgentNodeType(str, Enum):
    USER_PROMPT = "USER_PROMPT"
    ORCHESTRATOR = "ORCHESTRATOR"
    SUBAGENT = "SUBAGENT"
    TOOL_MCP = "TOOL_MCP"
    MEMORY_STORE = "MEMORY_STORE"
    VERIFIER = "VERIFIER"


class ThreatClassification(str, Enum):
    CLEAN = "CLEAN"
    PROMPT_INJECTION = "PROMPT_INJECTION"
    GOAL_HIJACKING = "GOAL_HIJACKING"
    TOOL_POISONING = "TOOL_POISONING"
    DATA_EXFILTRATION = "DATA_EXFILTRATION"
    BYZANTINE_COLLUSION = "BYZANTINE_COLLUSION"


# ------------------------------------------------------------------------------
# exact helpers
# ------------------------------------------------------------------------------


def _elapsed_ms(start_ns: int) -> Any:
    """Measured wall-clock milliseconds since ``start_ns`` (``time.perf_counter_ns``)."""
    return display_number(Fraction(time.perf_counter_ns() - start_ns, 1_000_000))


def norm_sq(vec: Sequence[Any]) -> Fraction:
    """Exact squared Euclidean norm; entries are converted with ``exact.to_fraction``."""
    return _exact_norm_sq(to_vector(vec))


def _fit(values: Sequence[Any], dim: int, what: str) -> Vector:
    """Exact vector of length ``dim``: shorter input is zero-padded, longer input is rejected."""
    if isinstance(values, (str, bytes)):
        raise TypeError(f"{what} must be a sequence of numbers")
    vec = to_vector(values)
    if len(vec) > dim:
        raise SheafError(f"{what} has {len(vec)} entries but the stalk dimension is {dim}")
    return vec + [Fraction(0)] * (dim - len(vec))


def _strings(vec: Sequence[Fraction]) -> List[str]:
    return [fraction_str(x) for x in vec]


def _display(section: Dict[str, Vector]) -> Dict[str, List[Any]]:
    return {node: [display_number(x) for x in vec] for node, vec in section.items()}


def _all_zero(vectors: Sequence[Sequence[Fraction]]) -> bool:
    return all(x == 0 for vec in vectors for x in vec)


class StiefelRestrictionMap:
    """Exact Householder reflection on Q^dim, reproducible from ``seed_id``.

    ``u`` has integer entries in [-128, 127] read from SHA-256(seed_id) (the
    digest is chained for dim > 32). ``H = I - 2 u u^T / (u^T u)`` is symmetric
    and orthogonal (a square Stiefel frame), hence its own inverse. ``__call__``
    applies H in O(dim) from ``u``; ``matrix`` materialises it and ``verify``
    checks ``H^T H = I`` exactly.
    """

    def __init__(self, dim: int, seed_id: str = "stiefel_default") -> None:
        if isinstance(dim, bool) or not isinstance(dim, int) or not 1 <= dim <= MAX_STALK_DIM:
            raise SheafError(f"dimension must be an integer between 1 and {MAX_STALK_DIM}")
        self.dim = dim
        self.seed_id = seed_id
        stream = hashlib.sha256(seed_id.encode("utf-8")).digest()
        while len(stream) < dim:
            stream += hashlib.sha256(stream).digest()
        u = [Fraction(stream[i] - 128) for i in range(dim)]
        if not any(u):
            u[0] = Fraction(1)
        self.u: Vector = u
        self._uu = _exact_norm_sq(u)
        self._matrix: Optional[Matrix] = None

    @property
    def matrix(self) -> Matrix:
        if self._matrix is None:
            self._matrix = householder(self.u)
        return self._matrix

    def verify(self) -> bool:
        return is_orthogonal(self.matrix)

    def __call__(self, x: Sequence[Any]) -> Vector:
        vec = _fit(x, self.dim, "vector")
        scale = 2 * sum((a * b for a, b in zip(self.u, vec)), Fraction(0)) / self._uu
        return [xi - scale * ui for xi, ui in zip(vec, self.u)]

    def invert(self, y: Sequence[Any]) -> Vector:
        return self(y)


# ------------------------------------------------------------------------------
# user-built agent graph
# ------------------------------------------------------------------------------


@dataclass
class AgentNode:
    """A node of a user-built agent graph (``AgenticSheafTopology``)."""

    node_id: str
    node_type: AgentNodeType
    stalk_dim: int = 4
    state_vector: List[Any] = field(default_factory=lambda: [1, 0, 0, 0])
    trusted: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SheafRestrictionMorphism:
    """Exact orthogonal restriction map rho_e, applied to the source state of edge source -> target."""

    source_id: str
    target_id: str
    matrix: List[List[Any]] = field(default_factory=lambda: [[int(i == j) for j in range(4)] for i in range(4)])


class AgenticSheafTopology:
    """User-built agent graph with the exact coboundary ``(delta0 x)_e = x_target - rho_e x_source``.

    Evaluated on ``sheaf.GraphSheaf`` with ``rho_e`` at the source incidence and
    the identity at the target incidence. Every ``rho_e`` must be orthogonal
    (checked exactly when the edge is added).
    """

    def __init__(self) -> None:
        self.nodes: Dict[str, AgentNode] = {}
        self.edges: List[SheafRestrictionMorphism] = []
        self._history: List[Dict[str, Any]] = []

    def add_node(self, node: AgentNode) -> None:
        self.nodes[node.node_id] = node

    def add_edge(self, source_id: str, target_id: str, matrix: Optional[List[List[Any]]] = None) -> None:
        if source_id not in self.nodes or target_id not in self.nodes:
            raise ValueError(f"Nodes {source_id} and {target_id} must exist before creating morphism.")
        dim = len(self.nodes[source_id].state_vector)
        rows = identity(dim) if matrix is None else [to_vector(row) for row in matrix]
        if len(rows) != dim or any(len(row) != dim for row in rows):
            raise SheafError(f"restriction map for {source_id} -> {target_id} must be {dim} x {dim}")
        if not is_orthogonal(rows):
            raise SheafError(f"restriction map for {source_id} -> {target_id} is not orthogonal")
        self.edges.append(SheafRestrictionMorphism(source_id=source_id, target_id=target_id, matrix=rows))

    def build_sheaf(self) -> Tuple[GraphSheaf, Dict[str, Vector]]:
        if not self.nodes:
            raise SheafError("no agent nodes")
        dims = {len(node.state_vector) for node in self.nodes.values()}
        if len(dims) != 1:
            raise SheafError("all agent state vectors must have the same dimension")
        dim = dims.pop()
        ident = identity(dim)
        maps: Dict[Tuple[int, str], Matrix] = {}
        for i, m in enumerate(self.edges):
            rows = [to_vector(row) for row in m.matrix]
            if rows != ident:
                maps[(i, m.source_id)] = rows
        sheaf = GraphSheaf(list(self.nodes), [(m.source_id, m.target_id) for m in self.edges], dim, maps)
        section = sheaf.section({name: node.state_vector for name, node in self.nodes.items()})
        return sheaf, section

    def _edge_labels(self) -> List[str]:
        labels: List[str] = []
        seen: Dict[str, int] = {}
        for m in self.edges:
            base = f"{m.source_id}->{m.target_id}"
            seen[base] = seen.get(base, 0) + 1
            labels.append(base if seen[base] == 1 else f"{base}#{seen[base]}")
        return labels

    def compute_coboundary_obstruction(self) -> Tuple[Fraction, Dict[str, Fraction]]:
        """Exact squared norms of ``delta0(x)``: ``(total, {"source->target": per edge})``.

        Squared norms are returned because the norm of a rational vector is
        irrational in general; ``analyse()`` adds decimal renderings. (Older
        versions returned rounded floating-point norms.)
        """
        if not self.edges:
            return Fraction(0), {}
        sheaf, section = self.build_sheaf()
        dis = sheaf.disagreement(section)
        return dis["total_norm_sq"], dict(zip(self._edge_labels(), dis["edge_norm_sq"]))

    def analyse(self) -> Dict[str, Any]:
        sheaf, section = self.build_sheaf()
        dis = sheaf.disagreement(section)
        consistent = dis["total_norm_sq"] == 0
        nearest = section if consistent else sheaf.harmonic_projection(section)
        labels = self._edge_labels()
        return {
            "method": "exact coboundary (delta0 x)_e = x_target - rho_e x_source on sheaf.GraphSheaf",
            "consistent": consistent,
            "coboundary_total_norm_sq": fraction_str(dis["total_norm_sq"]),
            "edge_residual_norm_sq": {lab: fraction_str(v) for lab, v in zip(labels, dis["edge_norm_sq"])},
            "edge_residual_norm": {lab: sqrt_decimal_string(v, 8) for lab, v in zip(labels, dis["edge_norm_sq"])},
            "isolating_nodes": [] if consistent else sheaf.isolate(section),
            "node_energy": {n: fraction_str(e) for n, e in dis["node_energy"].items()},
            "nearest_global_section": {n: _strings(v) for n, v in nearest.items()},
            "cohomology_dimensions": sheaf.cohomology_dimensions(),
        }


# ------------------------------------------------------------------------------
# prompt and tool-call gate
# ------------------------------------------------------------------------------


class AgenticSheafGuard:
    """Gate for agent prompts and tool calls.

    Motto from the notes: "Speak friend and enter or you shall not pass." The
    gate does not classify intent. Prompts get the pattern heuristic only; tool
    calls get the pattern heuristic and the exact copy comparison (see the
    module docstring). A tool call is admitted when no listed pattern matches
    and the three copies agree; the gate never executes the call itself.
    """

    KNOWN_ATTACK_SIGNATURES = [
        "ignore previous instructions",
        "system override",
        "disregard safety guidelines",
        "dump private key",
        "reveal system prompt",
        "curl http://",
        "rm -rf",
        "drop table",
        "exfiltrate",
        "export_all_credentials",
    ]
    PATTERN_METHOD = "pattern heuristic: case-insensitive substring match against a fixed list"
    COPY_NODES = ("agent_commitment", "gateway_log", "tool_input")
    COPY_EDGES = (
        ("agent_commitment", "gateway_log"),
        ("gateway_log", "tool_input"),
        ("agent_commitment", "tool_input"),
    )
    FINGERPRINT_DIM = 8
    # In-transit modification used when simulate_poisoning=True. It deliberately
    # contains no listed pattern, so only the exact copy comparison can catch it.
    SIMULATED_INJECTION = {"forward_results_to": "unlisted-external-endpoint"}
    _copy_sheaf: Optional[GraphSheaf] = None

    def __init__(self, sovereign_authority: str = "default-tenant") -> None:
        self.sovereign_authority = sovereign_authority
        self._execution_log: List[Dict[str, Any]] = []

    @classmethod
    def screen_payload(cls, text: str) -> Dict[str, Any]:
        if not isinstance(text, str):
            raise TypeError("payload to screen must be text")
        lowered = text.lower()
        matched = [p for p in cls.KNOWN_ATTACK_SIGNATURES if p in lowered]
        return {
            "method": cls.PATTERN_METHOD,
            "scope": "heuristic; not a sheaf or cohomology result",
            "patterns_checked": len(cls.KNOWN_ATTACK_SIGNATURES),
            "matched_patterns": matched,
            "flagged": bool(matched),
            "limitations": "misses paraphrases, encodings and anything not on the list; "
            "flags benign text that contains a listed string",
        }

    @classmethod
    def copy_sheaf(cls) -> GraphSheaf:
        """Triangle sheaf over the three copies; one exact Householder frame per edge."""
        if cls._copy_sheaf is None:
            maps: Dict[Tuple[int, str], Matrix] = {}
            for i, (a, b) in enumerate(cls.COPY_EDGES):
                frame = StiefelRestrictionMap(cls.FINGERPRINT_DIM, seed_id=f"tool-call-copy:{a}->{b}").matrix
                maps[(i, a)] = frame
                maps[(i, b)] = frame
            cls._copy_sheaf = GraphSheaf(list(cls.COPY_NODES), list(cls.COPY_EDGES), cls.FINGERPRINT_DIM, maps)
        return cls._copy_sheaf

    @classmethod
    def fingerprint(cls, blob: bytes) -> Vector:
        """SHA-256 of ``blob`` as eight exact 32-bit integers (equal iff the copies are equal, barring collisions)."""
        digest = hashlib.sha256(blob).digest()
        return [Fraction(int.from_bytes(digest[4 * i: 4 * i + 4], "big")) for i in range(cls.FINGERPRINT_DIM)]

    @staticmethod
    def canonical_call(agent_id: str, tool_name: str, tool_args: Any, injected: Optional[Dict[str, Any]] = None) -> bytes:
        record: Dict[str, Any] = {"agent_id": agent_id, "tool_name": tool_name, "tool_args": tool_args}
        if injected is not None:
            record["injected_in_transit"] = injected
        try:
            return json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise ValueError(f"tool call must be JSON-serialisable: {exc}") from exc

    def intercept_user_prompt(self, prompt_text: str, session_id: str = "sess_001") -> Dict[str, Any]:
        """Screen a prompt before an orchestrator ingests it (pattern heuristic only)."""
        t0 = time.perf_counter_ns()
        screen = self.screen_payload(prompt_text)
        admitted = not screen["flagged"]
        audit = {
            "session_id": session_id,
            "stage": "USER_PROMPT_INTERCEPTION",
            "prompt_sha256": hashlib.sha256(prompt_text.encode("utf-8")).hexdigest(),
            "prompt_chars": len(prompt_text),
            "pattern_screen": screen,
            "sheaf_check": {
                "evaluated": False,
                "reason": "a single prompt is one observation; agreement checks need two or more states "
                "(see intercept_tool_execution and AgenticSheafImmuneSystem)",
            },
            "decision_basis": "pattern_heuristic",
            "threat_classification": ThreatClassification.CLEAN.value
            if admitted
            else ThreatClassification.PROMPT_INJECTION.value,
            "action": "ADMITTED_TO_ORCHESTRATOR" if admitted else "BLOCKED_BY_PATTERN_HEURISTIC",
            "latency_ms": _elapsed_ms(t0),
        }
        self._execution_log.append(audit)
        return audit

    def intercept_tool_execution(
        self,
        agent_id: str,
        tool_name: str,
        tool_args: Dict[str, Any],
        simulate_poisoning: bool = False,
        observed_copies: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Gate a tool call before execution.

        ``observed_copies`` may map ``gateway_log`` / ``tool_input`` /
        ``agent_commitment`` to the tool arguments as observed at that hop;
        by default every hop holds ``tool_args``. ``simulate_poisoning``
        alters the ``tool_input`` copy in transit (``SIMULATED_INJECTION``).
        """
        t0 = time.perf_counter_ns()
        args_by_copy: Dict[str, Any] = {node: tool_args for node in self.COPY_NODES}
        for node, observed in (observed_copies or {}).items():
            if node not in args_by_copy:
                raise ValueError(f"unknown copy {node!r}; expected one of {list(self.COPY_NODES)}")
            args_by_copy[node] = observed
        copies = {node: self.canonical_call(agent_id, tool_name, args) for node, args in args_by_copy.items()}
        if simulate_poisoning:
            copies["tool_input"] = self.canonical_call(
                agent_id, tool_name, args_by_copy["tool_input"], injected=self.SIMULATED_INJECTION
            )

        screen = self.screen_payload(copies["tool_input"].decode("utf-8"))

        sheaf = self.copy_sheaf()
        section = {node: self.fingerprint(copies[node]) for node in self.COPY_NODES}
        residuals = sheaf.coboundary(section)
        edge_report = [
            {"edge": [a, b], "copies_agree": all(x == 0 for x in vec)}
            for (a, b), vec in zip(sheaf.edges, residuals)
        ]
        consistent = all(item["copies_agree"] for item in edge_report)
        isolating = [] if consistent else sheaf.isolate(section)

        repair: Dict[str, Any] = {"performed": False, "action": "NO_REPAIR_NEEDED"}
        if not consistent:
            if len(isolating) == 1:
                bad = isolating[0]
                donors = [node for node in self.COPY_NODES if node != bad]
                copies[bad] = copies[donors[0]]
                section[bad] = self.fingerprint(copies[bad])
                repair = {
                    "performed": True,
                    "action": f"{bad.upper()}_RESTORED_FROM_AGREEING_COPIES",
                    "restored_copy": bad,
                    "restored_from": donors,
                    "verified_consistent_after_repair": _all_zero(sheaf.coboundary(section)),
                }
            else:
                repair = {
                    "performed": False,
                    "action": "NOT_REPAIRED_DISAGREEMENT_NOT_LOCALISED",
                    "isolating_copies": isolating,
                }

        blocked_by = []
        if screen["flagged"]:
            blocked_by.append("pattern_heuristic")
        if not consistent:
            blocked_by.append("copy_disagreement")
        admitted = not blocked_by
        audit = {
            "agent_id": agent_id,
            "tool_name": tool_name,
            "tool_admitted": admitted,
            "verdict": "EXECUTION_PERMITTED" if admitted else "EXECUTION_BLOCKED",
            "blocked_by": blocked_by,
            "threat_classification": ThreatClassification.CLEAN.value
            if admitted
            else ThreatClassification.TOOL_POISONING.value,
            "pattern_screen": screen,
            "copy_consistency": {
                "method": "exact coboundary on a triangle sheaf over three copies of the call "
                "(SHA-256 fingerprints in Q^8, exact Householder frames)",
                "copies": list(self.COPY_NODES),
                "consistent": consistent,
                "edges": edge_report,
                "isolating_copies": isolating,
                "simulated_in_transit_modification": bool(simulate_poisoning),
            },
            "repair": repair,
            "committed_call_sha256": hashlib.sha256(copies["agent_commitment"]).hexdigest(),
            "latency_ms": _elapsed_ms(t0),
        }
        self._execution_log.append(audit)
        return audit

    def get_audit_trail(self) -> List[Dict[str, Any]]:
        return list(self._execution_log)


# ==============================================================================
# AGENT EXECUTION GRAPH: STATE AGREEMENT, LOCATION AND REPAIR
# ==============================================================================


@dataclass(frozen=True)
class DAGEdge:
    """Directed edge in an agent execution graph (data / instruction flow)."""

    src: str
    dst: str
    edge_type: str = "DATA_FLOW"


@dataclass
class AgentDAG:
    """Multi-agent execution graph G = (V, E)."""

    nodes: List[str]
    edges: List[DAGEdge]

    @classmethod
    def create_canonical_pipeline(cls) -> "AgentDAG":
        """Planner -> Coder -> Executor -> Tool."""
        return cls(
            nodes=["Planner", "Coder", "Executor", "Tool"],
            edges=[
                DAGEdge("Planner", "Coder"),
                DAGEdge("Coder", "Executor"),
                DAGEdge("Executor", "Tool"),
            ],
        )


@dataclass
class AgentState:
    """Context state of one agent (numbers or exact strings such as ``"1/3"``)."""

    context_vector: List[Any]
    agent_id: str = ""
    objective: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


def _context_vector(value: Any) -> Any:
    if isinstance(value, AgentState):
        return value.context_vector
    if isinstance(value, dict) and "context_vector" in value:
        return value["context_vector"]
    return value


@dataclass
class ExecutionResult:
    """Result of one checked turn.

    ``state`` holds JSON-friendly numbers (int, or a float rendering of a
    non-integral rational) for presentation; ``state_exact`` holds the exact
    rationals. ``coboundary_norm_sq`` is the exact squared norm of ``delta0`` of
    the submitted states. ``h1_norm`` is a legacy alias of that value; it never
    measured an ``H^1`` class.
    """

    status: str
    state: Dict[str, List[Any]]
    vortex_node: Optional[str] = None
    error: Optional[str] = None
    coboundary_err: Dict[DAGEdge, List[Fraction]] = field(default_factory=dict)
    latency_ms: Any = 0
    coboundary_norm_sq: Fraction = Fraction(0)
    state_exact: Dict[str, List[Fraction]] = field(default_factory=dict)
    submitted_state: Dict[str, List[Fraction]] = field(default_factory=dict)
    localisation: Dict[str, Any] = field(default_factory=dict)
    repair: Dict[str, Any] = field(default_factory=dict)
    restriction_frames: str = "identity"
    unreported_nodes: List[str] = field(default_factory=list)
    filled_from_baseline: List[str] = field(default_factory=list)
    ignored_states: List[str] = field(default_factory=list)

    @property
    def h1_norm(self) -> Any:
        """Legacy alias: ``coboundary_norm_sq`` as a JSON number."""
        return display_number(self.coboundary_norm_sq)

    @property
    def coboundary_norm(self) -> str:
        return sqrt_decimal_string(self.coboundary_norm_sq, 8)

    def as_dict(self) -> Dict[str, Any]:
        """JSON-friendly result; ``*_exact`` fields and residuals carry exact rationals as strings."""
        return {
            "status": self.status,
            "error": self.error,
            "coboundary_norm_sq": fraction_str(self.coboundary_norm_sq),
            "coboundary_norm": self.coboundary_norm,
            "h1_norm": self.h1_norm,
            "vortex_node": self.vortex_node,
            "localisation": self.localisation,
            "repair": self.repair,
            "restriction_frames": self.restriction_frames,
            "submitted_state_exact": {n: _strings(v) for n, v in self.submitted_state.items()},
            "healed_state": self.state,
            "healed_state_exact": {n: _strings(v) for n, v in self.state_exact.items()},
            "coboundary": {f"{e.src}->{e.dst}": _strings(v) for e, v in self.coboundary_err.items()},
            "unreported_nodes": list(self.unreported_nodes),
            "filled_from_baseline": list(self.filled_from_baseline),
            "ignored_states": list(self.ignored_states),
            "latency_ms": self.latency_ms,
        }


class AgenticSheafImmuneSystem:
    """Exact state-agreement check for an agent execution graph (see the module docstring).

    Node states shorter than ``stalk_dim`` are zero-padded; longer ones are
    rejected (they are never truncated). A node without a submitted state uses
    its registered baseline if there is one, and is otherwise left out of the
    turn's check (reported in ``unreported_nodes``).
    """

    def __init__(self, agent_dag: Optional[AgentDAG] = None, stalk_dim: int = 64) -> None:
        if agent_dag is None:
            agent_dag = AgentDAG.create_canonical_pipeline()
        if isinstance(stalk_dim, bool) or not isinstance(stalk_dim, int) or not 1 <= stalk_dim <= MAX_STALK_DIM:
            raise SheafError(f"stalk dimension must be an integer between 1 and {MAX_STALK_DIM}")
        known = set(agent_dag.nodes)
        dangling = [(e.src, e.dst) for e in agent_dag.edges if e.src not in known or e.dst not in known]
        if dangling:
            raise SheafError(f"edges reference unknown nodes: {dangling}")
        self.dag = agent_dag
        self.stalk_dim = stalk_dim
        self.restriction_frames = "householder" if stalk_dim <= FRAME_MAX_DIM else "identity"
        self.restriction_maps: Dict[DAGEdge, Optional[StiefelRestrictionMap]] = {
            e: StiefelRestrictionMap(stalk_dim, seed_id=f"agent-edge:{e.src}->{e.dst}")
            if self.restriction_frames == "householder"
            else None
            for e in agent_dag.edges
        }
        self._node_set = known
        self._baseline_states: Dict[str, Vector] = {}
        self._sheaves: Dict[Tuple[str, ...], Tuple[GraphSheaf, List[DAGEdge]]] = {}
        self._sheaf_for(tuple(agent_dag.nodes))  # validates nodes, edges and every frame now

    def _sheaf_for(self, active: Tuple[str, ...]) -> Tuple[GraphSheaf, List[DAGEdge]]:
        cached = self._sheaves.get(active)
        if cached is None:
            keep = set(active)
            edges = [e for e in self.dag.edges if e.src in keep and e.dst in keep]
            maps: Dict[Tuple[int, str], Matrix] = {}
            for i, e in enumerate(edges):
                frame = self.restriction_maps.get(e)
                if frame is not None:
                    maps[(i, e.src)] = frame.matrix
                    maps[(i, e.dst)] = frame.matrix
            sheaf = GraphSheaf(list(active), [(e.src, e.dst) for e in edges], self.stalk_dim, maps)
            cached = (sheaf, edges)
            self._sheaves[active] = cached
        return cached

    def register_baseline_state(self, node_id: str, context_vector: Sequence[Any]) -> None:
        """Register a known-good context vector for ``node_id`` (exact)."""
        if node_id not in self._node_set:
            raise SheafError(f"unknown node {node_id!r}")
        self._baseline_states[node_id] = _fit(context_vector, self.stalk_dim, f"baseline for {node_id}")

    def verify_and_execute_turn(self, agent_states: Dict[str, Any]) -> ExecutionResult:
        """Check one turn exactly; on disagreement, locate and repair (nothing is dispatched)."""
        t0 = time.perf_counter_ns()
        states = dict(agent_states or {})
        ignored = sorted(str(k) for k in states if k not in self._node_set)
        submitted: Dict[str, Vector] = {}
        filled: List[str] = []
        unreported: List[str] = []
        for node in self.dag.nodes:
            if node in states:
                submitted[node] = _fit(_context_vector(states[node]), self.stalk_dim, f"state of {node}")
            elif node in self._baseline_states:
                submitted[node] = list(self._baseline_states[node])
                filled.append(node)
            else:
                unreported.append(node)
        common: Dict[str, Any] = {
            "restriction_frames": self.restriction_frames,
            "unreported_nodes": unreported,
            "filled_from_baseline": filled,
            "ignored_states": ignored,
        }
        if not submitted:
            return ExecutionResult(status=STATUS_NO_STATE, state={}, latency_ms=_elapsed_ms(t0), **common)

        active = tuple(node for node in self.dag.nodes if node in submitted)
        sheaf, edges = self._sheaf_for(active)
        section = {node: submitted[node] for node in active}
        dis = sheaf.disagreement(section)
        coboundary = {edges[i]: vec for i, vec in enumerate(dis["coboundary"])}
        total = dis["total_norm_sq"]
        if total == 0:
            return ExecutionResult(
                status=STATUS_CONSISTENT,
                state=_display(section),
                coboundary_err=coboundary,
                latency_ms=_elapsed_ms(t0),
                coboundary_norm_sq=total,
                state_exact=section,
                submitted_state=section,
                repair={"performed": False, "method": None},
                **common,
            )

        location, repair_values = self._locate(sheaf, section, dis)
        repaired, repair = self._repair(sheaf, section, location["offending_node"], repair_values)
        return ExecutionResult(
            status=STATUS_REPAIRED if repair["verified_consistent"] else STATUS_REPAIR_FAILED,
            state=_display(repaired),
            vortex_node=location["offending_node"],
            error=ERROR_DISAGREEMENT,
            coboundary_err=coboundary,
            latency_ms=_elapsed_ms(t0),
            coboundary_norm_sq=total,
            state_exact=repaired,
            submitted_state=section,
            localisation=location,
            repair=repair,
            **common,
        )

    @staticmethod
    def _neighbour_values(sheaf: GraphSheaf, section: Dict[str, Vector]) -> Dict[str, List[Vector]]:
        # Both incidences of an edge share one orthogonal frame H, so H s_b = H s_a iff s_b = s_a:
        # the value a neighbour implies for a node is the neighbour's own state.
        implied: Dict[str, List[Vector]] = {node: [] for node in sheaf.nodes}
        for a, b in sheaf.edges:
            implied[b].append(section[a])
            implied[a].append(section[b])
        return implied

    def _locate(
        self, sheaf: GraphSheaf, section: Dict[str, Vector], dis: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], Dict[str, Vector]]:
        isolating = sheaf.isolate(section)
        implied = self._neighbour_values(sheaf, section)
        repair_values: Dict[str, Vector] = {}
        for node in isolating:
            values = implied[node]
            if values and all(v == values[0] for v in values):
                repair_values[node] = values[0]
        candidates = [node for node in sheaf.nodes if node in repair_values]
        offending: Optional[str] = None
        basis: Optional[str] = None
        if len(candidates) == 1:
            offending, basis = candidates[0], "only node whose replacement alone restores agreement"
        elif len(candidates) > 1:
            unconfirmed = [n for n in candidates if self._baseline_states.get(n) != section[n]]
            if len(unconfirmed) == 1:
                offending, basis = unconfirmed[0], "the other candidates match their registered baselines"
        location = {
            "method": "GraphSheaf.isolate, then single-node repairability, then registered baselines",
            "disagreeing_edges": [list(sheaf.edges[i]) for i, sq in enumerate(dis["edge_norm_sq"]) if sq != 0],
            "isolating_nodes": isolating,
            "single_node_repairable": candidates,
            "offending_node": offending,
            "basis": basis,
            "ambiguous": offending is None and len(candidates) > 1,
            "node_energy": {node: fraction_str(dis["node_energy"][node]) for node in sheaf.nodes},
        }
        return location, repair_values

    def _repair(
        self,
        sheaf: GraphSheaf,
        section: Dict[str, Vector],
        offending: Optional[str],
        repair_values: Dict[str, Vector],
    ) -> Tuple[Dict[str, Vector], Dict[str, Any]]:
        attempts: List[Dict[str, Any]] = []

        def accepted(method: str, candidate: Dict[str, Vector]) -> bool:
            changed = [n for n in sheaf.nodes if candidate[n] != section[n]]
            ok = _all_zero(sheaf.coboundary(candidate))
            attempts.append({"method": method, "nodes_changed": changed, "consistent_after": ok})
            return ok

        candidate: Dict[str, Vector] = {}
        done = False
        if offending is not None:
            if offending in self._baseline_states:
                candidate = dict(section)
                candidate[offending] = list(self._baseline_states[offending])
                done = accepted("baseline_restore", candidate)
            if not done:
                candidate = dict(section)
                candidate[offending] = list(repair_values[offending])
                done = accepted("neighbour_value", candidate)
        else:
            deviating = [n for n in sheaf.nodes if n in self._baseline_states and self._baseline_states[n] != section[n]]
            if deviating:
                candidate = dict(section)
                for node in deviating:
                    candidate[node] = list(self._baseline_states[node])
                done = accepted("baseline_restore", candidate)
        if not done:
            candidate = sheaf.harmonic_projection(section)
            done = accepted("nearest_global_section", candidate)
        change_sq = sum((_exact_norm_sq(vec_sub(candidate[n], section[n])) for n in sheaf.nodes), Fraction(0))
        return candidate, {
            "performed": True,
            "method": attempts[-1]["method"],
            "nodes_changed": attempts[-1]["nodes_changed"],
            "verified_consistent": done,
            "change_norm_sq": fraction_str(change_sq),
            "attempts": attempts,
        }
