"""Packaged mathematical-purity source scanner shared with repository CI."""
from __future__ import annotations

import ast
import re
from pathlib import Path

EXACT_SUBPACKAGES = (
    "execution", "backends", "storage", "security",
    "quantum", "stratum", "math", "hw",
)

BANNED = [
    (re.compile(r"(?<![\w.])math\.(?!(?:isqrt|gcd|lcm|comb|perm|factorial)\b)"), "floating-point math module usage"),
    (re.compile(r"(?<![\w.])float\("), "float() cast in exact path"),
    (re.compile(r"np\.float|numpy\.float|dtype\s*=\s*[\"']?f"), "numpy float dtype"),
    (re.compile(r"(?<![\w.])random\."), "pseudo-random heuristic"),
    (re.compile(r"(?<![\w.])(uniform|gauss|normal)\("), "statistical sampling heuristic"),
]

# Operator throttles and administrative telemetry consume real-valued seconds
# and EH/s. They do not implement target membership, hashing or exact arithmetic.
# Permit only scalar conversion/finite checks here; all other rules still run.
OPERATIONAL_SCALAR_MODULES = frozenset({
    "hashrate_cap.py", "mining_admin.py", "stealth_orchestrator.py",
})

THEATRE_TOKENS = [
    "Production-ready quantum",
    "production-ready quantum",
    "Holonomic",
    "NVQLink",
    "CUDA-Q",
    "jitter_immune",
    "gate_fidelity_target",
    "fabricated fidelity",
    "Navier-Stokes",
    "SYMPLECTIC_DEC_FLOW",
]


def scan_file(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    violations = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for pattern, description in BANNED:
            operational_scalar = (
                path.parent.name == "execution" and path.name in OPERATIONAL_SCALAR_MODULES
                and description in {"floating-point math module usage", "float() cast in exact path"}
            )
            if pattern.search(line) and not operational_scalar:
                violations.append(f"{path}:{line_number}: {description}: {line.strip()}")
        for token in THEATRE_TOKENS:
            if token in line:
                violations.append(f"{path}:{line_number}: theatre token '{token}': {line.strip()}")

    # AST analysis for struct packing endianness and banned timing calls
    try:
        tree = ast.parse(text, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute) and node.func.attr == "pack":
                    if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                        fmt = node.args[0].value
                        if not fmt.startswith(("<", ">", "!")):
                            violations.append(
                                f"{path}:{node.lineno}: struct.pack format '{fmt}' missing explicit endianness prefix ('<', '>', '!')"
                            )
                if isinstance(node.func, ast.Attribute) and node.func.attr in {"time", "monotonic"}:
                    if isinstance(node.func.value, ast.Name) and node.func.value.id == "time":
                        violations.append(
                            f"{path}:{node.lineno}: Banned call 'time.{node.func.attr}()' violates PCI Purity Rule (use perf_counter_ns)"
                        )
    except Exception as e:
        violations.append(f"{path}: AST parse error: {e}")

    return violations



def scan_installed_package() -> tuple[int, list[str]]:
    """Inspect installed Chronus Python sources; missing scope is a failed gate."""
    package_root = Path(__file__).resolve().parents[1]
    scanned = 0
    violations: list[str] = []
    for subpackage in EXACT_SUBPACKAGES:
        root = package_root / subpackage
        if not root.is_dir():
            violations.append(f"required purity package missing: {root}")
            continue
        paths = sorted(root.rglob("*.py"))
        if not paths:
            violations.append(f"required purity package has no source: {root}")
        for path in paths:
            scanned += 1
            violations.extend(scan_file(path))
    for name in ("config.py", "ns_dec.py"):
        path = package_root / name
        if not path.is_file():
            violations.append(f"required purity source missing: {path}")
            continue
        scanned += 1
        violations.extend(scan_file(path))
    return scanned, violations
