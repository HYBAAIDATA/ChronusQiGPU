"""Structural analogy: relational matching that ignores vocabulary.

A stored *causal structure* (identified mechanisms over variables, plus the
solution programme) is matched against the current task by searching for a
variable bijection (respecting domains) and an operator correspondence under
which the source mechanisms reproduce every transition observed so far in the
target.  Names never participate; surface (vocabulary) overlap is computed only
to be reported, so the superficial-analogy case is explicit:

* deep analogy — different vocabulary, matching causal structure → adopted;
* superficial analogy — same vocabulary, different structure → rejected;
* partial analogy — most structure matches, one mechanism differs → adopted,
  then the contradicted part is withdrawn (adaptation, not wholesale reuse).

An adopted analogy acts as a mixture prior on the posterior (mass = learned
reliability) and offers the transported programme as a candidate.  It is never
evidence: interventions still decide.
"""
from __future__ import annotations

import json
import math
from itertools import permutations
from typing import Any, Mapping, Sequence

from ...contracts import domain_hash
from ..interfaces import MemoryItem
from ..state import AnalogyMapping, AnalogyStatus, CognitiveState, MemoryKind
from ..worlds.mechanisms import Mechanism

#: a relational (not single-feature) match needs at least two elements related
MIN_MATCHED_OPERATORS = 2
#: adoption needs strong posterior odds (Jeffreys scale) that the source is
#: the true analogue: Bayes factor × learned base-rate odds ÷ candidates
ADOPTION_ODDS = 10.0


def _surface_tokens(names: Sequence[str]) -> frozenset[str]:
    tokens = set()
    for name in names:
        for part in str(name).lower().replace("-", "_").split("_"):
            if part and not part.isdigit():
                tokens.add(part)
    return frozenset(tokens)


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def _max_matching(options: Mapping[str, Sequence[str]]) -> dict[str, str]:
    """Maximum bipartite matching target-op → source-op (Kuhn's algorithm)."""
    match_source: dict[str, str] = {}

    def augment(target: str, seen: set[str]) -> bool:
        for source in options[target]:
            if source in seen:
                continue
            seen.add(source)
            if source not in match_source or augment(match_source[source], seen):
                match_source[source] = target
                return True
        return False

    for target in sorted(options):
        augment(target, set())
    return {target: source for source, target in match_source.items()}


class GraphAnalogyEngine:
    def __init__(self, context: Any, knowledge: Any, *, adopt_threshold: float = 0.5) -> None:
        self.context = context
        self.knowledge = knowledge
        self.adopt_threshold = float(adopt_threshold)
        self.sources: dict[str, dict[str, Any]] = {}
        self.adopted: dict[str, dict[str, Any]] = {}
        self.records: list[dict[str, Any]] = []

    def _analogy_id(self, memory_id: str) -> str:
        return "analogy-" + domain_hash("euclid.analogy.ref.v1", memory_id)[:12]

    # -- initial retrieval ---------------------------------------------------------------
    def find(self, structural_features: frozenset[str], memories: Sequence[MemoryItem],
             surface_features: frozenset[str] = frozenset()) -> list[AnalogyMapping]:
        ctx = self.context
        spec = ctx.spec
        mappings = []
        current_surface = _surface_tokens(
            list(spec.variables) + list(spec.operators) + [spec.surface_domain]
        )
        for item in memories:
            if item.kind is not MemoryKind.CAUSAL:
                continue
            payload = item.payload
            if payload.get("task_id") == spec.task_id:
                continue
            surface = _jaccard(current_surface, frozenset(payload.get("surface_tokens", ())))
            compatible = (
                spec.objective == "assign"
                and sorted(payload.get("domains", ())) == sorted(spec.domains)
                and bool(payload.get("mechanisms"))
            )
            analogy_id = self._analogy_id(item.memory_id)
            if compatible:
                self.sources[analogy_id] = {"memory_id": item.memory_id, "payload": payload,
                                            "surface": surface}
                status, rationale = (
                    AnalogyStatus.CANDIDATE,
                    "public structure compatible; awaiting interventional evidence",
                )
            elif surface > 0.0:
                status, rationale = (
                    AnalogyStatus.REJECTED,
                    f"superficial similarity rejected: surface {surface:.3f} with "
                    "incompatible variable structure",
                )
            else:
                continue
            mappings.append(AnalogyMapping(analogy_id, item.memory_id, 0.0, surface,
                                           0.0, status, rationale))
        return mappings

    # -- evidence-driven matching ----------------------------------------------------------
    def _match(self, payload: Mapping[str, Any]) -> dict[str, Any] | None:
        ctx = self.context
        posterior = ctx.posterior
        spec = ctx.spec
        source_domains = list(payload["domains"])
        source_mechs = {op: Mechanism.from_json(m) for op, m in payload["mechanisms"].items()}
        observed_ops = [op for op in spec.operators if posterior.observations[op]]
        if len(observed_ops) < MIN_MATCHED_OPERATORS:
            return None
        n = len(spec.domains)
        best: dict[str, Any] | None = None
        for perm in permutations(range(n)):
            # perm[target_var] = source_var
            if any(source_domains[perm[j]] != spec.domains[j] for j in range(n)):
                continue
            source_to_target = {perm[j]: j for j in range(n)}
            options: dict[str, list[str]] = {}
            transported: dict[str, Mechanism] = {}
            for source_op, mechanism in source_mechs.items():
                try:
                    transported[source_op] = mechanism.remap(source_to_target)
                except KeyError:
                    continue
            for op in observed_ops:
                rows = posterior.observations[op]
                options[op] = [
                    source_op for source_op, mechanism in sorted(transported.items())
                    if all(mechanism.apply(s, spec.domains) == r for s, r in rows)
                ]
            matching = _max_matching(options)
            score = len(matching) / len(observed_ops)
            # log Bayes factor: transported mechanisms reproduce the matched
            # observations with probability 1; by coincidence with the base
            # prior's predictive probability of exactly those observations.
            log_bf = sum(-posterior.prior_predictive_logprob(op) for op in matching)
            if best is None or score > best["score"] or (
                score == best["score"] and len(matching) > len(best["matching"])
            ):
                best = {"score": score, "matching": matching, "perm": list(perm),
                        "transported": transported, "observed": len(observed_ops),
                        "log_bayes_factor": log_bf}
        return best

    def refresh(self, state: CognitiveState) -> list[AnalogyMapping]:
        ctx = self.context
        if ctx.posterior is None:
            return []
        updates = []
        candidates = max(1, len(self.sources))
        for analogy_id, source in sorted(self.sources.items()):
            if analogy_id in self.adopted and self.adopted[analogy_id].get("abandoned"):
                continue
            match = self._match(source["payload"])
            if match is None:
                continue
            bucket = "exact" if match["score"] >= 1.0 else "partial"
            reliability = self.knowledge.analogy_reliability(bucket)
            matched = len(match["matching"])
            bayes_factor = math.exp(min(700.0, match["log_bayes_factor"]))
            prior_odds = reliability / max(1e-9, 1.0 - reliability) / candidates
            odds = bayes_factor * prior_odds
            adopt = (match["score"] >= self.adopt_threshold
                     and matched >= MIN_MATCHED_OPERATORS
                     and odds >= ADOPTION_ODDS)
            already = analogy_id in self.adopted and not self.adopted[analogy_id]["abandoned"]
            if adopt:
                # (Re-)prime on every refresh: as more operators are matched by
                # evidence, boosts narrow to the still-unmatched mechanisms and
                # the programme transfers once the matching covers it.
                self._prime(analogy_id, source, match, reliability)
            elif already:
                self._withdraw(analogy_id)
            status = AnalogyStatus.ADOPTED if adopt else AnalogyStatus.REJECTED
            rationale = (
                f"{matched}/{match['observed']} observed operators reproduced by the "
                f"source mechanisms under a variable bijection; Bayes factor against "
                f"coincidence {bayes_factor:.3g}; posterior odds {odds:.3g} over "
                f"{candidates} candidate(s); reliability {reliability:.3f}"
            )
            updates.append(AnalogyMapping(analogy_id, source["memory_id"], match["score"],
                                          source["surface"], reliability, status, rationale))
            self.records.append({"analogy_id": analogy_id, "score": match["score"],
                                 "matched": matched, "bayes_factor": bayes_factor,
                                 "posterior_odds": odds, "adopted": adopt})
        return updates

    def _prime(self, analogy_id: str, source: Mapping[str, Any], match: Mapping[str, Any],
               reliability: float) -> None:
        ctx = self.context
        posterior = ctx.posterior
        cap = float(self.knowledge.params.get("analogy_mass_cap", 0.9))
        mass = min(cap, max(0.05, reliability))
        matching: dict[str, str] = match["matching"]
        transported: dict[str, Mechanism] = match["transported"]
        unmatched_sources = [op for op in sorted(transported) if op not in matching.values()]
        previous = self.adopted.get(analogy_id, {})
        contradicted = set(previous.get("contradicted", ()))
        boosted = []
        for op in ctx.spec.operators:
            if op in matching or op in contradicted:
                if op in posterior.boosts and posterior.boosts[op]["source"] == analogy_id:
                    posterior.remove_boost(op)  # now explained by evidence
                continue
            pool = [transported[s] for s in unmatched_sources]
            if pool and posterior.boost(op, pool, mass, source=analogy_id):
                boosted.append(op)
        program = list(previous.get("program", []))
        source_program = source["payload"].get("program") or []
        inverse = {s: t for t, s in matching.items()}
        if not program and source_program and all(step in inverse for step in source_program):
            program = [inverse[step] for step in source_program]
            ctx.transfer_programs.append((tuple(program), analogy_id))
        tracked = sorted(set(previous.get("boosted", ())) | set(boosted))
        self.adopted[analogy_id] = {"boosted": tracked, "mass": mass, "program": program,
                                    "memory_id": source["memory_id"], "abandoned": False,
                                    "contradicted": sorted(contradicted),
                                    "matched": sorted(matching)}
        ctx.analogy_sources[analogy_id] = self.adopted[analogy_id]

    def _withdraw(self, analogy_id: str) -> None:
        record = self.adopted.get(analogy_id)
        if record is None:
            return
        for op in record["boosted"]:
            self.context.posterior.remove_boost(op)
        self.context.transfer_programs[:] = [
            row for row in self.context.transfer_programs if row[1] != analogy_id
        ]
        record["abandoned"] = True

    def abandon(self, state: CognitiveState) -> list[str]:
        """Withdraw transfers whose predictions were strongly contradicted."""
        from .control import STRONG_EVIDENCE_BF

        posterior = self.context.posterior
        abandoned = []
        for analogy_id, record in sorted(self.adopted.items()):
            if record["abandoned"]:
                continue
            contradicted = []
            for op in record["boosted"]:
                evidence = posterior.boost_evidence(op)
                if evidence and evidence["bayes_factor"] < 1.0 / STRONG_EVIDENCE_BF:
                    contradicted.append(op)
            for op in contradicted:
                posterior.remove_boost(op)
            record["contradicted"] = sorted(set(record.get("contradicted", [])) | set(contradicted))
            if record["boosted"] and len(record["contradicted"]) * 2 >= len(record["boosted"]):
                self._withdraw(analogy_id)
                abandoned.append(analogy_id)
        return abandoned

    def outcomes(self) -> list[dict[str, Any]]:
        """Per-adopted-analogy verification of transferred hypotheses."""
        posterior = self.context.posterior
        rows = []
        for analogy_id, record in sorted(self.adopted.items()):
            confirmed = contradicted = 0
            for op in record["boosted"]:
                if op in record.get("matched", ()):
                    confirmed += 1  # transported mechanism later reproduced by evidence
                    continue
                evidence = posterior.boost_evidence(op)
                if evidence is None:
                    contradicted += op in record.get("contradicted", ())
                    continue
                if evidence["posterior"] >= 0.5:
                    confirmed += 1
                elif evidence["bayes_factor"] < 1.0:
                    contradicted += 1
            rows.append({"analogy_id": analogy_id, "memory_id": record["memory_id"],
                         "confirmed": confirmed, "contradicted": contradicted,
                         "abandoned": record["abandoned"], "program_transferred": bool(record["program"])})
        return rows


def causal_memory_payload(spec: Any, identified: Mapping[str, Mechanism],
                          program: Sequence[str]) -> dict[str, Any]:
    return {
        "task_id": spec.task_id,
        "surface_domain": spec.surface_domain,
        "domains": list(spec.domains),
        "operators": list(spec.operators),
        "mechanisms": {op: m.to_json() for op, m in sorted(identified.items())},
        "program": list(program),
        "goal": [list(pair) for pair in spec.goal],
        "start": list(spec.initial_state),
        "surface_tokens": sorted(_surface_tokens(
            list(spec.variables) + list(spec.operators) + [spec.surface_domain])),
        "signature": json.dumps(sorted(m.kind for m in identified.values())),
    }


__all__ = [
    "ADOPTION_ODDS",
    "GraphAnalogyEngine",
    "MIN_MATCHED_OPERATORS",
    "causal_memory_payload",
]
