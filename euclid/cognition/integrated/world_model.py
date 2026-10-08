"""Bayesian mechanism world model: the active reasoning substrate.

For every operator the model keeps a posterior over the mechanism grammar,
separately under each *competing model hypothesis* about observation noise
(exact readings vs. two noise levels).  Model hypotheses are compared by
marginal likelihood, so the system can tell "my mechanism guess is wrong"
from "my readings are unreliable".

Discipline:

* Predictions and imagined rollouts are always returned as predictions;
  only executor results become observations.
* Posterior truncation is explicit (``prune_gap`` nats below the per-model
  maximum) and recorded; nothing is silently rounded to certainty.
* A localised collapse of the exact model for one operator is a measurable
  *breakdown* signal, answered by selective rebuild (grammar expansion or a
  change-point window) rather than global reset.
* Under a noisy model the predecessor of each step is the reading itself
  (plug-in approximation).  It is exact when readings are exact and is
  declared in every update record otherwise.
"""
from __future__ import annotations

import math
import random
from bisect import bisect_left
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from ..worlds.mechanisms import (
    DEFAULT_AGENT_KINDS,
    EXPANDED_AGENT_KINDS,
    Mechanism,
    State,
    hypothesis_space,
)

LOG2 = math.log(2.0)


@dataclass(frozen=True)
class NoiseModel:
    name: str
    epsilon: float


DEFAULT_NOISE_MODELS = (
    NoiseModel("exact", 0.0),
    NoiseModel("noisy-low", 0.03),
    NoiseModel("noisy-high", 0.10),
)


def _logsumexp(values: Iterable[float]) -> float:
    values = [v for v in values if v != -math.inf]
    if not values:
        return -math.inf
    top = max(values)
    return top + math.log(sum(math.exp(v - top) for v in values))


def entropy_bits(distribution: Mapping[Any, float]) -> float:
    return -sum(p * math.log2(p) for p in distribution.values() if p > 0.0)


class MechanismPosterior:
    """Episode-scoped posterior over operator mechanisms."""

    def __init__(
        self,
        domains: Sequence[int],
        operators: Sequence[str],
        *,
        kind_prior: Mapping[str, float] | None = None,
        noise_models: Sequence[NoiseModel] = DEFAULT_NOISE_MODELS,
        noise_prior: Sequence[float] | None = None,
        grammar: Iterable[str] = DEFAULT_AGENT_KINDS,
        prune_gap: float = 25.0,
        enumeration_limit: int = 4096,
        monte_carlo_samples: int = 400,
    ) -> None:
        self.domains = tuple(int(m) for m in domains)
        self.operators = tuple(operators)
        self.noise_models = tuple(noise_models)
        prior = list(noise_prior or [0.8] + [0.2 / (len(self.noise_models) - 1)] * (
            len(self.noise_models) - 1))
        if len(prior) != len(self.noise_models) or any(p <= 0 for p in prior):
            raise ValueError("noise prior must be positive and match the noise models")
        total = sum(prior)
        self.log_noise_prior = [math.log(p / total) for p in prior]
        self.prune_gap = float(prune_gap)
        self.enumeration_limit = int(enumeration_limit)
        self.monte_carlo_samples = int(monte_carlo_samples)
        self.kind_prior = dict(kind_prior or {})
        self.grammar = {op: frozenset(grammar) for op in self.operators}
        self._space_cache: dict[frozenset[str], list[Mechanism]] = {}
        self.space: dict[str, list[Mechanism]] = {
            op: self._space(self.grammar[op]) for op in self.operators
        }
        self.base_logprior: dict[str, dict[int, float]] = {}
        self.logprior: dict[str, dict[int, float]] = {}
        self.loglik: dict[str, list[dict[int, float]]] = {}
        for op in self.operators:
            self._reset_op(op)
        self.observations: dict[str, list[tuple[State, tuple[int, ...]]]] = {
            op: [] for op in self.operators
        }
        self.footprint: dict[str, set[int]] = {op: set() for op in self.operators}
        self.version = 0
        self.updates: list[dict[str, Any]] = []
        self.rebuilds: list[dict[str, Any]] = []
        self.boosts: dict[str, dict[str, Any]] = {}
        self._outputs: dict[tuple[int, State], list[State]] = {}
        self._log_match = [
            math.log(1.0 - m.epsilon) if m.epsilon > 0 else 0.0 for m in self.noise_models
        ]
        self._log_mismatch = [
            [math.log(m.epsilon / (size - 1)) if m.epsilon > 0 else -math.inf
             for size in self.domains]
            for m in self.noise_models
        ]
        self._cdf_cache: dict[tuple[int, str], tuple[list[float], list[int]]] = {}
        self._op_version: dict[str, int] = {op: 0 for op in self.operators}
        self._evidence_cache: dict[tuple[str, int, int], float] = {}
        self._weights_cache: dict[tuple[str, int, int], dict[int, float]] = {}
        self._marginal_cache: dict[tuple[int, str], list[tuple[Mechanism, float]]] = {}
        self._model_cache: tuple[int, list[float]] | None = None

    # -- construction ------------------------------------------------------------------
    def _space(self, grammar: frozenset[str]) -> list[Mechanism]:
        if grammar not in self._space_cache:
            self._space_cache[grammar] = hypothesis_space(self.domains, grammar)
        return self._space_cache[grammar]

    def _kind_logprior(self, space: Sequence[Mechanism]) -> dict[int, float]:
        counts: dict[str, int] = {}
        for mechanism in space:
            counts[mechanism.kind] = counts.get(mechanism.kind, 0) + 1
        weights = {
            kind: max(1e-9, float(self.kind_prior.get(kind, 1.0))) for kind in counts
        }
        total = sum(weights.values())
        return {
            index: math.log(weights[m.kind] / total) - math.log(counts[m.kind])
            for index, m in enumerate(space)
        }

    def _reset_op(self, op: str) -> None:
        prior = self._kind_logprior(self.space[op])
        self.base_logprior[op] = prior
        self.logprior[op] = dict(prior)
        self.loglik[op] = [{index: 0.0 for index in prior} for _ in self.noise_models]
        if hasattr(self, "_op_version"):
            self._bump(op)

    def _outputs_for(self, op: str, state: State) -> list[State]:
        space = self.space[op]
        key = (id(space), state)
        cached = self._outputs.get(key)
        if cached is None:
            cached = [m.apply(state, self.domains) for m in space]
            self._outputs[key] = cached
        return cached

    def _bump(self, op: str | None = None) -> None:
        if op is not None:
            self._op_version[op] = self._op_version.get(op, 0) + 1
        else:
            for name in self.operators:
                self._op_version[name] = self._op_version.get(name, 0) + 1
        self.version += 1
        self._marginal_cache.clear()
        self._cdf_cache.clear()
        self._model_cache = None

    # -- likelihood --------------------------------------------------------------------
    def _reading_loglik(self, model: NoiseModel, true: State, reading: Sequence[int]) -> float:
        if model.epsilon <= 0.0:
            return 0.0 if tuple(reading) == true else -math.inf
        e = self.noise_models.index(model)
        match = self._log_match[e]
        mismatch = self._log_mismatch[e]
        total = 0.0
        for index, (value, observed) in enumerate(zip(true, reading)):
            total += match if value == observed else mismatch[index]
        return total

    def model_posterior(self) -> list[float]:
        if self._model_cache and self._model_cache[0] == self.version:
            return self._model_cache[1]
        scores = []
        for e in range(len(self.noise_models)):
            evidence = self.log_noise_prior[e]
            for op in self.operators:
                evidence += self._evidence(op, e)
            scores.append(evidence)
        norm = _logsumexp(scores)
        posterior = [
            math.exp(s - norm) if norm != -math.inf else 1.0 / len(scores) for s in scores
        ]
        self._model_cache = (self.version, posterior)
        return posterior

    def _evidence(self, op: str, e: int) -> float:
        key = (op, self._op_version[op], e)
        cached = self._evidence_cache.get(key)
        if cached is None:
            prior = self.logprior[op]
            cached = _logsumexp(prior[i] + ll for i, ll in self.loglik[op][e].items())
            self._evidence_cache[key] = cached
        return cached

    def _op_model_weights(self, op: str, e: int) -> dict[int, float]:
        key = (op, self._op_version[op], e)
        cached = self._weights_cache.get(key)
        if cached is None:
            norm = self._evidence(op, e)
            prior = self.logprior[op]
            cached = (
                {}
                if norm == -math.inf
                else {i: math.exp(prior[i] + ll - norm) for i, ll in self.loglik[op][e].items()}
            )
            self._weights_cache[key] = cached
        return cached

    def marginal_indices(self, op: str) -> list[tuple[int, float]]:
        """``(space index, probability)`` mixed over model hypotheses, sorted."""
        key = (self.version, op)
        if key in self._marginal_cache:
            return self._marginal_cache[key]
        models = self.model_posterior()
        mass: dict[int, float] = {}
        for e, weight in enumerate(models):
            if weight <= 1e-15:
                continue
            for index, p in self._op_model_weights(op, e).items():
                mass[index] = mass.get(index, 0.0) + weight * p
        total = sum(mass.values())
        result = sorted(
            ((i, p / total) for i, p in mass.items() if total > 0),
            key=lambda row: (-row[1], row[0]),
        )
        self._marginal_cache[key] = result
        return result

    def marginal(self, op: str) -> list[tuple[Mechanism, float]]:
        """Mechanism marginal for ``op`` mixed over model hypotheses (sorted)."""
        space = self.space[op]
        return [(space[i], p) for i, p in self.marginal_indices(op)]

    def map_mechanism(self, op: str) -> tuple[Mechanism | None, float]:
        rows = self.marginal(op)
        return (rows[0][0], rows[0][1]) if rows else (None, 0.0)

    def op_entropy(self, op: str) -> float:
        return entropy_bits({index: p for index, (_, p) in enumerate(self.marginal(op))})

    def support_size(self, op: str, *, model: int = 0) -> int:
        return len(self.loglik[op][model])

    # -- prediction ---------------------------------------------------------------------
    def predictive(self, op: str, state: State) -> dict[State, float]:
        """Distribution over the *true* next state (prediction, never evidence)."""
        outputs = self._outputs_for(op, state)
        dist: dict[State, float] = {}
        for index, p in self.marginal_indices(op):
            nxt = outputs[index]
            dist[nxt] = dist.get(nxt, 0.0) + p
        return dist

    def outcome_entropy(self, op: str, state: State) -> float:
        return entropy_bits(self.predictive(op, state))

    def predictive_reading_prob(self, op: str, state: State, reading: Sequence[int]) -> float:
        models = self.model_posterior()
        outputs = self._outputs_for(op, state)
        total = 0.0
        for e, weight in enumerate(models):
            if weight <= 1e-15:
                continue
            model = self.noise_models[e]
            for index, p in self._op_model_weights(op, e).items():
                ll = self._reading_loglik(model, outputs[index], reading)
                if ll != -math.inf:
                    total += weight * p * math.exp(ll)
        return total

    def rollout(self, program: Sequence[str], state: State) -> list[dict[str, Any]]:
        """Imagined MAP trajectory with per-step outcome confidence."""
        rows = []
        for op in program:
            dist = self.predictive(op, state)
            nxt, p = max(dist.items(), key=lambda kv: (kv[1], kv[0]))
            rows.append({"op": op, "state": list(nxt), "confidence": p, "imagined": True})
            state = nxt
        return rows

    # -- learning ---------------------------------------------------------------------------
    def observe(self, op: str, state: State, reading: Sequence[int]) -> dict[str, Any]:
        """Bayesian update from one observed step; returns surprise in bits."""
        if op not in self.loglik:
            raise KeyError(f"unknown operator {op!r}")
        reading = tuple(int(v) for v in reading)
        predicted = self.predictive_reading_prob(op, state, reading)
        surprise = -math.log2(predicted) if predicted > 0 else math.inf
        outputs = self._outputs_for(op, state)
        for e, model in enumerate(self.noise_models):
            table = self.loglik[op][e]
            updated: dict[int, float] = {}
            for index, ll in table.items():
                step = self._reading_loglik(model, outputs[index], reading)
                if step != -math.inf:
                    updated[index] = ll + step
            if updated:
                top = max(self.logprior[op][i] + v for i, v in updated.items())
                updated = {
                    i: v for i, v in updated.items()
                    if self.logprior[op][i] + v >= top - self.prune_gap
                }
            self.loglik[op][e] = updated
        self.observations[op].append((tuple(state), reading))
        self.footprint[op].update(
            index for index, (a, b) in enumerate(zip(state, reading)) if a != b
        )
        self._bump(op)
        record = {
            "op": op,
            "surprise_bits": surprise if math.isfinite(surprise) else None,
            "predicted_probability": predicted,
            "exact_support": len(self.loglik[op][0]),
            "approximation": "plug-in predecessor under noisy models",
        }
        self.updates.append(record)
        return record

    def observe_trajectory(
        self, program: Sequence[str], start: State, readings: Sequence[Sequence[int]]
    ) -> list[dict[str, Any]]:
        records = []
        state = tuple(start)
        for op, reading in zip(program, readings):
            records.append(self.observe(op, state, reading))
            state = tuple(int(v) for v in reading)
        return records

    # -- analogy priors ------------------------------------------------------------------------
    def boost(
        self,
        op: str,
        mechanism: Mechanism | Sequence[Mechanism],
        mass: float,
        *,
        source: str,
    ) -> bool:
        """Mix transferred hypotheses into the prior: (1-mass)·prior + mass·U(set).

        A single mechanism is a point transfer; a set spreads the transferred
        mass uniformly (the analogy fixes *which* mechanisms but not yet which
        operator carries which).
        """
        if not 0.0 < mass < 1.0:
            raise ValueError("boost mass must be in (0, 1)")
        mechanisms = [mechanism] if isinstance(mechanism, Mechanism) else list(mechanism)
        index_of = {m: i for i, m in enumerate(self.space[op])}
        targets = sorted({index_of[m] for m in mechanisms if m in index_of})
        if not targets:
            return False
        share = mass / len(targets)
        base = self.base_logprior[op]
        target_set = set(targets)
        prior = {
            i: math.log((1.0 - mass) * math.exp(v) + (share if i in target_set else 0.0))
            for i, v in base.items()
        }
        self.logprior[op] = prior
        for e in range(len(self.noise_models)):
            for target in targets:
                if target not in self.loglik[op][e]:
                    replayed = self._replay_loglik(op, e, target)
                    if replayed != -math.inf:
                        self.loglik[op][e][target] = replayed
        self.boosts[op] = {
            "mechanisms": [self.space[op][i].to_json() for i in targets],
            "mechanism": self.space[op][targets[0]].to_json(),
            "mass": mass,
            "source": source,
        }
        self._bump(op)
        return True

    def _replay_loglik(self, op: str, e: int, index: int) -> float:
        model = self.noise_models[e]
        total = 0.0
        mechanism = self.space[op][index]
        for state, reading in self.observations[op]:
            total += self._reading_loglik(model, mechanism.apply(state, self.domains), reading)
        return total

    def prior_predictive_logprob(self, op: str) -> float:
        """log P(observations of ``op`` | base prior, exact readings).

        The probability that a mechanism drawn from the *unboosted* prior would
        reproduce every observed transition: the chance-coincidence term in an
        analogy's Bayes factor.
        """
        consistent = [
            i for i, mechanism in enumerate(self.space[op])
            if all(mechanism.apply(s, self.domains) == r for s, r in self.observations[op])
        ]
        base = self.base_logprior[op]
        return _logsumexp(base[i] for i in consistent)

    def remove_boost(self, op: str) -> None:
        if op in self.boosts:
            self.logprior[op] = dict(self.base_logprior[op])
            del self.boosts[op]
            self._bump(op)

    def boost_evidence(self, op: str) -> dict[str, float] | None:
        """Posterior vs prior mass of the boosted hypothesis (Bayes factor)."""
        if op not in self.boosts:
            return None
        boosted = {Mechanism.from_json(m) for m in self.boosts[op]["mechanisms"]}
        posterior = sum(p for m, p in self.marginal(op) if m in boosted)
        prior = float(self.boosts[op]["mass"])
        odds_post = posterior / max(1e-300, 1.0 - posterior)
        odds_prior = prior / (1.0 - prior)
        return {"prior": prior, "posterior": posterior, "bayes_factor": odds_post / odds_prior}

    # -- breakdown and rebuild ------------------------------------------------------------------
    def exact_collapsed(self) -> list[str]:
        """Operators whose exact-reading posterior has no surviving hypothesis."""
        return [op for op in self.operators if not self.loglik[op][0]]

    def rebuild(self, op: str) -> dict[str, Any]:
        """Selective rebuild of one operator's hypothesis space.

        Tries, in order of description cost: (1) grammar expansion explaining
        every observation exactly; (2) a change-point window — the longest
        recent suffix of observations explained exactly by one mechanism
        (non-stationarity).  Other operators are untouched.
        """
        observations = list(self.observations[op])
        record: dict[str, Any] = {"op": op, "observations": len(observations)}

        def consistent(space: Sequence[Mechanism], window) -> list[int]:
            return [
                i for i, m in enumerate(space)
                if all(m.apply(s, self.domains) == r for s, r in window)
            ]

        expanded = self._space(frozenset(EXPANDED_AGENT_KINDS))
        if self.grammar[op] != frozenset(EXPANDED_AGENT_KINDS):
            hits = consistent(expanded, observations)
            if hits:
                self.grammar[op] = frozenset(EXPANDED_AGENT_KINDS)
                self.space[op] = expanded
                self._reset_op(op)
                self._replay(op, observations)
                record.update({"resolution": "grammar-expansion", "consistent": len(hits)})
                self.rebuilds.append(record)
                self._bump(op)
                return record
        for start in range(1, len(observations)):
            window = observations[start:]
            hits = consistent(self.space[op], window)
            if hits:
                self._reset_op(op)
                self.observations[op] = []
                self._replay(op, window)
                record.update(
                    {"resolution": "change-point", "discarded": start, "consistent": len(hits)}
                )
                self.rebuilds.append(record)
                self._bump(op)
                return record
        record["resolution"] = "unresolved"
        self.rebuilds.append(record)
        return record

    def _replay(self, op: str, observations: Sequence[tuple[State, tuple[int, ...]]]) -> None:
        self.observations[op] = []
        for state, reading in observations:
            self.observe(op, state, reading)

    # -- planning support ---------------------------------------------------------------------------
    def map_table(self) -> dict[str, Mechanism]:
        table = {}
        for op in self.operators:
            mechanism, _ = self.map_mechanism(op)
            table[op] = mechanism if mechanism is not None else Mechanism("noop")
        return table

    def _cdf(self, op: str) -> tuple[list[float], list[int]]:
        key = (self.version, op)
        cached = self._cdf_cache.get(key)
        if cached is None:
            cumulative, indices, running = [], [], 0.0
            for index, p in self.marginal_indices(op):
                running += p
                cumulative.append(running)
                indices.append(index)
            cached = (cumulative, indices)
            self._cdf_cache[key] = cached
        return cached

    def sample_table(self, rng: random.Random) -> dict[str, Mechanism]:
        table = {}
        for op in self.operators:
            cumulative, indices = self._cdf(op)
            if not indices:
                table[op] = Mechanism("noop")
                continue
            position = min(len(indices) - 1, bisect_left(cumulative, rng.random()))
            table[op] = self.space[op][indices[position]]
        return table

    def success_probability(
        self,
        program: Sequence[str],
        start: State,
        goal: Sequence[tuple[int, int]],
        *,
        seed: int = 0,
    ) -> dict[str, Any]:
        """P(goal | program, posterior) by exact enumeration or Monte Carlo."""
        ops = list(dict.fromkeys(program))
        supports: dict[str, list[tuple[Mechanism, float]]] = {}
        product = 1
        complete = True
        for op in ops:
            rows = []
            cumulative = 0.0
            for mechanism, p in self.marginal(op):
                rows.append((mechanism, p))
                cumulative += p
                if cumulative >= 1.0 - 1e-9 or len(rows) >= 64:
                    break
            supports[op] = rows
            complete = complete and cumulative >= 1.0 - 1e-9
            product *= max(1, len(rows))
        # Exact enumeration only when every support is fully covered; a
        # truncated support would bias P(goal) downward, so sample instead.
        if complete and product <= self.enumeration_limit:
            probability = 0.0
            covered = 0.0

            def walk(index: int, table: dict[str, Mechanism], weight: float) -> None:
                nonlocal probability, covered
                if index == len(ops):
                    covered += weight
                    state = tuple(start)
                    for op in program:
                        state = table[op].apply(state, self.domains)
                    if all(state[i] == v for i, v in goal):
                        probability += weight
                    return
                for mechanism, p in supports[ops[index]]:
                    table[ops[index]] = mechanism
                    walk(index + 1, table, weight * p)

            walk(0, {}, 1.0)
            return {"probability": probability, "method": "exact-enumeration",
                    "mass_covered": covered, "joint_size": product}
        rng = random.Random(seed ^ self.version)
        cdfs = {op: self._cdf(op) for op in ops}
        hits = 0
        for _ in range(self.monte_carlo_samples):
            table = {}
            for op in ops:
                cumulative, indices = cdfs[op]
                position = min(len(indices) - 1, bisect_left(cumulative, rng.random()))
                table[op] = self.space[op][indices[position]]
            state = tuple(start)
            for op in program:
                state = table[op].apply(state, self.domains)
            hits += all(state[i] == v for i, v in goal)
        return {"probability": hits / self.monte_carlo_samples, "method": "monte-carlo",
                "samples": self.monte_carlo_samples, "joint_size": product}

    # -- summaries --------------------------------------------------------------------------------
    def identified(self, threshold: float = 0.95) -> dict[str, tuple[Mechanism, float]]:
        result = {}
        for op in self.operators:
            mechanism, p = self.map_mechanism(op)
            if mechanism is not None and p >= threshold:
                result[op] = (mechanism, p)
        return result

    def summary(self) -> dict[str, Any]:
        models = self.model_posterior()
        return {
            "version": self.version,
            "noise_model_posterior": {
                m.name: round(p, 6) for m, p in zip(self.noise_models, models)
            },
            "operators": {
                op: {
                    "map": (self.map_mechanism(op)[0].to_json()
                            if self.map_mechanism(op)[0] else None),
                    "map_probability": round(self.map_mechanism(op)[1], 6),
                    "entropy_bits": round(self.op_entropy(op), 6),
                    "exact_support": len(self.loglik[op][0]),
                    "grammar": sorted(self.grammar[op]),
                    "observations": len(self.observations[op]),
                    "boosted": op in self.boosts,
                }
                for op in self.operators
            },
            "rebuilds": list(self.rebuilds),
        }


__all__ = [
    "DEFAULT_NOISE_MODELS",
    "MechanismPosterior",
    "NoiseModel",
    "entropy_bits",
]
