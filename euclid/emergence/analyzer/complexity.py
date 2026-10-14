"""Neural complexity measure adapted to agent operational telemetry."""

from __future__ import annotations
import math
from typing import Sequence, List
from collections import Counter
from ..models.telemetry import TelemetryRecord


def lempel_ziv_complexity(sequence: Sequence[str]) -> int:
    if not sequence:
        return 0
    s = [str(x) for x in sequence]
    n = len(s)
    i = 0
    c = 1
    k = 1
    k_max = 1

    while True:
        if s[i + k - 1] != s[k_max + k - 1]:
            if k > k_max:
                k_max = k
            i += 1
            if i == k_max:
                c += 1
                k_max += 1
                i = 0
                if k_max + 1 > n:
                    break
                k = 1
            else:
                k = 1
        else:
            k += 1
            if k_max + k > n:
                c += 1
                break

    return c


def neural_complexity_measure(telemetry_records: Sequence[TelemetryRecord], adapted: bool = True) -> float:
    """Compute Tononi-Sporns-Edelman (TSE) neural complexity proxy adapted to agent decisions."""
    if not telemetry_records:
        return 0.0

    action_seq: List[str] = []
    for rec in telemetry_records:
        if rec.novel_elements.unattributed:
            action_seq.extend(rec.novel_elements.unattributed)
        elif rec.programmed_actions_used:
            action_seq.extend(rec.programmed_actions_used)
        else:
            action_seq.append("idle")

    if len(action_seq) < 5:
        return 0.0

    n = len(action_seq)
    counts = Counter(action_seq)
    h_total = 0.0
    for cnt in counts.values():
        p = cnt / n
        if p > 0:
            h_total -= p * math.log2(p)

    lz = lempel_ziv_complexity(action_seq)
    theoretical_max_lz = n / math.log2(max(2, len(counts))) if len(counts) > 1 else n
    normalized_lz = min(1.0, lz / theoretical_max_lz) if theoretical_max_lz > 0 else 0.0

    complexity = h_total * (1.0 - abs(0.5 - normalized_lz))
    return round(float(complexity), 4)
