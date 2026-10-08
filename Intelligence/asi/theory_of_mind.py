# pythagoras/asi/theory_of_mind.py — NEW

from dataclasses import dataclass

from Intelligence._born import born_evidence


@dataclass
class AgentModel:
    agent_id: str
    beliefs: dict  # what the agent believes about the code
    desires: list[str]  # what the agent wants
    intentions: list[str]  # what the agent plans to do
    knowledge_state: dict  # what the agent knows
    perspective: str  # the agent's viewpoint


class TheoryOfMindEngine:
    """Models other agents' mental states for better collaboration.

    In PYTHAGORAS context, 'agents' include:
    - Code reviewers (who have expectations about code style)
    - Test suites (which encode beliefs about correct behaviour)
    - Static analyzers (which have rules about what's acceptable)
    - Developers (who have preferences and domain knowledge)
    """

    def __init__(self):
        self.agent_models: dict[str, AgentModel] = {}

    def model_agent(self, agent_id: str, agent_type: str, observations: list) -> AgentModel:
        """Build a mental model of another agent from observations."""
        if agent_type == "code_reviewer":
            model = AgentModel(
                agent_id=agent_id,
                beliefs={
                    "prefers_readability": True,
                    "prefers_tests": True,
                    "rejects_complex_changes": True,
                },
                desires=["maintainable code", "test coverage", "minimal diff"],
                intentions=["review changes", "request modifications", "approve"],
                knowledge_state={"domain": "software_engineering", "expertise": "senior"},
                perspective="maintainability_and_safety",
            )
        elif agent_type == "test_suite":
            model = AgentModel(
                agent_id=agent_id,
                beliefs={"expected_behaviour": "preserved"},
                desires=["all_tests_pass", "no regressions"],
                intentions=["execute tests", "report failures"],
                knowledge_state={"behaviour_specifications": len(observations)},
                perspective="behavioural_correctness",
            )
        elif agent_type == "static_analyzer":
            model = AgentModel(
                agent_id=agent_id,
                beliefs={"rules": "enforced", "violations": "unacceptable"},
                desires=["zero violations", "type_safety"],
                intentions=["scan code", "report issues"],
                knowledge_state={"ruleset": "configured"},
                perspective="rule_compliance",
            )
        else:
            model = AgentModel(
                agent_id=agent_id,
                beliefs={},
                desires=[],
                intentions=[],
                knowledge_state={},
                perspective="unknown",
            )

        self.agent_models[agent_id] = model
        return model

    def predict_agent_response(self, agent_id: str, proposed_change: dict) -> dict:
        """Predict how an agent will respond to a proposed change."""
        model = self.agent_models.get(agent_id)
        if not model:
            return {"prediction": "unknown", "confidence": 0.0}

        # Simulate the agent's perspective on the change
        if "readability" in model.perspective:
            will_accept = proposed_change.get("improves_readability", False)
            return {
                "prediction": "accept" if will_accept else "request_changes",
                # One measured evidence bit (the readability flag)
                "confidence": born_evidence(1, 0),
                "reasoning": f"Agent values {model.desires}",
            }
        elif "behavioural" in model.perspective:
            will_accept = proposed_change.get("preserves_behaviour", True)
            return {
                "prediction": "pass" if will_accept else "fail",
                "confidence": born_evidence(1, 0),
                "reasoning": f"Agent expects {model.beliefs}",
            }
        elif "rule_compliance" in model.perspective:
            will_accept = proposed_change.get("rule_violations", 0) == 0
            return {
                "prediction": "clean" if will_accept else "issues_found",
                "confidence": born_evidence(1, 0),
            }

        return {"prediction": "unknown", "confidence": born_evidence(0, 0)}

    def false_belief_test(self, agent_id: str, actual_state: dict, believed_state: dict) -> bool:
        """Classic false-belief test: can the system distinguish what an agent
        believes from what is actually true?"""
        model = self.agent_models.get(agent_id)
        if not model:
            return False
        # The system passes if it can predict the agent's behaviour based on
        # the agent's BELIEFS, not the actual state
        predicted_from_belief = self.predict_agent_response(agent_id, believed_state)
        predicted_from_actual = self.predict_agent_response(agent_id, actual_state)
        return predicted_from_belief != predicted_from_actual
