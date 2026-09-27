# pythagoras/asi/continual_learning.py — NEW

from dataclasses import dataclass


@dataclass
class KnowledgeTask:
    task_id: str
    features: list  # learned parameters/weights
    importance: list  # Fisher information matrix (parameter importance)


class ContinualLearningEngine:
    """Implements Elastic Weight Consolidation (EWC) to prevent catastrophic forgetting.

    When learning a new task (new file/repository), important parameters
    from previous tasks are protected by adding a penalty for changing them.
    """

    def __init__(self, ewc_lambda: float = 1.0):
        self.ewc_lambda = ewc_lambda  # regularization strength
        self.tasks: list[KnowledgeTask] = []
        self.current_parameters: list = []

    def learn_task(self, task_id: str, training_data: list, n_steps: int = 100) -> dict:
        """Learn a new task while protecting important parameters from previous tasks."""
        # Initialise parameter vector on first task if not set externally
        if not self.current_parameters:
            self.current_parameters = [0.0] * max(len(training_data), 1)

        # Compute Fisher information for current task
        fisher_info = self._compute_fisher_information(training_data)

        # Store current task
        task = KnowledgeTask(task_id, list(self.current_parameters), fisher_info)
        self.tasks.append(task)

        # Learn with EWC penalty
        for step in range(n_steps):
            gradient = self._compute_gradient(training_data)
            ewc_penalty = self._compute_ewc_penalty()
            # Update parameters: gradient - lambda * ewc_penalty
            self.current_parameters = [
                p - 0.01 * (g + self.ewc_lambda * ep)
                for p, g, ep in zip(self.current_parameters, gradient, ewc_penalty)
            ]

        return {
            "task_id": task_id,
            "n_previous_tasks": len(self.tasks) - 1,
            "forgetting_measure": self._measure_forgetting(),
            "knowledge_retained": self._knowledge_retention(),
        }

    def _compute_fisher_information(self, data: list) -> list:
        """Compute Fisher Information Matrix (simplified diagonal approximation)."""
        if not self.current_parameters:
            return []
        # Fisher info = E[gradient^2] — measures how important each parameter is
        gradients = [self._compute_gradient([d]) for d in data[:10]]
        if not gradients:
            return [0.0] * len(self.current_parameters)
        fisher = [0.0] * len(self.current_parameters)
        for g in gradients:
            for i, val in enumerate(g):
                if i < len(fisher):
                    fisher[i] += val**2
        return [f / len(gradients) for f in fisher]

    def _compute_ewc_penalty(self) -> list:
        """EWC penalty: sum over previous tasks of Fisher * (current - old)^2."""
        if not self.tasks or not self.current_parameters:
            return [0.0] * max(len(self.current_parameters), 1)
        penalty = [0.0] * len(self.current_parameters)
        for task in self.tasks:
            for i in range(min(len(penalty), len(task.features), len(task.importance))):
                diff = self.current_parameters[i] - task.features[i]
                penalty[i] += task.importance[i] * diff * diff
        return penalty

    def _compute_gradient(self, data: list) -> list:
        """Compute gradient on data (simplified)."""
        if not self.current_parameters:
            return [0.0]
        return [
            0.01 * (sum(data) / max(len(data), 1) - p) for p in self.current_parameters[: len(data)]
        ]

    def _measure_forgetting(self) -> float:
        """Measure how much performance degraded on previous tasks."""
        if len(self.tasks) < 2:
            return 0.0
        # Simplified: compare current parameters to previous task parameters
        last_task = self.tasks[-2]
        if not last_task.features or not self.current_parameters:
            return 0.0
        diffs = [abs(c - f) for c, f in zip(self.current_parameters, last_task.features)]
        return sum(diffs) / max(len(diffs), 1)

    def _knowledge_retention(self) -> float:
        """Fraction of important parameters that haven't changed significantly."""
        if not self.tasks:
            return 1.0
        retained = 0
        total = 0
        for task in self.tasks[:-1]:  # all except current
            for i in range(
                min(len(self.current_parameters), len(task.features), len(task.importance))
            ):
                total += 1
                diff = abs(self.current_parameters[i] - task.features[i])
                if task.importance[i] > 0.1 and diff < 0.5:  # important and not changed much
                    retained += 1
        return retained / max(total, 1)
