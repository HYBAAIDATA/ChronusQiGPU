"""
AL HARAS — executable exact checks behind the formal notes
==========================================================
"Speak friend and enter or you shall not pass." (motto from the product notes)

Earlier versions of this module labelled hand-written float arithmetic as
"formally verified (Lean 4)" with a Common Criteria tier. Neither was true: no
Lean is executed in CI and no evaluation exists. The module now runs executable
checks, with exact integer and rational arithmetic, against the AL HARAS engines:

1. sheaf_coboundary_zero_iff_consistent (sheaf.GraphSheaf): delta^0 s = 0
   exactly for the consistent states, enumerated on a finite family for the
   constant sheaf; for a sheaf with Householder restriction maps, dim ker delta^0
   of an explicitly built coboundary matrix equals the engine's h^0, the
   harmonic projection lands in ker delta^0, and a perturbation of one node is
   located at that node.
2. cycle_sum_obstruction (sheaf.GraphSheaf): an edge cochain of the constant
   sheaf is a coboundary exactly when its signed sum around every cycle is zero
   (all cochains with entries in {-1, 0, 1} on two graphs, compared with
   GraphSheaf.is_coboundary); coboundaries telescope to zero around closed
   walks; h^1 equals the cycle rank.
3. braid_relations (braids): the Fibonacci braid relations over Z[zeta_5], with
   a mutated F-move as a negative control that must fail.
4. reed_solomon_repair (reed_solomon): every pattern of up to t symbol errors in
   a block is located and repaired exactly; t + 1 errors are never reported as
   a verified repair.

A check that holds on the finite family it enumerates is evidence, not a proof.
The Lean source formal/lean4/ChronusAlHaras.lean states the coboundary lemmas
behind checks 1 and 2 (edge consistency and the closed-walk telescoping sum);
it is not compiled or machine-checked in CI.
"""

import hashlib
import time
from dataclasses import dataclass, field
from fractions import Fraction
from itertools import combinations, product
from typing import Any, Callable, Dict, List, Optional, Tuple

from chronus.security.al_haras import braids, reed_solomon
from chronus.security.al_haras.cyclotomic import ONE, PHI_INVERSE, mat2_identity, mat2_mul
from chronus.security.al_haras.exact import householder, rank_and_nullspace
from chronus.security.al_haras.sheaf import GraphSheaf

LEAN_SOURCE_PATH = "formal/lean4/ChronusAlHaras.lean"
LEAN_THEOREMS = (
    "Chronus.AlHaras.coboundary_eq_zero_iff",
    "Chronus.AlHaras.coboundary_sum_walk",
    "Chronus.AlHaras.coboundary_sum_closed_walk",
    "Chronus.AlHaras.not_coboundary_of_closed_walk_sum_ne_zero",
)
VERIFICATION_METHOD = "EXECUTABLE_EXACT_CHECKS"

CheckResult = Tuple[bool, int, List[str]]


@dataclass
class FormalProofVerdict:
    """Outcome of one executable check (class name kept for API compatibility)."""

    check_id: str
    statement: str
    holds: bool
    cases_checked: int
    evidence: List[str] = field(default_factory=list)
    lean_counterpart: Optional[str] = None

    @property
    def status(self) -> str:
        return "HOLDS" if self.holds else "FAILS"

    def as_dict(self) -> Dict[str, Any]:
        return {
            "check_id": self.check_id,
            "statement": self.statement,
            "status": self.status,
            "holds": self.holds,
            "cases_checked": self.cases_checked,
            "evidence": list(self.evidence),
            "lean_counterpart": self.lean_counterpart,
        }


def _is_zero_cochain(cochain: List[List[Fraction]]) -> bool:
    return all(x == 0 for vec in cochain for x in vec)


def _coboundary_matrix(sheaf: GraphSheaf) -> List[List[Fraction]]:
    """delta^0 as an explicit (|E| d) x (|V| d) matrix, built from the restriction maps."""
    d = sheaf.dim
    index = {n: i for i, n in enumerate(sheaf.nodes)}
    maps = sheaf.maps
    rows = [[Fraction(0)] * (len(sheaf.nodes) * d) for _ in range(len(sheaf.edges) * d)]
    for e, (a, b) in enumerate(sheaf.edges):
        for i in range(d):
            row = rows[e * d + i]
            for j in range(d):
                row[index[b] * d + j] += maps[(e, b)][i][j]
                row[index[a] * d + j] -= maps[(e, a)][i][j]
    return rows


def _sheaf_coboundary_criterion() -> CheckResult:
    evidence: List[str] = []
    cases = 0

    # (a) constant sheaf with stalk Q on a triangle: every state with entries in {-1, 0, 1}.
    tri = GraphSheaf(["a", "b", "c"], [("a", "b"), ("b", "c"), ("c", "a")], 1)
    agree = zero_states = 0
    for values in product((-1, 0, 1), repeat=3):
        section = tri.section({n: [v] for n, v in zip(tri.nodes, values)})
        is_zero = _is_zero_cochain(tri.coboundary(section))
        zero_states += is_zero
        agree += is_zero == (values[0] == values[1] == values[2])
        cases += 1
    ok_constant = agree == cases
    evidence.append(
        f"constant sheaf on a triangle: {zero_states} of {cases} states have delta0 s = 0; "
        f"'delta0 s = 0 iff all states equal' holds for {agree} of {cases}"
    )

    # (b) Householder restriction maps on a 4-cycle with a chord, stalk Q^3.
    nodes = ["a", "b", "c", "d"]
    edges = [("a", "b"), ("b", "c"), ("c", "d"), ("d", "a"), ("a", "c")]
    maps = {
        (0, "b"): householder([Fraction(1), Fraction(2), Fraction(2)]),
        (2, "d"): householder([Fraction(2), Fraction(-1), Fraction(2)]),
    }
    sheaf = GraphSheaf(nodes, edges, 3, maps)
    h0 = sheaf.cohomology_dimensions()["h0"]
    matrix = _coboundary_matrix(sheaf)
    rank, kernel = rank_and_nullspace(matrix, len(nodes) * 3)
    nullity = len(nodes) * 3 - rank
    ok_dim = nullity == h0
    cases += 1
    ok_kernel = True
    for vec in kernel:
        section = {n: vec[i * 3:(i + 1) * 3] for i, n in enumerate(nodes)}
        ok_kernel = ok_kernel and _is_zero_cochain(sheaf.coboundary(section))
        cases += 1
    evidence.append(
        f"Householder-twisted sheaf: engine h0 = {h0}, nullity of the explicit coboundary matrix = {nullity}; "
        f"{len(kernel)} kernel basis vectors give delta0 = 0: {ok_kernel}"
    )

    state = sheaf.section({"a": [1, 2, 3], "b": [-1, 0, 4], "c": [2, 2, -3], "d": [0, 5, 1]})
    projected = sheaf.harmonic_projection(state)
    ok_projection = _is_zero_cochain(sheaf.coboundary(projected)) and sheaf.harmonic_projection(projected) == projected
    cases += 1
    evidence.append(f"harmonic projection of a non-section lands in ker delta0 and is idempotent: {ok_projection}")

    located = 0
    for node in nodes:
        perturbed = {n: list(v) for n, v in projected.items()}
        perturbed[node] = [x + y for x, y in zip(perturbed[node], [Fraction(1), Fraction(0), Fraction(-1)])]
        cob = sheaf.coboundary(perturbed)
        nonzero = {e for e, vec in enumerate(cob) if any(x != 0 for x in vec)}
        incident = {e for e, (a, b) in enumerate(edges) if node in (a, b)}
        located += nonzero == incident and sheaf.isolate(perturbed) == [node]
        cases += 1
    ok_located = located == len(nodes)
    evidence.append(
        f"perturbing one node of a global section: residual edges equal that node's edges and isolate() "
        f"returns it for {located} of {len(nodes)} nodes"
    )
    return ok_constant and ok_dim and ok_kernel and ok_projection and ok_located, cases, evidence


def _cycle_sum_obstruction() -> CheckResult:
    evidence: List[str] = []
    cases = 0
    ok = True
    graphs = [
        (
            "triangle",
            GraphSheaf(["a", "b", "c"], [("a", "b"), ("b", "c"), ("a", "c")], 1),
            [[(0, 1), (1, 1), (2, -1)]],
        ),
        (
            "4-cycle with chord",
            GraphSheaf(["a", "b", "c", "d"], [("a", "b"), ("b", "c"), ("c", "d"), ("d", "a"), ("a", "c")], 1),
            [[(0, 1), (1, 1), (4, -1)], [(4, 1), (2, 1), (3, 1)]],
        ),
    ]
    for name, sheaf, cycles in graphs:
        n_edges = len(sheaf.edges)
        agree = exact = total = 0
        for values in product((-1, 0, 1), repeat=n_edges):
            sums = [sum(sign * values[e] for e, sign in cycle) for cycle in cycles]
            is_cob = sheaf.is_coboundary([[v] for v in values])["is_coboundary"]
            exact += is_cob
            agree += is_cob == all(s == 0 for s in sums)
            total += 1
        telescoped = sections = 0
        for values in product((-1, 0, 1), repeat=len(sheaf.nodes)):
            cob = sheaf.coboundary(sheaf.section({n: [v] for n, v in zip(sheaf.nodes, values)}))
            telescoped += all(sum(sign * cob[e][0] for e, sign in cycle) == 0 for cycle in cycles)
            sections += 1
        h1 = sheaf.cohomology_dimensions()["h1"]
        cycle_rank = n_edges - len(sheaf.nodes) + 1
        ok = ok and agree == total and telescoped == sections and h1 == cycle_rank
        cases += total + sections + 1
        evidence.append(
            f"{name}: {exact} of {total} cochains are coboundaries; is_coboundary agrees with the cycle-sum "
            f"test on {agree} of {total}; coboundaries sum to zero around every cycle for {telescoped} of "
            f"{sections} sections; h1 = {h1}, cycle rank = {cycle_rank}"
        )
    return ok, cases, evidence


def _braid_relations() -> CheckResult:
    relations = braids.verify_relations()
    f_bad = [[PHI_INVERSE, ONE], [PHI_INVERSE, PHI_INVERSE]]
    sigma_1 = braids.generators()["sigma_1"]
    sigma_2_bad = mat2_mul(mat2_mul(f_bad, braids.R_MATRIX), f_bad)
    bad_involution = mat2_mul(f_bad, f_bad) == mat2_identity()
    bad_artin = mat2_mul(mat2_mul(sigma_1, sigma_2_bad), sigma_1) == mat2_mul(mat2_mul(sigma_2_bad, sigma_1), sigma_2_bad)
    evidence = [f"{name}: {value}" for name, value in sorted(relations.items())]
    evidence.append(
        f"negative control (F with one sign flipped): involution {bad_involution}, Artin relation {bad_artin}"
    )
    holds = all(relations.values()) and not bad_involution and not bad_artin
    return holds, len(relations) + 2, evidence


def _reed_solomon_repair() -> CheckResult:
    n, k = 12, 6
    t = (n - k) // 2
    data = hashlib.sha256(b"al-haras reed-solomon check").digest()[: 3 * k]
    envelope = reed_solomon.protect(data, n=n, k=k)
    block = range(k, 2 * k)  # byte positions of the second block
    repaired = rejected = cases = 0
    within = beyond = 0
    for errors in range(t + 2):
        for positions in combinations(block, errors):
            res = reed_solomon.heal(reed_solomon.inject_faults(data, positions), envelope)
            if errors <= t:
                within += 1
                repaired += (
                    res["integrity_verified"]
                    and res["repaired"] == data
                    and res["corrected_data_positions"] == list(positions)
                )
            else:
                beyond += 1
                rejected += not res["integrity_verified"]
            cases += 1
    parity = [list(p) for p in envelope["parity"]]
    parity[1][0] = (parity[1][0] + 1) % reed_solomon.P
    parity[1][1] = (parity[1][1] + 1) % reed_solomon.P
    mixed = reed_solomon.heal(reed_solomon.inject_faults(data, [k]), envelope, received_parity=parity)
    mixed_ok = mixed["integrity_verified"] and mixed["repaired"] == data
    cases += 1
    evidence = [
        f"RS({n}, {k}) over GF(257), t = {t}: {repaired} of {within} patterns with at most {t} byte errors in one "
        f"block repaired exactly at the injected positions",
        f"{rejected} of {beyond} patterns with {t + 1} errors not reported as a verified repair",
        f"1 data error plus 2 parity errors in one block repaired: {mixed_ok}",
    ]
    return repaired == within and rejected == beyond and mixed_ok, cases, evidence


class FormalTopologicalProofVerifier:
    """Runs the executable exact checks (class name kept for API compatibility)."""

    CHECKS: Tuple[Tuple[str, str, Optional[str], Callable[[], CheckResult]], ...] = (
        (
            "sheaf_coboundary_zero_iff_consistent",
            "For a sheaf on a graph with orthogonal restriction maps, delta0 s = 0 exactly when the states "
            "are consistent across every edge.",
            "Chronus.AlHaras.coboundary_eq_zero_iff",
            _sheaf_coboundary_criterion,
        ),
        (
            "cycle_sum_obstruction",
            "An edge cochain of the constant sheaf is a coboundary exactly when its signed sum around every "
            "cycle is zero; a non-zero cycle sum is an obstruction no node states can explain.",
            "Chronus.AlHaras.not_coboundary_of_closed_walk_sum_ne_zero",
            _cycle_sum_obstruction,
        ),
        (
            "braid_relations",
            "The Fibonacci braid generators over Z[zeta_5] satisfy F^2 = I, R^10 = I and the Artin relation.",
            None,
            _braid_relations,
        ),
        (
            "reed_solomon_repair",
            "RS(n, k) over GF(257) repairs every pattern of up to (n - k) / 2 symbol errors per block.",
            None,
            _reed_solomon_repair,
        ),
    )

    @classmethod
    def _run(cls, check_id: str, statement: str, lean: Optional[str], fn: Callable[[], CheckResult]) -> FormalProofVerdict:
        try:
            holds, cases, evidence = fn()
        except Exception as exc:  # a check that crashes is reported as not holding
            return FormalProofVerdict(check_id, statement, False, 0, [f"check raised {type(exc).__name__}: {exc}"], lean)
        return FormalProofVerdict(check_id, statement, bool(holds), cases, evidence, lean)

    @classmethod
    def run_check(cls, check_id: str) -> FormalProofVerdict:
        for cid, statement, lean, fn in cls.CHECKS:
            if cid == check_id:
                return cls._run(cid, statement, lean, fn)
        raise KeyError(f"unknown check {check_id!r}")

    @classmethod
    def verify_all_theorems(cls) -> Dict[str, Any]:
        """Run every check now (legacy method name: these are executable checks, not theorems)."""
        t0 = time.perf_counter_ns()
        verdicts = [cls._run(cid, statement, lean, fn) for cid, statement, lean, fn in cls.CHECKS]
        holding = sum(v.holds for v in verdicts)
        return {
            "verification_method": VERIFICATION_METHOD,
            "summary": (
                "Executable checks run at request time with exact arithmetic against the AL HARAS engines "
                "on finite instances; they are evidence, not proofs."
            ),
            "checks": [v.as_dict() for v in verdicts],
            "checks_run": len(verdicts),
            "checks_holding": holding,
            "all_checks_hold": holding == len(verdicts),
            "lean_specification": {
                "path": LEAN_SOURCE_PATH,
                "theorems": list(LEAN_THEOREMS),
                "machine_checked_in_ci": False,
                "note": "Specification source only; it is not compiled or machine-checked in CI.",
            },
            "elapsed_ns": time.perf_counter_ns() - t0,
        }
