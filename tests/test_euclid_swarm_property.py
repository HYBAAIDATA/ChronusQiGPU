"""Hypothesis-based property checks of swarm budgeting, DAGs and authority."""
import unittest

from hypothesis import given, settings, strategies as st

from euclid.swarm_evolution import (
    SwarmMission, SwarmRefused, SwarmTask, QualifiedAgent,
)

REV = "f" * 40


class PropertyQualification(unittest.TestCase):
    @settings(max_examples=100, deadline=None)
    @given(st.lists(st.integers(min_value=1, max_value=1000), min_size=1, max_size=30))
    def test_aggregate_budget_never_oversubscribes(self, costs):
        tasks = tuple(
            SwarmTask(f"t{i}", "worker", "task.run", cost)
            for i, cost in enumerate(costs)
        )
        exact = sum(costs)
        ok = SwarmMission("budget", "lead", "scope", exact, 100, tasks)
        self.assertEqual(sum(task.budget_units for task in ok.tasks), exact)
        if exact > 1:
            with self.assertRaises(SwarmRefused):
                SwarmMission("budget", "lead", "scope", exact - 1, 100, tasks)

    @settings(max_examples=80, deadline=None)
    @given(st.integers(min_value=2, max_value=30), st.integers(min_value=0, max_value=29))
    def test_forward_dependency_cycle_refused(self, size, edge):
        edge = edge % size
        # 0 -> 1 -> ... -> n-1, then 0 also depends on n-1.
        tasks = tuple(
            SwarmTask(f"t{i}", "worker", "task.run", 1,
                      (f"t{i-1}",) if i else (f"t{size-1}",))
            for i in range(size)
        )
        with self.assertRaises(SwarmRefused):
            SwarmMission("cyclic", "lead", "scope", size, 100, tasks)

    @settings(max_examples=80, deadline=None)
    @given(st.lists(st.sampled_from(["swarm.plan", "swarm.verify", "swarm.delegate"]),
                    min_size=1, max_size=8))
    def test_duplicate_acquired_skill_never_qualifies(self, names):
        if len(names) != len(set(names)):
            with self.assertRaises(SwarmRefused):
                QualifiedAgent("leader", REV, "scope", tuple(names),
                               {name: "claim." + name for name in names})
        else:
            candidate = QualifiedAgent("leader", REV, "scope", tuple(names),
                                       {name: "claim." + name for name in names})
            self.assertEqual(candidate.skills, tuple(names))


if __name__ == "__main__":
    unittest.main()
