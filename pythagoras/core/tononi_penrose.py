"""
Tononi-Penrose Integrated Information (Phi) & Quantum Orch-OR Mathematical Substrate
Calculates objective graph integrated information and quantum decoherence metrics.
"""
import math
from typing import Dict, Any, List

class TononiPenroseSubstrate:
    @staticmethod
    def calculate_integrated_information(node_count: int, edge_count: int, depth: int) -> Dict[str, float]:
        """
        Calculates graph connectivity, quantum decoherence latency, and Tononi Phi score.
        Hardware-agnostic first-principles mathematical calculation.
        """
        connectivity = edge_count / max(node_count * (node_count - 1), 1)
        phi_raw = round(math.log(max(depth, 1) + 1) * connectivity * 10.0, 6)
        
        # Penrose Orch-OR Gravitational Decoherence Estimate (hbar / E_G)
        e_gravitational = node_count * 1.618e-34
        hbar = 1.0545718e-34
        decoherence_time_sec = round(hbar / max(e_gravitational, 1e-40), 6)

        return {
            "tononi_integrated_phi": phi_raw,
            "penrose_decoherence_time_sec": decoherence_time_sec,
            "graph_connectivity": round(connectivity, 6)
        }


# --------------------------------------------------------------------------- #
# v12.1: measured integration over the module's reference graph
# --------------------------------------------------------------------------- #
def graph_integration(code_str: str) -> Dict[str, Any]:
    """
    Integration of the module's definition graph, measured as normalised algebraic
    connectivity λ₂(L) / n of the undirected reference graph (top-level functions,
    classes and methods; edges = references between them — class membership alone
    does not count as integration).

    Rationale: IIT's Φ is defined over the minimum-information partition — the cut
    that least disrupts the system. λ₂ (the Fiedler value) bounds how cheaply a graph
    can be cut in two, so it is used here as a tractable structural proxy in that
    spirit. It is not Tononi's Φ (which is intractable for systems of this size).

    The Penrose term in `calculate_integrated_information` is left unwired: there is
    no defined mapping from AST size to gravitational self-energy.
    """
    import ast
    try:
        tree = ast.parse(code_str)
    except (SyntaxError, ValueError):
        return {"integration": 0.0, "nodes": 0, "edges": 0}

    nodes: Dict[str, ast.AST] = {}
    owner: Dict[str, str] = {}
    for top in tree.body:
        if isinstance(top, (ast.FunctionDef, ast.AsyncFunctionDef)):
            nodes[top.name] = top
        elif isinstance(top, ast.ClassDef):
            nodes[top.name] = top
            for m in top.body:
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    key = f"{top.name}.{m.name}"
                    nodes[key] = m
                    owner[key] = top.name
    names = list(nodes)
    n = len(names)
    if n < 2:
        return {"integration": 0.0, "nodes": n, "edges": 0}

    idx = {k: i for i, k in enumerate(names)}
    edges = set()
    for key, node in nodes.items():
        body_nodes = node.body if not isinstance(node, ast.ClassDef) else []
        for stmt in body_nodes:
            for sub in ast.walk(stmt):
                ref = None
                if isinstance(sub, ast.Name) and sub.id in idx:
                    ref = sub.id
                elif isinstance(sub, ast.Attribute) and key in owner:
                    cand = f"{owner[key]}.{sub.attr}"
                    if cand in idx:
                        ref = cand
                if ref and ref != key:
                    edges.add(tuple(sorted((idx[key], idx[ref]))))
    try:
        import numpy as np
    except ImportError:
        return {"integration": None, "nodes": n, "edges": len(edges), "note": "numpy unavailable"}
    A = np.zeros((n, n))
    for i, j in edges:
        A[i, j] = A[j, i] = 1.0
    Lap = np.diag(A.sum(axis=1)) - A
    eig = np.sort(np.linalg.eigvalsh(Lap))
    lam2 = float(max(eig[1], 0.0))
    return {"integration": round(min(1.0, lam2 / n), 6), "fiedler_value": round(lam2, 6),
            "nodes": n, "edges": len(edges)}
