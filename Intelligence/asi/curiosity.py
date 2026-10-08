# pythagoras/asi/curiosity.py — NEW

from dataclasses import dataclass


@dataclass
class CuriositySignal:
    prediction_error: float
    information_gain: float
    novelty_bonus: float
    intrinsic_reward: float


class CuriosityDrivenExplorer:
    """Drives exploration through intrinsic motivation.

    Instead of only optimising φ (extrinsic reward), the system also
    seeks transformations where its surrogate model's predictions are
    most wrong — because that's where the most learning happens.
    """

    def __init__(self, surrogate_model=None, novelty_engine=None):
        self.surrogate = surrogate_model
        self.novelty = novelty_engine
        self.prediction_history: list[tuple[float, float]] = []  # (predicted, actual)

    def compute_curiosity(
        self, predicted_delta_phi: float, actual_delta_phi: float, behaviour_vector: list = None
    ) -> CuriositySignal:
        """Compute intrinsic reward from prediction error."""
        prediction_error = abs(actual_delta_phi - predicted_delta_phi)
        self.prediction_history.append((predicted_delta_phi, actual_delta_phi))

        # Information gain: how much did we learn from this observation?
        info_gain = self._estimate_information_gain()

        # Novelty bonus from novelty search engine
        novelty_bonus = 0.0
        if self.novelty and behaviour_vector:
            desc = self.novelty.compute_novelty(behaviour_vector)
            novelty_bonus = desc.novelty_score if desc.is_novel else 0.0

        # Intrinsic reward = equal blend of the three measured signals —
        # the invented 0.5/0.3/0.2 weighting is gone.
        intrinsic_reward = (prediction_error + info_gain + novelty_bonus) / 3.0

        return CuriositySignal(prediction_error, info_gain, novelty_bonus, intrinsic_reward)

    def _estimate_information_gain(self) -> float:
        """Estimate information gain from recent observations."""
        if len(self.prediction_history) < 5:
            return 0.0
        # Information gain ~ reduction in prediction variance
        recent = self.prediction_history[-10:]
        errors = [abs(a - p) for p, a in recent]
        if len(errors) < 2:
            return 0.0
        # Information gain = measured reduction in prediction error
        # between the first and second half of the window — not the
        # invented 1/(1+variance) transform.
        half = max(1, len(errors) // 2)
        early = sum(errors[:-half]) / max(len(errors[:-half]), 1)
        late = sum(errors[-half:]) / half
        return max(0.0, early - late)

    def suggest_curious_mutation(
        self, candidate_mutations: list, surrogate_predictions: list
    ) -> int:
        """Suggest the mutation with highest curiosity (most uncertain outcome)."""
        if not candidate_mutations:
            return -1
        # Choose the mutation where the surrogate is most uncertain
        # (highest prediction variance or most extreme prediction)
        uncertainties = [abs(p) for p in surrogate_predictions]  # simplified
        max_idx = uncertainties.index(max(uncertainties))
        return max_idx
