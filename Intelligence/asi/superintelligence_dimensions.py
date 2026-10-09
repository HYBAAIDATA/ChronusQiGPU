# pythagoras/asi/superintelligence_dimensions.py — NEW

from dataclasses import dataclass


@dataclass
class SuperintelligenceProfile:
    speed_si: float  # how much faster than human baseline
    quality_si: float  # how much qualitatively better solutions
    collective_si: float  # how much better than individual components
    mode: str  # "oracle", "genie", "sovereign"
    total_si: float  # composite score


class SuperintelligenceEvaluator:
    """Evaluates PYTHAGORAS across Bostrom's three dimensions."""

    def __init__(self, human_baseline_time: float = 3600.0, human_baseline_quality: float = 0.5):
        self.human_time = human_baseline_time  # seconds for human to do equivalent task
        self.human_quality = human_baseline_quality

    def evaluate(
        self,
        system_time: float,
        system_quality: float,
        individual_quality: float,
        n_components: int,
    ) -> SuperintelligenceProfile:
        """Evaluate across all three dimensions."""

        # Speed SI: how much faster than human
        speed_si = self.human_time / max(system_time, 1e-10)

        # Quality SI: how much better solutions than human
        quality_si = system_quality / max(self.human_quality, 1e-10)

        # Collective SI: how much better than sum of individual components
        if n_components > 1:
            expected_individual = individual_quality * n_components  # if independent
            collective_si = system_quality / max(expected_individual, 1e-10)
        else:
            collective_si = 1.0

        # Determine mode
        mode = "oracle"  # default: answers questions, doesn't act autonomously
        # In practice, PYTHAGORAS is an oracle (suggests changes, doesn't deploy them)

        # Plain mean of the three measured dimensions — the invented
        # 0.3/0.4/0.3 weighting is gone.
        total = (speed_si + quality_si + collective_si) / 3.0

        return SuperintelligenceProfile(
            speed_si=round(speed_si, 2),
            quality_si=round(quality_si, 2),
            collective_si=round(collective_si, 2),
            mode=mode,
            total_si=round(total, 2),
        )
