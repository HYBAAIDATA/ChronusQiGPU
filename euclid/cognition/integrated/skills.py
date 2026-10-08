"""Autonomous primitive discovery and an evidence-gated skill hierarchy.

Lifecycle of a candidate operator (every transition is an event record):

``discover → abstract → parameterise → sandbox → validate → compare →
generalise → adversarial test → sign → persist → reuse → monitor →
promote / deprecate``

* **discover** — contiguous windows of successful programs, rewritten as
  vocabulary-free mechanism patterns over role variables, recur across
  distinct tasks.
* **abstract / parameterise** — anti-unification across occurrences turns
  disagreeing constants into wildcards; agreeing constants stay literal.
* **sandbox** — the pattern's canonical instantiation is executed on a fixed
  probe corpus; its outputs define the semantic digest (what the macro *does*).
* **validate / generalise / adversarial** — planning with versus without the
  macro on stored task models: it must save search on the discovery tasks,
  save search on tasks it was *not* discovered from, and never turn a solvable
  task into a failure.
* **compare** — a macro semantically identical to an existing skill is a
  duplicate and is rejected.
* **sign / persist** — the record is sealed; reload recomputes the semantic
  digest and refuses a mismatch, so semantics (not just metadata) survive
  restart.
* **monitor / deprecate** — usage in later plans is tracked; capacity is
  bounded and the least useful skill is deprecated (history retained).
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from ...contracts import domain_hash
from ..worlds.mechanisms import Mechanism, canonical_roles, mechanism_variables
from .planning import plan

WILDCARD = "*"
_SEMANTIC_DOMAIN = "euclid.skill.semantics.v1"
_SEAL_DOMAIN = "euclid.skill.record.v1"


def _freeze(value: Any) -> Any:
    if isinstance(value, list):
        return tuple(_freeze(v) for v in value)
    return value


def abstract_window(mechanisms: Sequence[Mechanism]) -> tuple:
    """Role-canonical, vocabulary-free signature of a mechanism window."""
    variables: list[int] = []
    for mechanism in mechanisms:
        variables.extend(mechanism_variables(mechanism))
    roles = canonical_roles(variables)
    return tuple(m.abstract(roles) for m in mechanisms)


def _skeleton(step: Any) -> Any:
    """Replace integer constants by wildcards (keeps kinds and role structure)."""
    if isinstance(step, tuple):
        return tuple(_skeleton(part) for part in step)
    if isinstance(step, int) and not isinstance(step, bool):
        return WILDCARD
    return step


def anti_unify(patterns: Sequence[tuple]) -> tuple:
    """Most specific generalisation: constants that differ become wildcards."""

    def merge(parts: Sequence[Any]) -> Any:
        first = parts[0]
        if isinstance(first, tuple):
            return tuple(merge([p[i] for p in parts]) for i in range(len(first)))
        return first if all(p == first for p in parts) else WILDCARD

    return tuple(merge([p[i] for p in patterns]) for i in range(len(patterns[0])))


def _match_step(mechanism: Mechanism, pattern: Any, roles: dict[str, int]) -> dict[str, int] | None:
    """Extend a role→variable binding so ``mechanism`` matches a pattern step."""
    kind = pattern[0]
    if mechanism.kind != kind:
        return None
    bound = dict(roles)

    def bind_role(role: str, var: int) -> bool:
        if role in bound:
            return bound[role] == var
        if var in bound.values():
            return False
        bound[role] = var
        return True

    def bind_const(expected: Any, actual: int) -> bool:
        return expected == WILDCARD or expected == actual

    if kind == "noop":
        return bound
    if kind in ("add", "set"):
        return bound if bind_role(pattern[1], mechanism.params[0]) and bind_const(
            pattern[2], mechanism.params[1]) else None
    if kind in ("copy", "swap"):
        return bound if bind_role(pattern[1], mechanism.params[0]) and bind_role(
            pattern[2], mechanism.params[1]) else None
    if kind == "guard":
        if not (bind_role(pattern[1], mechanism.params[0])
                and bind_const(pattern[2], mechanism.params[1])):
            return None
        return _match_step(mechanism.inner, pattern[3], bound)  # type: ignore[arg-type]
    if kind == "pair":
        inner = _match_step(mechanism.inner, pattern[1], bound)  # type: ignore[arg-type]
        return _match_step(mechanism.second, pattern[2], inner) if inner is not None else None  # type: ignore[arg-type]
    return None


def instantiate(pattern: tuple, roles: Mapping[str, int], fill: int = 1) -> list[Mechanism]:
    """Concrete mechanisms for a pattern (wildcards filled with ``fill``)."""

    def build(step: Any) -> Mechanism:
        kind = step[0]
        const = (lambda c: fill if c == WILDCARD else int(c))
        if kind == "noop":
            return Mechanism("noop")
        if kind in ("add", "set"):
            return Mechanism(kind, (roles[step[1]], const(step[2])))
        if kind == "copy":
            return Mechanism(kind, (roles[step[1]], roles[step[2]]))
        if kind == "swap":
            a, b = sorted((roles[step[1]], roles[step[2]]))
            return Mechanism(kind, (a, b))
        if kind == "guard":
            return Mechanism(kind, (roles[step[1]], const(step[2])), build(step[3]))
        return Mechanism(kind, (), build(step[1]), build(step[2]))

    return [build(step) for step in pattern]


def _roles_of(pattern: Any, found: list[str]) -> list[str]:
    if isinstance(pattern, tuple):
        for part in pattern:
            _roles_of(part, found)
    elif isinstance(pattern, str) and pattern.startswith("r") and pattern[1:].isdigit():
        if pattern not in found:
            found.append(pattern)
    return found


def semantic_digest(pattern: tuple) -> str:
    """Outputs of the canonical instantiation on a fixed probe corpus."""
    roles = _roles_of(pattern, [])
    binding = {role: index for index, role in enumerate(roles)}
    size = max(2, len(roles))
    domains = tuple([5] * size)
    rng = random.Random(1729)
    corpus = [tuple(rng.randrange(5) for _ in range(size)) for _ in range(48)]
    try:
        mechanisms = instantiate(pattern, binding)
    except (KeyError, ValueError):
        return "uninstantiable"
    outputs = []
    for state in corpus:
        current = state
        for mechanism in mechanisms:
            current = mechanism.apply(current, domains)
        outputs.append(list(current))
    return domain_hash(_SEMANTIC_DOMAIN, {"pattern": repr(pattern), "outputs": outputs})


@dataclass
class SkillRecord:
    skill_id: str
    pattern: tuple
    level: str
    provenance: str
    support: set[str] = field(default_factory=set)
    surfaces: set[str] = field(default_factory=set)
    status: str = "candidate"
    dependencies: tuple[str, ...] = ()
    semantic: str = ""
    discovery_utility: float | None = None
    held_out_utility: float | None = None
    adversarial_failures: int = 0
    uses: int = 0
    successes: int = 0
    failures: int = 0
    transfers: int = 0
    events: list[dict[str, Any]] = field(default_factory=list)

    def body(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "pattern": repr(self.pattern),
            "level": self.level,
            "provenance": self.provenance,
            "support": sorted(self.support),
            "surfaces": sorted(self.surfaces),
            "status": self.status,
            "dependencies": list(self.dependencies),
            "semantic": self.semantic,
            "discovery_utility": self.discovery_utility,
            "held_out_utility": self.held_out_utility,
            "adversarial_failures": self.adversarial_failures,
            "uses": self.uses,
            "successes": self.successes,
            "failures": self.failures,
            "transfers": self.transfers,
            "events": list(self.events),
        }


@dataclass(frozen=True)
class TaskModel:
    """A stored, verified task model used to measure skill utility."""

    task_id: str
    surface: str
    domains: tuple[int, ...]
    operators: tuple[str, ...]
    table: Mapping[str, Mechanism]
    start: tuple[int, ...]
    goal: tuple[tuple[int, int], ...]
    max_length: int


class SkillLibrary:
    """Evidence-gated macro skills with bounded growth and full history."""

    def __init__(
        self,
        *,
        min_support: int = 2,
        capacity: int = 16,
        window_lengths: Sequence[int] = (2, 3, 4),
        trial_budget: int = 600,
    ) -> None:
        self.min_support = int(min_support)
        self.capacity = int(capacity)
        self.window_lengths = tuple(window_lengths)
        self.trial_budget = int(trial_budget)
        self.records: dict[str, SkillRecord] = {}
        self.occurrences: dict[tuple, list[tuple[str, str, tuple]]] = {}
        self.corpus: dict[str, TaskModel] = {}
        self.events: list[dict[str, Any]] = []
        self.revision = 0

    # -- discovery ---------------------------------------------------------------------
    def observe_solution(
        self,
        task: TaskModel,
        program: Sequence[str],
    ) -> list[str]:
        """Add a verified solution; return skeletons whose support grew."""
        self.corpus[task.task_id] = task
        mechanisms = [task.table[op] for op in program]
        grown = []
        for length in self.window_lengths:
            for start in range(0, len(mechanisms) - length + 1):
                window = mechanisms[start:start + length]
                if any(m.kind == "noop" for m in window):
                    continue
                pattern = abstract_window(window)
                key = _skeleton(pattern)
                rows = self.occurrences.setdefault(key, [])
                if all(row[0] != task.task_id for row in rows):
                    rows.append((task.task_id, task.surface, pattern))
                    grown.append(repr(key))
        self.revision += 1
        return grown

    def candidates(self) -> list[SkillRecord]:
        """Abstract and parameterise recurring windows into candidate skills."""
        created = []
        for key, rows in sorted(self.occurrences.items(), key=lambda kv: repr(kv[0])):
            if len({row[0] for row in rows}) < self.min_support:
                continue
            pattern = anti_unify([row[2] for row in rows])
            skill_id = "skill-" + domain_hash("euclid.skill.id.v1", repr(pattern))[:16]
            record = self.records.get(skill_id)
            if record is None:
                dependencies = tuple(
                    other.skill_id for other in self.records.values()
                    if other.status == "promoted" and len(other.pattern) < len(pattern)
                    and _contains(pattern, other.pattern)
                )
                record = SkillRecord(
                    skill_id, pattern,
                    "composed-skill" if dependencies else "composed-primitive",
                    provenance="window-mining:" + ",".join(sorted({r[0] for r in rows})[:6]),
                    dependencies=dependencies,
                )
                record.events.append({"event": "discovered", "support": len(rows)})
                record.events.append({"event": "abstracted",
                                      "wildcards": repr(pattern).count(WILDCARD)})
                self.records[skill_id] = record
                created.append(record)
            record.support = {row[0] for row in rows}
            record.surfaces = {row[1] for row in rows}
        return created

    # -- binding ---------------------------------------------------------------------------
    def bind_pattern(
        self, pattern: tuple, table: Mapping[str, Mechanism], operators: Sequence[str],
        *, limit: int = 4,
    ) -> list[tuple[str, ...]]:
        results: list[tuple[str, ...]] = []

        def walk(index: int, roles: dict[str, int], chosen: list[str]) -> None:
            if len(results) >= limit:
                return
            if index == len(pattern):
                results.append(tuple(chosen))
                return
            for op in operators:
                mechanism = table.get(op)
                if mechanism is None:
                    continue
                extended = _match_step(mechanism, pattern[index], roles)
                if extended is not None:
                    walk(index + 1, extended, chosen + [op])

        walk(0, {}, [])
        return results

    def bind(
        self, table: Mapping[str, Mechanism], operators: Sequence[str],
        *, statuses: Iterable[str] = ("promoted",),
    ) -> dict[str, tuple[str, ...]]:
        allowed = set(statuses)
        bound: dict[str, tuple[str, ...]] = {}
        for record in sorted(self.records.values(), key=lambda r: r.skill_id):
            if record.status not in allowed:
                continue
            for ops in self.bind_pattern(record.pattern, table, operators):
                bound[f"{record.skill_id}:{'+'.join(ops)}"] = ops
        return bound

    # -- validation ------------------------------------------------------------------------
    def _utility(self, record: SkillRecord, task: TaskModel) -> tuple[float, bool] | None:
        bindings = self.bind_pattern(record.pattern, task.table, task.operators)
        if not bindings:
            return None
        macros = {f"m{i}": ops for i, ops in enumerate(bindings)}
        without = plan(task.table, task.operators, task.start, task.goal, task.domains,
                       max_length=task.max_length, node_budget=self.trial_budget)
        with_macro = plan(task.table, task.operators, task.start, task.goal, task.domains,
                          max_length=task.max_length, node_budget=self.trial_budget,
                          macros=macros)
        broke = without.found and not with_macro.found
        if not without.found and with_macro.found:
            return 1.0, broke
        if not with_macro.found:
            return (-1.0 if without.found else 0.0), broke
        base = max(1, without.expanded)
        return (without.expanded - with_macro.expanded) / base, broke

    def lifecycle(self) -> list[dict[str, Any]]:
        """Run sandbox, validation, comparison and promotion on candidates."""
        report = []
        self.candidates()
        promoted_semantics = {
            r.semantic: r.skill_id for r in self.records.values() if r.status == "promoted"
        }
        for record in sorted(self.records.values(), key=lambda r: r.skill_id):
            if record.status != "candidate":
                continue
            record.semantic = semantic_digest(record.pattern)
            record.events.append({"event": "sandboxed", "semantic": record.semantic[:16]})
            if record.semantic == "uninstantiable":
                record.status = "rejected"
                record.events.append({"event": "rejected", "reason": "uninstantiable"})
                continue
            if record.semantic in promoted_semantics:
                record.status = "rejected"
                record.events.append({"event": "rejected", "reason": "duplicate-semantics",
                                      "of": promoted_semantics[record.semantic]})
                continue
            discovery, held_out, broken = [], [], 0
            for task_id, task in sorted(self.corpus.items()):
                measured = self._utility(record, task)
                if measured is None:
                    continue
                utility, broke = measured
                broken += int(broke)
                (discovery if task_id in record.support else held_out).append(utility)
            record.discovery_utility = (
                sum(discovery) / len(discovery) if discovery else None
            )
            record.held_out_utility = sum(held_out) / len(held_out) if held_out else None
            record.adversarial_failures = broken
            record.events.append({
                "event": "validated",
                "discovery_utility": record.discovery_utility,
                "held_out_utility": record.held_out_utility,
                "held_out_tasks": len(held_out),
                "adversarial_failures": broken,
            })
            accepted = (
                record.discovery_utility is not None
                and record.discovery_utility > 0.0
                and record.held_out_utility is not None
                and record.held_out_utility > 0.0
                and broken == 0
            )
            if not accepted:
                if record.held_out_utility is None:
                    record.events.append({"event": "awaiting-generalisation-evidence"})
                    continue
                record.status = "rejected"
                record.events.append({"event": "rejected", "reason": "no-measured-benefit"})
                report.append({"skill_id": record.skill_id, "status": "rejected"})
                continue
            record.status = "promoted"
            if record.level == "composed-primitive":
                record.level = "skill"
            record.events.append({"event": "signed", "seal": self.seal(record)[:16]})
            record.events.append({"event": "promoted"})
            promoted_semantics[record.semantic] = record.skill_id
            report.append({"skill_id": record.skill_id, "status": "promoted",
                           "pattern": repr(record.pattern)})
        self._enforce_capacity(report)
        self.events.extend(report)
        return report

    def _enforce_capacity(self, report: list[dict[str, Any]]) -> None:
        promoted = [r for r in self.records.values() if r.status == "promoted"]
        if len(promoted) <= self.capacity:
            return

        def score(record: SkillRecord) -> tuple:
            monitored = (record.successes - record.failures) / max(1, record.uses)
            return (monitored, record.held_out_utility or 0.0, record.skill_id)

        for record in sorted(promoted, key=score)[: len(promoted) - self.capacity]:
            self.deprecate(record.skill_id, "capacity: lowest measured utility")
            report.append({"skill_id": record.skill_id, "status": "deprecated"})

    # -- monitoring ---------------------------------------------------------------------------
    def record_use(self, label: str, success: bool, *, surface: str) -> None:
        skill_id = label.split(":", 1)[0]
        record = self.records.get(skill_id)
        if record is None:
            return
        record.uses += 1
        record.successes += int(success)
        record.failures += int(not success)
        if surface not in record.surfaces:
            record.transfers += 1
        if record.uses >= 6 and record.failures > 2 * record.successes:
            self.deprecate(skill_id, "monitored: plans using it mostly fail")

    def deprecate(self, skill_id: str, rationale: str) -> None:
        record = self.records[skill_id]
        record.status = "deprecated"
        record.events.append({"event": "deprecated", "rationale": rationale})

    # -- persistence ----------------------------------------------------------------------------
    def seal(self, record: SkillRecord) -> str:
        return domain_hash(_SEAL_DOMAIN, record.body())

    def to_payload(self) -> dict[str, Any]:
        rows = []
        for record in sorted(self.records.values(), key=lambda r: r.skill_id):
            body = record.body()
            rows.append({**body, "pattern_json": _to_json(record.pattern),
                         "seal": domain_hash(_SEAL_DOMAIN, body)})
        return {"schema": "euclid.skill-library/1", "skills": rows}

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any], **kwargs: Any) -> "SkillLibrary":
        if payload.get("schema") != "euclid.skill-library/1":
            raise ValueError("unsupported skill-library schema")
        library = cls(**kwargs)
        for row in payload.get("skills", ()):
            pattern = _freeze(row["pattern_json"])
            record = SkillRecord(
                row["skill_id"], pattern, row["level"], row["provenance"],
                set(row["support"]), set(row["surfaces"]), row["status"],
                tuple(row["dependencies"]), row["semantic"], row["discovery_utility"],
                row["held_out_utility"], int(row["adversarial_failures"]),
                int(row["uses"]), int(row["successes"]), int(row["failures"]),
                int(row["transfers"]), list(row["events"]),
            )
            if domain_hash(_SEAL_DOMAIN, record.body()) != row["seal"]:
                raise ValueError(f"skill {record.skill_id} seal mismatch")
            if record.semantic and semantic_digest(pattern) != record.semantic:
                raise ValueError(f"skill {record.skill_id} semantics changed across restart")
            library.records[record.skill_id] = record
        return library

    def summary(self) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for record in self.records.values():
            counts[record.status] = counts.get(record.status, 0) + 1
        return {
            "by_status": counts,
            "promoted": [
                {"skill_id": r.skill_id, "pattern": repr(r.pattern), "level": r.level,
                 "support": len(r.support), "uses": r.uses, "successes": r.successes,
                 "held_out_utility": r.held_out_utility, "surfaces": sorted(r.surfaces)}
                for r in sorted(self.records.values(), key=lambda r: r.skill_id)
                if r.status == "promoted"
            ],
            "corpus": len(self.corpus),
        }


def _contains(pattern: tuple, inner: tuple) -> bool:
    skeleton = [_skeleton(step) for step in pattern]
    target = [_skeleton(step) for step in inner]
    return any(skeleton[i:i + len(target)] == target for i in range(len(skeleton)))


def _to_json(value: Any) -> Any:
    if isinstance(value, tuple):
        return [_to_json(v) for v in value]
    return value


__all__ = [
    "SkillLibrary",
    "SkillRecord",
    "TaskModel",
    "WILDCARD",
    "abstract_window",
    "anti_unify",
    "instantiate",
    "semantic_digest",
]
