# pythagoras/asi/causal_reasoning.py — NEW

from dataclasses import dataclass, field
from typing import Optional, Sequence

import numpy as np

from . import manifold_bridge as mb


@dataclass
class CausalModel:
    variables: list[str]
    edges: dict[str, list[str]]  # parent -> [children]
    functions: dict[str, callable]  # variable -> structural function
    noise: dict[str, callable] = field(default_factory=dict)

    @classmethod
    def from_adjacency(
        cls,
        adjacency: np.ndarray,
        names: Optional[Sequence[str]] = None,
        functions: Optional[dict] = None,
        exogenous: Optional[Sequence[float]] = None,
    ) -> "CausalModel":
        """Build an SCM directly from an adjacency matrix A in R^{N x N}.

        A[i, j] != 0 encodes the causal edge i -> j with strength |A[i, j]|.
        Default structural functions are the linear parents' sum
        f_j(pv) = sum_i A[i, j] * pv[x_i]; explicit ``functions`` override.
        ``exogenous`` supplies constant noise terms U_j.
        """
        adj = np.asarray(adjacency, dtype=np.float64)
        n = adj.shape[0]
        names = list(names) if names is not None else [f"x{i}" for i in range(n)]
        edges = {name: [] for name in names}
        for i in range(n):
            for j in np.nonzero(adj[i] != 0)[0]:
                edges[names[i]].append(names[int(j)])
        if functions is None:
            functions = {}
            for j in range(n):
                weights = {names[i]: float(adj[i, j]) for i in np.nonzero(adj[:, j] != 0)[0]}
                functions[names[j]] = lambda pv, w=weights: sum(
                    wij * pv.get(p, 0.0) for p, wij in w.items()
                )
        noise = {}
        if exogenous is not None:
            for j in range(n):
                noise[names[j]] = lambda e=float(exogenous[j]): e
        return cls(variables=names, edges=edges, functions=functions, noise=noise)


@dataclass
class ManifoldCausalResult:
    """Dual-mode result of a do-operation lifted onto B_phi^11."""

    state: np.ndarray  # post-intervention joint state, folded into the ball
    values: dict  # variable -> value under the severed graph
    adjacency: np.ndarray  # severed adjacency actually propagated
    intervened: tuple  # variables pinned by the do-operator
    interventions: dict = field(default_factory=dict)  # accumulated do-set
    exogenous: Optional[np.ndarray] = None  # ambient U field propagated

    def to_scalar(self) -> float:
        return mb.scalar_projection(self.state)

    @property
    def scalar(self) -> float:
        return self.to_scalar()


class CausalReasoningEngine:
    """Implements Pearl's three-rung ladder of causation.

    Rung 1: Association (seeing) — P(Y | X)
    Rung 2: Intervention (doing) — P(Y | do(X))
    Rung 3: Counterfactual (imagining) — P(Y_x | X=x', Y=y')

    Manifold mode: the structural causal model accepts arbitrary DAGs
    across the 11 dimensions of B_phi^11.  do(X) is realised as explicit
    edge severing on the adjacency matrix A (A'[:, X] = 0), and values
    propagate over the remaining topological order — so results are
    invariant under any re-sorting of the variable list.  Multi-variable
    interventions do(X_i = v_i, X_j = v_j) are a single severed
    propagation pass.
    """

    def __init__(self, model: CausalModel):
        self.model = model
        self._index = {v: i for i, v in enumerate(model.variables)}

    # ------------------------------------------------------------------
    # Graph views
    # ------------------------------------------------------------------

    @property
    def adjacency_matrix(self) -> np.ndarray:
        """A in {0,1}^{N x N}: A[i, j] = 1 iff i is a causal parent of j."""
        adj = np.zeros((len(self.model.variables),) * 2, dtype=np.float64)
        for parent, children in self.model.edges.items():
            i = self._index.get(parent)
            if i is None:
                continue
            for child in children:
                j = self._index.get(child)
                if j is not None:
                    adj[i, j] = 1.0
        return adj

    def topological_order(self) -> list[str]:
        """A topological ordering of the DAG (Kahn over the adjacency).

        Falls back to the declared variable order when the graph is
        cyclic — matching the previous lenient behaviour.
        """
        try:
            order_idx = mb.topological_sort(self.adjacency_matrix)
        except ValueError:
            return list(self.model.variables)
        return [self.model.variables[i] for i in order_idx]

    def severed_adjacency(self, do_vars: Sequence[str]) -> np.ndarray:
        """Pearl graph surgery: delete every edge INTO each do-variable."""
        idxs = [self._index[v] for v in do_vars if v in self._index]
        severed = mb.sever_incoming_edges(self.adjacency_matrix, idxs)
        return (severed != 0).astype(np.float64)

    def _parents(self, var: str) -> list[str]:
        return [p for p, children in self.model.edges.items() if var in children]

    def _eval_order(self) -> list[str]:
        order = self.topological_order()
        missing = [v for v in self.model.variables if v not in order]
        return order + missing

    @classmethod
    def from_manifold_state(
        cls, state: np.ndarray, threshold: Optional[float] = None
    ) -> "CausalReasoningEngine":
        """Lift an 11-D Poincaré state into a structural causal model.

        The state's golden covariance defines the DAG (bridge.state_to_graph);
        structural functions are the induced linear couplings, and the
        ambient preimage supplies the exogenous field U_j = unfold(x)_j.
        """
        ball = mb.as_ball_vector(state)
        adj = mb.state_to_graph(ball, threshold=threshold)
        exogenous = mb.unfold_ball_vector(ball)
        model = CausalModel.from_adjacency(adj, exogenous=exogenous)
        return cls(model)

    # ------------------------------------------------------------------
    # Pearl's three rungs (scalar contract — preserved)
    # ------------------------------------------------------------------

    def observe(self, evidence: dict) -> dict:
        """Rung 1: Compute conditional distributions given evidence."""
        result = {}
        for var in self._eval_order():
            if var in evidence:
                result[var] = evidence[var]
            else:
                parents = self._parents(var)
                parent_values = {p: result.get(p, evidence.get(p, 0)) for p in parents}
                result[var] = self.model.functions[var](parent_values)
        return result

    def intervene(self, do: dict, evidence: Optional[dict] = None) -> dict:
        """Rung 2: Compute post-intervention distribution P(Y | do(X=x)).

        do(X=x) means we CUT all edges into X and set X=x directly.
        This is fundamentally different from observing X=x.
        """
        result = {}
        evidence = evidence or {}
        for var in self._eval_order():
            if var in do:
                result[var] = do[var]  # intervened — ignore parents
            elif var in evidence:
                result[var] = evidence[var]
            else:
                parents = self._parents(var)
                parent_values = {p: result.get(p, evidence.get(p, 0)) for p in parents}
                result[var] = self.model.functions[var](parent_values)
        return result

    def counterfactual(self, do: dict, observed: dict) -> dict:
        """Rung 3: Given we observed X=x', Y=y', what would Y have been if X=x?

        1. Abduction: Infer noise values from observed evidence
        2. Action: Apply do(X=x) with inferred noise
        3. Prediction: Compute Y under modified model
        """
        # Step 1: Abduction — recover noise terms
        inferred_noise = {}
        for var in self._eval_order():
            if var in observed:
                parents = self._parents(var)
                parent_values = {p: observed.get(p, 0) for p in parents}
                expected = self.model.functions[var](parent_values)
                inferred_noise[var] = observed[var] - expected

        # Step 2+3: Action + Prediction with fixed noise
        result = {}
        for var in self._eval_order():
            if var in do:
                result[var] = do[var]
            else:
                parents = self._parents(var)
                parent_values = {p: result.get(p, observed.get(p, 0)) for p in parents}
                computed = self.model.functions[var](parent_values)
                result[var] = computed + inferred_noise.get(var, 0)
        return result

    # ------------------------------------------------------------------
    # Manifold operators (S-2 elevation)
    # ------------------------------------------------------------------

    def intervene_matrix(self, do: dict, evidence: Optional[dict] = None) -> dict:
        """Rung 2 computed through the severed adjacency matrix.

        Identical result to :meth:`intervene`, but the graph surgery is
        performed explicitly on A (incoming columns zeroed) and values are
        propagated along the topological order of the severed DAG.  This
        makes the result provably invariant under variable re-sorting.
        """
        evidence = evidence or {}
        severed = self.severed_adjacency(list(do.keys()))
        order = mb.topological_sort(severed)
        result = {}
        for idx in order:
            var = self.model.variables[idx]
            if var in do:
                result[var] = do[var]
            elif var in evidence:
                result[var] = evidence[var]
            else:
                parents = [self.model.variables[i] for i in np.nonzero(severed[:, idx] != 0)[0]]
                parent_values = {p: result.get(p, evidence.get(p, 0)) for p in parents}
                result[var] = self.model.functions[var](parent_values)
        return result

    def intervene_on_state(
        self,
        state: np.ndarray,
        do: dict,
        evidence: Optional[dict] = None,
        prior: Optional[ManifoldCausalResult] = None,
    ) -> ManifoldCausalResult:
        """do-calculus on an 11-D manifold state.

        ``state`` supplies the exogenous field U = unfold(x): each variable
        evaluates f_j(parents) + U_j under the severed DAG, intervened
        variables are pinned to their do-values, and the joint result is
        folded back into B_phi^11.  ``do`` may be keyed by variable name
        or integer dimension index; multiple entries compose a
        multi-variable intervention in a single propagation pass.

        Composition: pass a previous result as ``prior`` to apply a further
        intervention to the post-intervention model — Pearl's composition
        of do-operators.  The exogenous field U is inherited unchanged and
        the intervention sets union (later pins override), so
        ``intervene_on_state(r.state, {j: b}, prior=r)`` is exactly
        ``do(X_i = a, X_j = b)`` on the original state.
        """
        if len(self.model.variables) != mb.MANIFOLD_DIM:
            raise ValueError(
                "intervene_on_state requires an 11-variable model "
                f"(got {len(self.model.variables)}) — build one with "
                "from_manifold_state or CausalModel.from_adjacency"
            )
        do_named = {
            (self.model.variables[k] if isinstance(k, (int, np.integer)) else k): v
            for k, v in do.items()
        }
        if prior is not None:
            interventions = {**prior.interventions, **do_named}
            exogenous = prior.exogenous
        else:
            interventions = do_named
            exogenous = None
        severed = self.severed_adjacency(list(interventions.keys()))
        if exogenous is None:
            exogenous = mb.unfold_ball_vector(mb.as_ball_vector(state))
        evidence = evidence or {}

        order = mb.topological_sort(severed)
        result = {}
        for idx in order:
            var = self.model.variables[idx]
            if var in interventions:
                result[var] = interventions[var]
            else:
                parents = [self.model.variables[i] for i in np.nonzero(severed[:, idx] != 0)[0]]
                parent_values = {p: result.get(p, evidence.get(p, 0.0)) for p in parents}
                result[var] = self.model.functions[var](parent_values) + float(exogenous[idx])

        joint = np.array([result[v] for v in self.model.variables], dtype=np.float64)
        return ManifoldCausalResult(
            state=mb.fold_ambient_vector(joint),
            values=result,
            adjacency=severed,
            intervened=tuple(interventions.keys()),
            interventions=dict(interventions),
            exogenous=np.asarray(exogenous, dtype=np.float64),
        )

    def discover_causal_structure(self, data: list[dict]) -> dict:
        """Discover causal graph from observational data using conditional independence tests."""
        variables = list(data[0].keys()) if data else []
        edges = {}
        for v in variables:
            edges[v] = []
        # Simplified: if X and Y are dependent but become independent given Z, then Z is a confounder
        for i, x in enumerate(variables):
            for y in variables[i + 1 :]:
                if self._are_dependent(data, x, y):
                    # Check if dependency is mediated by another variable
                    mediated = False
                    for z in variables:
                        if z not in (x, y) and self._are_conditionally_independent(data, x, y, z):
                            mediated = True
                            break
                    if not mediated:
                        edges[x].append(y)
        return edges

    def _are_dependent(self, data, x, y) -> bool:
        # Simplified correlation check
        xs = [d[x] for d in data]
        ys = [d[y] for d in data]
        if len(xs) < 3:
            return False
        mean_x, mean_y = sum(xs) / len(xs), sum(ys) / len(ys)
        cov = sum((a - mean_x) * (b - mean_y) for a, b in zip(xs, ys)) / len(xs)
        return abs(cov) > 0.1

    def _are_conditionally_independent(self, data, x, y, z) -> bool:
        # Simplified: check if correlation disappears when stratifying on z
        z_values = set(d[z] for d in data)
        for zv in z_values:
            subset = [d for d in data if d[z] == zv]
            if len(subset) > 2 and self._are_dependent(subset, x, y):
                return False
        return True
