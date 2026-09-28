"""Active Discovery Engine — the missing loop.

Instrumentation is not intelligence. The 20 attribute modules measure
intelligence; this engine *exercises* it. It closes the scientific loop:

    generate hypothesis -> design experiment -> predict -> intervene ->
    measure surprise -> revise beliefs -> record discovery -> broadcast

Hypothesis selection is driven by Bayesian experimental design: the engine
runs the experiment with the highest expected information gain (posterior
variance), not random search. A finding becomes a Discovery only if it is
(a) surprising under the current world model and (b) replicates across
independent trials — both necessary conditions for a claim to be more than
noise.

Surprise is measured against the engine's own theory, not a blank prior:
every experiment is absorbed into the causal theory as it lands, and an
untested composition is predicted from it (additive singleton effects
plus learned pairwise synergy). A composition that merely adds up what is
already known is a confirmation, never a discovery.
"""

import itertools
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from .bayesian_reasoning import BayesianReasoningEngine
from .compositional_generalization import CompositionalGeneralizationEngine, CompositionalRule
from .curiosity import CuriosityDrivenExplorer
from .global_workspace import GlobalWorkspace
from .metacognition import MetacognitiveMonitor
from .novelty_search import NoveltySearchEngine
from .neural_plasticity import NeuralPlasticity
from .safety_alignment import SafetyAlignmentLayer
from .world_model import WorldModel


@dataclass
class Hypothesis:
    """A falsifiable claim about the environment: applying `rule_composition`
    to a state will produce `predicted_effect`."""

    hypothesis_id: str
    rule_composition: list[str]
    predicted_effect: float
    predicted_variance: float
    tested: bool = False


@dataclass
class Discovery:
    """A replicated, surprising empirical finding — the atomic unit of
    machine-generated knowledge."""

    discovery_id: str
    hypothesis_id: str
    rule_composition: list[str]
    predicted_effect: float
    observed_effect: float
    surprise: float
    posterior_mean: float
    posterior_variance: float
    replications: int
    intrinsic_reward: float
    timestamp: float = field(default_factory=time.time)


class ActiveDiscoveryEngine:
    """Drives autonomous experimentation over a composable rule space.

    The engine treats the environment as a black box: state -> apply rules
    -> observe effect. It does not need to know *why* a composition works —
    only that the effect is real, surprising, and replicates. Explaining it
    is the causal engine's job; finding it is this engine's job.

    Attributes actively engaged per cycle:
      S-9  curiosity        — intrinsic reward from prediction error
      S-12 bayesian         — posterior over each composition's effect
      S-14 compositional    — hypothesis space = compositions of primitives
      S-7  novelty          — behavioural diversity of explored compositions
      S-4  metacognition    — strategy regulation from discovery rate
      S-15 safety           — every experiment gated before it runs
      S-17 global workspace — discoveries broadcast to all subsystems
    """

    def __init__(
        self,
        environment: Callable[[list[str], object], float],
        primitives: list[CompositionalRule],
        n_trials: int = 5,
        surprise_threshold: float = 0.15,
        replication_tolerance: float = 0.05,
        workspace: Optional[GlobalWorkspace] = None,
        experiments_reversible: bool = True,
    ):
        """
        environment: fn(rule_composition, initial_state) -> observed_effect.
            Black-box evaluation of applying a rule sequence to a state.
        primitives: composable rules forming the hypothesis space basis.
        n_trials: independent trials per hypothesis (replication).
        surprise_threshold: min |observed - predicted| to flag a discovery.
        replication_tolerance: max allowed std across trials for a claim.
        experiments_reversible: whether an experiment leaves the world as it
            found it (a simulation does; live intervention may not). The
            safety layer refuses irreversible experiments.
        """
        self.environment = environment
        self.primitives = {r.name: r for r in primitives}
        self.n_trials = n_trials
        self.surprise_threshold = surprise_threshold
        self.replication_tolerance = replication_tolerance
        self.experiments_reversible = experiments_reversible

        self.bayesian = BayesianReasoningEngine(prior_mean=0.0, prior_variance=1.0)
        self.compositional = CompositionalGeneralizationEngine()
        self.novelty = NoveltySearchEngine(k=3, novelty_threshold=0.05)
        self.metacognition = MetacognitiveMonitor()
        self.curiosity = CuriosityDrivenExplorer(novelty_engine=self.novelty)
        self.safety = SafetyAlignmentLayer()
        self.plasticity = NeuralPlasticity()
        self.workspace = workspace or GlobalWorkspace()

        for rule in primitives:
            self.compositional.add_primitive(rule)

        self.discoveries: list[Discovery] = []
        self.hypotheses_tested: list[Hypothesis] = []
        self.experiment_log: list[dict] = []
        self.theory = WorldModel()  # the system's learned causal theory
        self._law_signatures: set = set()  # (atomic alphabet, effect) already known
        self.goal_weight = 0.0  # 0 = pure exploration; >0 exploits known-good laws
        self.current_goal = "explore"  # autotelic objective
        self._cycle = 0

    # ------------------------------------------------------------------
    # Growth: chunk expansion and discovery-promoted primitives
    # ------------------------------------------------------------------

    def _expand(self, rules: list[str]) -> list[str]:
        """Expand chunked (non-primitive) rules into atomic rules.

        A discovery promoted to a chunk lets the system compose at a higher
        level of abstraction while the environment only ever sees atoms.
        """
        atomic = []
        for name in rules:
            rule = self.primitives.get(name)
            if rule is not None and not rule.is_primitive and rule.component_rules:
                atomic.extend(self._expand(rule.component_rules))
            else:
                atomic.append(name)
        return atomic

    def _promote_chunk(self, discovery: Discovery):
        """Growth: a replicated discovery becomes a new primitive.

        This is compositional chunking — the hypothesis space itself grows.
        'add3∘dbl' becomes a building block, so the next generation can
        explore 'add3∘dbl∘inc' without re-deriving the discovered law.
        """
        if len(discovery.rule_composition) < 2:
            return
        # Novelty gate: a composition that merely re-expresses a known law
        # (same atomic alphabet, same effect — e.g. a no-op prefix) is a
        # confirmatory replication, not growth. Do not promote it.
        atomic = self._expand(discovery.rule_composition)
        signature = (frozenset(atomic), round(discovery.observed_effect, 6))
        if signature in self._law_signatures:
            return
        self._law_signatures.add(signature)

        name = "∘".join(discovery.rule_composition)
        if name in self.primitives:
            return
        chunk = CompositionalRule(
            name=name,
            input_pattern=discovery.rule_composition[0],
            output_pattern="chunked_law",
            component_rules=list(discovery.rule_composition),
            is_primitive=False,
        )
        self.primitives[name] = chunk

    # ------------------------------------------------------------------
    # Hypothesis generation (S-14): the space of compositions
    # ------------------------------------------------------------------

    def generate_hypotheses(self, max_composition_length: int = 2) -> list[Hypothesis]:
        """Enumerate compositions of primitives not yet tested.

        Prior comes from the Bayesian engine: untested compositions get the
        broad prior; tested ones are not regenerated — science does not
        re-run settled experiments.
        """
        names = list(self.primitives.keys())
        tested_ids = {h.hypothesis_id for h in self.hypotheses_tested}
        hypotheses = []

        for length in range(1, max_composition_length + 1):
            for combo in itertools.product(names, repeat=length):
                hid = "∘".join(combo)
                if hid in tested_ids:
                    continue
                mean, var = self.bayesian.predict(hid)
                belief = self.bayesian.beliefs.get(hid)
                if belief is None or belief.n_observations == 0:
                    # Untested: the theory's prediction, not a blank prior.
                    mean, _ = self.theory.predict(self._expand(list(combo)))
                hypotheses.append(
                    Hypothesis(
                        hypothesis_id=hid,
                        rule_composition=list(combo),
                        predicted_effect=mean,
                        predicted_variance=var,
                    )
                )
        return hypotheses

    def select_experiment(self, hypotheses: list[Hypothesis]) -> Optional[Hypothesis]:
        """Bayesian experimental design: run the hypothesis with the highest
        posterior variance — maximum expected information gain.

        Exploitation bonus: compositions that build on confirmed discoveries
        get boosted — the system stands on its own findings (cumulative
        culture), while still preferring the unknown over the known.
        """
        if not hypotheses:
            return None
        discovered_ids = {d.hypothesis_id for d in self.discoveries}
        known = {tuple(self._expand(h.rule_composition)) for h in self.hypotheses_tested}

        def score(h: Hypothesis) -> float:
            builds_on_discovery = any(c in discovered_ids for c in h.rule_composition)
            exploration = h.predicted_variance * (1.5 if builds_on_discovery else 1.0)
            # UCB-style: when pursuing a goal, exploitation of high-posterior
            # compositions competes with exploration of uncertain ones.
            return exploration + self.goal_weight * h.predicted_effect

        def basis_known(h: Hypothesis) -> bool:
            # A composition is tested only once the theory knows its parts:
            # every atom, and every consecutive pair of a longer chain.
            # Otherwise an unmeasured part's own effect reads as a surprise
            # of the whole (a false discovery).
            atoms = self._expand(h.rule_composition)
            if len(atoms) == 1:
                return True
            parts = [(atom,) for atom in atoms]
            if len(atoms) > 2:
                parts += [tuple(atoms[i : i + 2]) for i in range(len(atoms) - 1)]
            return all(part in known for part in parts)

        # Equal scores: the shorter composition first, so the theory learns
        # its basis before it is asked to predict what builds on it.
        return max(
            hypotheses,
            key=lambda h: (basis_known(h), score(h), -len(self._expand(h.rule_composition))),
        )

    # ------------------------------------------------------------------
    # Autotelic goals: she sets her own objective
    # ------------------------------------------------------------------

    def set_goal(self, goal: str = "maximize_effect", weight: float = 1.0):
        """Pursue a self-generated objective. 'maximize_effect' shifts
        selection toward compositions with high learned posteriors — using
        what she knows, not just seeking what she doesn't."""
        self.current_goal = goal
        self.goal_weight = weight

    def what_should_i_test_next(self, k: int = 3) -> list[dict]:
        """Her curiosity, externalised: the top-k experiments she would run."""
        hypotheses = self.generate_hypotheses()
        discovered_ids = {d.hypothesis_id for d in self.discoveries}

        def score(h):
            bonus = 1.5 if any(c in discovered_ids for c in h.rule_composition) else 1.0
            return h.predicted_variance * bonus + self.goal_weight * h.predicted_effect

        ranked = sorted(hypotheses, key=score, reverse=True)[:k]
        return [
            {
                "composition": h.rule_composition,
                "predicted_effect": h.predicted_effect,
                "predicted_variance": h.predicted_variance,
                "reason": (
                    "builds on a discovery"
                    if any(c in discovered_ids for c in h.rule_composition)
                    else "maximum uncertainty — most to learn"
                ),
            }
            for h in ranked
        ]

    # ------------------------------------------------------------------
    # Transfer: knowledge learned in one universe carries to the next
    # ------------------------------------------------------------------

    def transfer_priors(self, source: "ActiveDiscoveryEngine"):
        """Knowledge transfer: another engine's posteriors become her priors.

        In a new environment she does not start blank — compositions that
        were valuable elsewhere are already believed valuable here, and the
        first experiment will confirm or refute the transfer (Bayesian
        update handles both). Growth that survives domain change.
        """
        for hid, belief in source.bayesian.beliefs.items():
            self.bayesian.beliefs[hid] = type(belief)(
                mean=belief.mean,
                variance=max(belief.variance, 0.1),  # widen: new domain, less certain
                n_observations=belief.n_observations,
            )

    # ------------------------------------------------------------------
    # Experimentation: intervene, replicate, measure surprise
    # ------------------------------------------------------------------

    def run_experiment(self, hypothesis: Hypothesis, initial_state) -> Optional[dict]:
        """Execute n_trials of the hypothesis. Returns None if the safety
        layer refuses the experiment (e.g., irreversible intervention)."""
        if not self.safety.safe_explore(
            {"reversible": self.experiments_reversible}, risk_tolerance=0.5
        ):
            return None

        atomic = self._expand(hypothesis.rule_composition)
        trials = [self.environment(atomic, initial_state) for _ in range(self.n_trials)]
        observed = sum(trials) / len(trials)
        mean_t = observed
        trial_std = (sum((t - mean_t) ** 2 for t in trials) / len(trials)) ** 0.5

        surprise = abs(observed - hypothesis.predicted_effect)

        # S-12: Bayesian posterior update on real evidence
        self.bayesian.update(
            hypothesis.hypothesis_id,
            observed,
            observation_variance=max(trial_std**2, 1e-6),
        )
        post_mean, post_var = self.bayesian.predict(hypothesis.hypothesis_id)

        # S-9: intrinsic reward — prediction error + info gain + novelty
        behaviour = [float(len(hypothesis.rule_composition)), observed]
        signal = self.curiosity.compute_curiosity(
            hypothesis.predicted_effect, observed, behaviour_vector=behaviour
        )

        # Plasticity: the subsystems that participated co-activate — which
        # pathways are actually used is recorded in the wiring, and the
        # intrinsic reward converts that activity into lasting structure.
        for pre, post in [
            ("compositional", "bayesian"),
            ("curiosity", "bayesian"),
            ("safety", "compositional"),
            ("novelty", "curiosity"),
        ]:
            self.plasticity.co_activate(pre, post)
        self.plasticity.deliver_reward(signal.intrinsic_reward)

        hypothesis.tested = True
        self.hypotheses_tested.append(hypothesis)
        self.experiment_log.append(
            {
                "hypothesis": hypothesis.hypothesis_id,
                "rules": atomic,
                "observed": observed,
                "trial_std": trial_std,
            }
        )
        # The theory learns from every experiment as it lands, so the next
        # hypothesis is predicted from everything known so far.
        self.theory.absorb_log(self.experiment_log[self.theory.n_absorbed :])
        self.theory.n_absorbed = len(self.experiment_log)

        return {
            "observed": observed,
            "trial_std": trial_std,
            "surprise": surprise,
            "posterior_mean": post_mean,
            "posterior_variance": post_var,
            "replicated": trial_std <= self.replication_tolerance,
            "intrinsic_reward": signal.intrinsic_reward,
        }

    # ------------------------------------------------------------------
    # The discovery loop
    # ------------------------------------------------------------------

    def discover(self, initial_state, n_cycles: int = 20, max_composition_length: int = 2) -> dict:
        """Run n_cycles of the full scientific loop and return a report."""
        new_discoveries = 0

        for _ in range(n_cycles):
            self._cycle += 1
            hypotheses = self.generate_hypotheses(max_composition_length)
            hypothesis = self.select_experiment(hypotheses)
            if hypothesis is None:
                break  # hypothesis space exhausted

            result = self.run_experiment(hypothesis, initial_state)
            if result is None:
                hypothesis.tested = True
                self.hypotheses_tested.append(hypothesis)
                continue

            # S-4: metacognitive monitoring of the discovery strategy itself
            self.metacognition.observe(
                phi=result["observed"],
                delta_phi=result["surprise"],
                strategy=self.metacognition.current_strategy,
            )

            # A discovery must be BOTH surprising AND replicated
            if result["surprise"] >= self.surprise_threshold and result["replicated"]:
                discovery = Discovery(
                    discovery_id=f"D{len(self.discoveries) + 1:04d}",
                    hypothesis_id=hypothesis.hypothesis_id,
                    rule_composition=hypothesis.rule_composition,
                    predicted_effect=hypothesis.predicted_effect,
                    observed_effect=result["observed"],
                    surprise=result["surprise"],
                    posterior_mean=result["posterior_mean"],
                    posterior_variance=result["posterior_variance"],
                    replications=self.n_trials,
                    intrinsic_reward=result["intrinsic_reward"],
                )
                self.discoveries.append(discovery)
                new_discoveries += 1

                # Growth: the discovery becomes a primitive — the hypothesis
                # space itself expands for future cycles.
                self._promote_chunk(discovery)

                # S-17: broadcast the discovery to every subsystem
                self.workspace.submit(
                    "discovery_engine",
                    {
                        "id": discovery.discovery_id,
                        "composition": discovery.rule_composition,
                        "effect": discovery.observed_effect,
                        "surprise": discovery.surprise,
                    },
                    priority=min(0.5 + discovery.surprise, 1.0),
                )
                self.workspace.broadcast_cycle()

                # Discovery is a strong reward event for the broadcast pathway
                self.plasticity.co_activate("discovery_engine", "global_workspace")
                self.plasticity.deliver_reward(discovery.surprise)

            # Homeostasis each cycle: idle pathways decay, dead ones prune,
            # proven ones crystallise, and plasticity matures with knowledge.
            self.plasticity.decay()
            self.plasticity.prune()
            self.plasticity.crystallize()
            self.plasticity.mature()

        # Consolidate: turn the experiment log into a causal theory.
        self.theory.absorb_log(self.experiment_log[self.theory.n_absorbed :])
        self.theory.n_absorbed = len(self.experiment_log)

        return {
            "cycles_run": self._cycle,
            "hypotheses_tested": len(self.hypotheses_tested),
            "discoveries": len(self.discoveries),
            "new_discoveries": new_discoveries,
            "discovery_rate": len(self.discoveries) / max(len(self.hypotheses_tested), 1),
            "broadcasts": len(self.workspace.broadcast_history),
            "metacognitive_strategy": self.metacognition.current_strategy,
            "laws_learned": len(self.theory.laws),
            "hypothesis_space_size": len(self.primitives),
            "plasticity": self.plasticity.report(),
        }

    # ------------------------------------------------------------------
    # Counterfactual credit assignment: what WOULD have worked?
    # ------------------------------------------------------------------

    def explain_failure(self, rule_composition: list[str]) -> dict:
        """Rung-3 analysis of a failed experiment.

        For each position in the composition, substitute every other atomic
        primitive and look up the resulting composition's posterior. The
        top-ranked substitution is the system's answer to 'what would have
        worked instead?' — counterfactual reasoning over its own evidence.
        """
        atomic = self._expand(rule_composition)
        hid = "∘".join(rule_composition)
        observed, _ = self.bayesian.predict(hid)
        tested_ids = {h.hypothesis_id for h in self.hypotheses_tested}
        atomic_primitives = [n for n, r in self.primitives.items() if r.is_primitive]

        suggestions = []
        for i in range(len(atomic)):
            for name in atomic_primitives:
                if name == atomic[i]:
                    continue
                candidate = atomic[:i] + [name] + atomic[i + 1 :]
                cid = "∘".join(candidate)
                mean, var = self.bayesian.predict(cid)
                suggestions.append(
                    {
                        "position": i,
                        "replace": atomic[i],
                        "with": name,
                        "candidate": cid,
                        "predicted_effect": mean,
                        "posterior_variance": var,
                        "tested": cid in tested_ids,
                    }
                )
        suggestions.sort(key=lambda s: s["predicted_effect"], reverse=True)

        return {
            "failed_composition": rule_composition,
            "observed_effect": observed,
            "best_counterfactual": suggestions[0] if suggestions else None,
            "suggestions": suggestions[:5],
        }

    def get_discovery_ledger(self) -> list[dict]:
        """The system's published findings — auditable machine knowledge."""
        return [
            {
                "id": d.discovery_id,
                "composition": " ∘ ".join(d.rule_composition),
                "predicted": round(d.predicted_effect, 4),
                "observed": round(d.observed_effect, 4),
                "surprise": round(d.surprise, 4),
                "posterior": (round(d.posterior_mean, 4), round(d.posterior_variance, 6)),
                "replications": d.replications,
            }
            for d in self.discoveries
        ]
