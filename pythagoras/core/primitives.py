"""PYTHAGORAS v12 AST transformation primitives.

The public v12 primitive vocabulary is retained, but the implementation uses
AST-aware transformations and the repository's canonical code-domain operators
where they already exist. Every result is a candidate; semantic acceptance is
left to the adapter's verification gate.
"""

from __future__ import annotations

import ast
from typing import Callable, List, Tuple


Primitive = Callable[[str, int], Tuple[str, str]]


class _RenameFirstLocal(ast.NodeTransformer):
    def __init__(self) -> None:
        self.old_name: str | None = None
        self.new_name: str | None = None

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        if self.old_name is not None:
            return node
        assigned = [
            child
            for child in ast.walk(node)
            if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store)
        ]
        if assigned:
            self.old_name = assigned[0].id
            self.new_name = f"{self.old_name}_pythagoras"
        return self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> ast.AST:
        if self.old_name is not None and node.id == self.old_name:
            return ast.copy_location(ast.Name(id=self.new_name or node.id, ctx=node.ctx), node)
        return node


class _SwapFirstBinaryOperator(ast.NodeTransformer):
    def __init__(self) -> None:
        self.changed = False

    def visit_BinOp(self, node: ast.BinOp) -> ast.AST:
        node = self.generic_visit(node)
        if self.changed:
            return node
        replacements = {
            ast.Add: ast.Sub,
            ast.Sub: ast.Add,
            ast.Mult: ast.Div,
            ast.Div: ast.Mult,
        }
        replacement = replacements.get(type(node.op))
        if replacement is not None:
            node.op = replacement()
            self.changed = True
        return node


class ASTPrimitives:
    """Stable v12 transformation vocabulary."""

    @staticmethod
    def _delegate(name: str, code_str: str) -> str:
        from pythagoras.domains import code_domain

        operation = getattr(code_domain, name)
        return operation(code_str)

    @staticmethod
    def apply_type_annotations(code_str: str, seed: int = 42) -> Tuple[str, str]:
        del seed
        return ASTPrimitives._delegate("mut_add_ann_assign", code_str), "ADD:AnnAssign"

    @staticmethod
    def function_split_refactor(code_str: str, seed: int = 42) -> Tuple[str, str]:
        del seed
        return (
            ASTPrimitives._delegate("mut_split_function", code_str),
            "NON_LOCAL:function_split_refactor",
        )

    @staticmethod
    def rename_variable(code_str: str, seed: int = 42) -> Tuple[str, str]:
        del seed
        try:
            tree = ast.parse(code_str)
            transformer = _RenameFirstLocal()
            new_tree = transformer.visit(tree)
            ast.fix_missing_locations(new_tree)
            if transformer.old_name is None:
                return code_str, "MUTATE:rename_variable"
            return ast.unparse(new_tree) + "\n", "MUTATE:rename_variable"
        except (SyntaxError, ValueError, TypeError):
            return code_str, "MUTATE:rename_variable"

    @staticmethod
    def swap_binary_operator(code_str: str, seed: int = 42) -> Tuple[str, str]:
        del seed
        try:
            tree = ast.parse(code_str)
            transformer = _SwapFirstBinaryOperator()
            new_tree = transformer.visit(tree)
            ast.fix_missing_locations(new_tree)
            if not transformer.changed:
                return code_str, "MUTATE:swap_binary_operator"
            return ast.unparse(new_tree) + "\n", "MUTATE:swap_binary_operator"
        except (SyntaxError, ValueError, TypeError):
            return code_str, "MUTATE:swap_binary_operator"

    @staticmethod
    def inject_docstring(code_str: str, seed: int = 42) -> Tuple[str, str]:
        del seed
        return ASTPrimitives._delegate("mut_add_docstring", code_str), "MUTATE:inject_docstring"

    @staticmethod
    def dead_code_branch(code_str: str, seed: int = 42) -> Tuple[str, str]:
        del seed
        try:
            tree = ast.parse(code_str)
        except (SyntaxError, ValueError, TypeError):
            return code_str, "MUTATE:dead_code_branch"
        branch = ast.If(
            test=ast.Constant(value=False),
            body=[ast.Assign(targets=[ast.Name(id="_pythagoras_probe", ctx=ast.Store())], value=ast.Constant(value=0))],
            orelse=[],
        )
        tree.body.append(branch)
        ast.fix_missing_locations(tree)
        return ast.unparse(tree) + "\n", "MUTATE:dead_code_branch"

    @staticmethod
    def list_comprehension(code_str: str, seed: int = 42) -> Tuple[str, str]:
        del seed
        # The canonical domain currently owns semantics-preserving loop rewrites.
        # Until a safe applicable pattern is found, this primitive is a measured no-op.
        return code_str, "MUTATE:list_comprehension"

    @classmethod
    def get_all_operators(cls) -> List[Tuple[str, Primitive]]:
        return [
            ("ADD:AnnAssign", cls.apply_type_annotations),
            ("NON_LOCAL:function_split_refactor", cls.function_split_refactor),
            ("MUTATE:rename_variable", cls.rename_variable),
            ("MUTATE:swap_binary_operator", cls.swap_binary_operator),
            ("MUTATE:inject_docstring", cls.inject_docstring),
            ("MUTATE:dead_code_branch", cls.dead_code_branch),
            ("MUTATE:list_comprehension", cls.list_comprehension),
        ]
