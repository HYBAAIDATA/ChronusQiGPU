"""Composite primitive discovery for the production PYTHAGORAS evolution engine."""

from typing import Callable, Dict, List, Optional, Tuple

from pythagoras.core.primitives import OPERATOR_REGISTRY, compose


class DiscoveredPrimitiveCandidate:
    """Evidence accumulated for one discovered composite operator."""

    def __init__(
        self,
        name: str,
        op_func: Callable[[str, int], Tuple[str, str]],
        discovery_gen: int,
        origin_target: str,
        recipe: Optional[List[str]] = None,
    ):
        self.name = name
        self.op_func = op_func
        self.recipe = recipe or list(getattr(op_func, "recipe", []) or [])
        self.discovery_gen = discovery_gen
        self.origin_target = origin_target
        self.evaluation_trials = 0
        self.successful_gains = 0
        self.cumulative_delta_phi = 0.0
        self.is_promoted = False

    def record_trial(self, delta_phi: float, parse_valid: bool, test_valid: bool) -> None:
        self.evaluation_trials += 1
        if parse_valid and test_valid and delta_phi > 0:
            self.successful_gains += 1
            self.cumulative_delta_phi += delta_phi

    def check_promotion_eligibility(self) -> bool:
        if self.is_promoted:
            return False
        if (
            self.evaluation_trials >= 2
            and self.successful_gains >= 1
            and self.cumulative_delta_phi > 0
        ):
            self.is_promoted = True
            return True
        return False


class PrimitiveDiscoveryEngine:
    """Discover and promote recipes from measured winning transformation paths."""

    def __init__(self):
        self.sandbox_pool: Dict[str, DiscoveredPrimitiveCandidate] = {}
        self.promoted_vocabulary: Dict[
            str, Callable[[str, int], Tuple[str, str]]
        ] = {}
        self.winner_history: List[List[str]] = []
        self.max_recipe_len = 3

    @staticmethod
    def _recipe_of(op_name: str, op_func: Optional[Callable] = None) -> List[str]:
        if op_func is not None and getattr(op_func, "recipe", None):
            return list(op_func.recipe)
        return [op_name] if op_name in OPERATOR_REGISTRY else []

    def discover_from_transformation(
        self,
        code_before: str,
        code_after: str,
        winning_op_name: str,
        gen: int,
        target_name: str,
        winning_op_func: Optional[Callable] = None,
    ) -> Optional[DiscoveredPrimitiveCandidate]:
        # Before/after remain explicit inputs because discovery provenance describes a
        # concrete accepted transition, even though recipe synthesis uses its winner path.
        _ = (code_before, code_after)
        recipe = self._recipe_of(winning_op_name, winning_op_func)
        if not recipe:
            return None

        self.winner_history.append(recipe)
        if len(self.winner_history) < 2:
            return None

        chain: List[str] = []
        for prior_recipe in reversed(self.winner_history):
            if len(chain) + len(prior_recipe) > self.max_recipe_len:
                break
            chain = prior_recipe + chain
            if len(chain) >= 2:
                break
        if len(chain) < 2:
            return None

        op = compose(chain)
        new_name = op.__name__
        if new_name in self.sandbox_pool or new_name in self.promoted_vocabulary:
            return None

        candidate = DiscoveredPrimitiveCandidate(
            new_name,
            op,
            gen,
            target_name,
            chain,
        )
        self.sandbox_pool[new_name] = candidate
        return candidate
