# pythagoras/asi/neural_plasticity.py — NEW

"""Neural plasticity — the cognitive wiring is learned, not designed.

Fixed pipelines are programmed behaviour. This module gives the system an
activity-dependent wiring layer: subsystems that co-fire during useful work
strengthen their connection; idle connections decay; frequently co-active
pairs that lack a connection sprout one; strong pathways crystallise into
stable structure.

Mechanisms implemented (all activity-driven, none hard-coded):

- Three-factor Hebbian rule: activity opens an eligibility trace; a later
  reward (neuromodulation) converts trace to weight. Learning is gated by
  consequence, not by correlation alone.
- Structural plasticity: candidate pairs that co-activate repeatedly
  sprout new synapses — the graph grows where activity demands it.
- Homeostatic decay + synaptic scaling: unrewarded or idle weights decay
  toward zero and total drive is normalised (Turrigiano-style), keeping
  the network stable without freezing it.
- Pruning: synapses below threshold are removed — use it or lose it.
- Crystallisation: sufficiently strong synapses become resistant to decay
  — the plasticity-to-stability transition that turns skill into habit.
- Maturational schedule: global plasticity level declines as knowledge
  consolidates — juvenile plasticity, adult stability.
"""

from dataclasses import dataclass


@dataclass
class PlasticSynapse:
    pre: str
    post: str
    weight: float = 0.1
    trace: float = 0.0  # eligibility trace opened by activity
    co_activations: int = 0
    crystallized: bool = False
    last_active: int = 0


class NeuralPlasticity:
    """Reward-modulated plastic wiring over the system's subsystems."""

    def __init__(
        self,
        learning_rate: float = 0.05,
        trace_decay: float = 0.9,
        weight_decay: float = 0.02,
        sprout_threshold: int = 3,
        prune_threshold: float = 0.02,
        crystallize_threshold: float = 0.8,
    ):
        self.learning_rate = learning_rate
        self.trace_decay = trace_decay
        self.weight_decay = weight_decay
        self.sprout_threshold = sprout_threshold
        self.prune_threshold = prune_threshold
        self.crystallize_threshold = crystallize_threshold

        self.synapses: dict[tuple[str, str], PlasticSynapse] = {}
        self.plasticity_level = 1.0  # juvenile: fully plastic
        self._tick = 0
        self._pair_proposals: dict[tuple[str, str], int] = {}
        self.reward_history: list[float] = []

    # ------------------------------------------------------------------
    # Activity + reward (three-factor Hebbian learning)
    # ------------------------------------------------------------------

    def co_activate(self, pre: str, post: str):
        """Two subsystems fired together. Opens an eligibility trace —
        potentiation awaits a reward signal; without reward it fades."""
        self._tick += 1
        key = (pre, post)
        syn = self.synapses.get(key)
        if syn is None:
            # No connection exists — record the proposal; repeated
            # co-activation will sprout a synapse (structural plasticity).
            self._pair_proposals[key] = self._pair_proposals.get(key, 0) + 1
            if self._pair_proposals[key] >= self.sprout_threshold:
                self.synapses[key] = PlasticSynapse(pre, post, weight=0.1, trace=1.0)
                self.synapses[key].last_active = self._tick
            return

        syn.trace = 1.0
        syn.co_activations += 1
        syn.last_active = self._tick

    def deliver_reward(self, reward: float):
        """Neuromodulatory signal: convert open traces into weight change.

        w += η · level · reward · trace · (1 - w)   — bounded potentiation.
        Negative reward depresses. Traces then decay (forgetting window).
        """
        self.reward_history.append(reward)
        for syn in self.synapses.values():
            if syn.trace > 0 and not syn.crystallized:
                delta = self.learning_rate * self.plasticity_level * reward * syn.trace
                syn.weight = min(1.0, max(0.0, syn.weight + delta * (1.0 - syn.weight)))
            syn.trace *= self.trace_decay
        self._homeostatic_scale()

    # ------------------------------------------------------------------
    # Homeostasis: decay and synaptic scaling keep the network stable
    # ------------------------------------------------------------------

    def decay(self):
        """Idle synapses weaken. Crystallised ones resist — LTP persistence."""
        self._tick += 1
        for syn in self.synapses.values():
            if not syn.crystallized:
                syn.weight *= 1.0 - self.weight_decay

    def _homeostatic_scale(self, target_total: float = 4.0):
        """Synaptic scaling: if total weight exceeds target, scale all down
        proportionally — preserves relative strengths, bounds the network."""
        total = sum(s.weight for s in self.synapses.values())
        if total > target_total:
            factor = target_total / total
            for syn in self.synapses.values():
                if not syn.crystallized:
                    syn.weight *= factor

    # ------------------------------------------------------------------
    # Structural plasticity: prune the dead, crystallise the proven
    # ------------------------------------------------------------------

    def prune(self) -> int:
        """Remove synapses that decayed below threshold. Returns count removed."""
        dead = [k for k, s in self.synapses.items() if s.weight < self.prune_threshold]
        for k in dead:
            del self.synapses[k]
        return len(dead)

    def crystallize(self) -> int:
        """Strong synapses become stable — resistant to decay and scaling.
        This is how practised skill becomes permanent structure."""
        n = 0
        for syn in self.synapses.values():
            if syn.weight >= self.crystallize_threshold and not syn.crystallized:
                syn.crystallized = True
                n += 1
        return n

    def mature(self, factor: float = 0.95):
        """Developmental plasticity schedule: consolidation reduces global
        plasticity over time — the system can still learn, but increasingly
        builds on stable structure rather than rewiring from scratch."""
        self.plasticity_level = max(0.1, self.plasticity_level * factor)

    # ------------------------------------------------------------------
    # Probes: inspect the emergent wiring
    # ------------------------------------------------------------------

    def strongest_pathways(self, k: int = 5) -> list[dict]:
        ranked = sorted(self.synapses.values(), key=lambda s: s.weight, reverse=True)[:k]
        return [
            {
                "pathway": f"{s.pre} → {s.post}",
                "weight": round(s.weight, 4),
                "co_activations": s.co_activations,
                "crystallized": s.crystallized,
            }
            for s in ranked
        ]

    def report(self) -> dict:
        n_cryst = sum(1 for s in self.synapses.values() if s.crystallized)
        return {
            "synapses": len(self.synapses),
            "crystallized": n_cryst,
            "plasticity_level": round(self.plasticity_level, 4),
            "pending_sprouts": len(self._pair_proposals),
            "mean_weight": round(
                sum(s.weight for s in self.synapses.values()) / max(len(self.synapses), 1),
                4,
            ),
            "strongest": self.strongest_pathways(),
        }
