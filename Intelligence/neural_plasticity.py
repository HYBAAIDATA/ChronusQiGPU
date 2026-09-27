"""Neural plasticity — adaptive cognitive wiring.

Reward-modulated plastic wiring over the system's subsystems:
three-factor Hebbian rule + structural plasticity + homeostasis +
pruning + crystallisation + a maturational schedule.

LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel
inline below. MUST NOT import from any sibling algorithm.
Substrate route: trace
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Set, Tuple

import numpy as np


@dataclass
class PlasticSynapse:
    pre: str
    post: str
    weight: float = 0.1
    trace: float = 0.0
    co_activations: int = 0
    crystallized: bool = False
    last_active: int = 0
    created_at: int = 0
    reward_accumulated: float = 0.0
    pathway_type: str = "excitatory"


@dataclass
class PlasticityEvent:
    tick: int
    event_type: str
    pre: str
    post: str
    weight_before: float
    weight_after: float
    reward: float
    plasticity_level: float


class NeuralPlasticity:
    """Three-factor Hebbian wiring with structural plasticity.

    Co-activation opens an eligibility trace; a later reward converts the
    trace into weight. Frequently co-active pairs sprout new synapses.
    Homeostatic scaling keeps total drive bounded; weak synapses are
    pruned; strong ones crystallize into stable structure.
    """

    def __init__(
        self,
        learning_rate: float = 0.05,
        trace_decay: float = 0.9,
        weight_decay: float = 0.02,
        sprout_threshold: int = 3,
        prune_threshold: float = 0.02,
        crystallize_threshold: float = 0.8,
        homeostatic_target: float = 4.0,
        max_synapses: int = 10000,
    ):
        self.learning_rate = learning_rate
        self.trace_decay = trace_decay
        self.weight_decay = weight_decay
        self.sprout_threshold = sprout_threshold
        self.prune_threshold = prune_threshold
        self.crystallize_threshold = crystallize_threshold
        self.homeostatic_target = homeostatic_target
        self.max_synapses = max_synapses

        self.synapses: Dict[Tuple[str, str], PlasticSynapse] = {}
        self.plasticity_level = 1.0
        self._tick = 0
        self._pair_proposals: Dict[Tuple[str, str], int] = {}
        self.reward_history: List[float] = []
        self.event_log: List[PlasticityEvent] = []
        self.subsystems: Set[str] = set()

    def register_subsystem(self, name: str):
        self.subsystems.add(name)

    def co_activate(self, pre: str, post: str, strength: float = 1.0):
        self._tick += 1
        self.subsystems.add(pre)
        self.subsystems.add(post)
        key = (pre, post)
        syn = self.synapses.get(key)
        if syn is None:
            self._pair_proposals[key] = self._pair_proposals.get(key, 0) + 1
            if self._pair_proposals[key] >= self.sprout_threshold:
                if len(self.synapses) < self.max_synapses:
                    self.synapses[key] = PlasticSynapse(
                        pre, post, weight=0.1, trace=1.0, created_at=self._tick
                    )
                    self.synapses[key].last_active = self._tick
                    self.event_log.append(
                        PlasticityEvent(
                            tick=self._tick,
                            event_type="sprout",
                            pre=pre,
                            post=post,
                            weight_before=0.0,
                            weight_after=0.1,
                            reward=0.0,
                            plasticity_level=self.plasticity_level,
                        )
                    )
            return

        syn.trace = min(1.0, syn.trace + strength)
        syn.co_activations += 1
        syn.last_active = self._tick

    def deliver_reward(self, reward: float):
        self.reward_history.append(reward)
        for syn in self.synapses.values():
            if syn.trace > 0 and not syn.crystallized:
                delta = self.learning_rate * self.plasticity_level * reward * syn.trace
                w_before = syn.weight
                syn.weight = min(1.0, max(0.0, syn.weight + delta * (1.0 - syn.weight)))
                syn.reward_accumulated += reward * syn.trace
                if abs(syn.weight - w_before) > 1e-6:
                    self.event_log.append(
                        PlasticityEvent(
                            tick=self._tick,
                            event_type="potentiate",
                            pre=syn.pre,
                            post=syn.post,
                            weight_before=w_before,
                            weight_after=syn.weight,
                            reward=reward,
                            plasticity_level=self.plasticity_level,
                        )
                    )
            syn.trace *= self.trace_decay
        self._homeostatic_scale()

    def decay(self):
        self._tick += 1
        for syn in self.synapses.values():
            if not syn.crystallized:
                syn.weight *= 1.0 - self.weight_decay

    def _homeostatic_scale(self):
        total = sum(s.weight for s in self.synapses.values())
        if total > self.homeostatic_target:
            factor = self.homeostatic_target / total
            for syn in self.synapses.values():
                if not syn.crystallized:
                    syn.weight *= factor

    def prune(self) -> int:
        dead = [k for k, s in self.synapses.items() if s.weight < self.prune_threshold]
        for k in dead:
            syn = self.synapses[k]
            self.event_log.append(
                PlasticityEvent(
                    tick=self._tick,
                    event_type="prune",
                    pre=syn.pre,
                    post=syn.post,
                    weight_before=syn.weight,
                    weight_after=0.0,
                    reward=0.0,
                    plasticity_level=self.plasticity_level,
                )
            )
            del self.synapses[k]
        return len(dead)

    def crystallize(self) -> int:
        n = 0
        for syn in self.synapses.values():
            if syn.weight >= self.crystallize_threshold and not syn.crystallized:
                syn.crystallized = True
                n += 1
                self.event_log.append(
                    PlasticityEvent(
                        tick=self._tick,
                        event_type="crystallize",
                        pre=syn.pre,
                        post=syn.post,
                        weight_before=syn.weight,
                        weight_after=syn.weight,
                        reward=0.0,
                        plasticity_level=self.plasticity_level,
                    )
                )
        return n

    def mature(self, factor: float = 0.95):
        self.plasticity_level = max(0.1, self.plasticity_level * factor)

    def strongest_pathways(self, k: int = 5) -> List[dict]:
        ranked = sorted(self.synapses.values(), key=lambda s: s.weight, reverse=True)[:k]
        return [
            {
                "pathway": f"{s.pre} → {s.post}",
                "weight": round(s.weight, 4),
                "co_activations": s.co_activations,
                "crystallized": s.crystallized,
                "reward_accumulated": round(s.reward_accumulated, 4),
            }
            for s in ranked
        ]

    def weakest_pathways(self, k: int = 5) -> List[dict]:
        ranked = sorted(self.synapses.values(), key=lambda s: s.weight)[:k]
        return [
            {
                "pathway": f"{s.pre} → {s.post}",
                "weight": round(s.weight, 4),
                "co_activations": s.co_activations,
                "age": self._tick - s.created_at,
            }
            for s in ranked
        ]

    def pathway_matrix(self) -> np.ndarray:
        subs = sorted(self.subsystems)
        n = len(subs)
        idx = {s: i for i, s in enumerate(subs)}
        M = np.zeros((n, n))
        for (pre, post), syn in self.synapses.items():
            M[idx[pre], idx[post]] = syn.weight
        return M

    def report(self) -> dict:
        n_cryst = sum(1 for s in self.synapses.values() if s.crystallized)
        return {
            "synapses": len(self.synapses),
            "subsystems": len(self.subsystems),
            "crystallized": n_cryst,
            "plasticity_level": round(self.plasticity_level, 4),
            "pending_sprouts": len(self._pair_proposals),
            "mean_weight": round(
                sum(s.weight for s in self.synapses.values()) / max(len(self.synapses), 1),
                4,
            ),
            "total_weight": round(sum(s.weight for s in self.synapses.values()), 4),
            "reward_mean": (
                round(float(np.mean(self.reward_history)), 4) if self.reward_history else 0.0
            ),
            "reward_std": (
                round(float(np.std(self.reward_history)), 4) if self.reward_history else 0.0
            ),
            "strongest": self.strongest_pathways(),
            "weakest": self.weakest_pathways(),
            "events": len(self.event_log),
        }

    def state_dict(self) -> dict:
        return {
            "synapses": [
                {
                    "pre": s.pre,
                    "post": s.post,
                    "weight": s.weight,
                    "trace": s.trace,
                    "co_activations": s.co_activations,
                    "crystallized": s.crystallized,
                    "last_active": s.last_active,
                    "created_at": s.created_at,
                    "reward_accumulated": s.reward_accumulated,
                }
                for s in self.synapses.values()
            ],
            "plasticity_level": self.plasticity_level,
            "tick": self._tick,
            "pair_proposals": {f"{k[0]}|{k[1]}": v for k, v in self._pair_proposals.items()},
            "reward_history": list(self.reward_history),
            "subsystems": sorted(self.subsystems),
        }

    def load_state_dict(self, state: dict):
        self.synapses = {}
        for s in state["synapses"]:
            syn = PlasticSynapse(
                pre=s["pre"],
                post=s["post"],
                weight=s["weight"],
                trace=s["trace"],
                co_activations=s["co_activations"],
                crystallized=s["crystallized"],
                last_active=s["last_active"],
                created_at=s["created_at"],
                reward_accumulated=s["reward_accumulated"],
            )
            self.synapses[(syn.pre, syn.post)] = syn
        self.plasticity_level = state["plasticity_level"]
        self._tick = state["tick"]
        proposals = {}
        for k, v in state["pair_proposals"].items():
            if isinstance(k, str):
                pre, post = k.split("|", 1)
                proposals[(pre, post)] = v
            else:
                proposals[tuple(k)] = v
        self._pair_proposals = proposals
        self.reward_history = list(state["reward_history"])
        self.subsystems = set(state["subsystems"])
