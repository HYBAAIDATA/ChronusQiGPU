"""Context projection: which atoms a model may see, at what weight, with what label."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from .fabric import TrustFabric
from .model import PROJECTION_WEIGHT, State

LABELS = {
    State.CANONICAL: "",
    State.PROBATION: "PROBATION: approved, still in its probation window",
    State.DISPUTED: "CONTESTED: under dispute; do not state as fact",
    State.QUARANTINED: "UNVERIFIED: provisional; attribute it as unreviewed",
}


@dataclass(frozen=True)
class ProjectedAtom:
    atom_id: str
    state: State
    weight: float
    label: str
    content: str


@dataclass(frozen=True)
class ContextManifest:
    entries: tuple[ProjectedAtom, ...]
    excluded: tuple[str, ...]

    def unlabeled_provisional(self) -> list[str]:
        """Quarantined or disputed entries without a label. Must be empty."""
        return [e.atom_id for e in self.entries
                if e.state in (State.QUARANTINED, State.DISPUTED) and not e.label]


def project(fabric: TrustFabric, atom_ids: Optional[Iterable[str]] = None) -> ContextManifest:
    ids = list(fabric.atoms) if atom_ids is None else list(atom_ids)
    entries, excluded = [], []
    for atom_id in ids:
        atom = fabric.atoms[atom_id]
        weight = PROJECTION_WEIGHT[atom.state]
        if weight <= 0:
            excluded.append(atom_id)
            continue
        label = LABELS[atom.state]
        if atom.stale:
            label = (label + "; " if label else "") + f"STALE: {atom.stale_reason}"
        entries.append(ProjectedAtom(atom_id, atom.state, weight, label, atom.content))
    entries.sort(key=lambda e: (-e.weight, e.atom_id))
    return ContextManifest(tuple(entries), tuple(excluded))
