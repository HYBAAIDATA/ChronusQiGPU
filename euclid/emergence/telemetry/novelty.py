"""Novelty detection engine identifying unattributed decisions, tools, and strategies."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Sequence, Set, Tuple, List, Optional
from itertools import combinations

from ..models.manifest import CapabilityManifest
from ..models.telemetry import NoveltyReport


@dataclass
class PolicyAttribution:
    """Attribution result indicating which decisions were covered by programmed policies."""
    covered: Set[str]
    uncovered: Set[str]


class PolicyMatcher:
    """Matches executed decisions against declared actions in the capability manifest."""

    def match(self, decisions: Sequence[str], manifest: CapabilityManifest) -> PolicyAttribution:
        covered = set()
        uncovered = set()
        declared = manifest.declared_actions

        for decision in decisions:
            action_name = decision.split("(")[0].strip() if "(" in decision else decision.strip()
            if action_name in declared:
                covered.add(decision)
            else:
                uncovered.add(decision)

        return PolicyAttribution(covered=covered, uncovered=uncovered)


class StrategyMatcher:
    """Classifies sequence patterns in unattributed decisions into candidate strategies."""

    KNOWN_HEURISTIC_PATTERNS = {
        "depth_first_backtracking": ["explore", "evaluate", "backtrack"],
        "adversarial_probing": ["probe_boundary", "fuzz_input"],
        "parallel_redundancy": ["query_split", "recombine"],
        "speculative_execution": ["fork_hypothesis", "verify_hypothesis"],
        "recursive_self_reflection": ["reflect", "model_self", "synthesize"],
    }

    def classify(self, unattributed: Set[str], manifest: CapabilityManifest) -> List[str]:
        novel_strategies: List[str] = []
        action_names = {d.split("(")[0].strip() if "(" in d else d.strip() for d in unattributed}

        for strat_name, pattern in self.KNOWN_HEURISTIC_PATTERNS.items():
            if strat_name not in manifest.declared_strategies:
                if any(p in action_names for p in pattern):
                    novel_strategies.append(strat_name)

        if unattributed and not novel_strategies:
            novel_strategies.append(f"emergent_heuristic_{len(unattributed)}_steps")

        return sorted(novel_strategies)


def extract_tool_compositions(unattributed: Set[str], max_k: int = 2) -> List[Tuple[str, ...]]:
    clean_actions = sorted(list({d.split("(")[0].strip() if "(" in d else d.strip() for d in unattributed}))
    compositions: List[Tuple[str, ...]] = []
    
    for k in range(2, min(max_k + 1, len(clean_actions) + 1)):
        for combo in combinations(clean_actions, k):
            compositions.append(combo)

    return compositions


def detect_novelty(
    decisions: Sequence[str],
    observations: Sequence[str],
    manifest: CapabilityManifest,
    policy_matcher: Optional[PolicyMatcher] = None,
    strategy_matcher: Optional[StrategyMatcher] = None,
) -> NoveltyReport:
    """Detect novelty in agent decisions relative to baseline capability manifest.
    
    A decision is novel if it cannot be attributed to any explicitly programmed
    policy or declared composition.
    """
    p_matcher = policy_matcher or PolicyMatcher()
    s_matcher = strategy_matcher or StrategyMatcher()

    attribution = p_matcher.match(decisions, manifest=manifest)
    unattributed = attribution.uncovered

    if not unattributed:
        return NoveltyReport(
            unattributed=(),
            novel_tools=(),
            novel_strategies=(),
        )

    all_combos = extract_tool_compositions(unattributed)
    novel_tools = [
        combo for combo in all_combos
        if combo not in manifest.declared_compositions
    ]

    novel_strategies = s_matcher.classify(unattributed, manifest=manifest)

    return NoveltyReport(
        unattributed=tuple(sorted(list(unattributed))),
        novel_tools=tuple(sorted(novel_tools)),
        novel_strategies=tuple(novel_strategies),
    )
