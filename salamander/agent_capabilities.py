"""Bounded executable successors to the deprecated .github/agents roles.

These are local diagnostics and draft producers, NOT autonomous authorities.
No supplied code is executed, no files are written, no action is authorized,
and absence of a static finding is not a security proof.
"""
from __future__ import annotations

import ast
import difflib
from dataclasses import dataclass
import hashlib
import json
import math
import threading
from fractions import Fraction
from pathlib import PurePosixPath
from typing import Any, Mapping

from .control_plane import EvidenceLedger

SCHEMA = "salamander.agent-capabilities.v1"
CONTRACT_REVISION = 2
ROLE_LAYERS = {
    "auditor": "TRUTH", "remediator": "CHANGE", "test_engineer": "CHANGE",
    "governance": "CONTROL", "provenance": "CONTROL", "math_verifier": "TRUTH",
    "security_verifier": "TRUTH", "quantum_checker": "TRUTH",
    "precision_sentinel": "TRUTH", "pin_verifier": "TRUTH",
}
MAX_BYTES = 131072
MAX_NODES = 10000
MAX_JSON_DEPTH = 24
MAX_JSON_ITEMS = 10000


def bounded_evidence(value: Any) -> dict[str, Any]:
    """Reject non-JSON objects, cycles and excessive work before serialization.

    Exact builtins only: custom Mapping/__iter__/JSON callbacks are not an
    execution surface. Serialized size is checked after bounded traversal.
    """
    remaining = MAX_JSON_ITEMS
    active: set[int] = set()

    def visit(item: Any, depth: int) -> None:
        nonlocal remaining
        remaining -= 1
        if depth > MAX_JSON_DEPTH or remaining < 0:
            raise ValueError("evidence structure budget exceeded")
        kind = type(item)
        if item is None or kind is bool:
            return
        if kind is str:
            if len(item) > MAX_BYTES:
                raise ValueError("evidence string budget exceeded")
            return
        if kind is int:
            if item.bit_length() > 4096:
                raise ValueError("evidence integer budget exceeded")
            return
        if kind is float:
            if not math.isfinite(item):
                raise ValueError("finite JSON numbers required")
            return
        if kind not in (dict, list):
            raise ValueError("plain JSON values required")
        if id(item) in active or len(item) > MAX_JSON_ITEMS:
            raise ValueError("cyclic or oversized evidence")
        active.add(id(item))
        try:
            if kind is dict:
                for key, child in item.items():
                    if type(key) is not str:
                        raise ValueError("JSON string keys required")
                    visit(key, depth + 1)
                    visit(child, depth + 1)
            else:
                for child in item:
                    visit(child, depth + 1)
        finally:
            active.remove(id(item))

    if type(value) is not dict:
        raise ValueError("plain JSON evidence object required")
    visit(value, 0)
    encoded = canonical(value)
    if len(encoded.encode("utf-8")) > MAX_BYTES:
        raise ValueError("evidence byte budget exceeded")
    return json.loads(encoded)


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def safe_path(path: str) -> bool:
    p = PurePosixPath(path)
    return bool(path and path.strip()) and str(p) != "." and len(path) <= 1024 and not p.is_absolute() and not any(
        part in ("..", ".git") for part in p.parts
    ) and "\\" not in path and ":" not in path and not any(ord(c) < 32 or ord(c) == 127 for c in path)


def exact_expression(text: str) -> Fraction:
    """Deliberately small exact-rational evaluator; no eval/import/call/power."""
    if type(text) is not str or len(text) > 2048:
        raise ValueError("bounded rational expression required")
    tree = ast.parse(text, mode="eval")
    if sum(1 for _ in ast.walk(tree)) > 128:
        raise ValueError("expression node budget exceeded")

    def visit(node: ast.AST) -> Fraction:
        if isinstance(node, ast.Expression):
            result = visit(node.body)
        elif isinstance(node, ast.Constant) and type(node.value) is int:
            result = Fraction(node.value)
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            result = visit(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1)
        elif isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Add): result = left + right
            elif isinstance(node.op, ast.Sub): result = left - right
            elif isinstance(node.op, ast.Mult): result = left * right
            else: result = left / right
        else:
            raise ValueError("outside exact-rational grammar")
        if max(result.numerator.bit_length(), result.denominator.bit_length()) > 4096:
            raise ValueError("exact arithmetic bit budget exceeded")
        return result
    return visit(tree)


def finding(status: str, reason: str, **details: Any) -> dict[str, Any]:
    return {"status": status, "reason": reason, **details}


def _math(data: Mapping[str, Any]) -> dict[str, Any]:
    cases = data.get("identities", [])
    if not cases:
        return finding("NOT_PROVABLE", "no exact rational identities supplied")
    if not isinstance(cases, list) or len(cases) > 32:
        raise ValueError("at most 32 identities")
    outcomes = [exact_expression(c["left"]) == exact_expression(c["right"]) for c in cases]
    return finding("PASS" if all(outcomes) else "FAIL", "exact rational identities only", outcomes=outcomes)




def _security(tree: ast.AST) -> dict[str, Any]:
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
            if name in {"eval", "exec", "system", "popen"}:
                hits.append({"line": node.lineno, "rule": "dynamic-execution"})
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(
            word in node.name.lower() for word in ("verify", "authenticate", "authorize")
        ):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
                body = body[1:]
            if len(body) == 1 and isinstance(body[0], ast.Return) and isinstance(body[0].value, ast.Constant) and body[0].value.value is True:
                hits.append({"line": node.lineno, "rule": "constant-true-verifier"})
        if isinstance(node, ast.ExceptHandler) and any(isinstance(x, ast.Pass) for x in node.body):
            hits.append({"line": node.lineno, "rule": "swallowed-exception-review"})
    return finding("FAIL" if hits else "NOT_PROVABLE", "bounded AST findings; not comprehensive security or key-lifecycle verification", findings=hits)


def _precision(tree: ast.AST, data: Mapping[str, Any]) -> dict[str, Any]:
    if data.get("declared_exact") is not True:
        return finding("NOT_PROVABLE", "no exact surface declared")
    lines = sorted({n.lineno for n in ast.walk(tree) if
                    isinstance(n, ast.Constant) and type(n.value) in (float, complex) or
                    isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in {"float", "complex"}})
    return finding("FAIL" if lines else "NOT_PROVABLE", "float/complex syntax scan only; runtime nondeterminism and numerical bounds unmeasured", lines=lines)


def _pin(tree: ast.AST, data: Mapping[str, Any]) -> dict[str, Any]:
    # The legacy hard-coded theorem_proven=False policy is NOT silently revived.
    pins = data.get("pins", {})
    if not pins:
        return finding("NOT_PROVABLE", "no current owner-selected literal pins supplied")
    if not isinstance(pins, dict) or len(pins) > 32 or any(type(v) is not bool for v in pins.values()):
        raise ValueError("at most 32 boolean literal pins")
    observed: dict[str, list[bool | None]] = {key: [] for key in pins}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and target.id in pins:
                    literal = node.value.value if isinstance(node.value, ast.Constant) and type(node.value.value) is bool else None
                    observed[target.id].append(literal)
    if any(any(v is not pins[k] for v in values) for k, values in observed.items()):
        return finding("FAIL", "literal assignment violates requested pin", observed=observed)
    return finding("PASS" if all(observed.values()) else "NOT_PROVABLE", "literal assignments only; not a whole-program proof", observed=observed)


def _audit(source: str, data: Mapping[str, Any]) -> dict[str, Any]:
    claims = data.get("claims", [])
    if not claims:
        return finding("NOT_PROVABLE", "no source-digest claims supplied")
    if not isinstance(claims, list) or len(claims) > 32:
        raise ValueError("at most 32 source-digest claims")
    holds = all(c.get("source_sha256") == sha(source) for c in claims)
    return finding("PASS" if holds else "FAIL", "claim/source digest binding only; does not prove claim semantics")






@dataclass(frozen=True)
class ExactComplex:
    """Complex rationals only; intermediate arithmetic has the same bit cap."""
    real: Fraction = Fraction(0)
    imag: Fraction = Fraction(0)

    def __post_init__(self):
        for value in (self.real, self.imag):
            if max(value.numerator.bit_length(), value.denominator.bit_length()) > 4096:
                raise ValueError("complex arithmetic bit budget exceeded")

    def __add__(self, other):
        return ExactComplex(self.real + other.real, self.imag + other.imag)

    def __mul__(self, other):
        return ExactComplex(self.real * other.real - self.imag * other.imag,
                            self.real * other.imag + self.imag * other.real)

    def conjugate(self):
        return ExactComplex(self.real, -self.imag)

    def as_json(self):
        return {"real": str(self.real), "imag": str(self.imag)}


def _complex(raw: Any) -> ExactComplex:
    if type(raw) is dict:
        if set(raw) != {"real", "imag"}:
            raise ValueError("complex entries require exactly real and imag")
        return ExactComplex(exact_expression(str(raw["real"])), exact_expression(str(raw["imag"])))
    if type(raw) not in (int, str):
        raise ValueError("exact integer/string or complex-rational object required")
    return ExactComplex(exact_expression(str(raw)))


def _quantum(data: Mapping[str, Any]) -> dict[str, Any]:
    raw = data.get("quantum")
    if not raw:
        return finding("NOT_PROVABLE", "no exact rational gate/channel/measurement supplied")
    kind, matrices = raw.get("kind"), raw.get("matrices")
    if kind not in ("unitary", "kraus", "projective_measurement") or not isinstance(matrices, list) or not 1 <= len(matrices) <= 8:
        raise ValueError("bounded unitary/Kraus/projective matrix list required")
    if kind == "unitary" and len(matrices) != 1:
        raise ValueError("unitary check requires one matrix")
    n = len(matrices[0])
    if not 1 <= n <= 8:
        raise ValueError("matrix dimension must be 1..8")
    parsed = []
    for matrix in matrices:
        if len(matrix) != n or any(len(row) != n for row in matrix):
            raise ValueError("square, equally sized matrices required")
        parsed.append([[_complex(x) for x in row] for row in matrix])
    zero, one = ExactComplex(), ExactComplex(Fraction(1))
    identity = [[one if i == j else zero for j in range(n)] for i in range(n)]

    def adjoint(matrix):
        return [[matrix[j][i].conjugate() for j in range(n)] for i in range(n)]

    def multiply(left, right):
        return [[sum((left[i][k] * right[k][j] for k in range(n)), zero)
                 for j in range(n)] for i in range(n)]

    checks = {}
    probabilities = None
    if kind == "projective_measurement":
        checks["hermitian"] = all(adjoint(p) == p for p in parsed)
        checks["idempotent"] = all(multiply(p, p) == p for p in parsed)
        checks["complete"] = all(sum((p[i][j] for p in parsed), zero) == identity[i][j]
                                  for i in range(n) for j in range(n))
        checks["orthogonal"] = all(all(value == zero for row in multiply(p, q) for value in row)
                                    for a, p in enumerate(parsed) for b, q in enumerate(parsed) if a != b)
        if "state" in raw:
            state = raw["state"]
            if not isinstance(state, list) or len(state) != n:
                raise ValueError("state dimension mismatch")
            state = [_complex(x) for x in state]
            checks["state_normalized"] = sum((x.conjugate() * x for x in state), zero) == one
            probabilities = [sum((state[i].conjugate() * p[i][j] * state[j]
                                  for i in range(n) for j in range(n)), zero) for p in parsed]
            checks["born_probabilities"] = (all(x.imag == 0 and x.real >= 0 for x in probabilities)
                                             and sum(probabilities, zero) == one)
    else:
        products = [multiply(adjoint(p), p) for p in parsed]
        checks["adjoint_completeness"] = all(sum((p[i][j] for p in products), zero) == identity[i][j]
                                              for i in range(n) for j in range(n))
        if kind == "unitary":
            checks["right_unitarity"] = multiply(parsed[0], adjoint(parsed[0])) == identity
    holds = all(checks.values())
    return finding("PASS" if holds else "FAIL", "exact complex-rational finite-matrix checks only",
                   scope={"unitary": "unitarity on both sides", "kraus": "Kraus trace preservation; CP by supplied Kraus form",
                          "projective_measurement": "orthogonal projective measurement; optional normalized-state Born probabilities"}[kind],
                   checks=checks, probabilities=[p.as_json() for p in probabilities] if probabilities is not None else None)


def _drafts(data: Mapping[str, Any], target: str, source: str) -> dict[str, Any]:
    patches = data.get("draft_files", {})
    if not patches:
        return finding("NOT_PROVABLE", "no candidate remediation supplied")
    if not isinstance(patches, dict) or len(patches) > 4:
        raise ValueError("remediation file cap is four")
    if any(not safe_path(p) or not isinstance(v, str) for p, v in patches.items()):
        raise ValueError("unsafe draft path or non-text candidate")
    if sum(len(v.encode()) for v in patches.values()) > MAX_BYTES:
        raise ValueError("remediation byte cap exceeded")
    baselines = data.get("baseline_files", {})
    if not isinstance(baselines, dict) or set(baselines) - set(patches):
        raise ValueError("baselines must correspond to draft files")
    metrics, diffs, baselines_sha256, failures = {}, {}, {}, []
    for path, candidate in patches.items():
        if not path.endswith('.py'):
            return finding("NOT_PROVABLE", "complexity/fanout metrics support Python drafts only")
        tree = ast.parse(candidate)
        if sum(1 for _ in ast.walk(tree)) > MAX_NODES:
            raise ValueError("draft AST budget exceeded")
        scopes = [("<module>", tree)] + [(f"{node.name}@{node.lineno}", node) for node in ast.walk(tree)
                                         if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        values = []
        for name, scope in scopes:
            nodes = list(ast.walk(scope))  # Conservative: nested scopes are included.
            complexity = 1 + sum(isinstance(node, (ast.If, ast.IfExp, ast.For, ast.AsyncFor, ast.While,
                                                   ast.ExceptHandler, ast.comprehension)) for node in nodes)
            complexity += sum(len(node.values) - 1 for node in nodes if isinstance(node, ast.BoolOp))
            complexity += sum(len(node.ifs) for node in nodes if isinstance(node, ast.comprehension))
            complexity += sum(len(node.cases) for node in nodes if isinstance(node, ast.Match))
            complexity += sum(node.guard is not None for node in nodes if isinstance(node, ast.match_case))
            calls = set()
            dynamic = False
            for node in nodes:
                if isinstance(node, ast.Call):
                    function = node.func
                    while isinstance(function, ast.Attribute): function = function.value
                    if not isinstance(function, ast.Name): dynamic = True
                    else: calls.add(ast.unparse(node.func))
            values.append({"scope": name, "cyclomatic_upper_bound": complexity,
                           "named_call_fanout": len(calls), "dynamic_call_target": dynamic})
            if complexity > 10 or len(calls) > 3 or dynamic:
                failures.append({"path": path, **values[-1]})
        metrics[path] = values
        baseline = baselines.get(path, source if path == target else None)
        if baseline is not None:
            if type(baseline) is not str: raise ValueError("text baseline required")
            baselines_sha256[path] = sha(baseline)
            # difflib omits the standard marker for lines without trailing LF.
            # Include it so the emitted draft remains a valid applyable patch.
            diff = difflib.unified_diff(baseline.splitlines(keepends=True),
                                        candidate.splitlines(keepends=True),
                                        fromfile='a/'+path, tofile='b/'+path)
            diffs[path] = ''.join(line if line.endswith('\n') else
                                  line + '\n\\ No newline at end of file\n' for line in diff)
    if failures:
        return finding("FAIL", "draft exceeds conservative syntactic complexity/fanout contract", violations=failures)
    reason = data.get("why_this_fix")
    if reason is not None and (type(reason) is not str or not reason.strip() or len(reason) > 2048):
        raise ValueError("bounded nonempty why_this_fix required when supplied")
    bundle = {"files": dict(patches), "unified_diffs": diffs, "baseline_sha256": baselines_sha256,
              "missing_baselines": sorted(set(patches) - set(baselines_sha256)), "metrics": metrics,
              "why_this_fix": reason, "auto_apply": False}
    if len(canonical(bundle).encode()) > MAX_BYTES:
        raise ValueError("complete remediation bundle byte cap exceeded")
    return finding("DRAFT", "bounded Python candidate; syntactic metrics only, no correctness or runtime call-graph proof", **bundle)


def _property_expression(text: str, variable: str, sample: Fraction) -> Fraction:
    # Reuse the exact evaluator after substituting integer-ratio AST constants.
    if type(text) is not str or len(text) > 2048:
        raise ValueError("bounded property expression required")
    tree = ast.parse(text, mode='eval')
    if sum(1 for _ in ast.walk(tree)) > 128:
        raise ValueError("property AST budget exceeded")
    class Substitute(ast.NodeTransformer):
        def visit_Name(self, node):
            if node.id != variable: raise ValueError("undeclared property variable")
            return ast.BinOp(left=ast.Constant(sample.numerator), op=ast.Div(),
                             right=ast.Constant(sample.denominator))
    tree = Substitute().visit(tree)
    return exact_expression(ast.unparse(ast.fix_missing_locations(tree)))


def _tests(data: Mapping[str, Any]) -> dict[str, Any]:
    cases = data.get("identities", [])
    falsifications = data.get("falsifications", [])
    properties = data.get("properties", [])
    if not cases and not properties and not falsifications:
        return finding("NOT_PROVABLE", "no known-answer/property/falsification cases supplied")
    for values, cap in ((cases, 32), (falsifications, 32), (properties, 8)):
        if not isinstance(values, list) or len(values) > cap:
            raise ValueError("test-case count budget exceeded")
    def render(node: ast.AST, variable=None) -> str:
        if isinstance(node, ast.Name) and node.id == variable: return '_sample'
        if isinstance(node, ast.Constant) and type(node.value) is int: return f"Fraction({node.value!r})"
        if isinstance(node, ast.UnaryOp): return f"({'-' if isinstance(node.op, ast.USub) else '+'}{render(node.operand, variable)})"
        op = {ast.Add: '+', ast.Sub: '-', ast.Mult: '*', ast.Div: '/'}[type(node.op)]
        return f"({render(node.left, variable)} {op} {render(node.right, variable)})"
    lines = ["from fractions import Fraction", "import unittest", "", "class ExactKnownAnswers(unittest.TestCase):"]
    for values, label, assertion in ((cases, 'identity', 'assertEqual'), (falsifications, 'falsification', 'assertNotEqual')):
        for i, case in enumerate(values):
            for key in ('left', 'right'): exact_expression(case[key])
            left, right = [render(ast.parse(case[k], mode='eval').body) for k in ('left', 'right')]
            lines.extend([f"    def test_{label}_{i}(self):", f"        self.{assertion}({left}, {right})"])
    predicates = []
    for i, prop in enumerate(properties):
        variable, samples = prop['variable'], prop['samples']
        if type(variable) is not str or not variable.isidentifier() or len(variable) > 32:
            raise ValueError("bounded property variable required")
        if not isinstance(samples, list) or not 1 <= len(samples) <= 32:
            raise ValueError("property requires 1..32 explicit exact samples")
        samples = [exact_expression(value) for value in samples]
        for value in samples:
            for key in ('left', 'right'): _property_expression(prop[key], variable, value)
        left, right = [render(ast.parse(prop[k], mode='eval').body, variable) for k in ('left', 'right')]
        sample_text = ', '.join(f'Fraction({value.numerator}, {value.denominator})' for value in samples)
        lines.extend([f"    def test_property_{i}(self):", f"        for _sample in [{sample_text}]:",
                      "            with self.subTest(sample=str(_sample)):", f"                self.assertEqual({left}, {right})"])
        predicates.append({"property": i, "failure_predicate": "left(sample) != right(sample)",
                           "sample_count": len(samples), "coverage": "explicit finite samples, not universal proof"})
    text = '\n'.join(lines) + '\n'
    if len(text.encode()) > MAX_BYTES: raise ValueError("generated test byte budget exceeded")
    return finding("DRAFT", "known-answer, finite-property and falsification tests; not executed by inspect",
                   files={"tests/test_agent_exact_known_answers.py": text}, auto_apply=False,
                   failure_predicates=predicates,
                   test_counts={"known_answer": len(cases), "property": len(properties), "falsification": len(falsifications)})


class AgentCapabilitySuite:
    """Tenant-bound local diagnostics; caller retains authentication/authorization."""
    def __init__(self, ledger: EvidenceLedger | None = None):
        self.ledger = ledger if ledger is not None else EvidenceLedger()
        self._append_lock = threading.RLock()

    def inspect(self, *, tenant_id: str, target: str, source: str,
                evidence: Mapping[str, Any] | None = None, at_ns: int = 0) -> dict[str, Any]:
        if type(at_ns) is not int or at_ns < 0:
            raise ValueError("nonnegative integer evidence timestamp required")
        if type(tenant_id) is not str or not tenant_id.strip() or len(tenant_id) > 256:
            raise ValueError("explicit bounded tenant identity required")
        if type(target) is not str or not safe_path(target):
            raise ValueError("safe repository-relative target required")
        if type(source) is not str or len(source.encode()) > MAX_BYTES:
            raise ValueError("source byte budget exceeded")
        data = bounded_evidence({} if evidence is None else evidence)
        try:
            tree = ast.parse(source)
            if sum(1 for _ in ast.walk(tree)) > MAX_NODES:
                raise ValueError("source AST node budget exceeded")
        except (SyntaxError, RecursionError) as exc:
            tree = None
            syntax_error = type(exc).__name__
        results: dict[str, Any] = {}
        checks = {
            "auditor": lambda: _audit(source, data), "remediator": lambda: _drafts(data, target, source),
            "test_engineer": lambda: _tests(data), "math_verifier": lambda: _math(data),
            "quantum_checker": lambda: _quantum(data),
            "security_verifier": lambda: _security(tree),
            "precision_sentinel": lambda: _precision(tree, data),
            "pin_verifier": lambda: _pin(tree, data),
        }
        for role, check in checks.items():
            try:
                if tree is None and role in {"security_verifier", "precision_sentinel", "pin_verifier"}:
                    results[role] = finding("NOT_PROVABLE", f"source parse failed: {syntax_error}")
                else:
                    results[role] = check()
            except (ValueError, TypeError, KeyError, ZeroDivisionError, SyntaxError, RecursionError, AttributeError, OverflowError):
                results[role] = finding("NOT_PROVABLE", "unsupported, invalid or over-budget input")
        results["provenance"] = finding("PASS", "input digest binding only; not canonical THESEUS custody",
                                           source_sha256=sha(source), input_sha256=sha(canonical(data)))
        truth = [v["status"] for k, v in results.items() if ROLE_LAYERS[k] == "TRUTH"]
        results["governance"] = finding("FAIL" if "FAIL" in truth else "PASS" if all(x == "PASS" for x in truth) else "NOT_PROVABLE",
                                           "aggregate diagnostic verdict only; no approval, merge or actuation authority")
        report = {"schema": SCHEMA, "contract_revision": CONTRACT_REVISION,
                  "tenant_id": tenant_id, "target": target,
                  "source_sha256": sha(source), "capabilities": results,
                  "self_healing_ready": False, "actuation": "NOT_PERFORMED"}
        # Do not put draft source or supplied evidence/secrets into the shared ledger.
        summary = {role: {"status": value["status"], "reason": value["reason"]} for role, value in results.items()}
        with self._append_lock:
            ref = self.ledger.append("agent-capability-review", {
                "tenant_id": tenant_id, "target": target, "source_sha256": sha(source),
                "input_sha256": sha(canonical(data)), "report_sha256": sha(canonical(report)),
                "capabilities": summary,
            }, at_ns=at_ns)
        return {**report, "evidence_ref": ref}
