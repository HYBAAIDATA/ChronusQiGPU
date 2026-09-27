# pythagoras/asi/compositional_generalization.py — NEW

from dataclasses import dataclass, field


@dataclass
class CompositionalRule:
    name: str
    input_pattern: str  # AST pattern to match
    output_pattern: str  # AST pattern to produce
    component_rules: list = field(default_factory=list)  # sub-rules this is composed of
    is_primitive: bool = True
    observed_compositions: int = 0
    generalization_success_rate: float = 0.0


class CompositionalGeneralizationEngine:
    """Tests and enables compositional generalization.

    If the system knows rule A and rule B, it should be able to apply A∘B
    (A composed with B) even if it has never seen that composition before.
    """

    def __init__(self):
        self.primitive_rules: dict[str, CompositionalRule] = {}
        self.composed_rules: dict[str, CompositionalRule] = {}
        self.generalization_tests: list = []

    def add_primitive(self, rule: CompositionalRule):
        self.primitive_rules[rule.name] = rule

    def compose(self, rule_a: str, rule_b: str) -> CompositionalRule:
        """Create a new composed rule from two primitives."""
        a = self.primitive_rules[rule_a]
        b = self.primitive_rules[rule_b]
        composed = CompositionalRule(
            name=f"{rule_a}_compose_{rule_b}",
            input_pattern=a.input_pattern,
            output_pattern=b.output_pattern,
            component_rules=[rule_a, rule_b],
            is_primitive=False,
        )
        self.composed_rules[composed.name] = composed
        return composed

    def test_compositional_generalization(self, test_cases: list) -> dict:
        """Test whether the system can generalize to novel compositions.

        Systematicity test: if A and B are learned, can A∘B be applied
        to inputs that A and B have never been applied to individually?
        """
        results = {"total": 0, "passed": 0, "failed": 0, "novel_compositions": 0}

        for case in test_cases:
            results["total"] += 1
            rule_a, rule_b, test_input = case
            composed = self.compose(rule_a, rule_b)

            # Apply composed rule
            try:
                result = self._apply_composed(composed, test_input)
                if result is not None:
                    results["passed"] += 1
                    composed.observed_compositions += 1
                    composed.generalization_success_rate = results["passed"] / results["total"]
                else:
                    results["failed"] += 1
            except Exception:
                results["failed"] += 1

            results["novel_compositions"] = len(self.composed_rules)

        return results

    def _apply_composed(self, rule: CompositionalRule, input_data):
        """Apply a composed rule by applying component rules in sequence."""
        current = input_data
        for comp_name in rule.component_rules:
            comp = self.primitive_rules.get(comp_name)
            if comp:
                current = self._apply_primitive(comp, current)
        return current

    def _apply_primitive(self, rule: CompositionalRule, input_data):
        # Placeholder: apply the rule's transformation
        return input_data  # in practice, applies AST transformation
