"""Shared structural scanners for the training/ contract verifiers.

Two substrates are verified:

- TypeScript sources (``src/lib/*.ts``) via :class:`TsSource`, a lexical
  structural scanner — comments and string literals are stripped in place
  (line numbers preserved), function/method/if-block boundaries are found by
  brace matching, and every query returns real line numbers. This is
  structural inspection of the code's shape, not text grep: matches inside
  strings and comments cannot produce false positives.

- Python sources via the real ``ast`` module (:func:`parse_py`).

Statuses:
    ``pass``            — invariant verified structurally.
    ``fail``            — code exists and violates the contract.
    ``not_implemented`` — the contracted functionality does not exist in the
                          codebase; nothing to verify, nothing passing.
    ``not_checkable``   — the property cannot be decided by static analysis;
                          the limit is documented honestly.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]

STATUS_PASS = "pass"
STATUS_FAIL = "fail"
STATUS_NOT_IMPLEMENTED = "not_implemented"
STATUS_NOT_CHECKABLE = "not_checkable"

ALL_STATUSES = (
    STATUS_PASS,
    STATUS_FAIL,
    STATUS_NOT_IMPLEMENTED,
    STATUS_NOT_CHECKABLE,
)


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


@dataclass
class Violation:
    file: str
    line: int
    detail: str
    fix: str = ""

    def to_dict(self) -> dict:
        return {"file": self.file, "line": self.line, "detail": self.detail, "fix": self.fix}


@dataclass
class RuleResult:
    agent: str
    rule: str
    status: str
    file: str = ""
    detail: str = ""
    fix: str = ""
    violations: list = field(default_factory=list)  # list[Violation]

    def to_dict(self) -> dict:
        return {
            "agent": self.agent,
            "file": self.file,
            "rule": self.rule,
            "status": self.status,
            "detail": self.detail,
            "fix": self.fix,
            "violations": [v.to_dict() for v in self.violations],
        }


def pass_(agent: str, rule: str, file: str = "", detail: str = "") -> RuleResult:
    return RuleResult(agent=agent, rule=rule, status=STATUS_PASS, file=file, detail=detail)


def fail(
    agent: str,
    rule: str,
    violations: list,
    file: str = "",
    detail: str = "",
    fix: str = "",
) -> RuleResult:
    return RuleResult(
        agent=agent,
        rule=rule,
        status=STATUS_FAIL,
        file=file,
        detail=detail,
        fix=fix,
        violations=list(violations),
    )


def not_implemented(agent: str, rule: str, detail: str, fix: str = "") -> RuleResult:
    return RuleResult(agent=agent, rule=rule, status=STATUS_NOT_IMPLEMENTED, detail=detail, fix=fix)


def not_checkable(agent: str, rule: str, detail: str) -> RuleResult:
    return RuleResult(agent=agent, rule=rule, status=STATUS_NOT_CHECKABLE, detail=detail)


# ---------------------------------------------------------------------------
# TypeScript structural scanner
# ---------------------------------------------------------------------------


def _strip_comments_and_strings(text: str) -> tuple[str, list]:
    """Blank out comments and string/template literal contents in place.

    Returns (stripped_text, literals) where literals is a list of
    (offset, content) for every string/template literal — comments never
    enter it, so literal lookups cannot false-positive on comment text.
    Stripped characters become spaces except newlines, which are preserved
    so line numbers stay exact.
    """
    out = list(text)
    literals: list[tuple[int, str]] = []
    i, n = 0, len(text)
    NORMAL, LINE_C, BLOCK_C, SQ, DQ, TPL = range(6)
    state = NORMAL
    lit_start = -1
    while i < n:
        c = text[i]
        if state == NORMAL:
            if c == "/" and i + 1 < n and text[i + 1] == "/":
                out[i] = out[i + 1] = " "
                i += 2
                state = LINE_C
                continue
            if c == "/" and i + 1 < n and text[i + 1] == "*":
                out[i] = out[i + 1] = " "
                i += 2
                state = BLOCK_C
                continue
            if c == "'":
                lit_start = i
                out[i] = " "
                i += 1
                state = SQ
                continue
            if c == '"':
                lit_start = i
                out[i] = " "
                i += 1
                state = DQ
                continue
            if c == "`":
                lit_start = i
                out[i] = " "
                i += 1
                state = TPL
                continue
            i += 1
        elif state == LINE_C:
            if c == "\n":
                state = NORMAL
            else:
                out[i] = " "
            i += 1
        elif state == BLOCK_C:
            if c == "*" and i + 1 < n and text[i + 1] == "/":
                out[i] = out[i + 1] = " "
                i += 2
                state = NORMAL
                continue
            if c != "\n":
                out[i] = " "
            i += 1
        elif state in (SQ, DQ, TPL):
            quote = {SQ: "'", DQ: '"', TPL: "`"}[state]
            if c == "\\":
                out[i] = " "
                if i + 1 < n and text[i + 1] != "\n":
                    out[i + 1] = " "
                i += 2
                continue
            if c == quote:
                out[i] = " "
                literals.append((lit_start, text[lit_start + 1 : i]))
                lit_start = -1
                i += 1
                state = NORMAL
                continue
            if c != "\n":
                out[i] = " "
            i += 1
    return "".join(out), literals


@dataclass
class TsRegion:
    """A brace-delimited region of a TypeScript file."""

    name: str
    start_line: int  # 1-based line of the declaration/pattern
    body_start: int  # offset of the opening '{'
    body_end: int  # offset of the matching '}'


# Parameter/argument list matcher: permits parens nested two deep (call
# defaults like `(ms) => new Promise((r) => setTimeout(r, ms))`) and `{...}`
# object type literals (which may contain `;`) two levels deep.
_PAREN1 = r"\([^()]*\)"
_PAREN2 = r"\((?:[^()]|" + _PAREN1 + r")*\)"
_PARAMS = r"\((?:[^(){}]|" + _PAREN2 + r"|\{(?:[^{}]|\{[^{}]*\})*\})*\)"

_METHOD_RE = re.compile(
    r"(?:^|[\s;}])(?:public\s+|private\s+|protected\s+|static\s+|async\s+|export\s+|readonly\s+|get\s+|set\s+)*"
    r"([A-Za-z_$][\w$]*)\s*" + _PARAMS + r"\s*(?::\s*[^\{;]+)?\{",
    re.MULTILINE,
)
_ARROW_RE = re.compile(
    r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*(?::[^=]+)?=\s*(?:async\s*)?"
    + _PARAMS
    + r"\s*(?::\s*[^=]+)?=>",
)
_FUNCTION_RE = re.compile(r"\bfunction\s+([A-Za-z_$][\w$]*)\s*" + _PARAMS)

# Control constructs that match the method regex shape but are not functions.
_CONTROL_KW = {
    "if",
    "for",
    "while",
    "switch",
    "catch",
    "return",
    "do",
    "else",
    "typeof",
    "new",
    "await",
    "yield",
    "delete",
    "void",
    "case",
    "throw",
    "constructor",
}


class TsSource:
    """Structural view of one TypeScript file."""

    def __init__(self, text: str, relpath: str):
        self.raw = text
        self.relpath = relpath
        self.code, self.literals = _strip_comments_and_strings(text)
        self._line_starts = [0]
        for m in re.finditer("\n", self.code):
            self._line_starts.append(m.end())
        self._raw_lines = text.splitlines()

    # -- line/column helpers -------------------------------------------------

    def line_of(self, offset: int) -> int:
        """1-based line number containing byte offset."""
        import bisect

        return bisect.bisect_right(self._line_starts, offset)

    def find(self, pattern: str, flags: int = 0) -> Iterator[tuple[int, str, re.Match]]:
        """Yield (line_number, line_text, match) for regex hits in stripped code."""
        for m in re.finditer(pattern, self.code, flags):
            line_no = self.line_of(m.start())
            line_text = self._raw_lines[line_no - 1] if line_no - 1 < len(self._raw_lines) else ""
            yield line_no, line_text, m

    def find_literal(self, needle: str) -> Iterator[tuple[int, str]]:
        """Yield (line_number, content) for string literals containing needle."""
        for off, content in self.literals:
            if needle in content:
                yield self.line_of(off), content

    # -- brace matching ------------------------------------------------------

    def brace_match(self, open_offset: int) -> int:
        """Offset of the '}' matching the '{' at open_offset (in stripped code)."""
        assert self.code[open_offset] == "{"
        depth = 0
        for i in range(open_offset, len(self.code)):
            if self.code[i] == "{":
                depth += 1
            elif self.code[i] == "}":
                depth -= 1
                if depth == 0:
                    return i
        raise ValueError(f"unbalanced braces in {self.relpath} at offset {open_offset}")

    def _region_from_brace(self, name: str, brace_off: int) -> TsRegion:
        end = self.brace_match(brace_off)
        # If the '{' we anchored on was a return-type object literal —
        # `f(x): { a: T } { body }` or `f(x): Promise<{ a: T }> { body }` —
        # the real body is the next '{' after the type closes.
        nxt = end + 1
        while nxt < len(self.code) and self.code[nxt] in " \t\r\n>":
            nxt += 1
        if nxt < len(self.code) and self.code[nxt] == "{":
            return self._region_from_brace(name, nxt)
        return TsRegion(
            name=name,
            start_line=self.line_of(brace_off),
            body_start=brace_off,
            body_end=end,
        )

    # -- function/method extraction ------------------------------------------

    def functions(self) -> list[TsRegion]:
        """All method/function bodies (nested included), in file order."""
        regions: list[TsRegion] = []
        for m in _METHOD_RE.finditer(self.code):
            if m.group(1) in _CONTROL_KW:
                continue
            brace_off = m.end() - 1
            regions.append(self._region_from_brace(m.group(1), brace_off))
        for m in _ARROW_RE.finditer(self.code):
            if m.group(1) in _CONTROL_KW:
                continue
            brace_off = self.code.find("{", m.end())
            if brace_off != -1:
                regions.append(self._region_from_brace(m.group(1), brace_off))
        for m in _FUNCTION_RE.finditer(self.code):
            if m.group(1) in _CONTROL_KW:
                continue
            brace_off = self.code.find("{", m.end())
            if brace_off != -1:
                regions.append(self._region_from_brace(m.group(1), brace_off))
        regions.sort(key=lambda r: r.body_start)
        return regions

    def function_named(self, name: str) -> Optional[TsRegion]:
        for r in self.functions():
            if r.name == name:
                return r
        return None

    def enclosing_function(self, offset: int) -> Optional[TsRegion]:
        """Innermost function region containing offset."""
        best = None
        for r in self.functions():
            if r.body_start < offset < r.body_end:
                if best is None or r.body_start > best.body_start:
                    best = r
        return best

    def if_block(self, cond_pattern: str) -> Optional[TsRegion]:
        """First `if (<cond matching pattern>) { ... }` region."""
        for m in re.finditer(r"\bif\s*\(", self.code):
            # find the close paren of the condition
            depth = 0
            j = m.end() - 1
            cond_start = j + 1
            while j < len(self.code):
                if self.code[j] == "(":
                    depth += 1
                elif self.code[j] == ")":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            cond = self.code[cond_start:j]
            if re.search(cond_pattern, cond):
                brace = self.code.find("{", j)
                if brace != -1:
                    return self._region_from_brace(f"if({cond.strip()[:40]})", brace)
        return None

    def region_text(self, region: TsRegion) -> str:
        return self.code[region.body_start : region.body_end + 1]

    def region_lines(self, region: TsRegion) -> tuple[int, int]:
        return self.line_of(region.body_start), self.line_of(region.body_end)


# ---------------------------------------------------------------------------
# Repository loading helpers
# ---------------------------------------------------------------------------


def load_ts(relpath: str) -> TsSource:
    p = REPO_ROOT / relpath
    return TsSource(p.read_text(encoding="utf-8"), relpath)


def glob_ts(dir_rel: str) -> list[TsSource]:
    out = []
    for p in sorted((REPO_ROOT / dir_rel).glob("*.ts")):
        out.append(TsSource(p.read_text(encoding="utf-8"), f"{dir_rel}/{p.name}"))
    return out


def parse_py(relpath: str) -> ast.Module:
    p = REPO_ROOT / relpath
    return ast.parse(p.read_text(encoding="utf-8"), filename=relpath)


def file_exists(relpath: str) -> bool:
    return (REPO_ROOT / relpath).is_file()


def top_level_assign(tree: ast.Module, name: str) -> Optional[ast.Assign]:
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == name:
                    return node
    return None


def calls_named(tree: ast.AST, name: str) -> list[ast.Call]:
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            fname = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
            if fname == name:
                out.append(node)
    return out
