# pythagoras/asi/world_model.py — NEW

"""World Model — the learned theory of the environment.

Discoveries are facts; a world model is a theory. This module absorbs the
discovery engine's experiment log and builds a causal model over rule
compositions: which rules cause effects, which are epiphenomenal, and what
untested compositions are expected to do.

Attribution is ablation-based causal inference: rule r at position i is a
cause iff removing it changes the observed effect. This is Pearl's rung-2
applied to the system's own experiment history — the difference between
knowing THAT add3∘dbl works and knowing WHY (both rules are individually
necessary).
"""

from dataclasses import dataclass


@dataclass
class CausalAttribution:
    composition: list[str]
    observed_effect: float
    contributions: dict  # "pos:rule" -> effect lost when ablated (None = untested)
    necessary_rules: list[str]  # positions whose ablation kills the effect
    sufficient: bool  # does the model know enough to explain the effect?


class WorldModel:
    """Cumulative causal theory built from the system's own experiments."""

    def __init__(self):
        self.laws: dict[str, float] = {}  # "a∘b" -> observed effect
        self.experiment_log: list[dict] = []
        self._singleton_effects: dict[str, float] = {}  # rule -> marginal effect
        self._interactions: dict[str, float] = {}  # "a∘b" -> synergy beyond singletons
        self.n_absorbed = 0  # how many log entries already absorbed

    # ------------------------------------------------------------------
    # Learning: absorb experimental evidence
    # ------------------------------------------------------------------

    def absorb_log(self, experiment_log: list[dict]):
        """Ingest an experiment log: [{rules: [...], observed: float}, ...]"""
        for entry in experiment_log:
            key = "∘".join(entry["rules"])
            self.laws[key] = entry["observed"]
            if len(entry["rules"]) == 1:
                self._singleton_effects[entry["rules"][0]] = entry["observed"]
        self.experiment_log.extend(experiment_log)
        self._learn_interactions()

    def _learn_interactions(self):
        """Learn pairwise synergy: interaction(a,b) = E(a∘b) - E(a) - E(b).

        Positive synergy = the composition is more than its parts (a real
        discovery signature). Negative = interference. This is how the model
        generalises to untested compositions instead of only recalling them.
        """
        for key, effect in self.laws.items():
            rules = key.split("∘")
            if len(rules) < 2:
                continue
            base = sum(self._singleton_effects.get(r, 0.0) for r in rules)
            self._interactions[key] = effect - base

    # ------------------------------------------------------------------
    # Prediction: what will this composition do?
    # ------------------------------------------------------------------

    def predict(self, rules: list[str]) -> tuple[float, str]:
        """Predict effect for a composition.

        Exact if the composition was tested; otherwise an additive
        approximation over learned singleton effects (explicitly labeled —
        the model knows when it is guessing).
        """
        key = "∘".join(rules)
        if key in self.laws:
            return self.laws[key], "measured"
        base = sum(self._singleton_effects.get(r, 0.0) for r in rules)
        # Apply learned synergies for measured consecutive pairs
        pairs = [
            "∘".join(rules[i : i + 2])
            for i in range(len(rules) - 1)
            if "∘".join(rules[i : i + 2]) in self._interactions
        ]
        if pairs:
            return base + sum(self._interactions[p] for p in pairs), "interaction_model"
        return base, "additive_approximation"

    # ------------------------------------------------------------------
    # Causal attribution: WHICH rules cause the effect? (ablation = do-calculus)
    # ------------------------------------------------------------------

    def attribute(self, rules: list[str]) -> CausalAttribution:
        """Ablate each position and measure the effect lost.

        contribution[i] = E(full) - E(full without rule i)
        A rule is necessary iff its removal collapses the effect.
        """
        key = "∘".join(rules)
        full = self.laws.get(key, 0.0)
        contributions = {}
        necessary = []
        all_known = True

        for i, r in enumerate(rules):
            ablated = rules[:i] + rules[i + 1 :]
            ablated_key = "∘".join(ablated)
            if ablated_key in self.laws:
                lost = full - self.laws[ablated_key]
                contributions[f"{i}:{r}"] = lost
                if lost > 0 and abs(self.laws[ablated_key]) < abs(full) * 0.5:
                    necessary.append(f"{i}:{r}")
            else:
                contributions[f"{i}:{r}"] = None
                all_known = False

        return CausalAttribution(
            composition=rules,
            observed_effect=full,
            contributions=contributions,
            necessary_rules=necessary,
            sufficient=all_known,
        )

    def has_theory(self) -> bool:
        """Does the model contain more than isolated facts?"""
        return len(self.laws) > 1
