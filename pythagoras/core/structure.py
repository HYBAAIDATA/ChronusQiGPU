"""
PYTHAGORAS Effective-Structure Analysis
=======================================
The φ-resonance metric and the EUCLID Lucas index are defined over a module's
*effective* AST: the structure Python actually binds and executes.

Excluded from the effective structure (and, except docstrings, counted as
redundancy that lowers the integrity factor):
  - docstrings / bare string statements (documentation, not structure; not penalised)
  - constant-false branches            (`if False:` / `if 0:` / `while False:`)
  - unreachable statements             (after return / raise / break / continue)
  - shadowed definitions               (a def/class overwritten before it is used)
  - repeated identical assignments     (same statement re-executed with no use between)
  - unreferenced private definitions   (`_name` defs this module never references)

Shared by: core.phi_metric, core.euclid_intelligence, core.primitives.
"""
import ast
import copy
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

PHI = (1.0 + math.sqrt(5.0)) / 2.0

_SCOPE_NODES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
_COMP_NODES = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
_TERMINATORS = (ast.Return, ast.Raise, ast.Break, ast.Continue)
# Singleton grammar nodes: carry no structural branching, excluded from level widths.
_NON_STRUCTURAL = (ast.expr_context, ast.operator, ast.cmpop, ast.boolop, ast.unaryop)

_TYPING_ALIASES = {"List": "list", "Dict": "dict", "Set": "set", "Tuple": "tuple",
                   "FrozenSet": "frozenset"}
_BUILTIN_TYPES = {"int", "float", "str", "bool", "list", "dict", "set", "tuple",
                  "bytes", "complex", "frozenset"}


# --------------------------------------------------------------------------- #
# Type inference (conservative: returns None whenever the type is not certain)
# --------------------------------------------------------------------------- #
def infer_type(node: ast.AST) -> Optional[str]:
    if isinstance(node, ast.Constant):
        v = node.value
        if isinstance(v, bool):
            return "bool"
        if isinstance(v, int):
            return "int"
        if isinstance(v, float):
            return "float"
        if isinstance(v, str):
            return "str"
        if isinstance(v, bytes):
            return "bytes"
        if isinstance(v, complex):
            return "complex"
        return None
    if isinstance(node, (ast.List, ast.ListComp)):
        return "list"
    if isinstance(node, (ast.Dict, ast.DictComp)):
        return "dict"
    if isinstance(node, (ast.Set, ast.SetComp)):
        return "set"
    if isinstance(node, ast.Tuple):
        return "tuple"
    if isinstance(node, ast.JoinedStr):
        return "str"
    if isinstance(node, ast.Compare):
        return "bool"
    if isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.Not):
            return "bool"
        t = infer_type(node.operand)
        return t if t in ("int", "float", "complex") else None
    if isinstance(node, ast.BinOp):
        lt, rt = infer_type(node.left), infer_type(node.right)
        if lt == rt == "str" and isinstance(node.op, ast.Add):
            return "str"
        if lt in ("int", "float") and rt in ("int", "float"):
            if isinstance(node.op, ast.Div):
                return "float"
            if isinstance(node.op, ast.Pow) and lt == rt == "int":
                return None  # int ** negative int is float
            if isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.FloorDiv, ast.Mod, ast.Pow)):
                return "float" if "float" in (lt, rt) else "int"
        return None
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        f = node.func.id
        if f == "len":
            return "int"
        if f in ("sorted",):
            return "list"
        if f in ("repr", "str"):
            return "str"
        if f in _BUILTIN_TYPES:
            return f
    return None


def annotation_type(ann: ast.AST) -> Optional[str]:
    """Maps a simple annotation (`int`, `list`, `List[int]`) to a builtin type name."""
    if isinstance(ann, ast.Name):
        if ann.id in _BUILTIN_TYPES:
            return ann.id
        return _TYPING_ALIASES.get(ann.id)
    if isinstance(ann, ast.Subscript):
        return annotation_type(ann.value)
    if isinstance(ann, ast.Attribute) and isinstance(ann.value, ast.Name) and ann.value.id == "typing":
        return _TYPING_ALIASES.get(ann.attr)
    return None


def types_compatible(annotated: str, inferred: str) -> bool:
    """PEP 484 numeric tower: bool <: int <: float <: complex."""
    if annotated == inferred:
        return True
    tower = ["bool", "int", "float", "complex"]
    if annotated in tower and inferred in tower:
        return tower.index(inferred) <= tower.index(annotated)
    return False


# --------------------------------------------------------------------------- #
# Scope helpers
# --------------------------------------------------------------------------- #
def iter_scope(node: ast.AST):
    """Yields nodes belonging to the scope of `node`, not descending into nested scopes.
    Nested def/class nodes themselves are yielded (their names bind in this scope)."""
    stack = list(ast.iter_child_nodes(node))
    while stack:
        n = stack.pop()
        yield n
        if isinstance(n, _SCOPE_NODES):
            # decorators, defaults, bases are evaluated in the enclosing scope
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                stack.extend(n.decorator_list)
                stack.extend(d for d in n.args.defaults if d is not None)
                stack.extend(d for d in n.args.kw_defaults if d is not None)
            elif isinstance(n, ast.ClassDef):
                stack.extend(n.decorator_list)
                stack.extend(n.bases)
            continue
        if isinstance(n, _COMP_NODES):
            # only the first iterable is evaluated in the enclosing scope
            if n.generators:
                stack.append(n.generators[0].iter)
            continue
        stack.extend(ast.iter_child_nodes(n))


def scope_bindings(scope: ast.AST) -> Dict[str, List[ast.AST]]:
    """Maps each name bound in `scope` to the nodes that bind it."""
    out: Dict[str, List[ast.AST]] = {}

    def add(name, n):
        out.setdefault(name, []).append(n)

    if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
        a = scope.args
        for arg in a.posonlyargs + a.args + a.kwonlyargs:
            add(arg.arg, arg)
        if a.vararg:
            add(a.vararg.arg, a.vararg)
        if a.kwarg:
            add(a.kwarg.arg, a.kwarg)
    for n in iter_scope(scope):
        if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            add(n.id, n)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            add(n.name, n)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            for al in n.names:
                add((al.asname or al.name).split(".")[0], n)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            add(n.name, n)
        elif isinstance(n, (ast.Global, ast.Nonlocal)):
            for nm in n.names:
                add(nm, n)
    return out


def all_loaded_names(tree: ast.AST) -> Set[str]:
    names = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
            names.add(n.id)
        elif isinstance(n, ast.Attribute):
            names.add(n.attr)
        elif isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value.isidentifier():
            names.add(n.value)  # __all__ entries, getattr strings
    return names


def is_docstring(stmt: ast.stmt) -> bool:
    return (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant)
            and isinstance(stmt.value.value, str))


def node_count(node: ast.AST) -> int:
    return sum(1 for _ in ast.walk(node))


def ast_depth(node: ast.AST, current: int = 0) -> int:
    children = list(ast.iter_child_nodes(node))
    if not children:
        return current
    return max(ast_depth(c, current + 1) for c in children)


def _dump(node: ast.AST) -> str:
    return ast.dump(node, annotate_fields=True, include_attributes=False)


def _const_truth(test: ast.AST) -> Optional[bool]:
    if isinstance(test, ast.Constant):
        return bool(test.value)
    return None


def _names_touched(stmts: List[ast.stmt]) -> Set[str]:
    out = set()
    for s in stmts:
        for n in ast.walk(s):
            if isinstance(n, ast.Name):
                out.add(n.id)
            elif isinstance(n, ast.Attribute):
                out.add(n.attr)
    return out


# --------------------------------------------------------------------------- #
# Redundancy detection (shared with the HEAL operator)
# --------------------------------------------------------------------------- #
@dataclass
class RedundantSpan:
    kind: str                 # dead_branch | unreachable | shadowed_definition | repeated_assignment | unreferenced_private
    node: ast.AST
    nodes: int                # AST nodes in the span
    removable: bool           # safe for HEAL to delete from source


def find_redundancy(tree: ast.Module) -> List[RedundantSpan]:
    spans: List[RedundantSpan] = []
    loaded = all_loaded_names(tree)

    def visit_body(stmts: List[ast.stmt], level: str):
        # unreachable statements after a terminator
        for i, s in enumerate(stmts):
            if isinstance(s, _TERMINATORS) and i + 1 < len(stmts):
                for dead in stmts[i + 1:]:
                    spans.append(RedundantSpan("unreachable", dead, node_count(dead), True))
                stmts = stmts[: i + 1]
                break

        defs_seen: Dict[str, int] = {}
        assigns_seen: Dict[str, Tuple[int, str]] = {}
        repeated_ids: Set[int] = set()
        for i, s in enumerate(stmts):
            # constant-false branches
            if isinstance(s, (ast.If, ast.While)) and _const_truth(s.test) is False and not s.orelse:
                spans.append(RedundantSpan("dead_branch", s, node_count(s), True))
                continue

            # shadowed definitions (undecorated, never used before being overwritten)
            if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if s.name in defs_seen:
                    j = defs_seen[s.name]
                    prev = stmts[j]
                    between = stmts[j + 1:i]
                    if (not prev.decorator_list and not s.decorator_list
                            and s.name not in _names_touched(between)):
                        spans.append(RedundantSpan("shadowed_definition", prev, node_count(prev), True))
                defs_seen[s.name] = i

            # repeated identical assignments to a simple name with no use in between
            if isinstance(s, (ast.Assign, ast.AnnAssign)):
                targets = s.targets if isinstance(s, ast.Assign) else [s.target]
                if len(targets) == 1 and isinstance(targets[0], ast.Name) and s.value is not None:
                    name = targets[0].id
                    sig = _dump(s)
                    if name in assigns_seen:
                        j, prev_sig = assigns_seen[name]
                        between = [b for b in stmts[j + 1:i] if id(b) not in repeated_ids]
                        if prev_sig == sig and name not in _names_touched(between):
                            spans.append(RedundantSpan("repeated_assignment", s, node_count(s), True))
                            repeated_ids.add(id(s))
                            continue
                    assigns_seen[name] = (i, sig)

            # unreferenced private definitions (module / class level only)
            if level in ("module", "class") and isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if s.name.startswith("_") and not s.name.startswith("__") and s.name not in loaded:
                    # not auto-removable: may be imported by another module in the host project
                    spans.append(RedundantSpan("unreferenced_private", s, node_count(s), False))

            # recurse
            if isinstance(s, ast.ClassDef):
                visit_body(s.body, "class")
            elif isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef)):
                visit_body(s.body, "function")
            else:
                for fld in ("body", "orelse", "finalbody"):
                    sub = getattr(s, fld, None)
                    if isinstance(sub, list) and sub and isinstance(sub[0], ast.stmt):
                        visit_body(sub, level)
                for h in getattr(s, "handlers", []) or []:
                    visit_body(h.body, level)
                for c in getattr(s, "cases", []) or []:
                    visit_body(c.body, level)

    visit_body(tree.body, "module")

    # one span per node: a removable classification wins over a non-removable one
    by_node: Dict[int, RedundantSpan] = {}
    for sp in spans:
        cur = by_node.get(id(sp.node))
        if cur is None or (sp.removable and not cur.removable):
            by_node[id(sp.node)] = sp
    spans = list(by_node.values())

    # drop spans nested inside another span (already counted by the outer span)
    contained = set()
    for sp in spans:
        for n in ast.walk(sp.node):
            if n is not sp.node:
                contained.add(id(n))
    return [sp for sp in spans if id(sp.node) not in contained]


def _strip(tree: ast.Module, drop_ids: Set[int]) -> ast.Module:
    """Returns a deep copy of `tree` without docstrings and without the statements in `drop_ids`."""
    clone = copy.deepcopy(tree)
    mapping = {id(a): b for a, b in zip(ast.walk(tree), ast.walk(clone))}
    drop = {id(mapping[i]) for i in drop_ids if i in mapping}

    def clean(stmts):
        # bare string statements (docstrings and stray string literals) are no-ops, not structure
        return [s for s in stmts if id(s) not in drop and not is_docstring(s)]

    for node in ast.walk(clone):
        for fld in ("body", "orelse", "finalbody"):
            sub = getattr(node, fld, None)
            if isinstance(sub, list) and sub and isinstance(sub[0], ast.stmt):
                cleaned = clean(sub)
                if fld == "body" and not cleaned and not isinstance(node, ast.Module):
                    cleaned = [ast.Pass()]
                setattr(node, fld, cleaned)
        if isinstance(node, ast.ExceptHandler):
            node.body = clean(node.body) or [ast.Pass()]
    return clone


# --------------------------------------------------------------------------- #
# Structure report
# --------------------------------------------------------------------------- #
@dataclass
class StructureReport:
    parse_ok: bool
    raw_nodes: int = 0
    effective_nodes: int = 0
    redundant_nodes: int = 0
    redundancy: Dict[str, int] = field(default_factory=dict)
    depth: int = 0
    level_widths: List[int] = field(default_factory=list)
    function_count: int = 0
    statement_count: int = 0
    annotation_sites: int = 0
    coherent_annotations: int = 0
    contradictory_annotations: int = 0
    coherent_ann_assigns: int = 0
    effective_tree: Optional[ast.Module] = None

    @property
    def integrity(self) -> float:
        """(1 - redundancy share) ** φ — redundancy is penalised super-linearly."""
        if not self.parse_ok or self.raw_nodes == 0:
            return 0.0
        share = self.redundant_nodes / self.raw_nodes
        return round(max(0.0, 1.0 - share) ** PHI, 6)

    @property
    def annotation_coherence(self) -> float:
        if self.annotation_sites == 0:
            return 0.0
        net = max(0, self.coherent_annotations - self.contradictory_annotations)
        return round(min(1.0, net / self.annotation_sites), 6)

    @property
    def annotation_density(self) -> float:
        return round(self.coherent_ann_assigns / max(self.effective_nodes, 1), 6)


def _level_widths(tree: ast.AST) -> List[int]:
    widths: List[int] = []
    frontier = [tree]
    while frontier:
        widths.append(len(frontier))
        nxt = []
        for n in frontier:
            nxt.extend(c for c in ast.iter_child_nodes(n) if not isinstance(c, _NON_STRUCTURAL))
        frontier = nxt
    return widths


def _annotation_stats(tree: ast.Module) -> Tuple[int, int, int, int]:
    sites = coherent = contradictory = coherent_ann_assigns = 0
    scopes: List[ast.AST] = [tree] + [n for n in ast.walk(tree)
                                      if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    class_bodies = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    for scope in scopes:
        if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = scope.args.posonlyargs + scope.args.args + scope.args.kwonlyargs
            parent_is_class = any(scope in c.body for c in class_bodies)
            if parent_is_class and args and args[0].arg in ("self", "cls"):
                args = args[1:]
            for a in args:
                sites += 1
                if a.annotation is not None:
                    coherent += 1
            sites += 1  # return annotation site
            if scope.returns is not None:
                coherent += 1
        seen: Set[str] = set()
        for n in iter_scope(scope):
            if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
                if n.target.id in seen:
                    continue
                seen.add(n.target.id)
                sites += 1
                at = annotation_type(n.annotation)
                vt = infer_type(n.value) if n.value is not None else None
                if at and vt and not types_compatible(at, vt):
                    contradictory += 1
                else:
                    coherent += 1
                    coherent_ann_assigns += 1
            elif (isinstance(n, ast.Assign) and len(n.targets) == 1
                  and isinstance(n.targets[0], ast.Name)):
                if n.targets[0].id in seen:
                    continue
                seen.add(n.targets[0].id)
                sites += 1
    return sites, coherent, contradictory, coherent_ann_assigns


def analyze_structure(code_str: str) -> StructureReport:
    try:
        tree = ast.parse(code_str)
    except (SyntaxError, ValueError):
        return StructureReport(parse_ok=False)

    raw_nodes = node_count(tree)
    spans = find_redundancy(tree)
    redundancy: Dict[str, int] = {}
    for sp in spans:
        redundancy[sp.kind] = redundancy.get(sp.kind, 0) + sp.nodes
    redundant_nodes = sum(redundancy.values())

    eff = _strip(tree, {id(sp.node) for sp in spans})
    sites, coherent, contradictory, coherent_ann = _annotation_stats(eff)

    return StructureReport(
        parse_ok=True,
        raw_nodes=raw_nodes,
        effective_nodes=node_count(eff),
        redundant_nodes=redundant_nodes,
        redundancy=redundancy,
        depth=ast_depth(eff),
        level_widths=_level_widths(eff),
        function_count=sum(1 for n in ast.walk(eff) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))),
        statement_count=len(eff.body),
        annotation_sites=sites,
        coherent_annotations=coherent,
        contradictory_annotations=contradictory,
        coherent_ann_assigns=coherent_ann,
        effective_tree=eff,
    )


def golden_growth_resonance(level_widths: List[int], target_ratio: float = PHI) -> float:
    """
    Proximity of the AST's level-to-level growth to golden (Fibonacci) growth.
    Over the expansion phase (level 1 up to the widest level), each ratio
    r_k = w_{k+1} / w_k scores min(r/target, target/r); the result is the mean.
    A Fibonacci tree scores 1.0.
    """
    if len(level_widths) < 3:
        return 0.0
    peak = max(range(len(level_widths)), key=lambda k: level_widths[k])
    ratios = [level_widths[k + 1] / level_widths[k]
              for k in range(1, peak) if level_widths[k] > 0]
    if not ratios:
        return 0.0
    scores = [min(r / target_ratio, target_ratio / r) for r in ratios if r > 0]
    return round(sum(scores) / len(scores), 6) if scores else 0.0
