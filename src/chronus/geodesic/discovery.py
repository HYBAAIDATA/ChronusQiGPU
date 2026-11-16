"""Evidence-first symmetry matching and exact variational metric discovery.

Inputs are explicitly supplied problem distances/features. No unknown
manifold is assumed. Exact root-system classification is an invariant-
fingerprint candidate, not a proof of group isomorphism. Gradient flow
optimises a *fixed-coordinate constant positive-definite metric*, not
all smooth Riemannian metrics. Results carry the precise classification.

All optimization arithmetic is Fraction; every step checks Sylvester's
criterion, objective descent and the analytic gradient. No finite-difference
guessing, hidden floating-point tolerance or fabricated speedup.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Sequence

from chronus.geodesic.root_systems import catalog

Q = Fraction
Matrix = tuple[tuple[Q, ...], ...]


@dataclass(frozen=True)
class MetricConstraint:
    """One displacement vector with a measured/declared target squared length."""
    delta: tuple[Q, ...]
    target_squared: Q
    weight: Q = Q(1)

    def __post_init__(self):
        object.__setattr__(self, "delta", tuple(Q(x) for x in self.delta))
        object.__setattr__(self, "target_squared", Q(self.target_squared))
        object.__setattr__(self, "weight", Q(self.weight))
        if not self.delta or self.target_squared < 0 or self.weight <= 0:
            raise ValueError("constraint needs nonempty delta, nonnegative squared distance and positive weight")


def exact_determinant(matrix: Matrix) -> Q:
    """Exact Fraction Gaussian elimination with row swaps."""
    n = len(matrix)
    if any(len(row) != n for row in matrix):
        raise ValueError("determinant requires square matrix")
    a = [[Q(value) for value in row] for row in matrix]
    det = Q(1)
    for c in range(n):
        pivot = next((r for r in range(c, n) if a[r][c]), None)
        if pivot is None:
            return Q(0)
        if pivot != c:
            a[c], a[pivot] = a[pivot], a[c]
            det = -det
        p = a[c][c]
        det *= p
        for r in range(c+1, n):
            factor = a[r][c]/p
            for j in range(c, n):
                a[r][j] -= factor * a[c][j]
    return det


def is_spd(metric: Matrix) -> bool:
    n = len(metric)
    return (
        n > 0 and all(len(row) == n for row in metric) and
        all(metric[i][j] == metric[j][i] for i in range(n) for j in range(n)) and
        all(exact_determinant(tuple(tuple(metric[i][j] for j in range(k))
                             for i in range(k))) > 0 for k in range(1, n+1))
    )


def identity_metric(dimension: int) -> Matrix:
    if type(dimension) is not int or not 1 <= dimension <= 11:
        raise ValueError("supported metric dimension must be 1..11")
    return tuple(tuple(Q(i == j) for j in range(dimension))
                 for i in range(dimension))


def squared_length(metric: Matrix, delta: Sequence[Q]) -> Q:
    if len(metric) != len(delta):
        raise ValueError("displacement/metric dimension mismatch")
    return sum((Q(delta[i])*metric[i][j]*Q(delta[j])
                for i in range(len(delta)) for j in range(len(delta))), Q(0))


@dataclass(frozen=True)
class LearnedMetric:
    metric: Matrix
    objective: Q
    initial_objective: Q
    steps: int
    stationary: bool
    certificate: str = "EXACT_RATIONAL_SPD_DESCENT"


class ManifoldDiscovery:
    """Bounded exact variational metric learning on SPD constant metrics."""

    def __init__(self, dimension: int, regularization: Q = Q(1, 1024)):
        self.dimension = dimension
        identity_metric(dimension)
        self.regularization = Q(regularization)
        if self.regularization <= 0:
            raise ValueError("positive regularization required")

    def _validated(self, constraints: Sequence[MetricConstraint]) -> None:
        if not constraints or len(constraints) > 4096:
            raise ValueError("1..4096 constraints required")
        if any(len(c.delta) != self.dimension for c in constraints):
            raise ValueError("constraint dimensions do not match metric")

    def objective(self, metric: Matrix,
                  constraints: Sequence[MetricConstraint]) -> Q:
        self._validated(constraints)
        if not is_spd(metric):
            raise ValueError("metric is not positive definite")
        return (sum((c.weight * (squared_length(metric, c.delta) -
                                 c.target_squared) ** 2 for c in constraints), Q(0)) +
                self.regularization * sum(
                    (metric[i][j] - Q(i == j))**2
                    for i in range(self.dimension) for j in range(self.dimension)
                ))

    def gradient(self, metric: Matrix,
                 constraints: Sequence[MetricConstraint]) -> Matrix:
        """Exact Frobenius gradient for the unconstrained symmetric matrix."""
        self._validated(constraints)
        n = self.dimension
        residuals = tuple((c.weight * 2 *
                           (squared_length(metric, c.delta)-c.target_squared), c.delta)
                          for c in constraints)
        return tuple(tuple(
            sum((r * d[i] * d[j] for r, d in residuals), Q(0)) +
            2*self.regularization*(metric[i][j] - Q(i == j))
            for j in range(n)) for i in range(n))

    def learn_metric(self, constraints: Sequence[MetricConstraint],
                     max_steps: int = 12) -> LearnedMetric:
        """Validated exact backtracking gradient flow; never claim optimality."""
        if type(max_steps) is not int or not 0 <= max_steps <= 256:
            raise ValueError("max_steps must be in 0..256")
        metric = identity_metric(self.dimension)
        initial = self.objective(metric, constraints)
        objective = initial
        steps = 0
        for _ in range(max_steps):
            grad = self.gradient(metric, constraints)
            if all(not v for row in grad for v in row):
                return LearnedMetric(metric, objective, initial, steps, True)
            step = Q(1, 8)
            updated = None
            for _trial in range(32):
                candidate = tuple(tuple(
                    metric[i][j] - step * grad[i][j]
                    for j in range(self.dimension))
                    for i in range(self.dimension))
                if is_spd(candidate):
                    value = self.objective(candidate, constraints)
                    if value < objective:
                        updated = (candidate, value)
                        break
                step /= 2
            if updated is None:
                break  # exact monotone descent refuses unsafe step
            metric, objective = updated
            steps += 1
        return LearnedMetric(metric, objective, initial, steps, False)

    @staticmethod
    def propose_manifold(*, graph_vertices: int | None = None,
                         graph_edges: int | None = None,
                         regular_degree: int | None = None,
                         root_count: int | None = None,
                         root_ambient_dimension: int | None = None
                         ) -> dict[str, object]:
        """Candidate generation from exact structural signatures.

        Ambiguous or insufficient facts return candidates with explicit
        uncertainty, never a false isomorphism certificate.
        """
        if any(x is not None and (type(x) is not int or x <= 0)
               for x in (graph_vertices, graph_edges, regular_degree,
                         root_count, root_ambient_dimension)):
            raise ValueError("counts must be positive ints if supplied")
        choices = []
        if (graph_vertices, graph_edges, regular_degree) == (120, 720, 12):
            choices.append("H4_600_CELL_GRAPH")
        if root_count is not None or root_ambient_dimension is not None:
            for key, spec in catalog().items():
                if root_count is not None and root_count != spec.get("roots"):
                    continue
                if (root_ambient_dimension is not None and
                        root_ambient_dimension != spec["ambient_dimension"]):
                    continue
                if key != "Leech":
                    choices.append(f"ROOT_{key}")
        return {
            "candidates": sorted(set(choices)),
            "classification": "EXACT_SIGNATURE_MATCH_NOT_GROUP_ISOMORPHISM",
            "requires_proof": ["coordinate map", "incidence parity",
                               "symmetry action", "metric equivalence"],
        }
