"""Explicit problem framing; extraction is a host adapter, never invented evidence."""

from dataclasses import dataclass
from fractions import Fraction
from ._contracts import ContractError, ratio, text


@dataclass(frozen=True)
class ProblemRepresentation:
    objective_id: str
    entities: tuple[str, ...]
    relations: tuple[tuple[str, str, str], ...]
    invariants: tuple[str, ...]
    unknowns: tuple[str, ...]
    symmetries: tuple[str, ...]
    success_criteria: tuple[str, ...]
    confidence: Fraction
    evidence_refs: tuple[str, ...]

    def __post_init__(self):
        text(self.objective_id)
        ratio(self.confidence)
        for rows in (
            self.entities,
            self.relations,
            self.invariants,
            self.unknowns,
            self.symmetries,
            self.success_criteria,
            self.evidence_refs,
        ):
            if type(rows) is not tuple or len(rows) > 256:
                raise ContractError("bounded immutable problem representation required")
        for source, relation, target in self.relations:
            if source not in self.entities or target not in self.entities:
                raise ContractError("relation references unknown entity")
            text(relation)


def represent_problem(objective, context, *, extractor, confidence_floor):
    ratio(confidence_floor)
    result = extractor(objective, context)
    if not isinstance(result, ProblemRepresentation) or result.objective_id != objective.id:
        raise ContractError("typed objective-bound framing required")
    if result.success_criteria != objective.success_criteria:
        raise ContractError("framing cannot rewrite acceptance criteria")
    if result.confidence < confidence_floor:
        raise ContractError("representation needs additional information")
    return result
