"""TOE causal capability stack — elevation §§6-10.

Separates the stages the brief requires on every causal answer::

    CAUSAL_GRAPH_SUPPLIED / CAUSAL_GRAPH_LEARNED
    EFFECT_IDENTIFIED / EFFECT_NOT_IDENTIFIED
    EFFECT_ESTIMATED
    INTERVENTION_EXECUTED
    COUNTERFACTUAL_GENERATED

and adds the four capabilities on top of ``toe.causal_ladder``:

* ``identifiability`` — an oracle that answers "can this causal question be
  answered from the evidence I possess?" BEFORE estimation, returning
  IDENTIFIED / PARTIALLY_IDENTIFIED / NOT_IDENTIFIED / UNAVAILABLE with a
  reason, the identification strategy, and trap warnings (collider /
  M-bias-shaped covariates that the criterion correctly excludes).
  Refusal to answer is a capability, not a failure.

* ``discover_structures`` — BOUNDED structural learning: a PC-style
  skeleton search plus v-structure orientation and Meek closure that
  returns an observationally-equivalent CLASS of admissible DAGs, never a
  fabricated unique graph. Gaussian partial correlation is the
  independence oracle; latent confounding is an explicit boundary, not an
  assumption away.

* ``compare_worlds`` — multi-counterfactual comparison: factual vs several
  intervened worlds with per-world deltas, responsible causal paths,
  assumptions, and per-node invariance across all worlds.

* ``evaluate_futures`` — multi-future reasoning over candidate actions:
  exact mean/variance propagation through the linear SCM (``f_i = Σw x_j +
  φ u_i``) gives a distribution per outcome per action, and horizon is the
  descendant depth — degradation is reported, not hidden.

Nothing here calls supplied-graph inference "causal discovery".
"""

from __future__ import annotations

import math
from itertools import combinations
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from .causal_ladder import (
    CausalCapabilityUnavailable,
    CausalGraph,
    StructuralCausalModel,
    counterfactual_state,
    d_separated,
    is_backdoor_admissible,
)
from .receipts import ReceiptLedger

CAUSAL_STACK_VERSION = "toe.causal_stack/v1"

STAGE_GRAPH_SUPPLIED = "CAUSAL_GRAPH_SUPPLIED"
STAGE_GRAPH_LEARNED = "CAUSAL_GRAPH_LEARNED"
STAGE_EFFECT_IDENTIFIED = "EFFECT_IDENTIFIED"
STAGE_EFFECT_NOT_IDENTIFIED = "EFFECT_NOT_IDENTIFIED"
STAGE_EFFECT_ESTIMATED = "EFFECT_ESTIMATED"
STAGE_INTERVENTION_EXECUTED = "INTERVENTION_EXECUTED"
STAGE_COUNTERFACTUAL_GENERATED = "COUNTERFACTUAL_GENERATED"

IDENTIFIED = "IDENTIFIED"
PARTIALLY_IDENTIFIED = "PARTIALLY_IDENTIFIED"
NOT_IDENTIFIED = "NOT_IDENTIFIED"
UNAVAILABLE = "UNAVAILABLE"


def _directed_path_exists(graph: CausalGraph, src: str, dst: str) -> bool:
    seen: Set[str] = set()
    stack = [src]
    while stack:
        node = stack.pop()
        if node == dst:
            return True
        if node in seen:
            continue
        seen.add(node)
        stack.extend(graph.children.get(node, []))
    return False


def _without_node(graph: CausalGraph, node: str) -> CausalGraph:
    return graph.without_incoming({node}).without_outgoing(node)


def _all_simple_paths(
    graph: CausalGraph, src: str, dst: str, cap: int = 32
) -> List[List[str]]:
    paths: List[List[str]] = []
    stack: List[Tuple[str, List[str]]] = [(src, [src])]
    while stack and len(paths) < cap:
        node, path = stack.pop()
        for child in graph.children.get(node, []):
            if child == dst:
                paths.append(path + [child])
            elif child not in path:
                stack.append((child, path + [child]))
    return paths


# ---------------------------------------------------------------------------
# §7 Identifiability oracle
# ---------------------------------------------------------------------------


def _proper_frontdoor(
    graph: CausalGraph, treatment: str, outcome: str, observed: Set[str]
) -> Optional[List[str]]:
    """Strict frontdoor check — all three Pearl conditions, bounded search.

    Candidates: observed children of the treatment that are ancestors of
    the outcome (single mediators, then their union). A candidate set Z is
    admissible iff (1) every directed path treatment→outcome passes through
    Z, (2) no backdoor path treatment→Z is open, (3) every backdoor path
    Z→outcome is blocked by {treatment}.
    """
    candidates = sorted(
        (
            set(graph.children.get(treatment, []))
            & (graph.ancestors(outcome) | {outcome})
            & observed
        )
        - {outcome}
    )
    for size in list(range(1, len(candidates) + 1)):
        for subset in combinations(candidates, size):
            z = list(subset)
            blocked = graph
            for node in z:
                blocked = _without_node(blocked, node)
            if _directed_path_exists(blocked, treatment, outcome):
                continue  # (1) fails: an X→Y path bypasses Z
            underlined = graph.without_outgoing(treatment)
            if not d_separated(underlined, {treatment}, set(z), ()):
                continue  # (2) fails: backdoor X→Z open
            if not all(
                is_backdoor_admissible(graph, node, outcome, {treatment})
                for node in z
            ):
                continue  # (3) fails: backdoor Z→Y not blocked by X
            return z
    return None


def _instrument_candidates(
    graph: CausalGraph, treatment: str, outcome: str, observed: Set[str]
) -> List[str]:
    """Graphical instrument screen (conservative).

    z qualifies iff (i) z is not a descendant of the treatment, (ii) z is
    d-connected to the treatment, and (iii) once the treatment's outgoing
    edges are cut, z is d-separated from the outcome — i.e. every z→Y path
    enters X through an arrowhead (exclusion + no z–Y confounding).
    Relevance (cov(z,x) ≠ 0) is a data-level condition the graph cannot
    prove, so an instrument yields bounds/an IV estimand — reported as
    PARTIALLY_IDENTIFIED, never a full ATE claim.
    """
    forbidden = graph.descendants(treatment) | {treatment, outcome}
    out: List[str] = []
    underlined_x = graph.without_outgoing(treatment)
    for z in sorted(observed - forbidden):
        try:
            if d_separated(graph, {z}, {treatment}, ()):
                continue
            if d_separated(underlined_x, {z}, {outcome}, ()):
                out.append(z)
        except ValueError:
            continue
    return out


def _collider_traps(
    graph: CausalGraph, treatment: str, outcome: str, observed: Set[str],
    adjustment: Sequence[str],
) -> List[str]:
    """Observed covariates that look adjustable but are colliders.

    c is flagged iff it is not in the admissible set and conditioning on
    it would open a treatment–outcome path — checked in both the full
    graph (associational collider trap: x→c←y is blocked until c is
    conditioned) and the treatment-underlined graph (backdoor trap:
    M-bias-shaped covariates). Such covariates must NOT be conditioned on.
    """
    underlined = graph.without_outgoing(treatment)
    adj = set(adjustment)
    traps: List[str] = []
    for c in sorted(observed - adj - {treatment, outcome}):
        for view in (graph, underlined):
            try:
                blocked = d_separated(view, {treatment}, {outcome}, adj)
                with_c = d_separated(view, {treatment}, {outcome}, adj | {c})
            except ValueError:
                continue
            if blocked and not with_c:
                traps.append(c)
                break
    return traps


def identifiability(
    graph: Optional[CausalGraph],
    treatment: str,
    outcome: str,
    *,
    observed: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    """Can this causal question be answered from the evidence possessed?

    Returns a verdict in {IDENTIFIED, PARTIALLY_IDENTIFIED,
    NOT_IDENTIFIED, UNAVAILABLE} with a reason and the strategy that
    succeeded (or failed last). This runs BEFORE estimation; a refusal is
    a first-class answer.
    """
    base: Dict[str, Any] = {
        "treatment": treatment,
        "outcome": outcome,
        "verdict": UNAVAILABLE,
        "reason": None,
        "strategy": None,
        "adjustment_set": None,
        "instruments": [],
        "warnings": [],
        "stage": None,
    }
    if graph is None:
        base["reason"] = "no causal structure supplied"
        return base
    unknown = [n for n in (treatment, outcome) if n not in graph.nodes]
    if unknown or treatment == outcome or not graph.is_dag():
        base["reason"] = (
            f"query malformed: unknown nodes {unknown}" if unknown
            else "treatment equals outcome" if treatment == outcome
            else "supplied graph is not a DAG"
        )
        return base

    observed_set = set(graph.nodes) if observed is None else set(observed)
    latents = sorted(set(graph.nodes) - observed_set)
    underlined = graph.without_outgoing(treatment)

    # Strategy 0: no open backdoor — identified with empty adjustment.
    if d_separated(underlined, {treatment}, {outcome}, ()):
        base.update(
            verdict=IDENTIFIED,
            strategy="no_adjustment",
            adjustment_set=[],
            reason="no open backdoor path between treatment and outcome",
            stage=STAGE_EFFECT_IDENTIFIED,
            warnings=_collider_traps(graph, treatment, outcome, observed_set, ()),
        )
        return base

    # Strategy 1: minimal backdoor-admissible set among observed variables.
    from .causal_ladder import identify_backdoor

    adj = identify_backdoor(graph, treatment, outcome, observed=observed_set)
    if adj is not None:
        base.update(
            verdict=IDENTIFIED,
            strategy="backdoor",
            adjustment_set=list(adj),
            reason=f"backdoor-admissible set {sorted(adj)} among observed variables",
            stage=STAGE_EFFECT_IDENTIFIED,
            warnings=_collider_traps(graph, treatment, outcome, observed_set, adj),
        )
        return base

    # Strategy 2: strict frontdoor.
    fd = _proper_frontdoor(graph, treatment, outcome, observed_set)
    if fd is not None:
        base.update(
            verdict=IDENTIFIED,
            strategy="frontdoor",
            adjustment_set=list(fd),
            reason=f"frontdoor set {sorted(fd)} intercepts all directed paths",
            stage=STAGE_EFFECT_IDENTIFIED,
        )
        return base

    # Strategy 3: instrument candidates — partial identification only.
    ivs = _instrument_candidates(graph, treatment, outcome, observed_set)
    if ivs:
        base.update(
            verdict=PARTIALLY_IDENTIFIED,
            strategy="instrument",
            instruments=ivs,
            reason=(
                f"instrument candidate(s) {ivs} satisfy the graphical IV "
                "conditions; relevance is a data-level condition and only "
                "an IV estimand/bounds are identified — not the ATE"
            ),
            stage=STAGE_EFFECT_IDENTIFIED,
        )
        return base

    base.update(
        verdict=NOT_IDENTIFIED,
        reason=(
            "unblocked backdoor path(s) traverse unobserved "
            f"{latents}" if latents else
            "no admissible identification strategy (backdoor, frontdoor, "
            "instrument) exists among observed variables"
        ),
        stage=STAGE_EFFECT_NOT_IDENTIFIED,
    )
    return base


# ---------------------------------------------------------------------------
# §8 Bounded structural learning — returns an equivalence class
# ---------------------------------------------------------------------------

_MAX_COND = 2
_ENUM_CAP = 64
_UNDIRECTED_ENUM_CAP = 10


def _corr_matrix(rows: Mapping[str, Sequence[float]]) -> Tuple[List[str], List[List[float]], int]:
    names = sorted(rows)
    cols = [[float(v) for v in rows[n]] for n in names]
    n = min((len(c) for c in cols), default=0)
    means = [sum(c[:n]) / n for c in cols]
    sds = []
    for c, m in zip(cols, means):
        v = sum((x - m) ** 2 for x in c[:n]) / max(1, n - 1)
        sds.append(math.sqrt(v))
    r = [[0.0] * len(names) for _ in names]
    for i in range(len(names)):
        for j in range(len(names)):
            if sds[i] == 0 or sds[j] == 0:
                r[i][j] = 1.0 if i == j else 0.0
                continue
            r[i][j] = sum(
                (cols[i][k] - means[i]) * (cols[j][k] - means[j]) for k in range(n)
            ) / ((n - 1) * sds[i] * sds[j])
    return names, r, n


def _invert_symmetric(m: List[List[float]]) -> Optional[List[List[float]]]:
    n = len(m)
    aug = [row[:] + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(m)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda i: abs(aug[i][col]))
        if abs(aug[pivot][col]) < 1e-12:
            return None
        aug[col], aug[pivot] = aug[pivot], aug[col]
        d = aug[col][col]
        aug[col] = [v / d for v in aug[col]]
        for i in range(n):
            if i != col and aug[i][col] != 0.0:
                f = aug[i][col]
                aug[i] = [a - f * b for a, b in zip(aug[i], aug[col])]
    return [row[n:] for row in aug]


def _partial_corr(r: List[List[float]], i: int, j: int, s: Sequence[int]) -> Optional[float]:
    idx = [i, j] + list(s)
    sub = [[r[a][b] for b in idx] for a in idx]
    inv = _invert_symmetric(sub)
    if inv is None:
        return None
    denom = inv[0][0] * inv[1][1]
    if denom <= 0:
        return None
    return -inv[0][1] / math.sqrt(denom)


def _meek(skel: Set[Tuple[str, str]], directed: Set[Tuple[str, str]]) -> Set[Tuple[str, str]]:
    """Meek rules R1-R3 closure on a PDAG. Returns the directed edge set."""
    directed = set(directed)
    undirected = set(skel) - directed - {(b, a) for a, b in directed}

    def has_path(a: str, b: str) -> bool:
        seen, stack = set(), [a]
        while stack:
            n = stack.pop()
            if n == b:
                return True
            if n in seen:
                continue
            seen.add(n)
            stack.extend(c for nn, c in directed if nn == n)
        return False

    changed = True
    while changed:
        changed = False
        for a, b in sorted(undirected):
            nodes = {x for e in skel for x in e}
            # R1: c→a and a—b with c,b nonadjacent → a→b
            r1 = any(
                (c, a) in directed
                and c != b
                and (min(c, b), max(c, b)) not in skel
                for c in nodes
            )
            # R2: a→c→b and a—b → a→b
            r2 = any(
                (a, c) in directed and (c, b) in directed for c in nodes
            )
            # R3: a—c, a—d, c→b, d→b, c,d nonadjacent → a→b
            r3 = any(
                (min(a, c), max(a, c)) in skel
                and (a, c) not in directed
                and (c, a) not in directed
                and (min(a, d), max(a, d)) in skel
                and (a, d) not in directed
                and (d, a) not in directed
                and (c, b) in directed
                and (d, b) in directed
                and c != d
                and (min(c, d), max(c, d)) not in skel
                for c in nodes
                for d in nodes
            )
            if r1 or r2 or r3:
                directed.add((a, b))
                undirected.discard((a, b))
                changed = True
                break
    return directed


def _enumerate_dags(
    nodes: List[str],
    skel: Set[Tuple[str, str]],
    directed: Set[Tuple[str, str]],
) -> Tuple[List[List[Tuple[str, str]]], int]:
    undirected = sorted(skel - directed - {(b, a) for a, b in directed})
    if len(undirected) > _UNDIRECTED_ENUM_CAP:
        return [], -1  # equivalence class too large to enumerate honestly
    found: List[List[Tuple[str, str]]] = []
    total = 0
    for bits in range(1 << len(undirected)):
        edges = set(directed)
        for k, (a, b) in enumerate(undirected):
            edges.add((a, b) if (bits >> k) & 1 else (b, a))
        g = CausalGraph.from_edges(edges, nodes)
        if not g.is_dag():
            continue
        # Same skeleton + same v-structures = same Markov class; require no
        # new colliders to stay inside the class.
        ok = True
        for c in nodes:
            ps = sorted(g.parents.get(c, []))
            for p1, p2 in combinations(ps, 2):
                if (min(p1, p2), max(p1, p2)) not in skel:
                    # unshielded collider p1→c←p2: admissible only if the
                    # PDAG already oriented both edges into c
                    if (p1, c) not in directed or (p2, c) not in directed:
                        ok = False
        total += 1
        if ok:
            found.append(sorted(edges))
        if len(found) >= _ENUM_CAP:
            break
    return found, total


def discover_structures(
    rows: Mapping[str, Sequence[float]],
    *,
    alpha: float = 0.35,
    max_cond: int = _MAX_COND,
) -> Dict[str, Any]:
    """Bounded observational structure learning → an equivalence class.

    Skeleton by marginal then conditional partial correlation (Gaussian
    oracle, |S| ≤ ``max_cond``), v-structure orientation from sepsets, Meek
    closure, then enumeration of the consistent DAGs when the remaining
    undirected frontier is small. The honest output is a SET of
    observationally equivalent structures — correlations alone cannot
    choose among them, and latent confounding is an explicit boundary.
    """
    names, r, n = _corr_matrix(rows)
    idx = {name: i for i, name in enumerate(names)}
    if n < 8:
        return {
            "available": False,
            "reason": f"need >= 8 observations, got {n}",
            "stage": STAGE_GRAPH_LEARNED,
            "version": CAUSAL_STACK_VERSION,
        }

    # Skeleton
    adj: Dict[str, Set[str]] = {nm: set(names) - {nm} for nm in names}
    sepsets: Dict[Tuple[str, str], Tuple[str, ...]] = {}
    margins: List[float] = []
    for level in range(0, max_cond + 1):
        for a, b in sorted(
            (a, b) for a in names for b in adj[a] if a < b
        ):
            if len(adj[a] - {b}) < level:
                continue
            removed = False
            for s in combinations(sorted(adj[a] - {b}), level):
                pc = _partial_corr(r, idx[a], idx[b], [idx[t] for t in s])
                if pc is None:
                    continue
                if abs(pc) < alpha:
                    adj[a].discard(b)
                    adj[b].discard(a)
                    sepsets[(a, b)] = s
                    margins.append(alpha - abs(pc))
                    removed = True
                    break
            if removed:
                continue

    skel = {tuple(sorted(e)) for a in names for e in [(a, b) for b in adj[a]]}
    skel = {e for e in skel if e[0] != e[1]}

    # v-structures
    directed: Set[Tuple[str, str]] = set()
    vstructs: List[Tuple[str, str, str]] = []
    for a, c in sorted(skel):
        for b in sorted(adj[c] - {a}):
            if a > b:
                continue  # each unshielded triple is visited once
            pair = (min(a, b), max(a, b))
            if pair in skel:
                continue
            sep = set(sepsets.get(pair, ()))
            if c not in sep:
                directed.add((a, c))
                directed.add((b, c))
                vstructs.append((a, c, b))

    directed = _meek(skel, directed)
    undirected = sorted(skel - directed - {(b, a) for a, b in directed})
    dags, candidates = _enumerate_dags(names, skel, directed)

    return {
        "available": True,
        "version": CAUSAL_STACK_VERSION,
        "stage": STAGE_GRAPH_LEARNED,
        "n_samples": n,
        "alpha": alpha,
        "independence_oracle": "gaussian partial correlation",
        "skeleton": sorted(skel),
        "v_structures": vstructs,
        "directed_edges": sorted(directed),
        "undirected_edges": undirected,
        "sepsets": {"{}|{}".format(a, b): list(s) for (a, b), s in sepsets.items()},
        "admissible_dags": dags,
        "equivalence_class_size": len(dags) if dags else (None if candidates < 0 else 0),
        "enumerated_all": candidates >= 0 and len(dags) < _ENUM_CAP,
        "separation_margin_min": min(margins) if margins else None,
        "boundaries": [
            "output is a Markov-equivalence class — observationally "
            "equivalent DAGs are indistinguishable from correlations alone",
            "latent confounders and selection bias are not ruled out",
            "gaussian partial correlation assumes (approximately) linear "
            "dependence and continuous variables",
            "supplied-graph inference was not used; this is the learned "
            "path (CAUSAL_GRAPH_LEARNED)",
        ],
    }


# ---------------------------------------------------------------------------
# §9 Multi-counterfactual world comparison
# ---------------------------------------------------------------------------


def compare_worlds(
    scm: StructuralCausalModel,
    factual: Mapping[str, Any],
    worlds: Sequence[Mapping[str, Any]],
    outcomes: Sequence[str],
    *,
    arithmetic: str = "float64",
    ledger: Optional[ReceiptLedger] = None,
) -> Dict[str, Any]:
    """FACTUAL vs WORLD A vs WORLD B ... — multi-counterfactual comparison.

    Each world is ``{"name": ..., "interventions": {node: value}}``.
    Per world: predicted state, delta vs factual, the causal path(s)
    responsible, the assumptions, and a receipt. Nodes that keep their
    factual value in every world are reported as invariants.
    """
    ledger = ledger or ReceiptLedger()
    factual_snapshot = {
        n: float(factual[n]) for n in factual if isinstance(factual[n], (int, float))
    }
    results: List[Dict[str, Any]] = []
    invariant_candidates: Optional[Set[str]] = None

    for w in worlds:
        name = str(w.get("name", f"world_{len(results)}"))
        ivs = dict(w.get("interventions", {}))
        try:
            cf = counterfactual_state(
                scm, ivs, factual, list(outcomes), arithmetic=arithmetic
            )
        except CausalCapabilityUnavailable as exc:
            results.append(
                {
                    "world": name,
                    "available": False,
                    "reason": exc.reason,
                    "missing_evidence": list(exc.missing),
                    "stage": None,
                }
            )
            continue
        cut = scm.mutilate(ivs)[0].graph
        paths = {
            o: [p for x in ivs for p in _all_simple_paths(cut, x, o)]
            for o in outcomes
        }
        values = cf["values"]
        delta = {
            o: values.get(o, float("nan")) - factual_snapshot.get(o, float("nan"))
            for o in outcomes
            if o in factual_snapshot
        }
        same = {
            n for n, v in values.items() if n in factual_snapshot and v == factual_snapshot[n]
        } - set(ivs)
        invariant_candidates = (
            same if invariant_candidates is None else invariant_candidates & same
        )
        receipt = ledger.issue(
            "counterfactual_world",
            inputs={"world": name, "interventions": cf["interventions"]},
            config={"outcomes": list(outcomes), "arithmetic": arithmetic},
            output={
                "outcome_values": cf["outcome_values"],
                "factual_model_sha256": cf["surgery"]["factual_graph_sha256"],
                "mutilated_graph_sha256": cf["surgery"]["mutilated_graph_sha256"],
            },
        )
        results.append(
            {
                "world": name,
                "available": True,
                "stage": STAGE_COUNTERFACTUAL_GENERATED,
                "interventions": cf["interventions"],
                "predicted_state": values,
                "outcome_values": cf["outcome_values"],
                "delta_vs_factual": delta,
                "causal_paths": paths,
                "assumptions": {
                    "edges_cut": cf["surgery"]["edges_cut"],
                    "exogenous_abduced": cf["abduced_exogenous"],
                    "model_form": "linear f_i = Σw x_j + φ u_i (abduction exact under it)",
                    "evidence_required": cf["required_evidence"],
                },
                "uncertainty": (
                    "none at unit level — abduction pins the exogenous "
                    "noise exactly under the linear model; model-form "
                    "uncertainty is a separate axis (§11)"
                ),
                "receipt": receipt.receipt_sha256,
            }
        )

    return {
        "version": CAUSAL_STACK_VERSION,
        "factual_state": factual_snapshot,
        "n_worlds": len(worlds),
        "worlds": results,
        "invariant_variables": sorted(invariant_candidates or ()),
        "ledger_verify": ledger.verify()["ok"],
    }


# ---------------------------------------------------------------------------
# §10 Multi-future reasoning — exact uncertainty propagation
# ---------------------------------------------------------------------------

_Z_05 = -1.6448536269514722
_Z_95 = 1.6448536269514722


def _propagate_moments(
    scm: StructuralCausalModel,
    interventions: Mapping[str, float],
    noise_sd: Optional[Mapping[str, float]],
) -> Dict[str, Dict[str, float]]:
    """Exact mean/variance propagation through the linear SCM.

    ``x_i = Σ_j w_ij x_j + φ u_i`` with independent ``u_i ~ N(0, σ_i)``;
    means and full covariances propagate in topological order, so every
    outcome gets an exact Gaussian distribution — no Monte Carlo. Depth is
    the longest directed chain to the node: the horizon axis.
    """
    phi = 1.6180339887498949
    order = scm.graph.topological_order()
    sd = {node: float((noise_sd or {}).get(node, 1.0)) for node in order}
    means: Dict[str, float] = {}
    covs: Dict[Tuple[str, str], float] = {}
    depth: Dict[str, int] = {}

    def cov(a: str, b: str) -> float:
        return covs.get((a, b), covs.get((b, a), 0.0))

    stats: Dict[str, Dict[str, float]] = {}
    for node in order:
        parents = scm.graph.parents.get(node, [])
        if node in interventions:
            m, v = float(interventions[node]), 0.0
            d = 0
            for other in stats:
                covs[(node, other)] = 0.0
        else:
            m = sum(
                scm.graph.edge_weights.get((p, node), 0.0) * means[p] for p in parents
            )
            v = phi * phi * sd[node] * sd[node] + sum(
                scm.graph.edge_weights.get((p, node), 0.0)
                * scm.graph.edge_weights.get((q, node), 0.0)
                * cov(p, q)
                for p in parents
                for q in parents
            )
            for other in stats:
                covs[(node, other)] = sum(
                    scm.graph.edge_weights.get((p, node), 0.0) * cov(p, other)
                    for p in parents
                )
            d = 1 + max([depth[p] for p in parents], default=-1)
        means[node] = m
        depth[node] = d
        covs[(node, node)] = v
        stats[node] = {
            "mean": m,
            "variance": v,
            "sd": math.sqrt(max(v, 0.0)),
            "p05": m + _Z_05 * math.sqrt(max(v, 0.0)),
            "p95": m + _Z_95 * math.sqrt(max(v, 0.0)),
            "depth": d,
        }
    return stats


def evaluate_futures(
    scm: StructuralCausalModel,
    actions: Sequence[Mapping[str, Any]],
    outcomes: Optional[Sequence[str]] = None,
    *,
    noise_sd: Optional[Mapping[str, float]] = None,
    ledger: Optional[ReceiptLedger] = None,
) -> Dict[str, Any]:
    """A1 / A2 / A3 … → a distribution over future states per action.

    Uncertainty is retained per outcome (Gaussian band from exact moment
    propagation); horizon degradation is measured as band width vs
    descendant depth — and reported, not hidden.
    """
    ledger = ledger or ReceiptLedger()
    wanted = list(outcomes) if outcomes is not None else list(scm.graph.nodes)
    baseline = _propagate_moments(scm, {}, noise_sd)
    futures: List[Dict[str, Any]] = []
    for a in actions:
        name = str(a.get("name", f"A{len(futures) + 1}"))
        ivs = {k: float(v) for k, v in dict(a.get("interventions", {})).items()}
        if not ivs:
            futures.append(
                {"action": name, "available": False, "reason": "empty intervention"}
            )
            continue
        mutilated, surgery = scm.mutilate(ivs)
        stats = _propagate_moments(mutilated, ivs, noise_sd)
        dists = {o: stats[o] for o in wanted if o in stats}
        receipt = ledger.issue(
            "future_evaluation",
            inputs={"action": name, "interventions": ivs},
            config={"outcomes": wanted},
            output={
                "outcome_means": {o: d["mean"] for o, d in dists.items()},
                "mutilated_graph_sha256": surgery["mutilated_graph_sha256"],
            },
        )
        degradation = [
            {
                "outcome": o,
                "depth": int(d["depth"]),
                "sd": d["sd"],
                "delta_mean": d["mean"] - baseline[o]["mean"],
            }
            for o, d in dists.items()
        ]
        futures.append(
            {
                "action": name,
                "available": True,
                "stage": STAGE_INTERVENTION_EXECUTED,
                "interventions": ivs,
                "outcome_distributions": dists,
                "surgery_edges_cut": surgery["edges_cut"],
                "horizon_degradation": degradation,
                "receipt": receipt.receipt_sha256,
            }
        )
    return {
        "version": CAUSAL_STACK_VERSION,
        "baseline_distributions": {o: baseline[o] for o in wanted if o in baseline},
        "actions": futures,
        "uncertainty_model": "exact Gaussian moment propagation, linear SCM",
        "ledger_verify": ledger.verify()["ok"],
    }


def futures_env(
    scm: StructuralCausalModel,
    noise_sd: Optional[Mapping[str, float]] = None,
):
    """A planning environment backed by the futures model, not point values.

    ``evaluate(interventions)`` mutilates the model and propagates exact
    Gaussian moments (the same engine as :func:`evaluate_futures`). Each
    node reports its mean under the plain name — identical to
    ``planning.scm_env`` — plus ``node@sd``, ``node@p05`` and ``node@p95``,
    so a planner's constraints can bind a distribution quantile (a chance
    constraint) rather than only the expected value.
    """

    def evaluate(interventions: Mapping[str, float]) -> Dict[str, float]:
        ivs = {str(k): float(v) for k, v in dict(interventions).items()}
        model = scm.mutilate(ivs)[0] if ivs else scm
        stats = _propagate_moments(model, ivs, noise_sd)
        out: Dict[str, float] = {}
        for node, st in stats.items():
            out[node] = st["mean"]
            out[f"{node}@sd"] = st["sd"]
            out[f"{node}@p05"] = st["p05"]
            out[f"{node}@p95"] = st["p95"]
        return out

    return evaluate


__all__ = [
    "CAUSAL_STACK_VERSION",
    "futures_env",
    "STAGE_GRAPH_SUPPLIED",
    "STAGE_GRAPH_LEARNED",
    "STAGE_EFFECT_IDENTIFIED",
    "STAGE_EFFECT_NOT_IDENTIFIED",
    "STAGE_EFFECT_ESTIMATED",
    "STAGE_INTERVENTION_EXECUTED",
    "STAGE_COUNTERFACTUAL_GENERATED",
    "IDENTIFIED",
    "PARTIALLY_IDENTIFIED",
    "NOT_IDENTIFIED",
    "UNAVAILABLE",
    "identifiability",
    "discover_structures",
    "compare_worlds",
    "evaluate_futures",
]
