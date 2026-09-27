# pythagoras/asi/developmental.py — NEW

from enum import Enum


class CognitiveStage(Enum):
    SENSORIMOTOR = "sensorimotor"  # basic reflex-like mutations
    PREOPERATIONAL = "preoperational"  # simple transformations, no abstraction
    CONCRETE = "concrete_operational"  # logical transformations on concrete code
    FORMAL = "formal_operational"  # abstract, hypothetical reasoning
    POSTFORMAL = "postformal"  # contextual, dialectical thinking


class DevelopmentalController:
    """Implements Piagetian developmental stages for PYTHAGORAS.

    The system progresses through stages as it demonstrates mastery:
    - Sensorimotor: basic AST mutations (add annotations)
    - Preoperational: simple refactoring (rename, extract)
    - Concrete: logical transformations (split functions, introduce guards)
    - Formal: abstract reasoning (design patterns, architectural changes)
    - Postformal: contextual reasoning (trade-off analysis, domain-specific)
    """

    def __init__(self):
        self.stage = CognitiveStage.SENSORIMOTOR
        self.schemas: dict[str, dict] = {}  # knowledge structures
        self.assimilation_count = 0
        self.accommodation_count = 0
        self.equilibration_events: list = []

    def observe(self, mutation_type: str, delta_phi: float, success: bool) -> dict:
        """Process a mutation through developmental framework."""
        if success:
            # Assimilation: fit into existing schema
            if mutation_type in self.schemas:
                self.schemas[mutation_type]["successes"] += 1
                self.assimilation_count += 1
            else:
                # Accommodation: create new schema
                self.schemas[mutation_type] = {
                    "successes": 1,
                    "failures": 0,
                    "stage": self.stage.value,
                }
                self.accommodation_count += 1

            # Check for equilibration (balance between assimilation and accommodation)
            if self._needs_equilibration():
                self._equilibrate()
        else:
            if mutation_type in self.schemas:
                self.schemas[mutation_type]["failures"] += 1

        return {
            "current_stage": self.stage.value,
            "schema_count": len(self.schemas),
            "assimilation_count": self.assimilation_count,
            "accommodation_count": self.accommodation_count,
            "equilibration_events": len(self.equilibration_events),
            "ready_for_advancement": self._ready_for_next_stage(),
        }

    def _needs_equilibration(self) -> bool:
        """Equilibration needed when accommodation rate is too high (disequilibrium)."""
        total = self.assimilation_count + self.accommodation_count
        if total < 10:
            return False
        accommodation_rate = self.accommodation_count / total
        return accommodation_rate > 0.5

    def _equilibrate(self) -> dict:
        """Restore balance by consolidating schemas."""
        # Merge similar schemas
        merged = 0
        schema_names = list(self.schemas.keys())
        for i, s1 in enumerate(schema_names):
            if s1 not in self.schemas:
                continue  # already merged into another schema
            for s2 in schema_names[i + 1 :]:
                if s2 not in self.schemas:
                    continue
                if self._schemas_similar(s1, s2):
                    self.schemas[s1]["successes"] += self.schemas[s2]["successes"]
                    self.schemas[s1]["failures"] += self.schemas[s2].get("failures", 0)
                    del self.schemas[s2]
                    merged += 1
                    break

        event = {"merged_schemas": merged, "stage": self.stage.value}
        self.equilibration_events.append(event)
        return event

    def _schemas_similar(self, s1: str, s2: str) -> bool:
        return s1.split(":")[0] == s2.split(":")[0]

    def _ready_for_next_stage(self) -> bool:
        """Check if the system has mastered its current stage."""
        stage_order = list(CognitiveStage)
        if self.stage == stage_order[-1]:
            return False
        total_successes = sum(s["successes"] for s in self.schemas.values())
        return total_successes > 50 and len(self.schemas) > 10

    def advance_stage(self) -> bool:
        """Advance to next developmental stage."""
        if not self._ready_for_next_stage():
            return False
        stage_order = list(CognitiveStage)
        idx = stage_order.index(self.stage)
        if idx < len(stage_order) - 1:
            self.stage = stage_order[idx + 1]
            return True
        return False

    def get_zone_of_proximal_development(self) -> list[str]:
        """Vygotsky's ZPD: mutations the system can do with scaffolding but not alone."""
        zpd = []
        for name, schema in self.schemas.items():
            success_rate = schema["successes"] / max(schema["successes"] + schema["failures"], 1)
            if 0.3 <= success_rate <= 0.7:  # can do with help, not yet mastered
                zpd.append(name)
        return zpd
