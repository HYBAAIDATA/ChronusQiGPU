"""Exact cellular sheaves on graphs, computed over the rationals.

A cellular sheaf on a graph G = (V, E) assigns a stalk Q^d to every vertex and
edge, and to every incidence v <| e a restriction map F_{v<|e}: Q^d -> Q^d.
For an oriented edge e = (a, b) the coboundary of a 0-cochain s is

    (delta^0 s)_e = F_{b<|e} s_b - F_{a<|e} s_a.

Facts used by AL HARAS, all computed exactly:

* s is a global section (agents/nodes agree) iff delta^0 s = 0.
  The per-edge residuals locate *where* agreement fails.
* dim H^0 = dim ker delta^0, obtained from the holonomy of the restriction maps
  around the fundamental cycles of a spanning forest.
* dim H^1 = dim H^0 - chi with chi = |V| d - |E| d (a graph has no 2-cells).
* An edge cochain c (for example, observed pairwise relations) represents the
  zero class of H^1 iff c = delta^0 s for some s. A non-zero class is a genuine
  cohomological obstruction: no assignment of node states explains c. Note that
  a coboundary delta^0 s is *always* the zero class, so inconsistent node states
  are detected by delta^0 s != 0, not by a non-zero H^1 class.
* The nearest global section (orthogonal projection onto H^0) repairs a state
  in place; with orthogonal restriction maps it has a closed form.

Restriction maps must be orthogonal (checked exactly), which covers the
Stiefel-frame maps described in the AL HARAS notes.
"""

from collections import deque
from fractions import Fraction
from typing import Any, Dict, List, Optional, Sequence, Tuple

from chronus.security.al_haras.exact import (
    Matrix,
    Vector,
    identity,
    is_orthogonal,
    mat_mul,
    mat_vec,
    norm_sq,
    rank_and_nullspace,
    solve_linear,
    sqrt_decimal_string,
    to_vector,
    transpose,
    vec_sub,
)

MAX_NODES = 256
MAX_EDGES = 2048
MAX_STALK_DIM = 64


class SheafError(ValueError):
    """Invalid sheaf construction or input."""


class GraphSheaf:
    def __init__(
        self,
        nodes: Sequence[str],
        edges: Sequence[Tuple[str, str]],
        stalk_dim: int,
        restriction_maps: Optional[Dict[Tuple[int, str], Matrix]] = None,
    ) -> None:
        if stalk_dim < 1 or stalk_dim > MAX_STALK_DIM:
            raise SheafError(f"stalk dimension must be between 1 and {MAX_STALK_DIM}")
        if len(nodes) > MAX_NODES or len(edges) > MAX_EDGES:
            raise SheafError("graph exceeds the supported size")
        if len(set(nodes)) != len(nodes):
            raise SheafError("node identifiers must be unique")
        self.nodes: List[str] = list(nodes)
        self.index = {n: i for i, n in enumerate(self.nodes)}
        self.edges: List[Tuple[str, str]] = []
        for a, b in edges:
            if a not in self.index or b not in self.index:
                raise SheafError(f"edge ({a}, {b}) references an unknown node")
            if a == b:
                raise SheafError("self-loops are not supported")
            self.edges.append((a, b))
        self.dim = stalk_dim
        # None stands for the identity map (constant sheaf); other maps are stored exactly.
        self._maps: Dict[Tuple[int, str], Optional[Matrix]] = {}
        supplied = restriction_maps or {}
        ident = identity(stalk_dim)
        for key, m in supplied.items():
            e, v = key
            if not (0 <= e < len(self.edges)) or v not in self.edges[e]:
                raise SheafError(f"restriction map key {key} does not match an incidence")
            if len(m) != stalk_dim or any(len(row) != stalk_dim for row in m):
                raise SheafError(f"restriction map for edge {e} at {v} has the wrong shape")
            m = [[Fraction(x) for x in row] for row in m]
            if not is_orthogonal(m):
                raise SheafError(f"restriction map for edge {e} at {v} is not orthogonal")
            self._maps[(e, v)] = None if m == ident else m
        self._forest_cache = None

    @property
    def maps(self) -> Dict[Tuple[int, str], Matrix]:
        """Every incidence map, identities materialised (for inspection)."""
        ident = identity(self.dim)
        return {
            (e, v): (self._maps.get((e, v)) or ident)
            for e, (a, b) in enumerate(self.edges)
            for v in (a, b)
        }

    def _apply(self, e: int, v: str, vec: Vector) -> Vector:
        m = self._maps.get((e, v))
        return list(vec) if m is None else mat_vec(m, vec)

    def _apply_t(self, e: int, v: str, vec: Vector) -> Vector:
        m = self._maps.get((e, v))
        return list(vec) if m is None else mat_vec(transpose(m), vec)

    def _mat(self, e: int, v: str) -> Matrix:
        return self._maps.get((e, v)) or identity(self.dim)

    # ------------------------------------------------------------------ helpers
    @classmethod
    def ring(cls, nodes: Sequence[str], stalk_dim: int) -> "GraphSheaf":
        """Constant sheaf on the cycle n0 -> n1 -> ... -> n0 (legacy topology)."""
        n = len(nodes)
        edges = [(nodes[i], nodes[(i + 1) % n]) for i in range(n)] if n > 1 else []
        return cls(nodes, edges, stalk_dim)

    def section(self, values: Dict[str, Sequence[Any]]) -> Dict[str, Vector]:
        missing = [n for n in self.nodes if n not in values]
        if missing:
            raise SheafError(f"missing node states: {missing}")
        out: Dict[str, Vector] = {}
        for n in self.nodes:
            vec = to_vector(values[n])
            if len(vec) != self.dim:
                raise SheafError(f"state for {n} has dimension {len(vec)}, expected {self.dim}")
            out[n] = vec
        return out

    def _neighbours(self):
        adj: Dict[str, List[Tuple[int, str]]] = {n: [] for n in self.nodes}
        for e, (a, b) in enumerate(self.edges):
            adj[a].append((e, b))
            adj[b].append((e, a))
        return adj

    def _forest(self):
        """Spanning forest with orthogonal transports T_v from each root frame.

        ``None`` encodes the identity transport, so constant sheaves stay cheap.
        """
        if self._forest_cache is not None:
            return self._forest_cache
        adj = self._neighbours()
        transport: Dict[str, Optional[Matrix]] = {}
        parent_edge: Dict[str, Optional[int]] = {}
        component: Dict[str, int] = {}
        components: List[List[str]] = []
        tree_edges = set()
        for root in self.nodes:
            if root in transport:
                continue
            cid = len(components)
            components.append([root])
            transport[root] = None
            parent_edge[root] = None
            component[root] = cid
            queue = deque([root])
            while queue:
                u = queue.popleft()
                for e, v in adj[u]:
                    if v in transport:
                        continue
                    # F_v T_v = F_u T_u  =>  T_v = F_v^T F_u T_u
                    fu, fv, tu = self._maps.get((e, u)), self._maps.get((e, v)), transport[u]
                    if fu is None and fv is None and tu is None:
                        t_v = None
                    else:
                        t_v = mat_mul(transpose(self._mat(e, v)), mat_mul(self._mat(e, u), tu or identity(self.dim)))
                    transport[v] = t_v
                    parent_edge[v] = e
                    component[v] = cid
                    components[cid].append(v)
                    tree_edges.add(e)
                    queue.append(v)
        self._forest_cache = (transport, parent_edge, component, components, tree_edges)
        return self._forest_cache

    def _holonomy_rows(self, cid: int) -> Matrix:
        """Constraint rows (F_b T_b - F_a T_a) for the non-tree edges of a component."""
        transport, _, component, _, tree_edges = self._forest()
        rows: Matrix = []
        for e, (a, b) in enumerate(self.edges):
            if e in tree_edges or component[a] != cid:
                continue
            if self._maps.get((e, a)) is None and self._maps.get((e, b)) is None and transport[a] is None and transport[b] is None:
                continue  # identity holonomy: no constraint
            ident = identity(self.dim)
            lhs = mat_mul(self._mat(e, b), transport[b] or ident)
            rhs = mat_mul(self._mat(e, a), transport[a] or ident)
            rows.extend(r for r in vec_sub_mat(lhs, rhs) if any(x != 0 for x in r))
        return rows

    # --------------------------------------------------------------- operators
    def coboundary(self, section: Dict[str, Vector]) -> List[Vector]:
        return [
            vec_sub(self._apply(e, b, section[b]), self._apply(e, a, section[a]))
            for e, (a, b) in enumerate(self.edges)
        ]

    def cohomology_dimensions(self) -> Dict[str, int]:
        _, _, _, components, _ = self._forest()
        h0 = 0
        for cid in range(len(components)):
            rows = self._holonomy_rows(cid)
            rank = rank_and_nullspace(rows, self.dim)[0] if rows else 0
            h0 += self.dim - rank
        chi = len(self.nodes) * self.dim - len(self.edges) * self.dim
        return {"h0": h0, "h1": h0 - chi, "euler_characteristic": chi}

    def disagreement(self, section: Dict[str, Vector]) -> Dict[str, Any]:
        cob = self.coboundary(section)
        per_edge = [norm_sq(v) for v in cob]
        total = sum(per_edge, Fraction(0))
        worst = max(range(len(per_edge)), key=lambda i: per_edge[i]) if per_edge else None
        energy = {n: Fraction(0) for n in self.nodes}
        for e, (a, b) in enumerate(self.edges):
            energy[a] += per_edge[e]
            energy[b] += per_edge[e]
        return {
            "coboundary": cob,
            "edge_norm_sq": per_edge,
            "total_norm_sq": total,
            "worst_edge": worst,
            "node_energy": energy,
        }

    def harmonic_projection(self, section: Dict[str, Vector]) -> Dict[str, Vector]:
        """Orthogonal projection of ``section`` onto the global sections H^0."""
        transport, _, _, components, _ = self._forest()
        projected: Dict[str, Vector] = {}
        for cid, members in enumerate(components):
            rows = self._holonomy_rows(cid)
            basis = rank_and_nullspace(rows, self.dim)[1] if rows else None
            pulled = [Fraction(0)] * self.dim
            for v in members:
                t = transport[v]
                pulled = [x + y for x, y in zip(pulled, section[v] if t is None else mat_vec(transpose(t), section[v]))]
            if basis is None:
                # no holonomy constraint: H^0 frame is all of Q^d, projection = transported mean
                x = [c / len(members) for c in pulled]
            elif not basis:
                x = [Fraction(0)] * self.dim
            else:
                # minimise sum_v |s_v - T_v B y|^2  =>  |C| (B^T B) y = B^T sum_v T_v^T s_v
                bmat = transpose(basis)  # d x k
                gram = mat_mul(transpose(bmat), bmat)
                normal = [[g * len(members) for g in row] for row in gram]
                y = solve_linear(normal, mat_vec(transpose(bmat), pulled), len(basis))
                x = mat_vec(bmat, y)
            for v in members:
                t = transport[v]
                projected[v] = list(x) if t is None else mat_vec(t, x)
        return projected

    def is_coboundary(self, cochain: Sequence[Sequence[Any]]) -> Dict[str, Any]:
        """Decide whether an edge cochain c is exact (zero class in H^1)."""
        if len(cochain) != len(self.edges):
            raise SheafError("cochain must assign a vector to every edge")
        c = [to_vector(v) for v in cochain]
        if any(len(v) != self.dim for v in c):
            raise SheafError("cochain vectors must match the stalk dimension")
        transport, parent_edge, component, components, tree_edges = self._forest()
        # s_v = T_v x_root + p_v ; propagate particular solutions along the forest
        particular: Dict[str, Vector] = {}
        for members in components:
            particular[members[0]] = [Fraction(0)] * self.dim
            for v in members[1:]:
                e = parent_edge[v]
                a, b = self.edges[e]
                u = a if v == b else b
                if v == b:  # F_b s_b - F_a s_a = c_e  => s_b = F_b^T (c_e + F_a s_a)
                    rhs = [x + y for x, y in zip(c[e], self._apply(e, a, particular[u]))]
                    particular[v] = self._apply_t(e, b, rhs)
                else:  # s_a = F_a^T (F_b s_b - c_e)
                    rhs = vec_sub(self._apply(e, b, particular[u]), c[e])
                    particular[v] = self._apply_t(e, a, rhs)
        exact = True
        defects: List[Dict[str, Any]] = []
        for cid, members in enumerate(components):
            rows: Matrix = []
            rhs_all: Vector = []
            cycle_edges: List[int] = []
            for e, (a, b) in enumerate(self.edges):
                if e in tree_edges or component[a] != cid:
                    continue
                ident = identity(self.dim)
                lhs = vec_sub_mat(
                    mat_mul(self._mat(e, b), transport[b] or ident), mat_mul(self._mat(e, a), transport[a] or ident)
                )
                g = vec_sub(vec_sub(self._apply(e, b, particular[b]), self._apply(e, a, particular[a])), c[e])
                rows.extend(lhs)
                rhs_all.extend(-x for x in g)
                cycle_edges.append(e)
                if all(x == 0 for row in lhs for x in row) and any(x != 0 for x in g):
                    defects.append({"edge": e, "nodes": [a, b], "cycle_defect_norm_sq": norm_sq(g)})
            if rows and solve_linear(rows, rhs_all, self.dim) is None:
                exact = False
                if not any(d["edge"] in cycle_edges for d in defects):
                    defects.append({"edge": None, "nodes": members, "cycle_defect_norm_sq": None})
        return {"is_coboundary": exact, "fundamental_cycle_defects": defects}

    def isolate(self, section: Dict[str, Vector], max_candidates: int = MAX_NODES) -> List[str]:
        """Nodes whose removal leaves the remaining states consistent (exact check)."""
        bad_edges = [e for e, v in enumerate(self.coboundary(section)) if any(x != 0 for x in v)]
        found = []
        for n in self.nodes[:max_candidates]:
            if all(n in self.edges[e] for e in bad_edges):
                found.append(n)
        return found


def vec_sub_mat(a: Matrix, b: Matrix) -> Matrix:
    return [vec_sub(r1, r2) for r1, r2 in zip(a, b)]


def analyse_states(
    states: Dict[str, Sequence[Any]],
    edges: Optional[Sequence[Tuple[str, str]]] = None,
    tolerance: Any = 0,
    restriction_maps: Optional[Dict[Tuple[int, str], Matrix]] = None,
) -> Dict[str, Any]:
    """Full, exact consistency analysis of node states on a graph.

    ``tolerance`` bounds the per-edge residual norm that is still accepted as
    agreement; the default 0 demands exact agreement.
    """
    nodes = list(states.keys())
    if not nodes:
        raise SheafError("no node states supplied")
    dims = {len(list(v)) for v in states.values()}
    if len(dims) != 1:
        raise SheafError("all node states must have the same dimension")
    dim = dims.pop()
    sheaf = (
        GraphSheaf(nodes, list(edges), dim, restriction_maps)
        if edges is not None
        else GraphSheaf.ring(nodes, dim)
    )
    section = sheaf.section(states)
    tol = to_vector([tolerance])[0]
    if tol < 0:
        raise SheafError("tolerance must be non-negative")
    dis = sheaf.disagreement(section)
    worst_sq = dis["edge_norm_sq"][dis["worst_edge"]] if dis["worst_edge"] is not None else Fraction(0)
    consistent = worst_sq <= tol * tol
    dims_h = sheaf.cohomology_dimensions()
    projection = sheaf.harmonic_projection(section) if not consistent else section
    repair_sq = sum((norm_sq(vec_sub(section[n], projection[n])) for n in nodes), Fraction(0))
    isolated = sheaf.isolate(section) if not consistent else []
    worst_edge = sheaf.edges[dis["worst_edge"]] if dis["worst_edge"] is not None and worst_sq > 0 else None
    return {
        "sheaf": sheaf,
        "section": section,
        "consistent": consistent,
        "tolerance": tol,
        "dimensions": dims_h,
        "edge_norm_sq": dis["edge_norm_sq"],
        "max_edge_norm_sq": worst_sq,
        "max_edge_norm": sqrt_decimal_string(worst_sq, 8),
        "total_norm_sq": dis["total_norm_sq"],
        "worst_edge": list(worst_edge) if worst_edge else None,
        "node_energy": dis["node_energy"],
        "nearest_global_section": projection,
        "repair_distance_sq": repair_sq,
        "repair_distance": sqrt_decimal_string(repair_sq, 8),
        "isolating_nodes": isolated,
    }
