"""Integrated information proxy measure (Phi) for agent decision graphs."""

from __future__ import annotations
import math
from typing import Sequence, Dict, Any, List
from collections import Counter


def shannon_entropy(labels: Sequence[str]) -> float:
    if not labels:
        return 0.0
    n = len(labels)
    counts = Counter(labels)
    ent = 0.0
    for cnt in counts.values():
        p = cnt / n
        if p > 0:
            ent -= p * math.log2(p)
    return ent


def joint_entropy(labels_x: Sequence[str], labels_y: Sequence[str]) -> float:
    if len(labels_x) != len(labels_y) or not labels_x:
        return 0.0
    n = len(labels_x)
    pairs = list(zip(labels_x, labels_y))
    counts = Counter(pairs)
    ent = 0.0
    for cnt in counts.values():
        p = cnt / n
        if p > 0:
            ent -= p * math.log2(p)
    return ent


def mutual_information(labels_x: Sequence[str], labels_y: Sequence[str]) -> float:
    hx = shannon_entropy(labels_x)
    hy = shannon_entropy(labels_y)
    hxy = joint_entropy(labels_x, labels_y)
    return max(0.0, hx + hy - hxy)


def integrated_information_proxy(decision_graph: Any) -> float:
    """Compute a proxy measure of integrated information (Phi*)."""
    if isinstance(decision_graph, list):
        decisions = []
        observations = []
        for item in decision_graph:
            if hasattr(item, "novel_elements"):
                unatt = list(item.novel_elements.unattributed)
                decisions.append(unatt[0] if unatt else "null_action")
                observations.append(item.task_signature)
            elif isinstance(item, dict):
                decisions.append(str(item.get("decision", "null")))
                observations.append(str(item.get("observation", "null")))

        if len(decisions) < 4:
            return 0.0

        whole_mi = mutual_information(decisions, observations)

        d_evens, o_evens = decisions[::2], observations[::2]
        d_odds, o_odds = decisions[1::2], observations[1::2]

        part1_mi = mutual_information(d_evens, o_evens)
        part2_mi = mutual_information(d_odds, o_odds)

        sum_parts = (part1_mi + part2_mi) / 2.0
        phi_proxy = max(0.0, whole_mi - sum_parts * 0.85)
        return round(phi_proxy, 4)

    return 0.0
