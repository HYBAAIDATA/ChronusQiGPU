# pythagoras/asi/robustness.py — NEW

import math
from dataclasses import dataclass


@dataclass
class RobustnessReport:
    in_distribution_accuracy: float
    out_of_distribution_accuracy: float
    robustness_gap: float
    adversarial_accuracy: float
    edge_case_pass_rate: float
    distributional_shift_detected: bool
    is_robust: bool


class RobustnessEvaluator:
    """Evaluates PYTHAGORAS robustness across distributional shifts.

    Marcus & Davis argue that true intelligence requires:
    - Common sense reasoning
    - Edge case handling
    - Adversarial robustness
    - Out-of-distribution generalization
    """

    def __init__(self):
        self.baseline_distribution: list = []
        self.ood_tests: list = []

    def set_baseline(self, training_examples: list):
        self.baseline_distribution = training_examples

    def evaluate(
        self, agent_fn, in_dist_test: list, ood_test: list, adversarial_test: list, edge_cases: list
    ) -> RobustnessReport:
        """Comprehensive robustness evaluation."""
        in_acc = self._evaluate_on_set(agent_fn, in_dist_test)
        ood_acc = self._evaluate_on_set(agent_fn, ood_test)
        adv_acc = self._evaluate_on_set(agent_fn, adversarial_test)
        edge_acc = self._evaluate_on_set(agent_fn, edge_cases)

        gap = in_acc - ood_acc
        shift_detected = gap > 0.15  # significant drop = distributional shift

        return RobustnessReport(
            in_distribution_accuracy=round(in_acc, 4),
            out_of_distribution_accuracy=round(ood_acc, 4),
            robustness_gap=round(gap, 4),
            adversarial_accuracy=round(adv_acc, 4),
            edge_case_pass_rate=round(edge_acc, 4),
            distributional_shift_detected=shift_detected,
            is_robust=(gap < 0.15 and adv_acc > 0.7 and edge_acc > 0.8),
        )

    def _evaluate_on_set(self, agent_fn, test_set: list) -> float:
        if not test_set:
            return 0.0
        passed = sum(1 for case in test_set if agent_fn(case))
        return passed / len(test_set)

    def detect_distributional_shift(self, new_data: list) -> bool:
        """Detect if new data is from a different distribution than training."""
        if not self.baseline_distribution or not new_data:
            return False
        # Simplified: compare feature distributions
        baseline_mean = sum(self.baseline_distribution) / len(self.baseline_distribution)
        new_mean = sum(new_data) / len(new_data)
        baseline_std = math.sqrt(
            sum((x - baseline_mean) ** 2 for x in self.baseline_distribution)
            / len(self.baseline_distribution)
        )
        if baseline_std == 0:
            return abs(new_mean - baseline_mean) > 0.1
        z_score = abs(new_mean - baseline_mean) / baseline_std
        return z_score > 2.0  # 2 standard deviations = shift
