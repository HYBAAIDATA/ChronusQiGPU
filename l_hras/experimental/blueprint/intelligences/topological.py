# l_hras/intelligences/topological.py

from dataclasses import dataclass
from typing import List

@dataclass
class Topology:
    vertices: List[str]
    edges: List[tuple]

@dataclass
class TopologicalSignature:
    betti: List[int]
    euler_char: int
    genus: int

def topological_analysis(topo: Topology) -> TopologicalSignature:
    """Compute the topological signature."""
    # Simplified: compute Betti numbers via connected components
    visited = set()
    components = 0
    adj = {v: [] for v in topo.vertices}
    for a, b in topo.edges:
        adj[a].append(b)
        adj[b].append(a)
    for v in topo.vertices:
        if v not in visited:
            components += 1
            stack = [v]
            while stack:
                u = stack.pop()
                if u not in visited:
                    visited.add(u)
                    stack.extend(adj[u])
    betti = [components, 0, 0]  # simplified
    euler = sum((-1) ** i * b for i, b in enumerate(betti))
    return TopologicalSignature(betti=betti, euler_char=euler, genus=0)

def is_simply_connected(sig: TopologicalSignature) -> bool:
    """A simply connected surface has no holes."""
    return sig.betti[0] == 1 and all(b == 0 for b in sig.betti[1:])
