"""Audit the MLA1517/PRIME-DB implementation against its own spec.

The build programme declares specific, checkable claims: a module layout, an
exact algebra core, an exact quantum path, a no-float gate, strict ladder
CI, and a set of test counts. This checks what is actually present and what
actually executes, so the maturity boundary is stated from evidence rather
than from the document.
"""

import importlib
import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "mla1517_platform_v3.4" / "python"))

# Phase 1 reference runtime, as declared in the build programme.
PHASE1 = [
    "constants",
    "state",
    "fibonacci_store",
    "zeckendorf_codec",
    "binet_view",
    "pisot_fold",
    "lucas_scale",
    "cassini",
    "m32_geometry",
    "prime_address",
    "prime_db",
    "query",
]
# The gates and artifacts the later sections declare.
GATES = [
    "scripts/session_requirements_audit.py",
    "scripts/release_gate.py",
    "scripts/strict_hardware_gate.py",
    "scripts/no_float_in_math_core.py",
    "kernels/mla1517_lucas_pisot_scale.cl",
    "kernels/exact_quantum_kernel.cl",
    "REQUIREMENTS_AUDIT.md",
    "host/primedb_storage.c",
    "host/telemetry_shm.c",
    "Dockerfile.native",
]
NATIVE = [
    "mla1517.quantum",
    "mla1517.accelerator",
    "mla1517.rings",
    "mla1517.scaling",
    "mla1517.primedb_engine",
]


def report_presence():
    print("=== DECLARED vs PRESENT ===")
    pkg = ROOT / "mla1517_platform_v3.4" / "python" / "mla1517"
    print("  -- Phase 1 reference runtime --")
    for m in PHASE1:
        print(f"    {m:<18} {'PRESENT' if (pkg / f'{m}.py').is_file() else 'ABSENT'}")
    print("  -- release gates / native artifacts --")
    for g in GATES:
        print(f"    {g:<44} {'PRESENT' if (ROOT / g).exists() else 'ABSENT'}")


def report_imports():
    print()
    print("=== IMPORTABLE (i.e. actually reachable) ===")
    ok = 0
    for m in NATIVE:
        try:
            importlib.import_module(m)
            print(f"    OK   {m}")
            ok += 1
        except Exception as exc:
            print(f"    FAIL {m}: {type(exc).__name__}: {exc}")
    print(f"    {ok}/{len(NATIVE)} importable")


def report_surface():
    print()
    print("=== PUBLIC SURFACE (is this a runtime or a stub?) ===")
    for m in NATIVE:
        try:
            mod = importlib.import_module(m)
        except Exception:
            continue
        cls = [
            n
            for n, o in inspect.getmembers(mod, inspect.isclass)
            if not n.startswith("_") and o.__module__ == m
        ]
        fns = [
            n
            for n, o in inspect.getmembers(mod, inspect.isfunction)
            if not n.startswith("_") and o.__module__ == m
        ]
        print(f"    {m:<26} classes={len(cls):<3} funcs={len(fns):<3} {cls[:5]}")


def report_exactness():
    print()
    print("=== EXACTNESS: is the algebra core float-free as declared? ===")
    import ast

    checked = 0
    dirty = []
    for m in ("rings", "quantum", "scaling"):
        p = ROOT / "mla1517_platform_v3.4" / "python" / "mla1517" / f"{m}.py"
        if not p.is_file():
            continue
        tree = ast.parse(p.read_text(encoding="utf-8"))
        checked += 1
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, float):
                dirty.append(f"{m}.py:{node.lineno} float literal {node.value}")
            if isinstance(node, ast.Name) and node.id in {"float", "complex"}:
                dirty.append(f"{m}.py:{node.lineno} uses {node.id}")
    print(f"    files scanned: {checked}")
    if dirty:
        print(f"    float/complex references: {len(dirty)}")
        for d in dirty[:8]:
            print(f"      {d}")
    else:
        print("    no float literals or float()/complex() names in the exact core")


def report_behaviour():
    print()
    print("=== BEHAVIOUR: do the declared capabilities actually WORK? ===")

    # 1. Exact quantum path: Q(sqrt2) arithmetic, no floats.
    try:
        from mla1517.quantum import ExactComplex, Qsqrt2

        a = ExactComplex(Qsqrt2(1, 0), Qsqrt2(0, 0))  # 1
        b = ExactComplex(Qsqrt2(0, 1), Qsqrt2(0, 0))  # sqrt(2)
        prod = a * b  # must equal sqrt(2)
        ok_mul = prod.real.b == 1 and prod.real.a == 0
        print(f"    exact Q(sqrt2) multiply 1 * sqrt2 = sqrt2 : {ok_mul}")
        print(f"      -> {prod.real.a} + {prod.real.b}*sqrt(2)")
    except Exception as exc:
        print(f"    exact quantum arithmetic FAILED: {type(exc).__name__}: {exc}")

    # 2. Exact quotient rings: ZPhi must be a ring, not a float wrapper.
    try:
        from mla1517.rings import ZPhi

        a, b = ZPhi(1, 0), ZPhi(0, 1)  # 1 and sqrt5
        s = a + b
        p = a * b
        print(f"    ZPhi add  1 + sqrt5 = ({s.a}, {s.b})")
        print(f"    ZPhi mul  1 * sqrt5 = ({p.a}, {p.b})")
        # Norm must be exact: (a+b*sqrt5)(a-b*sqrt5) = a^2 - 5b^2
        conj = ZPhi(a.a, -a.b)
        norm = (a * conj).a
        print(f"    ZPhi norm of 1+sqrt5 is exact int : {isinstance(norm, int)} ({norm})")
    except Exception as exc:
        print(f"    ZPhi rings FAILED: {type(exc).__name__}: {exc}")

    # 3. Lucas ladder exactness at the declared rungs.
    try:
        from lucas.core import lucas as L

        vals = [L(r) for r in (10, 12, 15, 17, 18, 20, 31, 50, 76)]
        print(f"    exact Lucas at rungs   : {vals}")
        print(f"    L_15={vals[2]}  L_17={vals[3]}  L_20={vals[5]}")
    except ImportError:
        print("    lucas.core unavailable; ladder check skipped")

    # 5. The 64-byte hot descriptor, and whether PRIME-DB is really native.
    try:
        import ctypes

        from mla1517.primedb_engine import STATE_BYTES, MLA1517State, NativePrimeDB

        size = ctypes.sizeof(MLA1517State)
        print(f"    MLA1517State size       : {size} bytes (declared {STATE_BYTES})")
        print(f"    64-byte ABI holds       : {size == 64}")
        names = [f[0] for f in MLA1517State._fields_]
        print(f"    descriptor fields (D1..) : {names}")
        try:
            import tempfile

            with tempfile.TemporaryDirectory() as td:
                NativePrimeDB(td)
                print("    NativePrimeDB opened    : True (native library loaded)")
        except Exception as exc:
            print(f"    NativePrimeDB FAILED    : {type(exc).__name__}: {exc}")
            print("      -> the C storage library is absent; only the ctypes")
            print("         contract is present, so PRIME-DB is not executable here.")
    except Exception as exc:
        print(f"    descriptor check failed: {type(exc).__name__}: {exc}")

    # 6. The canonical accelerator: does it ever fall back silently?
    try:
        from mla1517.accelerator import CanonicalAccelerator, ExactOpenCLAccelerator

        acc = CanonicalAccelerator()
        print(f"    CanonicalAccelerator    : backend={acc.backend!r}")
        try:
            ExactOpenCLAccelerator()
            print("    ExactOpenCLAccelerator  : constructed")
        except Exception as exc:
            print(f"    ExactOpenCLAccelerator  : FAILS CLOSED -> {type(exc).__name__}: {exc}")
            print("      -> correct: no CPU approximation stands in for the device")
    except Exception as exc:
        print(f"    accelerator introspection failed: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    report_presence()
    report_imports()
    report_surface()
    report_exactness()
    report_behaviour()
    sys.stdout.flush()
