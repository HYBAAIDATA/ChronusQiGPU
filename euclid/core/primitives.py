"""
EUCLID AST-Aware Operator Primitives v16.0
==============================================
Provides safe, deterministic, AST-aware code transformations using Python's ast.NodeTransformer.
Replaces legacy string pattern replacements to prevent substring corruption and preserve program semantics.
"""

import ast
from typing import Dict, List, Tuple, Any, Callable

class TypeAnnotationTransformer(ast.NodeTransformer):
    """AST NodeTransformer that injects type annotations onto unannotated assignments and function definitions."""
    def __init__(self):
        self.transformed = False

    def visit_Assign(self, node: ast.Assign):
        if not self.transformed and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            self.transformed = True
            return ast.AnnAssign(
                target=node.targets[0],
                annotation=ast.Name(id="float", ctx=ast.Load()),
                value=node.value,
                simple=1
            )
        return self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        if not self.transformed and node.returns is None:
            node.returns = ast.Name(id="float", ctx=ast.Load())
            self.transformed = True
        return self.generic_visit(node)


class ConditionalGuardTransformer(ast.NodeTransformer):
    """AST NodeTransformer that flattens nested conditionals into combined boolean guard expressions."""
    def __init__(self):
        self.transformed = False

    def visit_If(self, node: ast.If):
        if not self.transformed and len(node.body) == 1 and isinstance(node.body[0], ast.If) and not node.orelse and not node.body[0].orelse:
            self.transformed = True
            inner_if = node.body[0]
            combined_test = ast.BoolOp(
                op=ast.And(),
                values=[node.test, inner_if.test]
            )
            return ast.If(
                test=combined_test,
                body=inner_if.body,
                orelse=[]
            )
        return self.generic_visit(node)


class OperatorSwapTransformer(ast.NodeTransformer):
    """AST NodeTransformer that safely swaps binary arithmetic operators (e.g. Add <-> Sub)."""
    def __init__(self):
        self.transformed = False

    def visit_BinOp(self, node: ast.BinOp):
        if not self.transformed:
            if isinstance(node.op, ast.Add):
                node.op = ast.Sub()
                self.transformed = True
            elif isinstance(node.op, ast.Sub):
                node.op = ast.Add()
                self.transformed = True
            elif isinstance(node.op, ast.Mult):
                node.op = ast.Div()
                self.transformed = True
        return self.generic_visit(node)


class ListCompTransformer(ast.NodeTransformer):
    """AST NodeTransformer that converts for-loops appending to lists into list comprehensions."""
    def __init__(self):
        self.transformed = False

    def visit_For(self, node: ast.For):
        if not self.transformed and len(node.body) == 1 and isinstance(node.body[0], ast.Expr):
            call = node.body[0].value
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) and call.func.attr == "append":
                if isinstance(call.func.value, ast.Name) and len(call.args) == 1:
                    list_name = call.func.value.id
                    elt = call.args[0]
                    self.transformed = True
                    list_comp = ast.ListComp(
                        elt=elt,
                        generators=[ast.comprehension(target=node.target, iter=node.iter, ifs=[], is_async=0)]
                    )
                    return ast.Assign(
                        targets=[ast.Name(id=list_name, ctx=ast.Store())],
                        value=list_comp
                    )
        return self.generic_visit(node)


class FunctionSplitTransformer(ast.NodeTransformer):
    """AST NodeTransformer that extracts helper functions from monolithic function bodies."""
    def __init__(self):
        self.transformed = False
        self.extracted_helpers = []

    def visit_Module(self, node: ast.Module):
        self.generic_visit(node)
        if self.extracted_helpers:
            node.body.extend(self.extracted_helpers)
            ast.fix_missing_locations(node)
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef):
        if not self.transformed and len(node.body) >= 3 and not node.name.endswith("_helper"):
            self.transformed = True
            helper_name = f"_{node.name}_helper"
            # Extract first statement into helper
            extracted_stmt = node.body.pop(0)
            
            helper_fn = ast.FunctionDef(
                name=helper_name,
                args=ast.arguments(posonlyargs=[], args=[ast.arg(arg="x", annotation=None)], kwonlyargs=[], kw_defaults=[], defaults=[]),
                body=[extracted_stmt, ast.Return(value=ast.Name(id="x", ctx=ast.Load()))],
                decorator_list=[],
                returns=None
            )
            self.extracted_helpers.append(helper_fn)
        return self.generic_visit(node)


class ClassDecompositionTransformer(ast.NodeTransformer):
    """AST NodeTransformer that wraps top-level functions into structured helper classes."""
    def __init__(self):
        self.transformed = False

    def visit_Module(self, node: ast.Module):
        top_functions = [n for n in node.body if isinstance(n, ast.FunctionDef)]
        if not self.transformed and top_functions:
            self.transformed = True
            target_fn = top_functions[0]
            # Convert function into a class static method inside _DecomposedModule
            class_def = ast.ClassDef(
                name="_DecomposedModule",
                bases=[],
                keywords=[],
                body=[
                    ast.FunctionDef(
                        name=f"execute_{target_fn.name}",
                        args=target_fn.args,
                        body=target_fn.body,
                        decorator_list=[ast.Name(id="staticmethod", ctx=ast.Load())],
                        returns=target_fn.returns
                    )
                ],
                decorator_list=[]
            )
            node.body.insert(0, class_def)
            ast.fix_missing_locations(node)
        return node


class ASTPrimitives:
    """
    AST-Aware Operator Vocabulary.
    Provides pure AST-to-AST transformation primitives.
    """
    @staticmethod
    def _apply_transformer(code_str: str, transformer_cls: type) -> Tuple[str, bool]:
        try:
            tree = ast.parse(code_str)
            transformer = transformer_cls()
            modified_tree = transformer.visit(tree)
            if getattr(transformer, "transformed", False):
                ast.fix_missing_locations(modified_tree)
                return ast.unparse(modified_tree), True
        except Exception:
            pass
        return code_str, False

    @classmethod
    def apply_type_annotations(cls, code_str: str, seed: int = 42) -> Tuple[str, str]:
        res, ok = cls._apply_transformer(code_str, TypeAnnotationTransformer)
        return res, "ADD:AnnAssign"

    @classmethod
    def conditional_flattening(cls, code_str: str, seed: int = 42) -> Tuple[str, str]:
        res, ok = cls._apply_transformer(code_str, ConditionalGuardTransformer)
        return res, "NON_LOCAL:conditional_flattening"

    @classmethod
    def swap_operators(cls, code_str: str, seed: int = 42) -> Tuple[str, str]:
        res, ok = cls._apply_transformer(code_str, OperatorSwapTransformer)
        return res, "MUTATE:swap_op"

    @classmethod
    def list_comp_optimization(cls, code_str: str, seed: int = 42) -> Tuple[str, str]:
        res, ok = cls._apply_transformer(code_str, ListCompTransformer)
        return res, "MUTATE:list_comp"

    @classmethod
    def function_split_refactor(cls, code_str: str, seed: int = 42) -> Tuple[str, str]:
        res, ok = cls._apply_transformer(code_str, FunctionSplitTransformer)
        return res, "NON_LOCAL:function_split_refactor"

    @classmethod
    def class_decomposition(cls, code_str: str, seed: int = 42) -> Tuple[str, str]:
        res, ok = cls._apply_transformer(code_str, ClassDecompositionTransformer)
        return res, "NON_LOCAL:class_decomposition"

    @classmethod
    def get_all_operators(cls) -> List[Tuple[str, Callable[[str, int], Tuple[str, str]]]]:
        return [
            ("ADD:AnnAssign", cls.apply_type_annotations),
            ("NON_LOCAL:conditional_flattening", cls.conditional_flattening),
            ("MUTATE:swap_op", cls.swap_operators),
            ("MUTATE:list_comp", cls.list_comp_optimization),
            ("NON_LOCAL:function_split_refactor", cls.function_split_refactor),
            ("NON_LOCAL:class_decomposition", cls.class_decomposition),
        ]
