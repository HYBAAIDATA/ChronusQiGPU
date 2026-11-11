"""AL HARAS (HYBA Security): exact computations behind the legacy "Millennium"
security class names.

Older notes attached Millennium Prize Problems, "Perelman surgery", side-channel
eradication, Spectre/Meltdown immunity, latency figures for memory purges and
anti-jamming to the classes below. None of that is implemented or claimed. The
names are kept because the AL HARAS router imports them; every method returns
only what it computes, labelled as what was computed. Arithmetic is exact
(``int`` / ``fractions.Fraction``); API numbers are read with
``exact.to_fraction``; timings are measured with ``time.perf_counter_ns``.

1. ``RicciCurvatureDeCloaker``: Ollivier-Ricci curvature of every edge of an
   undirected, traffic-weighted graph. W1 between the two endpoint random-walk
   measures is the optimum of a transportation linear program, solved over the
   rationals and accepted only with an exact dual certificate. The "surgery" is
   the removal of every edge whose curvature is below a threshold, with exact
   connected-component counts before and after. Curvature is a structural
   statistic; it does not identify command-and-control or botnet traffic.
2. ``HodgeCovertChannelFilter``: exact Hodge decomposition of edge signals on a
   graph (gradient + curl + harmonic). A trace is read as an edge signal on the
   oriented cycle graph C_n: its gradient part is the trace minus its mean and
   its harmonic part is the mean. Nothing is removed from any real channel.
3. ``UltrametricMemorySandbox``: exact p-adic valuations and distances. An
   enclave is the closed p-adic ball ``c + p^k Z`` (a set of integer addresses);
   the check decides exactly whether two such address sets intersect. It does
   not model memory hardware and establishes no isolation property of a system.
4. ``AnosovColdBootScrambler``: in-place zeroisation of a mutable buffer with
   read-back verification. The Arnold cat map is a separate, optional and
   reversible byte permutation whose period is computed exactly; a permutation
   is not erasure.
5. ``PicardLefschetzAntiJammingFilter``: not implemented; the method validates
   its input and returns ``NOT_IMPLEMENTED``.
"""

import time
from collections import deque
from collections.abc import Hashable
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
from typing import Any, Dict, List, Optional, Sequence, Tuple

from chronus.security.al_haras.exact import (
    Matrix,
    Vector,
    decimal_string,
    fraction_str,
    mat_mul,
    mat_vec,
    norm_sq,
    rank_and_nullspace,
    solve_linear,
    to_fraction,
    to_vector,
    transpose,
)
from chronus.security.al_haras.expander import is_prime

__all__ = [
    "NetworkGraphEdge",
    "RicciCurvatureDeCloaker",
    "HodgeCovertChannelFilter",
    "UltrametricMemorySandbox",
    "AnosovColdBootScrambler",
    "PicardLefschetzAntiJammingFilter",
    "certify_transport",
    "ollivier_ricci_curvature",
    "p_adic_valuation",
    "solve_transport",
]

NOT_IMPLEMENTED = "NOT_IMPLEMENTED"


def _elapsed_us(started_ns: int) -> str:
    return decimal_string(Fraction(time.perf_counter_ns() - started_ns, 1000), 3)


def _dot(u: Sequence[Fraction], v: Sequence[Fraction]) -> Fraction:
    return sum((a * b for a, b in zip(u, v)), Fraction(0))


def _integer(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    return value


# ==============================================================================
# 1. OLLIVIER-RICCI CURVATURE AND THRESHOLD EDGE REMOVAL
# ==============================================================================

MAX_GRAPH_NODES = 256
MAX_GRAPH_EDGES = 512
MAX_NODE_DEGREE = 64
MAX_TRANSPORT_CELLS = 40_000


@dataclass
class NetworkGraphEdge:
    """An undirected edge with an exact traffic weight; ``curvature`` is set once computed."""

    source: Hashable
    target: Hashable
    traffic_weight: Fraction
    curvature: Optional[Fraction] = None


class _ResidualNetwork:
    """Residual graph for min-cost flow over Q; arcs are stored as (forward, reverse) pairs."""

    def __init__(self, size: int) -> None:
        self.out: List[List[int]] = [[] for _ in range(size)]
        self.head: List[int] = []
        self.capacity: List[Optional[Fraction]] = []  # None: no capacity bound
        self.cost: List[int] = []

    def add_arc(self, tail: int, head: int, capacity: Optional[Fraction], cost: int) -> int:
        index = len(self.head)
        for u, v, cap, c in ((tail, head, capacity, cost), (head, tail, Fraction(0), -cost)):
            self.out[u].append(len(self.head))
            self.head.append(v)
            self.capacity.append(cap)
            self.cost.append(c)
        return index

    def usable(self, arc: int) -> bool:
        cap = self.capacity[arc]
        return cap is None or cap > 0

    def shortest_paths(self, start: Sequence[int]):
        """Queue-based Bellman-Ford over usable arcs, minimising (cost, number of arcs).

        Residual costs may be negative. Ties in cost are broken by fewer arcs, so
        augmentations of equal cost follow shortest admissible paths (as in
        Edmonds-Karp). A label path with ``size`` arcs would contain a negative
        cycle, which cannot occur for an optimal residual graph; it is reported.
        """
        size = len(self.out)
        dist: List[Optional[Tuple[int, int]]] = [None] * size
        pred = [-1] * size
        queued = [False] * size
        queue: deque = deque()
        for node in start:
            dist[node] = (0, 0)
            queued[node] = True
            queue.append(node)
        while queue:
            u = queue.popleft()
            queued[u] = False
            du = dist[u]
            for arc in self.out[u]:
                if not self.usable(arc):
                    continue
                v = self.head[arc]
                candidate = (du[0] + self.cost[arc], du[1] + 1)
                if dist[v] is None or candidate < dist[v]:
                    if candidate[1] >= size:
                        raise RuntimeError("negative residual cycle: the transport plan is not optimal")
                    dist[v] = candidate
                    pred[v] = arc
                    if not queued[v]:
                        queued[v] = True
                        queue.append(v)
        return dist, pred


def solve_transport(
    supply: Sequence[Any], demand: Sequence[Any], cost: Sequence[Sequence[int]]
) -> Tuple[List[List[Fraction]], Fraction, List[Fraction], List[Fraction]]:
    """Exact optimal transportation plan with dual potentials (successive shortest paths over Q).

    Minimises sum_ij plan_ij * cost_ij subject to row sums ``supply``, column sums
    ``demand`` and plan >= 0, for integer costs. Returns ``(plan, total_cost, phi,
    psi)`` where phi_i - psi_j <= cost_ij for every pair, with equality wherever
    plan_ij > 0 (complementary slackness).
    """
    supply = [Fraction(s) for s in supply]
    demand = [Fraction(d) for d in demand]
    m, n = len(supply), len(demand)
    if len(cost) != m or any(len(row) != n for row in cost):
        raise ValueError("cost matrix must be len(supply) x len(demand)")
    if any(isinstance(c, bool) or not isinstance(c, int) for row in cost for c in row):
        raise TypeError("transport costs must be integers")
    if any(s < 0 for s in supply) or any(d < 0 for d in demand):
        raise ValueError("masses must be non-negative")
    total = sum(supply, Fraction(0))
    if total != sum(demand, Fraction(0)):
        raise ValueError("supply and demand must have the same total mass")
    size = m + n + 2
    origin, terminal = 0, size - 1
    net = _ResidualNetwork(size)
    for i, mass in enumerate(supply):
        net.add_arc(origin, 1 + i, mass, 0)
    for j, mass in enumerate(demand):
        net.add_arc(1 + m + j, terminal, mass, 0)
    cell = [[net.add_arc(1 + i, 1 + m + j, None, cost[i][j]) for j in range(n)] for i in range(m)]
    # Polynomial bound on augmentations (cost phases x Edmonds-Karp rounds); a safety net only.
    limit = (3 * size + 1) * (size * len(net.head) + 1)
    remaining = total
    rounds = 0
    while remaining > 0:
        dist, pred = net.shortest_paths([origin])
        if dist[terminal] is None:
            raise RuntimeError("transport problem is infeasible")
        push = remaining
        node = terminal
        while node != origin:
            arc = pred[node]
            cap = net.capacity[arc]
            if cap is not None and cap < push:
                push = cap
            node = net.head[arc ^ 1]
        node = terminal
        while node != origin:
            arc = pred[node]
            if net.capacity[arc] is not None:
                net.capacity[arc] -= push
            if net.capacity[arc ^ 1] is not None:
                net.capacity[arc ^ 1] += push
            node = net.head[arc ^ 1]
        remaining -= push
        rounds += 1
        if rounds > limit:
            raise RuntimeError("transport solver exceeded its augmentation bound")
    potential, _ = net.shortest_paths(range(size))
    plan = [[net.capacity[cell[i][j] ^ 1] for j in range(n)] for i in range(m)]
    total_cost = sum((plan[i][j] * cost[i][j] for i in range(m) for j in range(n)), Fraction(0))
    phi = [Fraction(-potential[1 + i][0]) for i in range(m)]
    psi = [Fraction(-potential[1 + m + j][0]) for j in range(n)]
    return plan, total_cost, phi, psi


def certify_transport(
    supply: Sequence[Fraction],
    demand: Sequence[Fraction],
    cost: Sequence[Sequence[int]],
    plan: Sequence[Sequence[Fraction]],
    phi: Sequence[Fraction],
    psi: Sequence[Fraction],
) -> bool:
    """Exact linear-programming optimality certificate for a transportation plan.

    True iff the plan is feasible (non-negative, row sums = supply, column sums =
    demand), the duals are feasible (phi_i - psi_j <= cost_ij for all pairs) and
    the primal and dual objectives are equal. By weak duality the plan's cost is
    then the exact optimum, i.e. W1 when ``cost`` is a metric on the supports.
    """
    m, n = len(supply), len(demand)
    if len(plan) != m or any(len(row) != n for row in plan) or len(phi) != m or len(psi) != n:
        return False
    if any(x < 0 for row in plan for x in row):
        return False
    if any(sum(row, Fraction(0)) != supply[i] for i, row in enumerate(plan)):
        return False
    if any(sum((plan[i][j] for i in range(m)), Fraction(0)) != demand[j] for j in range(n)):
        return False
    if any(phi[i] - psi[j] > cost[i][j] for i in range(m) for j in range(n)):
        return False
    primal = sum((plan[i][j] * cost[i][j] for i in range(m) for j in range(n)), Fraction(0))
    dual = _dot(phi, supply) - _dot(psi, demand)
    return primal == dual


def _walk_measure(adjacency: Dict[Hashable, Dict[Hashable, Fraction]], node: Hashable, idleness: Fraction):
    neighbours = adjacency[node]
    total = sum(neighbours.values(), Fraction(0))
    measure: Dict[Hashable, Fraction] = {}
    if idleness:
        measure[node] = idleness
    for other, weight in neighbours.items():
        measure[other] = (1 - idleness) * weight / total
    return measure


def _hop_distances(adjacency: Dict[Hashable, Dict[Hashable, Fraction]], start: Hashable, radius: int):
    dist = {start: 0}
    queue = deque([start])
    while queue:
        u = queue.popleft()
        if dist[u] == radius:
            continue
        for v in adjacency[u]:
            if v not in dist:
                dist[v] = dist[u] + 1
                queue.append(v)
    return dist


def ollivier_ricci_curvature(
    adjacency: Dict[Hashable, Dict[Hashable, Fraction]],
    x: Hashable,
    y: Hashable,
    idleness: Fraction = Fraction(0),
    distance_cache: Optional[Dict[Hashable, Dict[Hashable, int]]] = None,
) -> Dict[str, Any]:
    """Exact Ollivier-Ricci curvature kappa(x, y) = 1 - W1(m_x, m_y) / d(x, y) of an edge x ~ y.

    ``adjacency[u][v]`` is the (positive, exact) weight of the edge u ~ v. The
    random-walk measure is m_x(x) = idleness and m_x(z) = (1 - idleness) w_xz / sum_z' w_xz'
    for neighbours z; d is the hop distance, so d(x, y) = 1 and every support pair
    is within distance 3.
    """
    if y not in adjacency.get(x, {}):
        raise ValueError("curvature is defined here on edges: x and y must be adjacent")
    cache: Dict[Hashable, Dict[Hashable, int]] = {} if distance_cache is None else distance_cache
    mu = _walk_measure(adjacency, x, idleness)
    nu = _walk_measure(adjacency, y, idleness)
    sources, sinks = list(mu), list(nu)
    for b in sinks:
        if b not in cache:
            cache[b] = _hop_distances(adjacency, b, 3)
    cost = [[cache[b][a] for b in sinks] for a in sources]
    supply = [mu[a] for a in sources]
    demand = [nu[b] for b in sinks]
    plan, w1, phi, psi = solve_transport(supply, demand, cost)
    return {
        "curvature": 1 - w1,
        "wasserstein_1": w1,
        "certified": certify_transport(supply, demand, cost, plan, phi, psi),
        "sources": sources,
        "sinks": sinks,
        "plan": plan,
    }


def _component_count(nodes: Sequence[Hashable], adjacency: Dict[Hashable, Dict[Hashable, Fraction]]) -> int:
    seen: set = set()
    count = 0
    for start in nodes:
        if start in seen:
            continue
        count += 1
        seen.add(start)
        queue = deque([start])
        while queue:
            u = queue.popleft()
            for v in adjacency[u]:
                if v not in seen:
                    seen.add(v)
                    queue.append(v)
    return count


class RicciCurvatureDeCloaker:
    """Exact Ollivier-Ricci curvature of a traffic-weighted graph, and threshold edge removal.

    Name kept for existing callers. For an edge x ~ y,

        kappa(x, y) = 1 - W1(m_x, m_y) / d(x, y)

    (Ollivier 2009), with d the hop distance and m_x the random-walk measure
    m_x(x) = alpha, m_x(z) = (1 - alpha) w_xz / sum_z' w_xz' (idleness alpha as in
    Lin-Lu-Yau 2011; default 0). Traffic weights enter only through m_x. W1 is the
    optimum of the transportation linear program between the two measures, solved
    exactly and accepted only with an exact dual certificate. Edges are
    undirected; repeated edges between one pair are merged by adding weights.

    ``execute_perelman_surgery`` (name kept) removes every edge whose curvature is
    strictly below ``curvature_threshold``. It is a threshold rule on a graph
    statistic: not Ricci flow, not a proof of anything, and not a detector of
    malicious traffic.
    """

    def __init__(self, curvature_threshold: Any = Fraction(-2, 5), idleness: Any = 0) -> None:
        self.curvature_threshold: Fraction = to_fraction(curvature_threshold)
        self.idleness: Fraction = to_fraction(idleness)
        if not 0 <= self.idleness < 1:
            raise ValueError("idleness alpha must satisfy 0 <= alpha < 1")
        self.edges: List[NetworkGraphEdge] = []
        self.nodes: set = set()
        self._node_order: List[Hashable] = []

    def add_edge(self, source: Hashable, target: Hashable, traffic_weight: Any = 1) -> None:
        if source == target:
            raise ValueError("an edge needs two distinct endpoints (self-loops have no curvature)")
        weight = to_fraction(traffic_weight)
        if weight <= 0:
            raise ValueError("traffic weight must be positive")
        if len(self.edges) >= MAX_GRAPH_EDGES:
            raise ValueError(f"at most {MAX_GRAPH_EDGES} edges are supported")
        new_nodes = [node for node in (source, target) if node not in self.nodes]
        if len(self.nodes) + len(new_nodes) > MAX_GRAPH_NODES:
            raise ValueError(f"at most {MAX_GRAPH_NODES} nodes are supported")
        for node in new_nodes:
            self.nodes.add(node)
            self._node_order.append(node)
        self.edges.append(NetworkGraphEdge(source, target, weight))

    def _graph(self):
        adjacency: Dict[Hashable, Dict[Hashable, Fraction]] = {node: {} for node in self._node_order}
        orientation: Dict[frozenset, Tuple[Hashable, Hashable]] = {}
        for edge in self.edges:
            a, b = edge.source, edge.target
            adjacency[a][b] = adjacency[a].get(b, Fraction(0)) + edge.traffic_weight
            adjacency[b][a] = adjacency[b].get(a, Fraction(0)) + edge.traffic_weight
            orientation.setdefault(frozenset((a, b)), (a, b))
        return adjacency, orientation

    def _curvature_details(self):
        adjacency, orientation = self._graph()
        for node, neighbours in adjacency.items():
            if len(neighbours) > MAX_NODE_DEGREE:
                raise ValueError(f"node {node!r} has degree {len(neighbours)}; at most {MAX_NODE_DEGREE} is supported")
        extra = 1 if self.idleness else 0
        cells = sum((len(adjacency[a]) + extra) * (len(adjacency[b]) + extra) for a, b in orientation.values())
        if cells > MAX_TRANSPORT_CELLS:
            raise ValueError("graph too large for the exact transport computation")
        cache: Dict[Hashable, Dict[Hashable, int]] = {}
        details = {
            key: ollivier_ricci_curvature(adjacency, a, b, self.idleness, cache)
            for key, (a, b) in orientation.items()
        }
        for edge in self.edges:
            edge.curvature = details[frozenset((edge.source, edge.target))]["curvature"]
        return adjacency, orientation, details

    def compute_ollivier_ricci_curvatures(self) -> Dict[str, Fraction]:
        """Exact curvature of every distinct edge, keyed ``"source->target"`` (first orientation added)."""
        _, orientation, details = self._curvature_details()
        return {f"{a}->{b}": details[key]["curvature"] for key, (a, b) in orientation.items()}

    def execute_perelman_surgery(self) -> Dict[str, Any]:
        """Remove every edge whose exact curvature is strictly below the threshold.

        Name kept for existing callers. All curvatures are computed on the graph
        before any removal; nothing is removed unless every curvature carries a
        valid transport certificate. ``self.edges`` keeps the remaining edges.
        """
        started = time.perf_counter_ns()
        adjacency, orientation, details = self._curvature_details()
        components_before = _component_count(self._node_order, adjacency)
        certified = all(d["certified"] for d in details.values())
        below = [key for key in orientation if details[key]["curvature"] < self.curvature_threshold]
        removed = below if certified else []
        if removed:
            gone = set(removed)
            self.edges = [e for e in self.edges if frozenset((e.source, e.target)) not in gone]
        adjacency_after, _ = self._graph()
        components_after = _component_count(self._node_order, adjacency_after)
        if not orientation:
            status = "NO_EDGES"
        elif not certified:
            status = "CURVATURE_NOT_CERTIFIED_NOTHING_REMOVED"
        elif removed:
            status = "EDGES_REMOVED"
        else:
            status = "NO_EDGE_BELOW_THRESHOLD"
        labels = {key: f"{a}->{b}" for key, (a, b) in orientation.items()}
        return {
            "method": (
                "exact Ollivier-Ricci curvature kappa(x, y) = 1 - W1(m_x, m_y) of each edge "
                "(hop distance; traffic-weighted random-walk measures); W1 from a transportation "
                "linear program solved over the rationals and checked with an exact dual certificate"
            ),
            "rule": "remove every edge with curvature < curvature_threshold; curvatures are computed before any removal",
            "curvature_threshold": fraction_str(self.curvature_threshold),
            "idleness_alpha": fraction_str(self.idleness),
            "edges_analyzed": len(orientation),
            "curvatures": {labels[k]: fraction_str(details[k]["curvature"]) for k in orientation},
            "curvatures_decimal": {labels[k]: decimal_string(details[k]["curvature"], 6) for k in orientation},
            "transport_optimality_certified": certified,
            "edges_below_threshold": len(below),
            "removed_edges": [
                {
                    "source": orientation[k][0],
                    "target": orientation[k][1],
                    "traffic_weight": fraction_str(adjacency[orientation[k][0]][orientation[k][1]]),
                    "ollivier_ricci_curvature": fraction_str(details[k]["curvature"]),
                    "curvature_decimal": decimal_string(details[k]["curvature"], 6),
                    "wasserstein_1": fraction_str(details[k]["wasserstein_1"]),
                }
                for k in removed
            ],
            "removed_edge_count": len(removed),
            "remaining_edge_count": len(orientation) - len(removed),
            "connected_components_before": components_before,
            "connected_components_after": components_after,
            "status": status,
            "compute_time_us_measured": _elapsed_us(started),
            "scope": (
                "Curvature is a structural statistic of the supplied graph. Negative values mark edges "
                "whose endpoint neighbourhoods are poorly connected to each other, such as bridges between "
                "clusters; this does not identify command-and-control, botnet or exfiltration traffic."
            ),
        }


# ==============================================================================
# 2. EXACT HODGE DECOMPOSITION OF EDGE SIGNALS
# ==============================================================================

MAX_TRACE_SAMPLES = 1 << 16
MAX_COMPLEX_NODES = 64
MAX_COMPLEX_EDGES = 128
MAX_COMPLEX_TRIANGLES = 128


def _project_onto_columns(matrix: Matrix, vector: Vector) -> Tuple[Vector, Vector]:
    """Orthogonal projection of ``vector`` onto the column space of ``matrix`` (exact).

    Solves the normal equations M^T M y = M^T v, which are always consistent, and
    returns (M y, y). M y is the same for every solution y.
    """
    columns = len(matrix[0]) if matrix else 0
    if columns == 0:
        return [Fraction(0)] * len(vector), []
    mt = transpose(matrix)
    y = solve_linear(mat_mul(mt, matrix), mat_vec(mt, vector), columns)
    if y is None:
        raise RuntimeError("normal equations reported inconsistent")
    return mat_vec(matrix, y), y


class HodgeCovertChannelFilter:
    """Exact Hodge decomposition of edge signals; name kept for existing callers.

    For a graph with oriented edges and optional filled triangles, every edge
    signal splits orthogonally as

        flow = gradient (im d0) + curl (im d1^T) + harmonic (ker d0^T and ker d1),

    computed by exact least squares. ``sanitize_side_channels`` reads a trace as
    the signal on the edges of the oriented cycle graph C_n (sample i on edge
    i -> i+1 mod n). C_n has no 2-cells, so the curl part is zero, the harmonic
    part is the mean and the gradient part is the trace minus its mean. A timing
    or power side channel lives in a trace's variation, which is the gradient
    part; this decomposition does not detect, bound or remove side channels.
    """

    @staticmethod
    def _read_trace(samples: Sequence[Any]) -> Vector:
        values = list(samples)
        if len(values) > MAX_TRACE_SAMPLES:
            raise ValueError(f"at most {MAX_TRACE_SAMPLES} samples are supported")
        return to_vector(values)

    @staticmethod
    def _cycle_parts(trace: Vector) -> Dict[str, Any]:
        mean = sum(trace, Fraction(0)) / len(trace)
        gradient = [x - mean for x in trace]
        potential = [Fraction(0)]
        for value in gradient[:-1]:
            potential.append(potential[-1] + value)
        return {"mean": mean, "gradient": gradient, "harmonic": [mean] * len(trace), "potential": potential}

    @staticmethod
    def verify_cycle_decomposition(
        trace: Sequence[Fraction],
        gradient: Sequence[Fraction],
        harmonic: Sequence[Fraction],
        potential: Sequence[Fraction],
    ) -> Dict[str, bool]:
        """Exact identities of a decomposition of ``trace`` on the oriented cycle C_n."""
        n = len(trace)
        if not (len(gradient) == len(harmonic) == len(potential) == n):
            return {"sizes_match": False}
        return {
            "sizes_match": True,
            "reconstruction": all(g + h == w for w, g, h in zip(trace, gradient, harmonic)),
            "gradient_is_coboundary_of_potential": all(
                potential[(i + 1) % n] - potential[i] == gradient[i] for i in range(n)
            ),
            "harmonic_is_divergence_free": all(harmonic[i - 1] == harmonic[i] for i in range(n)),
            "parts_orthogonal": _dot(gradient, harmonic) == 0,
        }

    @classmethod
    def decompose_signal(cls, signal_samples: Sequence[Any]) -> Tuple[Vector, Vector, Vector]:
        """Legacy 3-tuple ``(exact, co_exact, harmonic)`` of a trace on the cycle graph C_n.

        ``exact`` is the gradient part (trace minus mean), ``harmonic`` the mean, and
        ``co_exact`` the remainder trace - exact - harmonic, which is zero because C_n
        has no 2-cells. All parts are exact rationals.
        """
        trace = cls._read_trace(signal_samples)
        if not trace:
            return [], [], []
        parts = cls._cycle_parts(trace)
        co_exact = [w - g - h for w, g, h in zip(trace, parts["gradient"], parts["harmonic"])]
        return parts["gradient"], co_exact, parts["harmonic"]

    @classmethod
    def decompose_edge_flow(
        cls,
        nodes: Sequence[Hashable],
        edges: Sequence[Tuple[Hashable, Hashable]],
        flow: Sequence[Any],
        triangles: Optional[Sequence[Tuple[Hashable, Hashable, Hashable]]] = None,
    ) -> Dict[str, Any]:
        """Exact Hodge decomposition of an edge signal on a graph with optional filled triangles.

        (d0 f)_e = f(b) - f(a) for e = (a, b); (d1 w)_t = w_ij + w_jk + w_ki for a
        triangle t = (i, j, k), with signs from the edge orientations. Returns exact
        parts, a node potential with d0 potential = gradient, the dimensions of the
        three subspaces and the exact identities that were checked.
        """
        nodes = list(nodes)
        edges = [tuple(e) for e in edges]
        triangles = [tuple(t) for t in (triangles or [])]
        if len(set(nodes)) != len(nodes):
            raise ValueError("node identifiers must be unique")
        if len(nodes) > MAX_COMPLEX_NODES or len(edges) > MAX_COMPLEX_EDGES or len(triangles) > MAX_COMPLEX_TRIANGLES:
            raise ValueError("complex exceeds the supported size")
        omega = to_vector(flow)
        if len(omega) != len(edges):
            raise ValueError("flow must assign one value to every edge")
        index = {node: i for i, node in enumerate(nodes)}
        d0: Matrix = []
        oriented: Dict[Tuple[Hashable, Hashable], Tuple[int, int]] = {}
        for e, edge in enumerate(edges):
            if len(edge) != 2:
                raise ValueError(f"edge {e} must have two endpoints")
            a, b = edge
            if a not in index or b not in index:
                raise ValueError(f"edge {e} references an unknown node")
            if a == b:
                raise ValueError("self-loops are not supported")
            if (a, b) in oriented:
                raise ValueError("parallel edges are not supported")
            row = [Fraction(0)] * len(nodes)
            row[index[a]] = Fraction(-1)
            row[index[b]] = Fraction(1)
            d0.append(row)
            oriented[(a, b)] = (e, 1)
            oriented[(b, a)] = (e, -1)
        d1: Matrix = []
        for t, triangle in enumerate(triangles):
            if len(triangle) != 3:
                raise ValueError(f"triangle {t} must have three vertices")
            row = [Fraction(0)] * len(edges)
            i, j, k = triangle
            for u, v in ((i, j), (j, k), (k, i)):
                if (u, v) not in oriented:
                    raise ValueError(f"triangle {t} uses a missing edge ({u}, {v})")
                e, sign = oriented[(u, v)]
                row[e] += sign
            d1.append(row)
        gradient, potential = _project_onto_columns(d0, omega)
        if d1:
            curl, _ = _project_onto_columns(transpose(d1), omega)
        else:
            curl = [Fraction(0)] * len(omega)
        harmonic = [w - g - c for w, g, c in zip(omega, gradient, curl)]
        rank0 = rank_and_nullspace(d0, len(nodes))[0] if d0 else 0
        rank1 = rank_and_nullspace(d1, len(edges))[0] if d1 else 0
        checks = {
            "chain_complex_d1_d0_is_zero": all(x == 0 for row in mat_mul(d1, d0) for x in row) if d1 else True,
            "reconstruction": all(g + c + h == w for w, g, c, h in zip(omega, gradient, curl, harmonic)),
            "gradient_equals_d0_of_potential": (mat_vec(d0, potential) == gradient) if d0 and potential else not any(gradient),
            "harmonic_divergence_free": all(x == 0 for x in mat_vec(transpose(d0), harmonic)) if d0 else True,
            "harmonic_curl_free": all(x == 0 for x in mat_vec(d1, harmonic)) if d1 else True,
            "gradient_curl_orthogonal": _dot(gradient, curl) == 0,
            "gradient_harmonic_orthogonal": _dot(gradient, harmonic) == 0,
            "curl_harmonic_orthogonal": _dot(curl, harmonic) == 0,
        }
        return {
            "gradient": gradient,
            "curl": curl,
            "harmonic": harmonic,
            "potential": potential,
            "dimensions": {
                "edges": len(edges),
                "gradient_space": rank0,
                "curl_space": rank1,
                "harmonic_space": len(edges) - rank0 - rank1,
            },
            "norms_sq": {
                "flow": norm_sq(omega),
                "gradient": norm_sq(gradient),
                "curl": norm_sq(curl),
                "harmonic": norm_sq(harmonic),
            },
            "identities_verified": checks,
            "verified": all(checks.values()),
        }

    @classmethod
    def sanitize_side_channels(cls, bus_trace: Sequence[Any]) -> Dict[str, Any]:
        """Exact Hodge decomposition of a trace on C_n (name kept for existing callers).

        Returns the projection onto the gradient subspace (trace minus its mean), the
        residual (harmonic part, the mean), a potential whose coboundary is the
        projection, exact squared norms and the identities that were verified.
        Nothing is sanitised: see the class docstring.
        """
        started = time.perf_counter_ns()
        trace = cls._read_trace(bus_trace)
        if not trace:
            return {
                "evaluated": False,
                "status": "EMPTY_TRACE",
                "samples": 0,
                "scope": "no samples supplied; nothing was decomposed",
            }
        parts = cls._cycle_parts(trace)
        gradient, harmonic = parts["gradient"], parts["harmonic"]
        checks = cls.verify_cycle_decomposition(trace, gradient, harmonic, parts["potential"])
        total, projected, residual = norm_sq(trace), norm_sq(gradient), norm_sq(harmonic)
        checks["pythagoras"] = total == projected + residual
        verified = all(checks.values())
        return {
            "evaluated": True,
            "method": (
                "exact Hodge decomposition on the oriented cycle graph C_n (sample i is the value on edge "
                "i -> i+1 mod n); C_n has no 2-cells, so trace = gradient part + harmonic part"
            ),
            "samples": len(trace),
            "projection_subspace": "gradient flows im(d0): traces whose samples sum to zero",
            "projection": [fraction_str(x) for x in gradient],
            "residual_subspace": "harmonic flows ker(d0^T): constant traces",
            "residual": [fraction_str(x) for x in harmonic],
            "potential": [fraction_str(x) for x in parts["potential"]],
            "mean": fraction_str(parts["mean"]),
            "trace_norm_sq": fraction_str(total),
            "projection_norm_sq": fraction_str(projected),
            "residual_norm_sq": fraction_str(residual),
            "projection_share_of_norm_sq_decimal": decimal_string(projected / total, 6) if total else None,
            "identities_verified": checks,
            "status": "DECOMPOSITION_VERIFIED" if verified else "DECOMPOSITION_CHECK_FAILED",
            "compute_time_us_measured": _elapsed_us(started),
            "scope": (
                "A timing or power side channel is carried by a trace's variation, which is the projection "
                "kept here. This decomposition does not detect, bound or remove any side channel."
            ),
        }


# ==============================================================================
# 3. EXACT p-ADIC VALUATIONS, DISTANCES AND BALLS OF INTEGER ADDRESSES
# ==============================================================================

MAX_BALL_EXPONENT = 64


def p_adic_valuation(n: int, p: int) -> Optional[int]:
    """Largest k with p^k | n, for n != 0; ``None`` for n = 0 (0 has no finite valuation)."""
    n = _integer(n, "n")
    if n == 0:
        return None
    n = abs(n)
    k = 0
    while n % p == 0:
        n //= p
        k += 1
    return k


class UltrametricMemorySandbox:
    """Exact p-adic distances between integer addresses; name kept for existing callers.

    |x|_p = p^(-v_p(x)) and d(x, y) = |x - y|_p satisfy the strong triangle
    inequality d(x, z) <= max(d(x, y), d(y, z)). An enclave registered with centre
    c and exponent k is the closed ball B(c, p^-k) = {c + j p^k : j an integer},
    i.e. one residue class mod p^k. Two closed balls are either disjoint or nested,
    and ``verify_non_overlapping_isolation`` decides which, exactly.

    That is the only property checked: whether two strided sets of integers share
    an element. It says nothing about how a machine isolates memory (page tables,
    caches, speculative execution) and is not a memory-isolation control.
    """

    def __init__(self, prime_p: int = 257) -> None:
        prime_p = _integer(prime_p, "prime_p")
        if not is_prime(prime_p):
            raise ValueError("prime_p must be a prime number")
        self.p = prime_p
        self._enclaves: Dict[Hashable, Tuple[int, int]] = {}

    def register_enclave(self, enclave_id: Hashable, base_address: int, ball_exponent: int = 1) -> Dict[str, Any]:
        """Register the closed ball B(base_address, p^-ball_exponent); re-registering replaces it."""
        center = _integer(base_address, "base_address")
        exponent = _integer(ball_exponent, "ball_exponent")
        if not 1 <= exponent <= MAX_BALL_EXPONENT:
            raise ValueError(f"ball_exponent must be between 1 and {MAX_BALL_EXPONENT}")
        self._enclaves[enclave_id] = (center, exponent)
        return self._describe(enclave_id)

    def _describe(self, enclave_id: Hashable) -> Dict[str, Any]:
        center, exponent = self._enclaves[enclave_id]
        modulus = self.p**exponent
        return {
            "enclave": enclave_id,
            "center": center,
            "exponent_k": exponent,
            "radius": fraction_str(Fraction(1, modulus)),
            "address_set": f"{center % modulus} mod {self.p}^{exponent}",
        }

    def p_adic_valuation(self, n: int) -> Optional[int]:
        return p_adic_valuation(n, self.p)

    def p_adic_absolute_value(self, n: int) -> Fraction:
        k = self.p_adic_valuation(n)
        return Fraction(0) if k is None else Fraction(1, self.p**k)

    def p_adic_distance(self, addr_a: int, addr_b: int) -> Fraction:
        """d_p(a, b) = |a - b|_p as an exact rational (0 when a = b)."""
        return self.p_adic_absolute_value(_integer(addr_a, "addr_a") - _integer(addr_b, "addr_b"))

    def ball_relation(self, center_a: int, exponent_a: int, center_b: int, exponent_b: int) -> str:
        """'disjoint', 'equal', 'a_inside_b' or 'b_inside_a' for B(c_a, p^-k_a) and B(c_b, p^-k_b)."""
        k = self.p_adic_valuation(center_a - center_b)
        if k is not None and k < min(exponent_a, exponent_b):
            return "disjoint"
        if exponent_a == exponent_b:
            return "equal"
        return "a_inside_b" if exponent_a > exponent_b else "b_inside_a"

    def verify_non_overlapping_isolation(self, enclave_a: Hashable, enclave_b: Hashable) -> Dict[str, Any]:
        """Decide exactly whether the address sets of two registered enclaves intersect."""
        for name in (enclave_a, enclave_b):
            if name not in self._enclaves:
                raise ValueError(f"unknown enclave {name!r}; register it first")
        (center_a, k_a), (center_b, k_b) = self._enclaves[enclave_a], self._enclaves[enclave_b]
        relation = self.ball_relation(center_a, k_a, center_b, k_b)
        disjoint = relation == "disjoint"
        return {
            "metric": f"{self.p}-adic distance d(x, y) = |x - y|_{self.p} on integer addresses (exact)",
            "enclave_a": enclave_a,
            "enclave_b": enclave_b,
            "ball_a": self._describe(enclave_a),
            "ball_b": self._describe(enclave_b),
            "center_difference": center_a - center_b,
            "valuation_of_center_difference": self.p_adic_valuation(center_a - center_b),
            "p_adic_distance": fraction_str(self.p_adic_distance(center_a, center_b)),
            "relation": relation,
            "balls_disjoint": disjoint,
            "property_checked": (
                "whether the address sets {c + j*p^k : j an integer} of the two enclaves share an element; "
                "closed p-adic balls are disjoint or nested, decided by comparing v_p(c_a - c_b) with the exponents"
            ),
            "status": "ADDRESS_SETS_DISJOINT" if disjoint else "ADDRESS_SETS_INTERSECT",
            "not_established": (
                "memory isolation by hardware or an operating system, page-table or cache separation, "
                "and any resistance to speculative-execution attacks"
            ),
        }


# ==============================================================================
# 4. ZEROISATION OF MUTABLE BUFFERS; OPTIONAL REVERSIBLE CAT-MAP PERMUTATION
# ==============================================================================

_CAT_MAP = (2, 1, 1, 1)
_CAT_MAP_INVERSE = (1, -1, -1, 2)


def _mat2_mul(x: Tuple[int, int, int, int], y: Tuple[int, int, int, int], m: int) -> Tuple[int, int, int, int]:
    return (
        (x[0] * y[0] + x[1] * y[2]) % m,
        (x[0] * y[1] + x[1] * y[3]) % m,
        (x[2] * y[0] + x[3] * y[2]) % m,
        (x[2] * y[1] + x[3] * y[3]) % m,
    )


def _mat2_pow(x: Tuple[int, int, int, int], exponent: int, m: int) -> Tuple[int, int, int, int]:
    result = (1 % m, 0, 0, 1 % m)
    base = tuple(v % m for v in x)
    while exponent:
        if exponent & 1:
            result = _mat2_mul(result, base, m)
        base = _mat2_mul(base, base, m)
        exponent >>= 1
    return result


@lru_cache(maxsize=32)
def _cat_map_period(modulus: int) -> int:
    """Smallest t >= 1 with A^t = I mod ``modulus`` for A = [[2, 1], [1, 1]] (A is the square of
    the Fibonacci matrix, so t <= Pisano period <= 6 * modulus)."""
    identity = (1, 0, 0, 1)
    current = _CAT_MAP
    for t in range(1, 6 * modulus + 1):
        if current == identity:
            return t
        current = _mat2_mul(_CAT_MAP, current, modulus)
    raise RuntimeError("cat map period not found within the Pisano bound")


class AnosovColdBootScrambler:
    """Zeroisation of a mutable buffer, plus an optional reversible cat-map permutation.

    Name kept for existing callers. ``emergency_ram_purge`` overwrites a
    ``bytearray`` (or writable ``memoryview``) with zeros in place and reads it back
    to verify. An immutable ``bytes`` object cannot be overwritten, so it is reported
    as not zeroised. Only the given buffer is affected: other copies (the caller's
    objects, interpreter or operating-system buffers, swap, CPU caches) and DRAM
    remanence are out of scope, and no cold-boot resistance or latency is claimed.

    The Arnold cat map A = [[2, 1], [1, 1]] (det 1, trace 3) acts on byte pairs
    mod 256 as a bijection; ``scramble_bytes`` / ``unscramble_bytes`` apply it and
    its inverse [[1, -1], [-1, 2]]. A^t is the identity after the period returned by
    ``map_period`` (192 for modulus 256), so scrambling is reversible and is not
    erasure.
    """

    A00: int = 2
    A01: int = 1
    A10: int = 1
    A11: int = 1
    P: int = 257
    BYTE_MODULUS: int = 256

    @classmethod
    def _modulus(cls, modulus: Optional[int]) -> int:
        m = cls.P if modulus is None else _integer(modulus, "modulus")
        if not 2 <= m <= 1 << 20:
            raise ValueError("modulus must be between 2 and 2^20")
        return m

    @classmethod
    def iterate_arnold_map(cls, x: int, y: int, iterations: int = 8, modulus: Optional[int] = None) -> Tuple[int, int]:
        """(x, y) -> (2x + y, x + y) mod ``modulus`` (default 257), applied ``iterations`` times."""
        m = cls._modulus(modulus)
        if _integer(iterations, "iterations") < 0:
            raise ValueError("iterations must be non-negative")
        a = _mat2_pow(_CAT_MAP, iterations, m)
        x, y = _integer(x, "x") % m, _integer(y, "y") % m
        return (a[0] * x + a[1] * y) % m, (a[2] * x + a[3] * y) % m

    @classmethod
    def inverse_arnold_map(cls, x: int, y: int, iterations: int = 8, modulus: Optional[int] = None) -> Tuple[int, int]:
        """Inverse of ``iterate_arnold_map``: (x, y) -> (x - y, 2y - x) mod ``modulus``, ``iterations`` times."""
        m = cls._modulus(modulus)
        if _integer(iterations, "iterations") < 0:
            raise ValueError("iterations must be non-negative")
        a = _mat2_pow(_CAT_MAP_INVERSE, iterations, m)
        x, y = _integer(x, "x") % m, _integer(y, "y") % m
        return (a[0] * x + a[1] * y) % m, (a[2] * x + a[3] * y) % m

    @classmethod
    def map_period(cls, modulus: Optional[int] = None) -> int:
        """Exact period of the cat map mod ``modulus``: the order of A in SL_2(Z/modulus)."""
        return _cat_map_period(cls._modulus(modulus))

    @classmethod
    def _apply_to_pairs(cls, data: Any, matrix: Tuple[int, int, int, int], rounds: int) -> bytes:
        if _integer(rounds, "rounds") < 0:
            raise ValueError("rounds must be non-negative")
        out = bytearray(data)
        a = _mat2_pow(matrix, rounds, cls.BYTE_MODULUS)
        for i in range(0, len(out) - 1, 2):
            x, y = out[i], out[i + 1]
            out[i] = (a[0] * x + a[1] * y) % cls.BYTE_MODULUS
            out[i + 1] = (a[2] * x + a[3] * y) % cls.BYTE_MODULUS
        return bytes(out)

    @classmethod
    def scramble_bytes(cls, data: Any, rounds: int = 1) -> bytes:
        """Apply the cat map ``rounds`` times to consecutive byte pairs mod 256 (a trailing odd byte is kept)."""
        return cls._apply_to_pairs(data, _CAT_MAP, rounds)

    @classmethod
    def unscramble_bytes(cls, data: Any, rounds: int = 1) -> bytes:
        """Exact inverse of ``scramble_bytes`` with the same ``rounds``."""
        return cls._apply_to_pairs(data, _CAT_MAP_INVERSE, rounds)

    @classmethod
    def zeroise(cls, buffer: Any) -> Dict[str, Any]:
        """Overwrite a writable byte buffer with zeros in place, then read every byte back."""
        if isinstance(buffer, memoryview):
            if buffer.readonly:
                raise TypeError("read-only memoryview cannot be zeroised")
            view = buffer.cast("B")
        elif isinstance(buffer, bytearray):
            view = buffer
        else:
            raise TypeError("zeroise needs a bytearray or a writable memoryview")
        length = len(view)
        view[:] = bytes(length)
        nonzero = sum(1 for byte in view if byte)
        return {"buffer_length": length, "nonzero_bytes_after": nonzero, "zeroised_in_place": nonzero == 0}

    @classmethod
    def emergency_ram_purge(cls, secret_bytes: Any) -> Dict[str, Any]:
        """Zeroise ``secret_bytes`` in place when it is mutable; report honestly when it is not.

        Name kept for existing callers. No scrambling is applied: see the class docstring.
        """
        started = time.perf_counter_ns()
        mutable = isinstance(secret_bytes, bytearray) or (
            isinstance(secret_bytes, memoryview) and not secret_bytes.readonly
        )
        if mutable:
            outcome = cls.zeroise(secret_bytes)
            status = "ZEROISED_AND_VERIFIED" if outcome["zeroised_in_place"] else "ZEROISATION_VERIFY_FAILED"
            reason = None
        elif isinstance(secret_bytes, (bytes, memoryview)):
            outcome = {"buffer_length": len(secret_bytes), "nonzero_bytes_after": None, "zeroised_in_place": False}
            status = "NOT_ZEROISED_IMMUTABLE_INPUT"
            reason = (
                "an immutable bytes object (or read-only memoryview) cannot be overwritten; pass a bytearray "
                "or writable memoryview to zeroise it in place"
            )
        else:
            raise TypeError("expected bytes, bytearray or memoryview")
        return {
            "operation": "in-place zeroisation of a mutable buffer with read-back verification",
            "input_type": type(secret_bytes).__name__,
            "buffer_length": outcome["buffer_length"],
            "zeroised_in_place": outcome["zeroised_in_place"],
            "nonzero_bytes_after": outcome["nonzero_bytes_after"],
            "status": status,
            "reason": reason,
            "cat_map_scramble": {
                "applied": False,
                "note": "the Arnold cat map is a reversible permutation of byte pairs, not erasure; "
                "it is available separately as scramble_bytes / unscramble_bytes",
                "period_mod_256": cls.map_period(cls.BYTE_MODULUS),
            },
            "not_established": (
                "erasure of other copies (the caller's objects, interpreter or operating-system buffers, swap, "
                "CPU caches), DRAM remanence, and any cold-boot or physical-probe resistance"
            ),
            "compute_time_us_measured": _elapsed_us(started),
        }


# ==============================================================================
# 5. PICARD-LEFSCHETZ "ANTI-JAMMING": NOT IMPLEMENTED
# ==============================================================================


class PicardLefschetzAntiJammingFilter:
    """Not implemented: there is no anti-jamming filter in this package.

    Name and signature kept for existing callers. Picard-Lefschetz theory deforms
    the integration contour of an oscillatory integral onto steepest-descent paths
    (Lefschetz thimbles); it is not a signal filter, and this package has no jamming
    model, receiver chain or measurement to filter. The method validates its input
    (finite numeric I/Q pairs) and returns ``NOT_IMPLEMENTED``; it returns no
    samples and no signal-quality figure.
    """

    MAX_SAMPLES = 1 << 16

    @classmethod
    def filter_jammed_waveform(
        cls,
        signal_iq_samples: Sequence[Sequence[Any]],
        jamming_phase_intensity: Any = Fraction(5, 2),
    ) -> Dict[str, Any]:
        samples = [list(sample) for sample in signal_iq_samples]
        if len(samples) > cls.MAX_SAMPLES:
            raise ValueError(f"at most {cls.MAX_SAMPLES} samples are supported")
        for sample in samples:
            if len(sample) != 2:
                raise ValueError("each I/Q sample must be a pair (I, Q)")
            to_vector(sample)
        intensity = to_fraction(jamming_phase_intensity)
        return {
            "status": NOT_IMPLEMENTED,
            "requested_operation": "anti-jamming restoration of I/Q samples via Picard-Lefschetz thimbles",
            "reason": (
                "no anti-jamming filter is implemented: Picard-Lefschetz theory concerns contour deformation "
                "of oscillatory integrals, and there is no jamming model, receiver chain or measurement here"
            ),
            "input_samples": len(samples),
            "input_validated": True,
            "jamming_phase_intensity": fraction_str(intensity),
            "jamming_phase_intensity_used": False,
        }
