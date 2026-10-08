"""Program structure (Python AST) → Problem."""

from __future__ import annotations

import ast
from typing import Any, Dict, List, Mapping, Tuple

from ..problem import Problem
from .base import ProblemAdapter


def _functions(tree: ast.AST) -> Dict[str, ast.AST]:
    out: Dict[str, ast.AST] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.setdefault(node.name, node)
    return out


class CodeStructureAdapter(ProblemAdapter):
    """``source``: Python source text; ``entry`` / ``target``: function
    names for the reachability question ("can ``entry`` reach ``target``
    through calls?"). Parsing is translation; reachability, components and
    bottlenecks are answered by the backend's topology."""

    name = "code"

    def to_problem(self, raw: Mapping[str, Any]) -> Problem:
        tree = ast.parse(raw["source"])
        funcs = _functions(tree)
        calls: List[Tuple[str, str]] = []
        features: Dict[str, List[float]] = {"branches": [], "calls": [], "statements": []}
        for name, node in sorted(funcs.items()):
            callees = set()
            branches = 0
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call):
                    f = sub.func
                    callee = (
                        f.id
                        if isinstance(f, ast.Name)
                        else f.attr if isinstance(f, ast.Attribute) else None
                    )
                    if callee in funcs and callee != name:
                        callees.add(callee)
                elif isinstance(sub, (ast.If, ast.For, ast.While, ast.Try, ast.With, ast.IfExp)):
                    branches += 1
            calls.extend((name, c) for c in sorted(callees))
            features["branches"].append(float(branches))
            features["calls"].append(float(len(callees)))
            features["statements"].append(
                float(sum(isinstance(s, ast.stmt) for s in ast.walk(node)))
            )
        isolated = [(n, n) for n in funcs if not any(n in e for e in calls)]
        return Problem(
            domain=str(raw.get("domain", self.name)),
            observation=features,
            transitions=calls + isolated,
            navigation=(raw["entry"], raw["target"]) if raw.get("entry") else None,
            metadata={"adapter": self.name, "functions": sorted(funcs)},
        )

    def interpret(self, episode: Mapping[str, Any]) -> Dict[str, Any]:
        out = super().interpret(episode)
        nav = episode.get("navigation") or {}
        if nav:
            out["call_path"] = nav.get("route")
            out["unreachable_functions"] = nav.get("unreachable_from_source")
            out["critical_functions"] = nav.get("articulation_points")
        return out


__all__ = ["CodeStructureAdapter"]
