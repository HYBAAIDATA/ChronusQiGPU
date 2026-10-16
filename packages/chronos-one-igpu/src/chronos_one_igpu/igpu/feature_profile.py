"""Vendor-neutral immutable logical fabric profiles; hardware facts are separate."""
from dataclasses import dataclass
import hashlib
from ..m5_ultra import PadFabric
from .resident import canonical


@dataclass(frozen=True)
class FeatureProfile:
    pad_qubits: tuple
    edges: tuple
    origin_digest: str | None = None

    def __post_init__(self):
        counts = tuple(self.pad_qubits)
        if not 1 <= len(counts) <= 32 or any(type(n) is not int or not 1 <= n <= 1024 for n in counts) or sum(counts) > 4096:
            raise ValueError("bounded exact pad/register counts required")
        edges = tuple(tuple(edge) for edge in self.edges)
        if any(len(e) != 2 or any(type(i) is not int or not 0 <= i < len(counts) for i in e) or e[0] == e[1] for e in edges):
            raise ValueError("invalid logical fabric edge")
        edges = tuple(sorted((min(i, j), max(i, j)) for i, j in edges))
        if len(set(edges)) != len(edges):
            raise ValueError("duplicate logical fabric edge")
        if self.origin_digest is not None and (not isinstance(self.origin_digest, str) or len(self.origin_digest) != 64 or any(c not in '0123456789abcdef' for c in self.origin_digest)):
            raise ValueError("origin SHA-256 required")
        object.__setattr__(self, 'pad_qubits', counts)
        object.__setattr__(self, 'edges', edges)

    @classmethod
    def from_model(cls, model):
        if not isinstance(model, PadFabric) or model.measured_by_chronus:
            raise ValueError("unmeasured canonical PadFabric required")
        if any(type(p.index) is not int or p.index != i or type(p.subunits) is not int or p.subunits < 1 for i, p in enumerate(model.pads)):
            raise ValueError("canonical pad identity required")
        return cls(tuple(p.subunits * p.spec.log2_hilbert_dim for p in model.pads),
                   tuple((e.source, e.target) for e in model.links),
                   hashlib.sha256(canonical(model.as_dict())).hexdigest())

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict) or set(value) != {'pad_qubits', 'edges', 'origin_digest'}:
            raise ValueError("versioned feature profile fields required")
        return cls(**value)

    def to_dict(self):
        return {'pad_qubits': list(self.pad_qubits), 'edges': [list(e) for e in self.edges], 'origin_digest': self.origin_digest}

    @property
    def digest(self):
        return hashlib.sha256(canonical(self.to_dict())).hexdigest()

    def register_layout(self, mode='full_register'):
        if mode not in ('full_register', 'pad'):
            raise ValueError("explicit register layout required")
        counts = self.pad_qubits if mode == 'full_register' else (1,) * len(self.pad_qubits)
        offsets = []; cursor = 0
        for n in counts:
            offsets.append(cursor); cursor += n
        # Local register chains plus inter-pad anchor graph. These are exact
        # logical edges, not an inference of physical entanglement links.
        edges = [(start+j, start+j+1) for start, count in zip(offsets, counts) for j in range(count-1)]
        edges += [(offsets[i], offsets[j]) for i, j in self.edges]
        return cursor, tuple(sorted(edges)), tuple(offsets)
