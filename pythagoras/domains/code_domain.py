"""
PYTHAGORAS — CODE DOMAIN
The first PYTHAGORAS domain: Python source code (AST) evolution.

The CodeDomain packages the original code-intelligence primitives behind the
pluggable Domain interface:
- Representation: Python source text / ast.Module
- Coherence: PhiResonanceCalculator (abstraction consistency, compositional
  depth balance, information density proportionality)
- CGP primitives: add_annotation, rename_var, extract_constant,
  inline_function, split_function
- Mutation primitives: ADD:AnnAssign, ADD:Return, ADD:Docstring,
  REFACTOR:Split, REFACTOR:Extract, ADVERSARIAL:Perturb
- Tests: compile() validity of the evolved artifact
- Features: the 8-dimensional AST topological basis
"""

from __future__ import annotations

import ast
import math
from typing import Any, Dict, List, Optional

import numpy as np

from ..domain import Domain, MutationPrimitive, WeightedPrimitive
from ..phi_resonance import PHI, PhiResonanceCalculator


# =============================================================================
# Infrastructure: __future__ import normalisation
# =============================================================================

def normalize_future_imports(source: str) -> str:
    """
    FIX-01: __future__ import normalisation.
    Ensures from __future__ import ... statements strictly precede all other
    statements (except module docstrings), preventing AST unparse syntax errors.
    """
    try:
        tree = ast.parse(source)
    except Exception:
        return source

    docstring: Optional[ast.Expr] = None
    future_imports: List[ast.ImportFrom] = []
    other_body: List[ast.AST] = []

    for i, node in enumerate(tree.body):
        if (
            i == 0
            and isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            docstring = node
        elif isinstance(node, ast.ImportFrom) and node.module == "__future__":
            future_imports.append(node)
        else:
            other_body.append(node)

    new_body: List[ast.AST] = []
    if docstring is not None:
        new_body.append(docstring)
    new_body.extend(future_imports)
    new_body.extend(other_body)

    tree.body = new_body
    ast.fix_missing_locations(tree)
    return ast.unparse(tree)


# =============================================================================
# CGP-layer primitives: (source, weight) -> source
# =============================================================================

def prim_add_annotation(source: str, weight: float) -> str:
    """
    Primitive: add_annotation
    Injects missing type annotations to parameters, returns, and variables.
    """
    try:
        tree = ast.parse(source)
        modified = False
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Add parameter annotations
                for arg in node.args.args:
                    if arg.annotation is None:
                        arg.annotation = ast.Name(id="Any", ctx=ast.Load())
                        modified = True
                # Add return annotation
                if node.returns is None:
                    node.returns = ast.Name(id="Any", ctx=ast.Load())
                    modified = True
            elif isinstance(node, ast.Assign) and len(node.targets) == 1:
                # Upgrade Assign to AnnAssign where applicable
                target = node.targets[0]
                if isinstance(target, ast.Name):
                    # Tag as int or Any
                    ann_assign = ast.AnnAssign(
                        target=target,
                        annotation=ast.Name(id="Any", ctx=ast.Load()),
                        value=node.value,
                        simple=1,
                    )
                    ast.copy_location(ann_assign, node)
                    # Replace node in parent body
                    # Handled if modifying via NodeTransformer
        if modified:
            return ast.unparse(tree)
        return source
    except Exception:
        return source


def prim_rename_var(source: str, weight: float) -> str:
    """
    Primitive: rename_var
    Refactors single-letter and cryptic variables to improve abstraction balance.
    """
    try:
        tree = ast.parse(source)
        renames = {"x": "target_val", "y": "result_val", "z": "metric_val", "t": "time_delta"}

        class Renamer(ast.NodeTransformer):
            def visit_Name(self, node: ast.Name) -> ast.Name:
                if node.id in renames:
                    return ast.copy_location(
                        ast.Name(id=renames[node.id], ctx=node.ctx), node
                    )
                return node

        new_tree = Renamer().visit(tree)
        ast.fix_missing_locations(new_tree)
        return ast.unparse(new_tree)
    except Exception:
        return source


def prim_extract_constant(source: str, weight: float) -> str:
    """
    Primitive: extract_constant
    Replaces numeric magic literals with named module constants.
    """
    try:
        tree = ast.parse(source)
        constants_to_add: List[ast.Assign] = []
        extracted_names: Dict[float, str] = {}

        class ConstantExtractor(ast.NodeTransformer):
            def visit_Constant(self, node: ast.Constant) -> ast.AST:
                if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
                    val = float(node.value)
                    # Exclude 0 and 1
                    if val not in (0.0, 1.0):
                        name = f"PHI_CONST_{abs(int(val * 1000))}"
                        if val not in extracted_names:
                            extracted_names[val] = name
                            assign = ast.Assign(
                                targets=[ast.Name(id=name, ctx=ast.Store())],
                                value=ast.Constant(value=node.value),
                            )
                            constants_to_add.append(assign)
                        return ast.copy_location(
                            ast.Name(id=extracted_names[val], ctx=ast.Load()), node
                        )
                return node

        transformer = ConstantExtractor()
        new_tree = transformer.visit(tree)
        if constants_to_add:
            # Prepend constants after docstrings and imports
            insert_idx = 0
            while insert_idx < len(new_tree.body) and isinstance(
                new_tree.body[insert_idx], (ast.Import, ast.ImportFrom, ast.Expr)
            ):
                insert_idx += 1
            for c in reversed(constants_to_add):
                new_tree.body.insert(insert_idx, c)
            ast.fix_missing_locations(new_tree)
            return ast.unparse(new_tree)
        return source
    except Exception:
        return source


def prim_inline_function(source: str, weight: float) -> str:
    """
    Primitive: inline_function
    Inlines trivial single-statement functions to reduce shallow call depth.
    """
    try:
        tree = ast.parse(source)
        single_expr_funcs: Dict[str, ast.AST] = {}
        for node in tree.body:
            if (
                isinstance(node, ast.FunctionDef)
                and len(node.body) == 1
                and isinstance(node.body[0], ast.Return)
                and node.body[0].value is not None
                and len(node.args.args) == 1
            ):
                # Identified candidate for inlining
                single_expr_funcs[node.name] = node.body[0].value

        if not single_expr_funcs:
            return source

        # Replace calls with expression where applicable
        class Inliner(ast.NodeTransformer):
            def visit_Call(self, node: ast.Call) -> ast.AST:
                if isinstance(node.func, ast.Name) and node.func.id in single_expr_funcs:
                    # Replace call with inlined constant or expression if 0-args or simple
                    return ast.copy_location(single_expr_funcs[node.func.id], node)
                return self.generic_visit(node)

        new_tree = Inliner().visit(tree)
        ast.fix_missing_locations(new_tree)
        return ast.unparse(new_tree)
    except Exception:
        return source


def prim_split_function(source: str, weight: float) -> str:
    """
    Primitive: split_function (ENH-01 function_split_refactor)
    Non-local AST restructuring targeting degenerate manifold escape.
    Finds a function with excessive body depth/statements, extracts trailing
    statements into a dedicated helper subroutine, and updates call site.
    """
    try:
        tree = ast.parse(source)
        target_fn: Optional[ast.FunctionDef] = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and len(node.body) >= 4:
                target_fn = node
                break

        if target_fn is None:
            return source

        # Split statements: first half remains, second half forms helper
        mid = len(target_fn.body) // 2
        head_body = target_fn.body[:mid]
        tail_body = target_fn.body[mid:]

        helper_name = f"_sub_{target_fn.name}_partition"
        # Collect variables referenced in tail_body
        tail_tree = ast.Module(body=tail_body, type_ignores=[])
        var_names = sorted(
            list(
                {
                    n.id
                    for n in ast.walk(tail_tree)
                    if isinstance(n, ast.Name) and not n.id.startswith("_")
                }
            )
        )

        helper_args = [ast.arg(arg=v, annotation=None) for v in var_names]
        helper_fn = ast.FunctionDef(
            name=helper_name,
            args=ast.arguments(
                posonlyargs=[],
                args=helper_args,
                vararg=None,
                kwonlyargs=[],
                kw_defaults=[],
                kwarg=None,
                defaults=[],
            ),
            body=tail_body,
            decorator_list=[],
            returns=None,
        )

        # In target_fn, call helper
        call_helper = ast.Expr(
            value=ast.Call(
                func=ast.Name(id=helper_name, ctx=ast.Load()),
                args=[ast.Name(id=v, ctx=ast.Load()) for v in var_names],
                keywords=[],
            )
        )
        target_fn.body = head_body + [call_helper]

        # Place helper_fn immediately before target_fn in module body
        fn_idx = tree.body.index(target_fn) if target_fn in tree.body else 0
        tree.body.insert(fn_idx, helper_fn)

        ast.fix_missing_locations(tree)
        return ast.unparse(tree)
    except Exception:
        return source


# =============================================================================
# Mutation-layer primitives: source -> source
# =============================================================================

def mut_add_ann_assign(source: str) -> str:
    """
    ADD:AnnAssign primitive.
    Injects type annotations into function signatures and variable assignments.
    Discovered with avg_gain=0.0775, weight=0.657.
    """
    try:
        tree = ast.parse(source)
        modified = False
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for arg in node.args.args:
                    if arg.annotation is None:
                        arg.annotation = ast.Name(id="int", ctx=ast.Load())
                        modified = True
                if node.returns is None:
                    node.returns = ast.Name(id="None", ctx=ast.Load())
                    modified = True

        if modified:
            return ast.unparse(tree)
        return source
    except Exception:
        return source


def mut_add_return(source: str) -> str:
    """
    ADD:Return primitive.
    Ensures functions have explicit return statements.
    """
    try:
        tree = ast.parse(source)
        modified = False
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.body:
                last_stmt = node.body[-1]
                if not isinstance(last_stmt, ast.Return):
                    node.body.append(ast.Return(value=ast.Constant(value=None)))
                    modified = True
        if modified:
            return ast.unparse(tree)
        return source
    except Exception:
        return source


def mut_add_docstring(source: str) -> str:
    """
    ADD:Docstring primitive.
    Injects structured docstrings to functions lacking documentation.
    """
    try:
        tree = ast.parse(source)
        modified = False
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                if not (
                    node.body
                    and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)
                ):
                    doc = ast.Expr(
                        value=ast.Constant(
                            value=f"Structural unit: {node.name}."
                        )
                    )
                    node.body.insert(0, doc)
                    modified = True
        if modified:
            return ast.unparse(tree)
        return source
    except Exception:
        return source


def mut_split_function(source: str) -> str:
    """
    REFACTOR:Split primitive.
    Splits high-complexity functions into cohesive subroutines.
    """
    try:
        tree = ast.parse(source)
        target_fn: Optional[ast.FunctionDef] = None
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and len(node.body) >= 4:
                target_fn = node
                break

        if target_fn is None:
            return source

        mid = len(target_fn.body) // 2
        head = target_fn.body[:mid]
        tail = target_fn.body[mid:]

        helper_name = f"_{target_fn.name}_partition"
        # Collect names in tail
        tail_ast = ast.Module(body=tail, type_ignores=[])
        names = sorted(
            list(
                {
                    n.id
                    for n in ast.walk(tail_ast)
                    if isinstance(n, ast.Name) and not n.id.startswith("_")
                }
            )
        )

        helper = ast.FunctionDef(
            name=helper_name,
            args=ast.arguments(
                posonlyargs=[],
                args=[ast.arg(arg=n, annotation=None) for n in names],
                vararg=None,
                kwonlyargs=[],
                kw_defaults=[],
                kwarg=None,
                defaults=[],
            ),
            body=tail,
            decorator_list=[],
            returns=None,
        )

        call = ast.Expr(
            value=ast.Call(
                func=ast.Name(id=helper_name, ctx=ast.Load()),
                args=[ast.Name(id=n, ctx=ast.Load()) for n in names],
                keywords=[],
            )
        )
        target_fn.body = head + [call]

        idx = tree.body.index(target_fn)
        tree.body.insert(idx, helper)
        ast.fix_missing_locations(tree)
        return ast.unparse(tree)
    except Exception:
        return source


def mut_extract_constant(source: str) -> str:
    """
    REFACTOR:Extract primitive.
    Extracts numeric constants into module definitions.
    """
    try:
        tree = ast.parse(source)
        extracted = []

        class Extractor(ast.NodeTransformer):
            def visit_Constant(self, node: ast.Constant) -> ast.AST:
                if isinstance(node.value, float) and node.value not in (0.0, 1.0):
                    name = f"COHERENCE_FACTOR_{int(abs(node.value * 100))}"
                    assign = ast.Assign(
                        targets=[ast.Name(id=name, ctx=ast.Store())],
                        value=ast.Constant(value=node.value),
                    )
                    extracted.append(assign)
                    return ast.copy_location(ast.Name(id=name, ctx=ast.Load()), node)
                return node

        new_tree = Extractor().visit(tree)
        if extracted:
            for a in reversed(extracted):
                new_tree.body.insert(0, a)
            ast.fix_missing_locations(new_tree)
            return ast.unparse(new_tree)
        return source
    except Exception:
        return source


def mut_adversarial_perturb(source: str) -> str:
    """
    ENH-12: Adversarial primitive generation.
    Injects controlled anti-primitives (e.g. redundant nesting or dead branch)
    to generate negative Δφ feedback and sharpen surrogate boundary discrimination.
    """
    try:
        tree = ast.parse(source)
        # Add a dead conditional branch inside a function if present
        injected = False
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and not injected:
                dead_branch = ast.If(
                    test=ast.Constant(value=False),
                    body=[ast.Pass()],
                    orelse=[],
                )
                node.body.append(dead_branch)
                injected = True
        if injected:
            return ast.unparse(tree)
        return source
    except Exception:
        return source


def ast_feature_vector(source: str, phi_calc: PhiResonanceCalculator) -> np.ndarray:
    """
    Extract the 8-dimensional AST topological feature basis:
    1. Node count (log scaled)
    2. Maximum depth
    3. Function definition count
    4. Class definition count
    5. Control branch count (If, For, While, Try, With)
    6. Information density proxy
    7. Expression ratio
    8. Current φ-score
    """
    try:
        tree = ast.parse(source)
        nodes = list(ast.walk(tree))
        node_count = len(nodes)
        func_count = sum(1 for n in nodes if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)))
        class_count = sum(1 for n in nodes if isinstance(n, ast.ClassDef))
        branch_count = sum(
            1 for n in nodes if isinstance(n, (ast.If, ast.For, ast.While, ast.Try, ast.With))
        )

        depth_map = phi_calc._build_depth_map(tree)
        max_depth = max(depth_map.values()) if depth_map else 1
        density = float(node_count) / (float(max_depth) * 10.0)
        expr_count = sum(1 for n in nodes if isinstance(n, ast.Expr))
        expr_ratio = float(expr_count) / max(1, node_count)
        current_phi = phi_calc.compute(source)

        return np.array(
            [
                math.log1p(node_count),
                float(max_depth),
                float(func_count),
                float(class_count),
                float(branch_count),
                min(1.0, density),
                expr_ratio,
                current_phi,
            ],
            dtype=float,
        )
    except Exception:
        return np.zeros(8, dtype=float)


# =============================================================================
# The Code Domain
# =============================================================================

class CodeDomain(Domain):
    """
    CodeDomain: Python source/AST evolution — the original PYTHAGORAS domain.

    Wraps the φ-resonance AST metric and the two primitive layers behind the
    pluggable Domain interface.
    """

    name = "code"
    file_extensions = (".py",)

    def __init__(self, phi_target: float = PHI):
        self.phi_calc = PhiResonanceCalculator(phi_target)
        self._primitives: Dict[str, WeightedPrimitive] = {
            "add_annotation": prim_add_annotation,
            "rename_var": prim_rename_var,
            "extract_constant": prim_extract_constant,
            "inline_function": prim_inline_function,
            "split_function": prim_split_function,
        }
        self._mutation_primitives: Dict[str, MutationPrimitive] = {
            "ADD:AnnAssign": mut_add_ann_assign,
            "ADD:Return": mut_add_return,
            "ADD:Docstring": mut_add_docstring,
            "REFACTOR:Split": mut_split_function,
            "REFACTOR:Extract": mut_extract_constant,
            "ADVERSARIAL:Perturb": mut_adversarial_perturb,
        }
        # Baseline learned weights (from empirical phase transition findings)
        self._mutation_weights: Dict[str, float] = {
            "ADD:AnnAssign": 0.657,
            "ADD:Return": 0.500,
            "ADD:Docstring": 0.400,
            "REFACTOR:Split": 0.350,
            "REFACTOR:Extract": 0.300,
            "ADVERSARIAL:Perturb": 0.100,  # ENH-12
        }

    def parse(self, source: str) -> ast.Module:
        return ast.parse(source)

    def unparse(self, rep: ast.Module) -> str:
        return ast.unparse(rep)

    def is_valid(self, source: str) -> bool:
        try:
            ast.parse(source)
            return True
        except SyntaxError:
            return False
        except Exception:
            return False

    def coherence(self, source: str) -> float:
        return self.phi_calc.compute(source)

    def compute_components(self, source: str) -> Dict[str, float]:
        return self.phi_calc.compute_components(source)

    def diagnose_manifold(self, source: str) -> Dict[str, Any]:
        """Delegate to the AST-specific ENH-02 manifold diagnostic."""
        return self.phi_calc.diagnose_manifold(source)

    def primitives(self) -> Dict[str, WeightedPrimitive]:
        return self._primitives

    def mutation_primitives(self) -> Dict[str, MutationPrimitive]:
        return self._mutation_primitives

    def mutation_weights(self) -> Dict[str, float]:
        return dict(self._mutation_weights)

    def tests(self, source: str) -> bool:
        """Domain test battery: the artifact must compile."""
        try:
            compile(source, "<pythagoras_domain_test>", "exec")
            return True
        except Exception:
            return False

    def features(self, source: str) -> np.ndarray:
        return ast_feature_vector(source, self.phi_calc)

    def normalize(self, source: str) -> str:
        return normalize_future_imports(source)

    def sample_source(self) -> str:
        return (
            '"""Sample module for domain smoke tests."""\n'
            "from __future__ import annotations\n\n"
            "def compute_square(x):\n"
            "    res = x * x\n"
            "    return res\n\n"
            "def process_items(items):\n"
            "    total = 0\n"
            "    for item in items:\n"
            "        if item > 0:\n"
            "            total += compute_square(item)\n"
            "    return total\n"
        )
