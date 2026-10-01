"""
AST Transformation Primitives & Refactoring Operators
=====================================================
Every operator is a real source-to-source transform that returns the input
unchanged when it finds no applicable site. Edits are made at exact AST
positions on the original text, so comments and formatting elsewhere survive.

Behaviour-preserving (always active):
    ADD:AnnAssign                       annotate an assignment with its inferred type
    NON_LOCAL:function_split_refactor   golden-section extract-method
    NON_LOCAL:conditional_flattening    `if a:` + nested `if b:` → `if a and b:`
    MUTATE:list_comprehension           append-loop → list comprehension
    HEAL:dead_code_elimination          SALAMANDER: remove dead / shadowed / repeated code
    MUTATE:inject_docstring             module docstring if missing (φ-neutral)

Behaviour-changing (active only when the host supplies a test runner):
    MUTATE:swap_binary_operator
    MUTATE:rename_variable              consistent rename of one local within one function

Not implemented as a behaviour-preserving transform (inert, returns input):
    NON_LOCAL:class_decomposition

Operators take (code_str, seed) and return (new_code, operator_name). `seed`
selects among applicable sites, so different seeds explore different paths.
"""
import ast
import re
import random
from typing import Callable, Dict, List, Optional, Set, Tuple

from pythagoras.core.structure import (
    PHI, infer_type, iter_scope, scope_bindings, find_redundancy, is_docstring,
)

Operator = Callable[[str, int], Tuple[str, str]]


# --------------------------------------------------------------------------- #
# Text helpers (AST col offsets are UTF-8 byte offsets)
# --------------------------------------------------------------------------- #
def _col(line: str, byte_col: int) -> int:
    return len(line.encode("utf-8")[:byte_col].decode("utf-8", errors="ignore"))


def _indent(line: str) -> str:
    return line[: len(line) - len(line.lstrip())]


def _starts_line(lines: List[str], node: ast.AST) -> bool:
    line = lines[node.lineno - 1]
    return line[: _col(line, node.col_offset)].strip() == ""


def _ends_line(lines: List[str], node: ast.AST) -> bool:
    line = lines[node.end_lineno - 1]
    rest = line[_col(line, node.end_col_offset):].strip()
    return rest == "" or rest.startswith("#")


def _has_multiline_string(node: ast.AST) -> bool:
    for n in ast.walk(node):
        if isinstance(n, (ast.Constant, ast.JoinedStr)) and isinstance(getattr(n, "value", ""), (str, list)):
            if getattr(n, "end_lineno", n.lineno) > n.lineno:
                return True
    return False


def _has_comment(lines: List[str], start: int, end: int) -> bool:
    return any("#" in lines[i] for i in range(start - 1, end))


def _replace_lines(code: str, start: int, end: int, new_text: str) -> str:
    """Replaces 1-based inclusive line range [start, end] with new_text."""
    lines = code.splitlines(keepends=True)
    return "".join(lines[: start - 1]) + new_text + "".join(lines[end:])


def _parses(code: str) -> bool:
    try:
        ast.parse(code)
        return True
    except (SyntaxError, ValueError):
        return False


def _seg(code: str, node: ast.AST) -> Optional[str]:
    return ast.get_source_segment(code, node)


def _statement_lists(tree: ast.AST):
    """Yields every statement list in the tree."""
    for n in ast.walk(tree):
        for fld in ("body", "orelse", "finalbody"):
            sub = getattr(n, fld, None)
            if isinstance(sub, list) and sub and isinstance(sub[0], ast.stmt):
                yield n, sub
        for h in getattr(n, "handlers", []) or []:
            yield h, h.body


def _pick(cands: list, seed: int):
    if not cands:
        return None
    return random.Random(seed).choice(cands)


# --------------------------------------------------------------------------- #
# ADD:AnnAssign
# --------------------------------------------------------------------------- #
def _annotation_candidates(tree: ast.Module) -> List[Tuple[ast.Assign, str]]:
    cands = []
    scopes = [tree] + [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    for scope in scopes:
        binds = scope_bindings(scope)
        for name, nodes in binds.items():
            assigns = []
            ok = True
            for b in nodes:
                if isinstance(b, ast.arg) or isinstance(b, (ast.Global, ast.Nonlocal)):
                    ok = False
                    break
                if not isinstance(b, ast.Name):
                    ok = False
                    break
                parent = getattr(b, "_parent", None)
                if not (isinstance(parent, ast.Assign) and len(parent.targets) == 1 and parent.targets[0] is b):
                    ok = False
                    break
                assigns.append(parent)
            if not ok or not assigns:
                continue
            types = {infer_type(a.value) for a in assigns}
            if len(types) != 1 or None in types:
                continue
            first = min(assigns, key=lambda a: (a.lineno, a.col_offset))
            cands.append((first, types.pop()))
    return cands


def _link_parents(tree: ast.AST) -> None:
    for n in ast.walk(tree):
        for c in ast.iter_child_nodes(n):
            c._parent = n


def apply_type_annotations(code_str: str, seed: int = 42) -> Tuple[str, str]:
    """ADD:AnnAssign — annotates one simple assignment with its inferred builtin type.
    Only names whose every binding in the scope is a plain assignment of the same inferred
    type are eligible. Class bodies are skipped (annotations there create dataclass fields)."""
    name = "ADD:AnnAssign"
    try:
        tree = ast.parse(code_str)
    except (SyntaxError, ValueError):
        return code_str, name
    _link_parents(tree)
    lines = code_str.splitlines(keepends=True)
    dead = set()
    for sp in find_redundancy(tree):
        dead.update(id(n) for n in ast.walk(sp.node))
    cands = [(a, t) for a, t in _annotation_candidates(tree)
             if a.targets[0].end_lineno == a.lineno and id(a) not in dead]
    pick = _pick(sorted(cands, key=lambda c: (c[0].lineno, c[0].col_offset)), seed)
    if pick is None:
        return code_str, name
    assign, typ = pick
    tgt = assign.targets[0]
    line = lines[tgt.lineno - 1]
    c = _col(line, tgt.end_col_offset)
    lines[tgt.lineno - 1] = line[:c] + f": {typ}" + line[c:]
    out = "".join(lines)
    return (out if _parses(out) else code_str), name


# --------------------------------------------------------------------------- #
# MUTATE:list_comprehension
# --------------------------------------------------------------------------- #
def list_comprehension(code_str: str, seed: int = 42) -> Tuple[str, str]:
    """`acc = []` immediately followed by `for x in it: acc.append(e)` (optionally guarded by a
    single `if`) becomes `acc = [e for x in it (if c)]`. Skipped when the loop variable is used
    after the loop, when `acc` is referenced inside the loop, or when comments would be lost."""
    name = "MUTATE:list_comprehension"
    try:
        tree = ast.parse(code_str)
    except (SyntaxError, ValueError):
        return code_str, name
    lines = code_str.splitlines(keepends=True)
    cands = []
    scopes = [tree] + [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    scope_of = {}
    for sc in scopes:
        for n in iter_scope(sc):
            scope_of[id(n)] = sc

    for _, stmts in _statement_lists(tree):
        for i in range(len(stmts) - 1):
            init, loop = stmts[i], stmts[i + 1]
            if isinstance(init, ast.Assign) and len(init.targets) == 1 and isinstance(init.targets[0], ast.Name):
                acc, ann = init.targets[0].id, None
            elif isinstance(init, ast.AnnAssign) and isinstance(init.target, ast.Name) and init.value is not None:
                acc, ann = init.target.id, init.annotation
            else:
                continue
            if not (isinstance(init.value, ast.List) and not init.value.elts):
                continue
            if not isinstance(loop, ast.For) or loop.orelse:
                continue
            body, cond = loop.body, None
            if len(body) == 1 and isinstance(body[0], ast.If) and not body[0].orelse and len(body[0].body) == 1:
                cond, body = body[0].test, body[0].body
            if len(body) != 1 or not isinstance(body[0], ast.Expr):
                continue
            call = body[0].value
            if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                    and call.func.attr == "append" and isinstance(call.func.value, ast.Name)
                    and call.func.value.id == acc and len(call.args) == 1 and not call.keywords):
                continue
            elt = call.args[0]
            # accumulator must not be read inside the loop except as the append receiver
            uses = [n for n in ast.walk(loop) if isinstance(n, ast.Name) and n.id == acc]
            if len(uses) != 1 or any(isinstance(n, ast.Name) and n.id == acc for n in ast.walk(loop.iter)):
                continue
            if any(isinstance(n, (ast.NamedExpr, ast.Yield, ast.YieldFrom, ast.Await)) for n in ast.walk(loop)):
                continue
            # loop variables must not be used after the loop in the same scope
            loop_vars = {n.id for n in ast.walk(loop.target) if isinstance(n, ast.Name)}
            sc = scope_of.get(id(loop), tree)
            used_after = any(isinstance(n, ast.Name) and n.id in loop_vars and n.lineno > loop.end_lineno
                             for n in iter_scope(sc))
            if used_after:
                continue
            if not (_starts_line(lines, init) and _ends_line(lines, loop)):
                continue
            if init.end_lineno != init.lineno or _has_comment(lines, init.lineno, loop.end_lineno):
                continue
            cands.append((init, loop, acc, ann, elt, cond))

    pick = _pick(cands, seed)
    if pick is None:
        return code_str, name
    init, loop, acc, ann, elt, cond = pick
    tgt, it, e = _seg(code_str, loop.target), _seg(code_str, loop.iter), _seg(code_str, elt)
    if None in (tgt, it, e):
        return code_str, name
    if isinstance(loop.iter, (ast.Tuple, ast.IfExp, ast.Lambda, ast.NamedExpr)) and not it.startswith("("):
        it = f"({it})"
    if isinstance(elt, (ast.Lambda, ast.NamedExpr)) and not e.startswith("("):
        e = f"({e})"
    comp = f"[{e} for {tgt} in {it}"
    if cond is not None:
        c = _seg(code_str, cond)
        if isinstance(cond, (ast.IfExp, ast.Lambda, ast.NamedExpr)):
            c = f"({c})"
        comp += f" if {c}"
    comp += "]"
    head = acc + (f": {_seg(code_str, ann)}" if ann is not None else "")
    new = f"{_indent(lines[init.lineno - 1])}{head} = {comp}\n"
    out = _replace_lines(code_str, init.lineno, loop.end_lineno, new)
    return (out if _parses(out) else code_str), name


# --------------------------------------------------------------------------- #
# NON_LOCAL:conditional_flattening
# --------------------------------------------------------------------------- #
def _wrap_test(code: str, test: ast.AST) -> str:
    s = _seg(code, test)
    low_precedence = (isinstance(test, ast.BoolOp) and isinstance(test.op, ast.Or)) or \
        isinstance(test, (ast.IfExp, ast.Lambda, ast.NamedExpr))
    return f"({s})" if low_precedence and not (s.startswith("(") and s.endswith(")")) else s


def conditional_flattening(code_str: str, seed: int = 42) -> Tuple[str, str]:
    """`if a:` whose whole body is `if b:` (no else on either) becomes `if a and b:`.
    Short-circuit evaluation order is preserved."""
    name = "NON_LOCAL:conditional_flattening"
    try:
        tree = ast.parse(code_str)
    except (SyntaxError, ValueError):
        return code_str, name
    lines = code_str.splitlines(keepends=True)
    cands = []
    for outer in ast.walk(tree):
        if not (isinstance(outer, ast.If) and not outer.orelse and len(outer.body) == 1):
            continue
        inner = outer.body[0]
        if not (isinstance(inner, ast.If) and not inner.orelse):
            continue
        if outer.test.end_lineno != outer.lineno or inner.test.end_lineno != inner.lineno:
            continue
        if inner.lineno <= outer.lineno or inner.body[0].lineno <= inner.lineno:
            continue
        if any(lines[k].strip() for k in range(outer.lineno, inner.lineno - 1)):
            continue  # comments or blank-adjacent content between the headers
        if not (_starts_line(lines, outer) and _starts_line(lines, inner)) or _has_multiline_string(inner):
            continue
        o_ind, i_ind = _indent(lines[outer.lineno - 1]), _indent(lines[inner.lineno - 1])
        if not i_ind.startswith(o_ind) or len(i_ind) <= len(o_ind):
            continue
        body_lines = lines[inner.body[0].lineno - 1: inner.end_lineno]
        delta = len(i_ind) - len(o_ind)
        if any(l.strip() and not l.startswith(" " * delta) for l in body_lines):
            continue
        cands.append((outer, inner, o_ind, delta, body_lines))
    pick = _pick(cands, seed)
    if pick is None:
        return code_str, name
    outer, inner, o_ind, delta, body_lines = pick
    inner_header = lines[inner.lineno - 1]
    tail = inner_header[_col(inner_header, inner.test.end_col_offset):]
    colon = tail.index(":")
    header = f"{o_ind}if {_wrap_test(code_str, outer.test)} and {_wrap_test(code_str, inner.test)}{tail[colon:]}"
    if not header.endswith("\n"):
        header += "\n"
    body = "".join(l[delta:] if l.strip() else l for l in body_lines)
    out = _replace_lines(code_str, outer.lineno, inner.end_lineno, header + body)
    return (out if _parses(out) else code_str), name


# --------------------------------------------------------------------------- #
# NON_LOCAL:function_split_refactor — golden-section extract-method
# --------------------------------------------------------------------------- #
_HELPER_SUFFIX = "_part"
_FORBIDDEN_IN_BLOCK = (ast.Return, ast.Yield, ast.YieldFrom, ast.Await, ast.Global, ast.Nonlocal,
                       ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda,
                       ast.AsyncFor, ast.AsyncWith, ast.Delete)


def _escaping_jumps(stmts: List[ast.stmt]) -> bool:
    """True if a break/continue in stmts targets a loop outside stmts."""
    def walk(n, in_loop):
        if isinstance(n, (ast.Break, ast.Continue)) and not in_loop:
            return True
        for c in ast.iter_child_nodes(n):
            if walk(c, in_loop or isinstance(n, (ast.For, ast.While))):
                return True
        return False
    return any(walk(s, False) for s in stmts)


def _stores(stmts: List[ast.stmt]) -> Set[str]:
    out = set()
    for s in stmts:
        for n in iter_scope(ast.Module(body=[s], type_ignores=[])):
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
                out.add(n.id)
            elif isinstance(n, (ast.Import, ast.ImportFrom)):
                out.update((a.asname or a.name).split(".")[0] for a in n.names)
            elif isinstance(n, ast.ExceptHandler) and n.name:
                out.add(n.name)
        for n in ast.walk(s):  # walrus binds the enclosing function scope even inside comprehensions
            if isinstance(n, ast.NamedExpr):
                out.add(n.target.id)
    return out


def _loads(stmts: List[ast.stmt]) -> Set[str]:
    out = set()
    for s in stmts:
        for n in ast.walk(s):
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
                out.add(n.id)
            elif isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Name):
                out.add(n.target.id)
    return out


def _uses_name_mangling(stmts: List[ast.stmt]) -> bool:
    for s in stmts:
        for n in ast.walk(s):
            ident = n.attr if isinstance(n, ast.Attribute) else (n.id if isinstance(n, ast.Name) else "")
            if ident.startswith("__") and not ident.endswith("__"):
                return True
    return False


def _closures_reading(stmts: List[ast.stmt], names: Set[str]) -> bool:
    for s in stmts:
        for n in ast.walk(s):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
                if _loads([n] if isinstance(n, ast.stmt) else [ast.Expr(value=n)]) & names:
                    return True
    return False


def function_split_refactor(code_str: str, seed: int = 42) -> Tuple[str, str]:
    """NON_LOCAL:function_split_refactor — extracts a contiguous block of a function body into a
    module-level helper. Block length is chosen nearest the golden section of the body
    (major segment = round(m / φ)). Values the block needs become parameters; values it
    produces that are read later are returned. Blocks containing return/yield/await,
    escaping break/continue, closures, `super()`, `locals()`, name mangling or multi-line
    strings are never extracted. Helpers produced by this operator are not split again."""
    name = "NON_LOCAL:function_split_refactor"
    try:
        tree = ast.parse(code_str)
    except (SyntaxError, ValueError):
        return code_str, name
    lines = code_str.splitlines(keepends=True)
    taken = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | \
            {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}

    targets = []  # (fn, top_level_stmt, is_method)
    for top in tree.body:
        if isinstance(top, (ast.FunctionDef, ast.AsyncFunctionDef)):
            targets.append((top, top, False))
        elif isinstance(top, ast.ClassDef):
            targets.extend((m, top, True) for m in top.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)))
    def _already_split(fn) -> bool:
        prefix = f"_{fn.name.strip('_')}{_HELPER_SUFFIX}"
        return any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id.startswith(prefix)
                   for n in ast.walk(fn))

    # one golden division per function; helpers produced here are not divided again
    targets = [t for t in targets
               if not t[0].name.rstrip("0123456789").endswith(_HELPER_SUFFIX) and not _already_split(t[0])]
    random.Random(seed).shuffle(targets)
    targets.sort(key=lambda t: -len(t[0].body))

    for fn, top, is_method in targets:
        body = fn.body[1:] if fn.body and is_docstring(fn.body[0]) else list(fn.body)
        m = len(body)
        if m < 4 or body[0].lineno == fn.lineno:
            continue
        params = [a.arg for a in fn.args.posonlyargs + fn.args.args + fn.args.kwonlyargs]
        if fn.args.vararg:
            params.append(fn.args.vararg.arg)
        if fn.args.kwarg:
            params.append(fn.args.kwarg.arg)
        golden = max(2, round(m / PHI))
        lengths = sorted(range(2, m), key=lambda L: (abs(L - golden), -L))
        for L in lengths:
            for a in range(0, m - L + 1):
                block, before, after = body[a:a + L], body[:a], body[a + L:]
                if any(isinstance(n, _FORBIDDEN_IN_BLOCK) for s in block for n in ast.walk(s)):
                    continue
                if _escaping_jumps(block) or _uses_name_mangling(block) and is_method:
                    continue
                loads = _loads(block)
                if loads & {"super", "locals", "vars", "eval", "exec", "__class__"}:
                    continue
                if any(_has_multiline_string(s) for s in block):
                    continue
                stores = _stores(block)
                if _closures_reading(before, stores):
                    continue
                if not (_starts_line(lines, block[0]) and _ends_line(lines, block[-1])):
                    continue
                if before and before[-1].end_lineno >= block[0].lineno:
                    continue
                if after and after[0].lineno <= block[-1].end_lineno:
                    continue
                defined_before = set(params) | _stores(before)
                returns = sorted(stores & _loads(after))
                args = [p for p in params if p in loads or p in returns]
                args += sorted(((loads | set(returns)) & defined_before) - set(args))
                ind = _indent(lines[block[0].lineno - 1])
                start, end = block[0].lineno, block[-1].end_lineno

                helper = f"_{fn.name.strip('_')}{_HELPER_SUFFIX}"
                k = 2
                while helper in taken:
                    helper = f"_{fn.name.strip('_')}{_HELPER_SUFFIX}{k}"
                    k += 1

                hbody = []
                for l in lines[start - 1:end]:
                    if not l.strip():
                        hbody.append("\n")
                    elif l.startswith(ind):
                        hbody.append("    " + l[len(ind):])
                    else:
                        hbody.append(l)
                if hbody and not hbody[-1].endswith("\n"):
                    hbody[-1] += "\n"
                if returns:
                    hbody.append(f"    return {', '.join(returns)}\n")
                helper_src = f"def {helper}({', '.join(args)}):\n" + "".join(hbody)

                lhs = f"{', '.join(returns)} = " if returns else ""
                call = f"{ind}{lhs}{helper}({', '.join(args)})\n"
                out = _replace_lines(code_str, start, end, call)

                insert_at = (top.decorator_list[0].lineno if top.decorator_list else top.lineno) - 1
                out_lines = out.splitlines(keepends=True)
                while insert_at > 0 and out_lines[insert_at - 1].lstrip().startswith("#"):
                    insert_at -= 1
                lead = "\n\n" if insert_at > 0 and out_lines[insert_at - 1].strip() else ""
                out = "".join(out_lines[:insert_at]) + lead + helper_src + "\n\n" + "".join(out_lines[insert_at:])
                if _parses(out):
                    return out, name
    return code_str, name


# --------------------------------------------------------------------------- #
# HEAL:dead_code_elimination (SALAMANDER)
# --------------------------------------------------------------------------- #
def dead_code_elimination(code_str: str, seed: int = 42) -> Tuple[str, str]:
    """Removes constant-false branches, unreachable statements, shadowed definitions and
    repeated identical assignments (with any comment block attached directly above them).
    Unreferenced private helpers are left in place: another module may import them."""
    name = "HEAL:dead_code_elimination"
    try:
        tree = ast.parse(code_str)
    except (SyntaxError, ValueError):
        return code_str, name
    lines = code_str.splitlines(keepends=True)
    spans = [sp for sp in find_redundancy(tree) if sp.removable]
    if not spans:
        return code_str, name

    parent_body = {}
    for owner, stmts in _statement_lists(tree):
        for s in stmts:
            parent_body[id(s)] = (owner, stmts)

    remove: Set[int] = set()   # 0-based line indexes
    removed_stmt_ids = {id(sp.node) for sp in spans}
    for sp in spans:
        node = sp.node
        if not (_starts_line(lines, node) and _ends_line(lines, node)):
            continue
        start = (node.decorator_list[0].lineno if getattr(node, "decorator_list", None) else node.lineno) - 1
        k = start
        while k > 0 and lines[k - 1].lstrip().startswith("#"):
            k -= 1
        remove.update(range(k, node.end_lineno))
        # keep one blank-line separator tidy: drop a blank line directly after a removed def
        if node.end_lineno < len(lines) and not lines[node.end_lineno].strip() and \
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            remove.add(node.end_lineno)

    # never leave a body empty
    for owner, stmts in _statement_lists(tree):
        if stmts and all(id(s) in removed_stmt_ids for s in stmts) and not isinstance(owner, ast.Module):
            first = stmts[0]
            keep = first.lineno - 1
            remove.discard(keep)
            lines[keep] = _indent(lines[keep]) + "pass\n"
            for k in range(keep + 1, stmts[-1].end_lineno):
                remove.add(k)

    out = "".join(l for i, l in enumerate(lines) if i not in remove)
    return (out if _parses(out) else code_str), name


# --------------------------------------------------------------------------- #
# MUTATE:inject_docstring (φ-neutral: docstrings are excluded from structure)
# --------------------------------------------------------------------------- #
def inject_docstring(code_str: str, seed: int = 42) -> Tuple[str, str]:
    name = "MUTATE:inject_docstring"
    try:
        tree = ast.parse(code_str)
    except (SyntaxError, ValueError):
        return code_str, name
    if tree.body and is_docstring(tree.body[0]):
        return code_str, name
    # Preserve a Unix shebang and a PEP 263 encoding cookie.  A module docstring
    # must still precede any __future__ imports, so it is inserted immediately
    # after this lexical preamble rather than blindly at byte zero.
    lines = code_str.splitlines(keepends=True)
    insert_at = 0
    if lines and lines[0].startswith("#!"):
        insert_at = 1
    cookie = re.compile(r"coding[:=]\s*([-\w.]+)")
    for i in range(min(2, len(lines))):
        if cookie.search(lines[i]):
            insert_at = max(insert_at, i + 1)
    lines.insert(insert_at, '"""Module documentation pending."""\n')
    out = "".join(lines)
    return (out if _parses(out) else code_str), name


# --------------------------------------------------------------------------- #
# Behaviour-changing mutations (require a host test runner)
# --------------------------------------------------------------------------- #
_SWAP = {ast.Add: ("+", "-"), ast.Sub: ("-", "+"), ast.Mult: ("*", "/"), ast.Div: ("/", "*")}


def swap_binary_operator(code_str: str, seed: int = 42) -> Tuple[str, str]:
    """MUTATE:swap_binary_operator — changes behaviour; only meaningful under host tests."""
    name = "MUTATE:swap_binary_operator"
    try:
        tree = ast.parse(code_str)
    except (SyntaxError, ValueError):
        return code_str, name
    lines = code_str.splitlines(keepends=True)
    cands = []
    for n in ast.walk(tree):
        if isinstance(n, ast.BinOp) and type(n.op) in _SWAP and n.left.end_lineno == n.right.lineno:
            line = lines[n.left.end_lineno - 1]
            a, b = _col(line, n.left.end_col_offset), _col(line, n.right.col_offset)
            old, new = _SWAP[type(n.op)]
            if line[a:b].strip() == old:
                cands.append((n.left.end_lineno, a, b, old, new))
    pick = _pick(cands, seed)
    if pick is None:
        return code_str, name
    ln, a, b, old, new = pick
    line = lines[ln - 1]
    lines[ln - 1] = line[:a] + line[a:b].replace(old, new, 1) + line[b:]
    out = "".join(lines)
    return (out if _parses(out) else code_str), name


def rename_variable(code_str: str, seed: int = 42) -> Tuple[str, str]:
    """MUTATE:rename_variable — renames one local consistently within one function."""
    name = "MUTATE:rename_variable"
    try:
        tree = ast.parse(code_str)
    except (SyntaxError, ValueError):
        return code_str, name
    taken = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    cands = []
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        binds = scope_bindings(fn)
        nested = [n for n in ast.walk(fn) if n is not fn and isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef))]
        nested_names = {x.id for nd in nested for x in ast.walk(nd) if isinstance(x, ast.Name)}
        for var, nodes in binds.items():
            if all(isinstance(b, ast.Name) for b in nodes) and var not in nested_names:
                occ = [n for n in iter_scope(fn) if isinstance(n, ast.Name) and n.id == var]
                if occ and f"{var}_v" not in taken:
                    cands.append(occ)
    pick = _pick(cands, seed)
    if pick is None:
        return code_str, name
    lines = code_str.splitlines(keepends=True)
    for n in sorted(pick, key=lambda n: (n.lineno, n.col_offset), reverse=True):
        line = lines[n.lineno - 1]
        a, b = _col(line, n.col_offset), _col(line, n.end_col_offset)
        lines[n.lineno - 1] = line[:a] + n.id + "_v" + line[b:]
    out = "".join(lines)
    return (out if _parses(out) else code_str), name


def class_decomposition(code_str: str, seed: int = 42) -> Tuple[str, str]:
    """NON_LOCAL:class_decomposition — no behaviour-preserving class split is defined yet; inert."""
    return code_str, "NON_LOCAL:class_decomposition"


# --------------------------------------------------------------------------- #
# Registry & composition
# --------------------------------------------------------------------------- #
OPERATOR_REGISTRY: Dict[str, Operator] = {
    "ADD:AnnAssign": apply_type_annotations,
    "NON_LOCAL:function_split_refactor": function_split_refactor,
    "NON_LOCAL:conditional_flattening": conditional_flattening,
    "NON_LOCAL:class_decomposition": class_decomposition,
    "MUTATE:list_comprehension": list_comprehension,
    "MUTATE:inject_docstring": inject_docstring,
    "HEAL:dead_code_elimination": dead_code_elimination,
    "MUTATE:swap_binary_operator": swap_binary_operator,
    "MUTATE:rename_variable": rename_variable,
}
BEHAVIOUR_CHANGING = {"MUTATE:swap_binary_operator", "MUTATE:rename_variable"}


def compose(recipe: List[str], name: Optional[str] = None) -> Operator:
    """Builds a macro-operator that applies registry operators in sequence."""
    unknown = [r for r in recipe if r not in OPERATOR_REGISTRY]
    if unknown:
        raise ValueError(f"unknown operators in recipe: {unknown}")
    label = name or "AUTO:Composite[" + "+".join(recipe) + "]"

    def _composite(code_str: str, seed: int = 42) -> Tuple[str, str]:
        out = code_str
        for i, op in enumerate(recipe):
            out, _ = OPERATOR_REGISTRY[op](out, seed + i)
        return out, label

    _composite.recipe = list(recipe)
    _composite.__name__ = label
    return _composite


class ASTPrimitives:
    apply_type_annotations = staticmethod(apply_type_annotations)
    function_split_refactor = staticmethod(function_split_refactor)
    conditional_flattening = staticmethod(conditional_flattening)
    class_decomposition = staticmethod(class_decomposition)
    list_comprehension = staticmethod(list_comprehension)
    inject_docstring = staticmethod(inject_docstring)
    dead_code_elimination = staticmethod(dead_code_elimination)
    swap_binary_operator = staticmethod(swap_binary_operator)
    rename_variable = staticmethod(rename_variable)

    @staticmethod
    def dead_code_branch(code_str: str, seed: int = 42) -> Tuple[str, str]:
        """Retired in v12.1 (added unreachable code). Kept for import compatibility; inert."""
        return code_str, "MUTATE:dead_code_branch"

    @classmethod
    def get_all_operators(cls, include_behaviour_changing: bool = False) -> List[Tuple[str, Operator]]:
        ops = ["ADD:AnnAssign", "NON_LOCAL:function_split_refactor", "MUTATE:list_comprehension",
               "HEAL:dead_code_elimination", "MUTATE:inject_docstring"]
        if include_behaviour_changing:
            ops += sorted(BEHAVIOUR_CHANGING)
        return [(o, OPERATOR_REGISTRY[o]) for o in ops]
