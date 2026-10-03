"""
EUCLID Isolated Validation & Execution Sandbox v16.0
========================================================
Executes candidate AST bytecode in a process-isolated sandbox with strict AST safety validation,
restricted built-ins whitelist, resource limits, and timeout controls to prevent arbitrary code execution,
filesystem tampering, and system-level abuse.
"""

import ast
import sys
import time
import logging
import builtins
import multiprocessing
from typing import Tuple, Optional, Callable, Dict, Any, Set

logger = logging.getLogger(__name__)

# Strict AST Safety Blacklists / Whitelists
FORBIDDEN_MODULES: Set[str] = {
    "os", "sys", "subprocess", "socket", "shutil", "urllib", "http", "requests",
    "builtins", "importlib", "ctypes", "threading", "multiprocessing", "signal",
    "pty", "platform", "posix", "resource", "code", "codeop", "pickle", "cPickle",
    "marshal", "shelve", "dbm", "sqlite3", "pathlib", "tempfile", "asyncio"
}

FORBIDDEN_CALLS: Set[str] = {
    "eval", "exec", "open", "__import__", "compile", "breakpoint", "globals",
    "locals", "getattr", "setattr", "delattr", "input", "system", "popen", "spawn"
}

FORBIDDEN_ATTRS: Set[str] = {
    "__subclasses__", "__bases__", "__mro__", "__globals__", "__code__",
    "__closure__", "__builtins__", "__import__", "__class__"
}

# Whitelisted safe builtins dictionary for isolated execution
SAFE_BUILTINS: Dict[str, Any] = {
    "abs": abs, "all": all, "any": any, "bin": bin, "bool": bool, "chr": chr,
    "complex": complex, "dict": dict, "dir": dir, "divmod": divmod,
    "enumerate": enumerate, "filter": filter, "float": float, "format": format,
    "frozenset": frozenset, "hash": hash, "hex": hex, "int": int,
    "isinstance": isinstance, "issubclass": issubclass, "len": len, "list": list,
    "map": map, "max": max, "min": min, "oct": oct, "ord": ord, "pow": pow,
    "print": print, "range": range, "repr": repr, "reversed": reversed,
    "round": round, "set": set, "slice": slice, "sorted": sorted, "str": str,
    "sum": sum, "tuple": tuple, "type": type, "zip": zip,
    "ValueError": ValueError, "TypeError": TypeError, "ZeroDivisionError": ZeroDivisionError,
    "Exception": Exception, "IndexError": IndexError, "KeyError": KeyError,
    "AttributeError": AttributeError, "ArithmeticError": ArithmeticError,
    "LookupError": LookupError, "AssertionError": AssertionError, "RuntimeError": RuntimeError,
    "NameError": NameError,
    "None": None, "True": True, "False": False,
    "__build_class__": getattr(builtins, "__build_class__", None),
    "__name__": "__main__",
    "staticmethod": staticmethod,
    "classmethod": classmethod,
    "property": property,
}

class ASTSafetyValidator(ast.NodeVisitor):
    """
    AST Safety Inspector.
    Scans candidate AST nodes for dangerous imports, calls, or attribute accesses prior to compilation.
    """
    def __init__(self):
        self.violations = []

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            mod_root = alias.name.split('.')[0]
            if mod_root in FORBIDDEN_MODULES:
                self.violations.append(f"Forbidden import: '{alias.name}'")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module:
            mod_root = node.module.split('.')[0]
            if mod_root in FORBIDDEN_MODULES:
                self.violations.append(f"Forbidden import from: '{node.module}'")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        if isinstance(node.func, ast.Name):
            if node.func.id in FORBIDDEN_CALLS:
                self.violations.append(f"Forbidden function call: '{node.func.id}()'")
        elif isinstance(node.func, ast.Attribute):
            if node.func.attr in FORBIDDEN_CALLS:
                self.violations.append(f"Forbidden method call: '{node.func.attr}()'")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute):
        if node.attr in FORBIDDEN_ATTRS:
            self.violations.append(f"Forbidden dunder attribute access: '{node.attr}'")
        self.generic_visit(node)

    @classmethod
    def validate_code_str(cls, code_str: str) -> Tuple[bool, str]:
        """Parses and inspects code_str for safety violations."""
        try:
            tree = ast.parse(code_str)
        except Exception as e:
            return False, f"ParseError: {str(e)}"

        validator = cls()
        validator.visit(tree)
        if validator.violations:
            first_v = validator.violations[0]
            return False, f"SecurityViolation: {first_v}"
        return True, "AST_SAFETY_CLEAN"


def _spawn_worker_entry(code_str: str, external_test_code: Optional[str], conn):
    """
    Child process worker target executing inside a restricted namespace.
    """
    try:
        # Apply OS-level resource limits if available on Linux/Unix
        try:
            import resource
            resource.setrlimit(resource.RLIMIT_CPU, (2, 2))  # 2s max CPU
            resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
        except (ImportError, AttributeError, Exception):
            pass

        # Restricted execution namespace with Whitelisted Builtins ONLY
        restricted_ns = {"__builtins__": SAFE_BUILTINS, "__name__": "__main__"}
        
        # Compile and execute candidate code string
        compiled = compile(code_str, filename="<candidate>", mode="exec")
        exec(compiled, restricted_ns)

        if external_test_code:
            compiled_test = compile(external_test_code, filename="<test_suite>", mode="exec")
            exec(compiled_test, restricted_ns)

        conn.send({"success": True, "error": None})
    except Exception as e:
        conn.send({"success": False, "error": f"{type(e).__name__}: {str(e)}"})
    finally:
        conn.close()


class IsolatedProcessEvaluator:
    """
    Process Isolation Sandbox.
    Prevents unauthorized system access, infinite loops, memory bombs, and filesystem tampering.
    """
    def __init__(self, timeout_sec: float = 2.0):
        self.timeout_sec = timeout_sec

    def evaluate_validity(
        self, 
        code_str: str, 
        external_test_runner: Optional[Callable[[str], bool]] = None,
        external_test_code: Optional[str] = None
    ) -> Tuple[bool, bool, bool, str]:
        """
        Gated validity pipeline:
        1. AST Parse & Security Audit
        2. Bytecode Compilation
        3. Restricted Process Runtime Execution (with timeout & resource limits)
        4. External Test Validation (if provided)
        
        Returns: (parse_valid, compile_valid, runtime_test_valid, diagnostic_message)
        """
        # Step 1: AST Parse & Security Audit
        safe, sec_msg = ASTSafetyValidator.validate_code_str(code_str)
        if not safe:
            if "ParseError" in sec_msg:
                return False, False, False, sec_msg
            return True, False, False, sec_msg  # Parsed, but failed security/compilation audit

        # Step 2: Bytecode Compilation Check
        try:
            tree = ast.parse(code_str)
            compile(tree, filename="<candidate>", mode="exec")
            compile_valid = True
        except Exception as e:
            return True, False, False, f"CompileError: {str(e)}"

        # Step 3: Spawn Isolated Child Process using Pipe IPC
        parent_conn, child_conn = multiprocessing.Pipe()
        
        p = multiprocessing.Process(
            target=_spawn_worker_entry,
            args=(code_str, external_test_code, child_conn)
        )

        try:
            p.start()
            child_conn.close()  # Close child end in parent

            if parent_conn.poll(timeout=self.timeout_sec):
                res = parent_conn.recv()
            else:
                res = {"success": False, "error": f"TimeoutError: Execution exceeded {self.timeout_sec}s threshold"}
                if p.is_alive():
                    p.terminate()
                    p.join(timeout=0.5)

            p.join(timeout=0.5)

            if not res.get("success", False):
                err_msg = res.get("error", "RuntimeError")
                return True, True, False, f"RuntimeExecutionError: {err_msg}"

        except Exception as e:
            logger.warning(f"Process sandbox execution exception: {str(e)}")
            return True, True, False, f"SandboxExecutionException: {str(e)}"
        finally:
            if p.is_alive():
                p.terminate()

        # Step 4: External Test Runner (if provided by host repo)
        if external_test_runner is not None:
            try:
                test_passed = external_test_runner(code_str)
                if not test_passed:
                    return True, True, False, "HostTestSuiteFailed: External test suite returned False"
            except Exception as e:
                return True, True, False, f"HostTestSuiteError: {str(e)}"

        return True, True, True, "VALIDATED_CLEAN"
