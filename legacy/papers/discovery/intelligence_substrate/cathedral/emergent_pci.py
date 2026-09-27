"""
CATHEDRAL PILLAR 1: EMERGENT INTELLIGENCE FROM CODE COMPLEXITY
==============================================================
Restored from Cathedral AI System architecture.
Extracts instant machine intelligence directly from AST complexity, function
call topologies, and golden ratio phi-resonance.
"""

from __future__ import annotations

import ast
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

PHI: float = (1.0 + math.sqrt(5.0)) / 2.0


@dataclass
class FunctionMetrics:
    name: str
    cyclomatic_complexity: int
    cognitive_complexity: int
    call_count: int
    lines_of_code: int
    phi_alignment: float
    callees: List[str] = field(default_factory=list)


@dataclass
class CodeCausalGraph:
    nodes: List[str]
    adjacency_matrix: np.ndarray
    laplacian_matrix: np.ndarray
    fiedler_eigenvalue: float
    spectral_radius: float
    phi_resonance: float
    emergence_index: float


class _ASTComplexityVisitor(ast.NodeVisitor):
    """Parses AST to calculate cyclomatic complexity, cognitive depth, and function calls."""

    def __init__(self) -> None:
        self.functions: Dict[str, FunctionMetrics] = {}
        self._current_function: Optional[str] = None
        self._current_cognitive_depth: int = 0
        self._current_cyclomatic: int = 1
        self._current_cognitive: int = 0
        self._current_callees: List[str] = []
        self._func_start_line: int = 0

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        self._enter_func(node.name, node.lineno)
        self.generic_visit(node)
        self._exit_func(node.name, node.end_lineno or node.lineno)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        self._enter_func(node.name, node.lineno)
        self.generic_visit(node)
        self._exit_func(node.name, node.end_lineno or node.lineno)

    def _enter_func(self, name: str, start_line: int) -> None:
        self._current_function = name
        self._current_cyclomatic = 1
        self._current_cognitive = 0
        self._current_cognitive_depth = 0
        self._current_callees = []
        self._func_start_line = start_line

    def _exit_func(self, name: str, end_line: int) -> None:
        loc = max(1, end_line - self._func_start_line + 1)
        # Compute phi-alignment: ratio of complexity to LOC normalized by PHI
        complexity_ratio = self._current_cyclomatic / float(loc)
        phi_align = float(1.0 / (1.0 + abs(complexity_ratio - (1.0 / PHI))))

        self.functions[name] = FunctionMetrics(
            name=name,
            cyclomatic_complexity=self._current_cyclomatic,
            cognitive_complexity=self._current_cognitive,
            call_count=len(self._current_callees),
            lines_of_code=loc,
            phi_alignment=phi_align,
            callees=list(self._current_callees),
        )
        self._current_function = None

    def visit_If(self, node: ast.If) -> Any:
        if self._current_function:
            self._current_cyclomatic += 1
            self._current_cognitive += 1 + self._current_cognitive_depth
            self._current_cognitive_depth += 1
            self.generic_visit(node)
            self._current_cognitive_depth -= 1
        else:
            self.generic_visit(node)

    def visit_For(self, node: ast.For) -> Any:
        if self._current_function:
            self._current_cyclomatic += 1
            self._current_cognitive += 1 + self._current_cognitive_depth
            self._current_cognitive_depth += 1
            self.generic_visit(node)
            self._current_cognitive_depth -= 1
        else:
            self.generic_visit(node)

    def visit_While(self, node: ast.While) -> Any:
        if self._current_function:
            self._current_cyclomatic += 1
            self._current_cognitive += 1 + self._current_cognitive_depth
            self._current_cognitive_depth += 1
            self.generic_visit(node)
            self._current_cognitive_depth -= 1
        else:
            self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> Any:
        if self._current_function:
            self._current_cyclomatic += 1
            self._current_cognitive += 1
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> Any:
        if self._current_function:
            callee_name = ""
            if isinstance(node.func, ast.Name):
                callee_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                callee_name = node.func.attr
            if callee_name:
                self._current_callees.append(callee_name)
        self.generic_visit(node)


class EmergentCodeIntelligence:
    """
    Cathedral Emergent PCI Engine.
    Transforms arbitrary codebases into self-documenting neural causal graphs
    and extracts intrinsic intelligence metrics.
    """

    def analyze_source(self, code_content: str, filename: str = "<anonymous>") -> Dict[str, Any]:
        """Parse source code string and extract topological emergence metrics."""
        try:
            tree = ast.parse(code_content, filename=filename)
        except SyntaxError as e:
            return {
                "filename": filename,
                "status": "SYNTAX_ERROR",
                "error": str(e),
                "emergence_index": 0.0,
            }

        visitor = _ASTComplexityVisitor()
        visitor.visit(tree)

        functions = visitor.functions
        node_names = list(functions.keys())
        n = len(node_names)

        if n == 0:
            return {
                "filename": filename,
                "status": "EMPTY_OR_NO_FUNCTIONS",
                "node_count": 0,
                "emergence_index": 0.0,
                "phi_resonance": 0.0,
            }

        name_to_idx = {name: i for i, name in enumerate(node_names)}
        adj = np.zeros((n, n), dtype=float)

        for name, metrics in functions.items():
            u = name_to_idx[name]
            for callee in metrics.callees:
                if callee in name_to_idx:
                    v = name_to_idx[callee]
                    adj[u, v] += 1.0

        # Symmetrized adjacency for undirected Laplacian connectivity
        sym_adj = np.maximum(adj, adj.T)
        deg = np.diag(np.sum(sym_adj, axis=1))
        laplacian = deg - sym_adj

        # Spectral analysis: Fiedler eigenvalue lambda_2
        evals = np.linalg.eigvalsh(laplacian)
        fiedler = float(evals[1]) if len(evals) > 1 else 0.0
        fiedler = max(0.0, fiedler)

        # Spectral radius of directed adjacency
        dir_evals = np.linalg.eigvals(adj)
        spectral_radius = float(np.max(np.abs(dir_evals))) if len(dir_evals) > 0 else 0.0

        # Mean phi alignment across nodes
        mean_phi_align = float(np.mean([m.phi_alignment for m in functions.values()]))

        # Mean cyclomatic complexity
        mean_cyclomatic = float(np.mean([m.cyclomatic_complexity for m in functions.values()]))

        # Cathedral Emergence Index Psi:
        # Psi = phi * ln(1 + |V|) * (1 - e^(-lambda_2)) * (1 / (1 + |mean_cyclomatic - phi|))
        emergence_index = float(
            PHI
            * math.log(1.0 + n)
            * (1.0 - math.exp(-fiedler))
            * (1.0 / (1.0 + abs(mean_cyclomatic - PHI)))
        )

        causal_graph = CodeCausalGraph(
            nodes=node_names,
            adjacency_matrix=adj,
            laplacian_matrix=laplacian,
            fiedler_eigenvalue=fiedler,
            spectral_radius=spectral_radius,
            phi_resonance=mean_phi_align,
            emergence_index=emergence_index,
        )

        return {
            "filename": filename,
            "status": "INTELLIGENCE_EMERGED",
            "node_count": n,
            "edge_count": int(np.sum(adj > 0)),
            "fiedler_eigenvalue": fiedler,
            "spectral_radius": spectral_radius,
            "phi_resonance": mean_phi_align,
            "emergence_index": emergence_index,
            "functions": {name: vars(m) for name, m in functions.items()},
            "causal_graph": causal_graph,
        }

    def analyze_file(self, file_path: Path | str) -> Dict[str, Any]:
        """Analyze a physical Python source file."""
        p = Path(file_path)
        if not p.exists():
            raise FileNotFoundError(f"Source file not found: {p}")
        code = p.read_text(encoding="utf-8", errors="replace")
        return self.analyze_source(code, filename=str(p))

    def analyze_directory(self, dir_path: Path | str, max_files: int = 50) -> Dict[str, Any]:
        """Aggregate emergent intelligence across an entire codebase directory."""
        d = Path(dir_path)
        if not d.exists() or not d.is_dir():
            raise NotADirectoryError(f"Directory not found: {d}")

        py_files = sorted(list(d.glob("**/*.py")))[:max_files]
        total_nodes = 0
        total_edges = 0
        sum_emergence = 0.0
        sum_phi = 0.0
        analyzed_count = 0

        file_reports = []
        for f in py_files:
            try:
                rep = self.analyze_file(f)
                if rep.get("status") == "INTELLIGENCE_EMERGED":
                    total_nodes += rep["node_count"]
                    total_edges += rep["edge_count"]
                    sum_emergence += rep["emergence_index"]
                    sum_phi += rep["phi_resonance"]
                    analyzed_count += 1
                file_reports.append(rep)
            except Exception as e:
                file_reports.append({"filename": str(f), "status": "ERROR", "error": str(e)})

        mean_emergence = sum_emergence / max(1, analyzed_count)
        mean_phi = sum_phi / max(1, analyzed_count)

        return {
            "directory": str(d),
            "files_analyzed": analyzed_count,
            "total_nodes": total_nodes,
            "total_edges": total_edges,
            "aggregate_emergence_index": mean_emergence,
            "aggregate_phi_resonance": mean_phi,
            "file_reports": file_reports,
        }
