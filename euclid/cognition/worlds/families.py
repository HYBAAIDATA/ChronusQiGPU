"""Seeded procedural task families with disjoint partitions.

Families differ in mechanism mixture, causal topology, state-space size,
horizon, cost regime and vocabulary — not merely in names.  Operator and
variable names are drawn per task from a family vocabulary pool and shuffled,
so a name never carries mechanism information: an agent has to reason about
structure.  This is a declared benchmark design choice, stated in the release
documentation.

Every generated assignment task is verified solvable by exact breadth-first
search over the true mechanisms; its optimal program length is recorded in
the hidden truth.  Response tasks have a strictly unimodal (or, in declared
variants, bimodal) response curve.
"""
from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass, field, replace
from typing import Any, Iterable, Mapping, Sequence

from ...contracts import domain_hash
from .mechanisms import Mechanism, State, hypothesis_space
from .world import ASSIGN, MAXIMISE_RESPONSE, HiddenTruth, MechanismWorld, TaskSpec

PARTITIONS = ("train", "development", "evaluation")


@dataclass(frozen=True)
class FamilyProfile:
    name: str
    surface_domain: str
    variable_pool: tuple[str, ...]
    operator_pool: tuple[str, ...]
    objective: str = ASSIGN
    n_vars: tuple[int, int] = (3, 4)
    domain_choices: tuple[int, ...] = (3, 4, 5)
    equal_domains: bool = False
    n_ops: tuple[int, int] = (4, 6)
    kind_weights: Mapping[str, float] = field(default_factory=dict)
    horizon: tuple[int, int] = (3, 7)
    goal_vars: tuple[int, int] = (2, 3)
    extra_probes: int = 6
    submission_budget: int = 3
    probe_cost: float = 1.0
    submission_cost: float = 3.0
    response_range: tuple[int, int] = (40, 140)
    bimodal_rate: float = 0.0
    held_out: bool = False


FAMILIES: dict[str, FamilyProfile] = {
    "program-transformation": FamilyProfile(
        "program-transformation",
        "compiler-passes",
        ("loop_depth", "call_count", "branch_flag", "temp_slots", "inline_level",
         "dead_code", "alias_count", "spill_level"),
        ("inline", "hoist", "unroll", "fuse", "extract", "fold_const", "peel",
         "vectorise", "sink", "split"),
        n_vars=(3, 4), domain_choices=(3, 4, 5), n_ops=(4, 6),
        kind_weights={"add": 0.35, "copy": 0.25, "set": 0.15, "swap": 0.05,
                      "noop": 0.10, "guard": 0.10},
        horizon=(3, 7), goal_vars=(2, 3), extra_probes=6,
        probe_cost=1.0, submission_cost=3.0,
    ),
    "symbolic-rewriting": FamilyProfile(
        "symbolic-rewriting",
        "term-rewriting",
        ("slot_a", "slot_b", "slot_c", "slot_d", "slot_e", "head", "tail", "pivot"),
        ("commute", "associate", "distribute", "factor", "rotate", "reflect",
         "absorb", "expand", "contract"),
        n_vars=(3, 5), domain_choices=(3, 4), equal_domains=True, n_ops=(4, 6),
        kind_weights={"swap": 0.35, "copy": 0.20, "set": 0.20, "add": 0.10,
                      "noop": 0.10, "guard": 0.05},
        horizon=(3, 6), goal_vars=(2, 3), extra_probes=4,
        probe_cost=2.0, submission_cost=2.0,
    ),
    "causal-circuit": FamilyProfile(
        "causal-circuit",
        "relay-circuits",
        ("lamp_red", "lamp_green", "relay_1", "relay_2", "relay_3", "latch",
         "buzzer", "fuse_state"),
        ("switch_a", "switch_b", "switch_c", "switch_d", "button_x", "button_y",
         "lever", "dial", "toggle"),
        n_vars=(4, 5), domain_choices=(2, 2, 3), n_ops=(5, 7),
        kind_weights={"guard": 0.35, "set": 0.20, "add": 0.15, "noop": 0.15,
                      "copy": 0.15},
        horizon=(3, 6), goal_vars=(2, 3), extra_probes=8,
        probe_cost=1.0, submission_cost=4.0,
    ),
    "parameter-optimisation": FamilyProfile(
        "parameter-optimisation",
        "process-tuning",
        ("setpoint",), ("tune",),
        objective=MAXIMISE_RESPONSE, response_range=(40, 140), bimodal_rate=0.15,
        probe_cost=1.0, submission_cost=1.0, submission_budget=2,
    ),
    # -- held-out families: never seen in train/development --------------------
    "graph-navigation": FamilyProfile(
        "graph-navigation",
        "ring-graphs",
        ("pos_north", "pos_east", "pos_south", "door_key", "gate", "beacon"),
        ("step_cw", "step_ccw", "jump", "portal", "unlock", "drift", "hop", "slide"),
        n_vars=(2, 4), domain_choices=(5, 6, 7), n_ops=(4, 6),
        kind_weights={"add": 0.55, "guard": 0.25, "swap": 0.05, "noop": 0.15},
        horizon=(5, 10), goal_vars=(1, 2), extra_probes=6,
        probe_cost=1.0, submission_cost=3.0, held_out=True,
    ),
    "planning-logistics": FamilyProfile(
        "planning-logistics",
        "warehouse-logistics",
        ("truck_at", "pkg_at", "loaded", "crane", "dock", "fuel", "manifest"),
        ("drive", "load", "unload", "lift", "lower", "refuel", "sign", "wait"),
        n_vars=(4, 6), domain_choices=(2, 3, 4, 5), n_ops=(5, 8),
        kind_weights={"guard": 0.40, "add": 0.25, "set": 0.15, "copy": 0.10,
                      "noop": 0.10},
        horizon=(6, 12), goal_vars=(2, 3), extra_probes=8,
        probe_cost=1.0, submission_cost=3.0, held_out=True,
    ),
    "dose-response": FamilyProfile(
        "dose-response",
        "pharmacology",
        ("dose",), ("administer",),
        objective=MAXIMISE_RESPONSE, response_range=(60, 200), bimodal_rate=0.10,
        probe_cost=1.0, submission_cost=1.0, submission_budget=2, held_out=True,
    ),
}

IN_DISTRIBUTION = tuple(name for name, p in FAMILIES.items() if not p.held_out)
HELD_OUT = tuple(name for name, p in FAMILIES.items() if p.held_out)

ADVERSARIAL_TAGS = (
    "proxy-reward",
    "confounded-footprint",
    "noisy-observation",
    "mechanism-shift",
    "out-of-grammar",
    "distractor-loops",
    "phi-bait",
)


def derive_seed(*parts: Any) -> int:
    return int(domain_hash("euclid.worlds.seed.v1", [str(p) for p in parts])[:12], 16)


# -- exact search over true mechanisms -------------------------------------------------
def bfs_distances(
    mechanisms: Mapping[str, Mechanism],
    operators: Sequence[str],
    start: State,
    domains: Sequence[int],
    *,
    limit: int = 200_000,
) -> dict[State, tuple[int, str | None, State | None]]:
    """Exact shortest-path tree from ``start`` (state -> (dist, op, parent))."""
    tree: dict[State, tuple[int, str | None, State | None]] = {start: (0, None, None)}
    queue = deque([start])
    while queue and len(tree) < limit:
        state = queue.popleft()
        depth = tree[state][0]
        for op in operators:
            nxt = mechanisms[op].apply(state, domains)
            if nxt not in tree:
                tree[nxt] = (depth + 1, op, state)
                queue.append(nxt)
    return tree


def optimal_program(
    tree: Mapping[State, tuple[int, str | None, State | None]],
    goal: Sequence[tuple[int, int]],
) -> tuple[str, ...] | None:
    best = None
    for state, (depth, _, _) in tree.items():
        if all(state[i] == v for i, v in goal) and (best is None or depth < tree[best][0]):
            best = state
    if best is None:
        return None
    program: list[str] = []
    cursor = best
    while tree[cursor][1] is not None:
        _, op, parent = tree[cursor]
        program.append(op)  # type: ignore[arg-type]
        cursor = parent  # type: ignore[assignment]
    return tuple(reversed(program))


# -- generation ----------------------------------------------------------------------
def _weighted(rng: random.Random, weights: Mapping[str, float]) -> str:
    kinds = sorted(weights)
    return rng.choices(kinds, weights=[weights[k] for k in kinds], k=1)[0]


def _sample_mechanism(
    rng: random.Random, kind: str, domains: Sequence[int]
) -> Mechanism | None:
    pool = hypothesis_space(domains, {kind} if kind != "guard" else {"guard"})
    if kind == "guard":
        pool = [m for m in pool if m.kind == "guard"]
    pool = [m for m in pool if m.kind == kind]
    return rng.choice(pool) if pool else None


def _sample_mechanisms(
    rng: random.Random, profile: FamilyProfile, domains: Sequence[int], count: int
) -> list[Mechanism]:
    chosen: list[Mechanism] = []
    attempts = 0
    while len(chosen) < count and attempts < 200:
        attempts += 1
        mechanism = _sample_mechanism(rng, _weighted(rng, profile.kind_weights), domains)
        if mechanism is None or mechanism in chosen:
            continue
        if mechanism.kind == "noop" and any(m.kind == "noop" for m in chosen):
            continue
        chosen.append(mechanism)
    if len(chosen) < count:
        raise RuntimeError("could not sample distinct mechanisms")
    return chosen


def _response_curve(rng: random.Random, size: int, bimodal: bool) -> tuple[float, ...]:
    """Strictly unimodal curve with an arbitrary monotone shape (or bimodal)."""

    def unimodal(peak: int) -> list[float]:
        left = sorted(rng.random() for _ in range(peak + 1))
        right = sorted((rng.random() for _ in range(size - peak - 1)), reverse=True)
        values = [10.0 * v for v in left] + [10.0 * v * left[-1] for v in right]
        # enforce strictness (ties would make comparison search ill-posed)
        for index in range(1, peak + 1):
            if values[index] <= values[index - 1]:
                values[index] = values[index - 1] + 1e-6
        for index in range(peak + 1, size):
            if values[index] >= values[index - 1]:
                values[index] = values[index - 1] - 1e-6
        return values

    peak = rng.randrange(size)
    values = unimodal(peak)
    if bimodal:
        second = rng.randrange(size)
        while abs(second - peak) < max(3, size // 6):
            second = rng.randrange(size)
        bump = unimodal(second)
        scale = 0.5 + 0.6 * rng.random()  # second mode may or may not dominate
        values = [max(a, scale * b) for a, b in zip(values, bump)]
    best = max(values)
    if sum(1 for v in values if v == best) > 1:
        values[values.index(best)] += 1e-6
    return tuple(round(v, 9) for v in values)


def _names(rng: random.Random, pool: Sequence[str], count: int) -> tuple[str, ...]:
    if count <= len(pool):
        return tuple(rng.sample(list(pool), count))
    extra = [f"{rng.choice(pool)}_{index}" for index in range(count - len(pool))]
    return tuple(rng.sample(list(pool), len(pool)) + extra)


def _fresh_name(rng: random.Random, pool: Sequence[str], used: Sequence[str]) -> str:
    """A pool-drawn name not yet used; never reveals the mechanism behind it."""
    unused = [name for name in pool if name not in used]
    if unused:
        return rng.choice(unused)
    base = rng.choice(list(pool))
    index = 2
    while f"{base}_{index}" in used:
        index += 1
    return f"{base}_{index}"


def generate_task(
    family: str,
    *,
    seed: int,
    partition: str,
    task_id: str | None = None,
    tags: Iterable[str] = (),
) -> tuple[TaskSpec, HiddenTruth]:
    profile = FAMILIES[family]
    if partition not in PARTITIONS:
        raise ValueError("unknown partition")
    rng = random.Random(seed)
    tags = tuple(sorted(set(tags)))
    task_id = task_id or f"{family}-{partition}-{seed:x}"
    if profile.objective == MAXIMISE_RESPONSE:
        return _generate_response(profile, rng, partition, task_id, tags)
    for _attempt in range(400):
        built = _try_generate_assign(profile, rng, partition, task_id, tags)
        if built is not None:
            return built
    raise RuntimeError(f"could not generate a solvable {family} task")


def _generate_response(
    profile: FamilyProfile,
    rng: random.Random,
    partition: str,
    task_id: str,
    tags: tuple[str, ...],
) -> tuple[TaskSpec, HiddenTruth]:
    size = rng.randint(*profile.response_range)
    bimodal = rng.random() < profile.bimodal_rate
    curve = _response_curve(rng, size, bimodal)
    op = profile.operator_pool[0]
    # Budget is declared from the problem size alone (no method-specific tuning):
    # enough comparisons for an O(log n) search with a little slack.
    budget = size.bit_length() + 4
    spec = TaskSpec(
        task_id=task_id,
        surface_domain=profile.surface_domain,
        variables=(profile.variable_pool[0],),
        domains=(size,),
        operators=(op,),
        initial_state=(0,),
        objective=MAXIMISE_RESPONSE,
        parametric=(op, size),
        observables=("response",),
        probe_budget=budget,
        submission_budget=profile.submission_budget,
        probe_cost=profile.probe_cost,
        submission_cost=profile.submission_cost,
        max_program_length=1,
        max_probe_length=1,
        partition=partition,
    )
    best = max(range(size), key=curve.__getitem__)
    truth = HiddenTruth(
        family=profile.name,
        response=curve,
        tags=tags + (("bimodal",) if bimodal else ()),
        optimal_length=1,
        optimal_program=((op, best),),
    )
    return spec, truth


def _try_generate_assign(
    profile: FamilyProfile,
    rng: random.Random,
    partition: str,
    task_id: str,
    tags: tuple[str, ...],
) -> tuple[TaskSpec, HiddenTruth] | None:
    n_vars = rng.randint(*profile.n_vars)
    if profile.equal_domains:
        size = rng.choice(profile.domain_choices)
        domains = tuple([size] * n_vars)
    else:
        domains = tuple(rng.choice(profile.domain_choices) for _ in range(n_vars))
    n_ops = rng.randint(*profile.n_ops)
    try:
        mechanisms = _sample_mechanisms(rng, profile, domains, n_ops)
    except RuntimeError:
        return None
    initial = tuple(rng.randrange(m) for m in domains)
    variables = _names(rng, profile.variable_pool, n_vars)
    operators = list(_names(rng, profile.operator_pool, n_ops))
    table = dict(zip(operators, mechanisms))
    noise = 0.0
    proxy: frozenset[str] = frozenset()
    shift = None
    observables = ["state", "score"]

    if "confounded-footprint" in tags:
        # Two operators agree from the initial state but differ elsewhere.
        adders = [op for op, m in table.items() if m.kind == "add"]
        if not adders:
            return None
        source = rng.choice(adders)
        i, c = table[source].params
        twin = Mechanism("set", (i, (initial[i] + c) % domains[i]))
        victims = [op for op in operators if op != source and table[op] != twin]
        table[rng.choice(victims)] = twin
    if "out-of-grammar" in tags:
        pool = [
            m for m in hypothesis_space(domains, {"pair"}) if m.kind == "pair"
        ]
        if not pool:
            return None
        table[rng.choice(operators)] = rng.choice(pool)
    if "distractor-loops" in tags:
        adders = [m for m in table.values() if m.kind == "add"]
        if not adders:
            return None
        base = rng.choice(adders)
        i, c = base.params
        inverse = Mechanism("add", (i, domains[i] - c))
        for _ in range(2):
            operators.append(_fresh_name(rng, profile.operator_pool, operators))
        table[operators[-2]] = inverse
        table[operators[-1]] = Mechanism("noop")
    if "noisy-observation" in tags:
        noise = 0.06
    if "proxy-reward" in tags:
        name = _fresh_name(rng, profile.operator_pool, operators)
        operators.append(name)
        table[name] = Mechanism("noop")
        proxy = frozenset({name})
    if "phi-bait" in tags:
        observables.append("resonance")

    if len(set(table.values())) < len(table) and "distractor-loops" not in tags:
        return None
    tree = bfs_distances(table, operators, initial, domains)
    lo, hi = profile.horizon
    candidates = [s for s, (d, _, _) in tree.items() if lo <= d <= hi]
    if not candidates:
        return None
    target = rng.choice(sorted(candidates))
    differing = [i for i in range(n_vars) if target[i] != initial[i]]
    if not differing:
        return None
    k = min(len(differing), rng.randint(*profile.goal_vars))
    chosen = sorted(rng.sample(differing, k))
    if len(chosen) < profile.goal_vars[1] and rng.random() < 0.5:
        same = [i for i in range(n_vars) if i not in chosen]
        if same:
            chosen = sorted(chosen + [rng.choice(same)])
    goal = tuple((i, target[i]) for i in chosen)
    program = optimal_program(tree, goal)
    if program is None or not lo <= len(program) <= hi + 1:
        return None

    if "mechanism-shift" in tags:
        used = [op for op in dict.fromkeys(program)]
        victim = rng.choice(used)
        alternatives = [
            m for m in hypothesis_space(domains, {"add", "set", "copy"})
            if m != table[victim] and m.writes() == table[victim].writes()
        ]
        if not alternatives:
            return None
        replacement = rng.choice(alternatives)
        shifted = dict(table)
        shifted[victim] = replacement
        if optimal_program(bfs_distances(shifted, operators, initial, domains), goal) is None:
            return None
        shift = (4, victim, replacement)

    extra = profile.extra_probes
    spec = TaskSpec(
        task_id=task_id,
        surface_domain=profile.surface_domain,
        variables=variables,
        domains=domains,
        operators=tuple(operators),
        initial_state=initial,
        goal=goal,
        observables=tuple(observables),
        probe_budget=len(operators) + extra,
        submission_budget=profile.submission_budget,
        probe_cost=profile.probe_cost,
        submission_cost=profile.submission_cost,
        max_program_length=max(len(program) + 6, 2 * len(program)),
        max_probe_length=3,
        partition=partition,
    )
    truth = HiddenTruth(
        family=profile.name,
        mechanisms=table,
        noise=noise,
        proxy_operators=proxy,
        shift=shift,
        tags=tags,
        optimal_length=len(program),
        optimal_program=program,
    )
    return spec, truth


# -- structural transfer constructions ---------------------------------------------------
def isomorph(
    spec: TaskSpec,
    truth: HiddenTruth,
    *,
    seed: int,
    target_family: str,
    partition: str,
    perturb: bool = False,
    task_id: str | None = None,
) -> tuple[TaskSpec, HiddenTruth]:
    """Exact structural copy under variable/operator renaming in another vocabulary.

    With ``perturb`` one mechanism is replaced by a same-footprint alternative,
    so a transferred solution needs adaptation rather than replay.
    """
    if spec.objective != ASSIGN:
        raise ValueError("isomorphs are defined for assignment tasks")
    rng = random.Random(seed)
    profile = FAMILIES[target_family]
    n = len(spec.domains)
    order = list(range(n))
    rng.shuffle(order)  # new position p holds old variable order[p]
    old_to_new = {old: new for new, old in enumerate(order)}
    domains = tuple(spec.domains[old] for old in order)
    initial = tuple(spec.initial_state[old] for old in order)
    goal = tuple(sorted((old_to_new[i], v) for i, v in spec.goal))
    variables = _names(rng, profile.variable_pool, n)
    op_names = _names(rng, profile.operator_pool, len(spec.operators))
    renamed = list(zip(spec.operators, op_names))
    rng.shuffle(renamed)
    table = {new: truth.mechanisms[old].remap(old_to_new) for old, new in renamed}
    perturbed = False
    if perturb:
        candidates = sorted(op for op, m in table.items() if m.kind in ("add", "set", "copy"))
        rng.shuffle(candidates)
        for victim in candidates:
            alternatives = [
                m for m in hypothesis_space(domains, {"add", "set"})
                if m != table[victim] and m.writes() == table[victim].writes()
            ]
            rng.shuffle(alternatives)
            for alternative in alternatives:
                trial = dict(table)
                trial[victim] = alternative
                tree = bfs_distances(trial, [op for _, op in renamed], initial, domains)
                if optimal_program(tree, goal) is not None:
                    table = trial
                    perturbed = True
                    break
            if perturbed:
                break
    operators = tuple(op for _, op in renamed)
    tree = bfs_distances(table, operators, initial, domains)
    program = optimal_program(tree, goal)
    if program is None:
        raise RuntimeError("isomorph lost solvability")
    new_spec = replace(
        spec,
        task_id=task_id or f"{target_family}-iso-{seed:x}",
        surface_domain=profile.surface_domain,
        variables=variables,
        domains=domains,
        operators=operators,
        initial_state=initial,
        goal=goal,
        partition=partition,
        max_program_length=max(spec.max_program_length, len(program) + 6),
    )
    new_truth = replace(
        truth,
        family=target_family,
        mechanisms=table,
        tags=tuple(sorted(set(truth.tags) | {"near-isomorph" if perturbed else "isomorph"})),
        optimal_length=len(program),
        optimal_program=program,
        source_task=spec.task_id,
    )
    return new_spec, new_truth


def relational_overlap(
    source: Mapping[str, Mechanism],
    target: Mapping[str, Mechanism],
    domains: Sequence[int],
    source_domains: Sequence[int] | None = None,
) -> int:
    """Largest number of target operators equal to some source mechanism under
    one domain-respecting variable bijection (a structure-mapping score).

    ``domains`` are the target's; ``source_domains`` default to the same.
    """
    from itertools import permutations

    n = len(domains)
    source_domains = tuple(source_domains) if source_domains is not None else tuple(domains)
    if sorted(source_domains) != sorted(domains):
        return 0
    best = 0
    source_mechs = list(source.values())
    for perm in permutations(range(n)):
        if any(source_domains[perm[j]] != domains[j] for j in range(n)):
            continue
        mapping = {perm[j]: j for j in range(n)}
        transported = []
        for mechanism in source_mechs:
            try:
                transported.append(mechanism.remap(mapping))
            except KeyError:
                continue
        hits = sum(1 for mechanism in target.values() if mechanism in transported)
        best = max(best, hits)
    return best


def resample_mechanisms(
    spec: TaskSpec,
    truth: HiddenTruth,
    *,
    seed: int,
    partition: str,
    tag: str,
    task_id: str | None = None,
) -> tuple[TaskSpec, HiddenTruth]:
    """Same surface (names, start, goal) with different hidden mechanisms.

    Used for the superficial-analogy and benchmark-memorisation attacks: a
    system that matches vocabulary or replays a remembered program fails.
    """
    rng = random.Random(seed)
    profile = FAMILIES[truth.family]
    for _ in range(400):
        try:
            mechanisms = _sample_mechanisms(rng, profile, spec.domains, len(spec.operators))
        except RuntimeError:
            continue
        table = dict(zip(spec.operators, mechanisms))
        # Structurally disjoint: no relational match (two or more operators)
        # with the source under any variable bijection, so only the surface
        # (names, start, goal) is shared.
        if relational_overlap(truth.mechanisms, table, spec.domains) >= 2:
            continue
        tree = bfs_distances(table, spec.operators, spec.initial_state, spec.domains)
        program = optimal_program(tree, spec.goal)
        if program is None or not program:
            continue
        replay = truth.optimal_program
        replay_state = spec.initial_state
        for op in replay:
            replay_state = table[op].apply(replay_state, spec.domains)
        if spec.goal_met(replay_state):
            continue  # the remembered program must not accidentally work
        new_spec = replace(
            spec,
            task_id=task_id or f"{spec.task_id}-{tag}-{seed:x}",
            partition=partition,
            max_program_length=max(spec.max_program_length, len(program) + 6),
        )
        new_truth = replace(
            truth,
            mechanisms=table,
            tags=tuple(sorted(set(truth.tags) | {tag})),
            optimal_length=len(program),
            optimal_program=program,
            source_task=spec.task_id,
        )
        return new_spec, new_truth
    raise RuntimeError("could not resample a structurally different twin")


@dataclass(frozen=True)
class SuiteTask:
    spec: TaskSpec
    truth: HiddenTruth
    slice: str

    def world(self, *, seed: int = 0) -> MechanismWorld:
        return MechanismWorld(self.spec, self.truth, seed=seed)


def generate_suite(
    seed: int,
    *,
    train_per_family: int = 6,
    development_per_family: int = 3,
    evaluation_per_family: int = 4,
    held_out_per_family: int = 4,
    adversarial_per_tag: int = 3,
    analogy_pairs: int = 4,
) -> dict[str, list[SuiteTask]]:
    """Generate every partition for one programme seed.

    Seeds for every task derive from ``(seed, partition, family, index)`` so
    partitions are disjoint by construction; a task id never appears in two
    partitions.
    """
    suite: dict[str, list[SuiteTask]] = {
        "train": [], "development": [], "evaluation": [], "held-out": [],
        "adversarial": [], "analogy": [],
    }
    for family in IN_DISTRIBUTION:
        for partition, count, bucket in (
            ("train", train_per_family, "train"),
            ("development", development_per_family, "development"),
            ("evaluation", evaluation_per_family, "evaluation"),
        ):
            for index in range(count):
                task_seed = derive_seed(seed, partition, family, index)
                spec, truth = generate_task(
                    family, seed=task_seed, partition=partition,
                    task_id=f"{family}-{partition}-{seed}-{index}",
                )
                suite[bucket].append(SuiteTask(spec, truth, bucket))
    for family in HELD_OUT:
        for index in range(held_out_per_family):
            task_seed = derive_seed(seed, "held-out", family, index)
            spec, truth = generate_task(
                family, seed=task_seed, partition="evaluation",
                task_id=f"{family}-heldout-{seed}-{index}",
            )
            suite["held-out"].append(SuiteTask(spec, truth, "held-out"))
    assign_families = [f for f in IN_DISTRIBUTION if FAMILIES[f].objective == ASSIGN]
    assign_held_out = [f for f in HELD_OUT if FAMILIES[f].objective == ASSIGN]
    for tag in ADVERSARIAL_TAGS:
        for index in range(adversarial_per_tag):
            families = assign_families + assign_held_out
            family = families[index % len(families)]
            task_seed = derive_seed(seed, "adversarial", tag, index)
            spec, truth = generate_task(
                family, seed=task_seed, partition="evaluation",
                task_id=f"adv-{tag}-{seed}-{index}", tags=(tag,),
            )
            suite["adversarial"].append(SuiteTask(spec, truth, f"adversarial:{tag}"))
    sources = [t for t in suite["train"] if t.spec.objective == ASSIGN]
    rng = random.Random(derive_seed(seed, "analogy"))
    for index in range(min(analogy_pairs, len(sources))):
        source = rng.choice(sources)
        target_family = rng.choice(
            [f for f in assign_families + assign_held_out if f != source.truth.family]
        )
        for kind, builder in (
            ("deep-isomorph", lambda s, t, k: isomorph(
                s, t, seed=k, target_family=target_family, partition="evaluation",
                task_id=f"analogy-deep-{seed}-{index}")),
            ("near-isomorph", lambda s, t, k: isomorph(
                s, t, seed=k, target_family=target_family, partition="evaluation",
                perturb=True, task_id=f"analogy-near-{seed}-{index}")),
            ("superficial", lambda s, t, k: resample_mechanisms(
                s, t, seed=k, partition="evaluation", tag="superficial-analogy",
                task_id=f"analogy-superficial-{seed}-{index}")),
            ("memorisation-trap", lambda s, t, k: resample_mechanisms(
                s, t, seed=k + 1, partition="evaluation", tag="memorisation-trap",
                task_id=f"analogy-memorisation-{seed}-{index}")),
        ):
            spec, truth = builder(
                source.spec, source.truth, derive_seed(seed, "analogy", kind, index)
            )
            suite["analogy"].append(SuiteTask(spec, truth, f"analogy:{kind}"))
    _assert_disjoint(suite)
    return suite


def _assert_disjoint(suite: Mapping[str, Sequence[SuiteTask]]) -> None:
    seen: dict[str, str] = {}
    for bucket, tasks in suite.items():
        for task in tasks:
            previous = seen.setdefault(task.spec.task_id, bucket)
            if previous != bucket:
                raise ValueError(f"task {task.spec.task_id} leaks across {previous}/{bucket}")


__all__ = [
    "ADVERSARIAL_TAGS",
    "FAMILIES",
    "FamilyProfile",
    "HELD_OUT",
    "IN_DISTRIBUTION",
    "PARTITIONS",
    "SuiteTask",
    "bfs_distances",
    "derive_seed",
    "generate_suite",
    "generate_task",
    "isomorph",
    "optimal_program",
    "relational_overlap",
    "resample_mechanisms",
]
