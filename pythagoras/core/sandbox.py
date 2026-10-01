"""
AL HARAS Security Guard: Static Audit & Isolated Validity Gate
==============================================================
AL HARAS owns execution safety for every candidate PYTHAGORAS evaluates.

1. Static audit (always): walks the AST and reports calls that touch the host
   (process spawning, dynamic code execution, filesystem writes/deletes, network,
   unsafe deserialisation, native code). Findings are tagged by scope:
     - "import_time": runs when the module is executed (module/class body,
       decorators, default arguments) — these BLOCK execution.
     - "deferred":    inside function bodies — reported, not blocking, because
       the validity gate does not call functions.
2. Isolated execution (when no host test runner is supplied): the candidate runs
   in a separate interpreter (`python -I`) inside a throwaway directory, with a
   wall-clock timeout and, on POSIX, CPU / memory / file-size limits.
   For hard network isolation, run the host itself in a container without egress.

verify_validity(code_str, external_test_runner=None) -> (parse_v, compile_v, runtime_v)
keeps the v12 contract. runtime_v means "module executes cleanly in isolation"
(or "host test runner passed"); it does not by itself prove behaviour is unchanged.
"""
import ast
import hashlib
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

# (rule_id, description, matcher(dotted_call_name, call_node) -> bool)
_WRITE_MODES = set("wax+")


def _open_writes(call: ast.Call) -> bool:
    mode = None
    if len(call.args) >= 2 and isinstance(call.args[1], ast.Constant):
        mode = call.args[1].value
    for kw in call.keywords:
        if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
            mode = kw.value.value
    if mode is None:
        return len(call.args) >= 2 or any(kw.arg == "mode" for kw in call.keywords)  # non-literal mode: flag
    return isinstance(mode, str) and bool(_WRITE_MODES & set(mode))


AUDIT_RULES: List[Tuple[str, str, Callable[[str, ast.Call], bool]]] = [
    ("AH001", "dynamic code execution", lambda n, c: n in ("eval", "exec", "compile", "__import__", "builtins.eval", "builtins.exec")),
    ("AH002", "process spawning", lambda n, c: n.startswith("subprocess.") or n in (
        "os.system", "os.popen", "os.fork", "os.forkpty", "pty.spawn") or n.startswith(("os.exec", "os.spawn", "os.posix_spawn"))),
    ("AH003", "filesystem delete / move", lambda n, c: n in (
        "os.remove", "os.unlink", "os.rmdir", "os.removedirs", "os.rename", "os.replace",
        "shutil.rmtree", "shutil.move") or n.endswith((".unlink", ".rmdir"))),
    ("AH004", "filesystem write", lambda n, c: (n in ("open", "io.open", "builtins.open") and _open_writes(c))
        or n.endswith((".write_text", ".write_bytes")) or n in ("shutil.copy", "shutil.copyfile", "shutil.copytree")),
    ("AH005", "network access", lambda n, c: n.startswith(("socket.", "urllib.request.", "http.client.", "requests.",
                                                          "httpx.", "ftplib.", "smtplib.", "telnetlib."))),
    ("AH006", "unsafe deserialisation", lambda n, c: n in ("pickle.load", "pickle.loads", "marshal.load", "marshal.loads",
                                                          "shelve.open", "yaml.load", "yaml.unsafe_load")),
    ("AH007", "native code / interpreter internals", lambda n, c: n.startswith(("ctypes.", "cffi.")) or n in ("sys.settrace", "sys.setprofile")),
    ("AH008", "process / signal control", lambda n, c: n in ("os.kill", "os.killpg", "signal.signal", "sys.exit", "os._exit", "exit", "quit")),
    ("AH009", "environment mutation", lambda n, c: n in ("os.putenv", "os.unsetenv", "os.chdir", "os.chmod", "os.chown", "os.setuid")),
]


def _dotted(func: ast.AST, aliases: Dict[str, str]) -> str:
    parts = []
    while isinstance(func, ast.Attribute):
        parts.append(func.attr)
        func = func.value
    if isinstance(func, ast.Name):
        parts.append(aliases.get(func.id, func.id))
    else:
        return ""
    return ".".join(reversed(parts))


def _import_aliases(tree: ast.AST) -> Dict[str, str]:
    aliases: Dict[str, str] = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                aliases[a.asname or a.name.split(".")[0]] = a.name if a.asname else a.name.split(".")[0]
        elif isinstance(n, ast.ImportFrom) and n.module:
            for a in n.names:
                aliases[a.asname or a.name] = f"{n.module}.{a.name}"
    return aliases


def _import_time_nodes(tree: ast.Module) -> set:
    """ids of nodes executed when the module itself runs."""
    out = set()
    stack = list(tree.body)
    while stack:
        n = stack.pop()
        out.add(id(n))
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            stack.extend(n.decorator_list)
            stack.extend(d for d in n.args.defaults + n.args.kw_defaults if d is not None)
            continue
        if isinstance(n, ast.Lambda):
            continue
        if isinstance(n, ast.If) and isinstance(n.test, ast.Compare) and isinstance(n.test.left, ast.Name) \
                and n.test.left.id == "__name__":
            continue  # `if __name__ == "__main__":` does not run under the gate
        stack.extend(ast.iter_child_nodes(n))
    return out


@dataclass
class AuditReport:
    rules_checked: int
    violations: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def blocking(self) -> List[Dict[str, Any]]:
        return [v for v in self.violations if v["scope"] == "import_time"]

    @property
    def approved(self) -> bool:
        return not self.blocking

    def to_dict(self) -> Dict[str, Any]:
        return {"rules_checked": self.rules_checked, "approved_for_execution": self.approved,
                "violations": self.violations, "blocking_violations": len(self.blocking)}


def al_haras_audit(code_str: str) -> AuditReport:
    try:
        tree = ast.parse(code_str)
    except (SyntaxError, ValueError):
        return AuditReport(rules_checked=len(AUDIT_RULES))
    aliases = _import_aliases(tree)
    import_time = _import_time_nodes(tree)
    violations = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _dotted(node.func, aliases)
        if not name:
            continue
        for rule_id, desc, match in AUDIT_RULES:
            try:
                hit = match(name, node)
            except Exception:
                hit = False
            if hit:
                violations.append({"rule": rule_id, "description": desc, "call": name,
                                   "line": getattr(node, "lineno", None),
                                   "scope": "import_time" if id(node) in import_time else "deferred"})
                break
    return AuditReport(rules_checked=len(AUDIT_RULES), violations=violations)


# --------------------------------------------------------------------------- #
# Isolated execution
# --------------------------------------------------------------------------- #
@dataclass
class SandboxConfig:
    timeout_sec: float = 5.0
    memory_mb: int = 1024
    cpu_sec: int = 10
    max_file_mb: int = 16
    extra_sys_path: List[str] = field(default_factory=list)  # host package roots, if candidates import them


DEFAULT_CONFIG = SandboxConfig()
_BOOTSTRAP = (
    "import sys\n"
    "sys.path[:0] = {paths!r}\n"
    "src = open({path!r}, encoding='utf-8').read()\n"
    "exec(compile(src, {path!r}, 'exec'), {{'__name__': '__pythagoras_candidate__', '__builtins__': __builtins__}})\n"
)


def _limits(cfg: SandboxConfig):
    def apply():
        try:
            import resource
            mem = cfg.memory_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
            resource.setrlimit(resource.RLIMIT_CPU, (cfg.cpu_sec, cfg.cpu_sec))
            fs = cfg.max_file_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_FSIZE, (fs, fs))
        except Exception:
            pass
    return apply if os.name == "posix" else None


_RESULT_CACHE: Dict[str, Tuple[bool, str]] = {}


def run_isolated(code_str: str, cfg: SandboxConfig = DEFAULT_CONFIG) -> Tuple[bool, str]:
    key = hashlib.sha256((code_str + repr(cfg)).encode("utf-8")).hexdigest()
    if key in _RESULT_CACHE:
        return _RESULT_CACHE[key]
    with tempfile.TemporaryDirectory(prefix="pythagoras_") as td:
        path = os.path.join(td, "candidate.py")
        with open(path, "w", encoding="utf-8") as f:
            f.write(code_str)
        cmd = [sys.executable, "-I", "-c", _BOOTSTRAP.format(paths=list(cfg.extra_sys_path), path=path)]
        try:
            proc = subprocess.run(cmd, cwd=td, capture_output=True, text=True, timeout=cfg.timeout_sec,
                                  env={"PATH": os.environ.get("PATH", ""), "PYTHONHASHSEED": "0"},
                                  preexec_fn=_limits(cfg))
            ok = proc.returncode == 0
            reason = "ok" if ok else (proc.stderr.strip().splitlines() or ["nonzero exit"])[-1][:300]
        except subprocess.TimeoutExpired:
            ok, reason = False, f"timeout after {cfg.timeout_sec}s"
    _RESULT_CACHE[key] = (ok, reason)
    return ok, reason


def validate(code_str: str, external_test_runner: Optional[Callable[[str], bool]] = None,
             cfg: SandboxConfig = DEFAULT_CONFIG) -> Dict[str, Any]:
    """Full validity record: parse, compile, AL HARAS audit, isolated run or host test runner."""
    rec: Dict[str, Any] = {"parse_valid": False, "compile_valid": False, "runtime_valid": False,
                           "runtime_mode": None, "reason": None, "audit": None}
    try:
        tree = ast.parse(code_str)
        rec["parse_valid"] = True
    except (SyntaxError, ValueError) as e:
        rec["reason"] = f"parse: {e}"
        return rec
    try:
        compile(tree, filename="<candidate>", mode="exec")
        rec["compile_valid"] = True
    except (SyntaxError, ValueError, TypeError) as e:
        rec["reason"] = f"compile: {e}"
        return rec

    audit = al_haras_audit(code_str)
    rec["audit"] = audit.to_dict()
    if not audit.approved:
        rec["runtime_mode"] = "blocked_by_al_haras"
        rec["reason"] = "; ".join(f"{v['rule']} {v['call']} (line {v['line']})" for v in audit.blocking)
        return rec

    if external_test_runner is not None:
        rec["runtime_mode"] = "host_test_runner"
        try:
            rec["runtime_valid"] = bool(external_test_runner(code_str))
            rec["reason"] = "host tests passed" if rec["runtime_valid"] else "host tests failed"
        except Exception as e:
            rec["reason"] = f"host test runner raised: {type(e).__name__}: {e}"
        return rec

    rec["runtime_mode"] = "isolated_module_execution"
    rec["runtime_valid"], rec["reason"] = run_isolated(code_str, cfg)
    return rec


def verify_validity(code_str: str, external_test_runner: Optional[Callable[[str], bool]] = None,
                    cfg: SandboxConfig = DEFAULT_CONFIG) -> Tuple[bool, bool, bool]:
    r = validate(code_str, external_test_runner, cfg)
    return r["parse_valid"], r["compile_valid"], r["runtime_valid"]
