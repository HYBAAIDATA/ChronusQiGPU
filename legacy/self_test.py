"""Mining system self-test — the OVERALL gate.

Executes, in order:

1. Lucas substrate battery (core, cassini, trace, bound, pool, ladder).
2. ``turing_core.run_self_verification()`` — incl. the T_phi / M15 /
   Cassini asserts.
3. Purity gates — no forbidden imports anywhere in ``lucas/``,
   ``Intelligence/``, ``mining/`` or the root driver files.
4. Wire discipline — AST check that no subsystem imports a sibling.
5. Safety FSM — four-state leg, edge-table enforcement, never two
   consecutive blocks.
6. Folded state — bit-exact round-trip, all five fold-space ops equal
   the raw answers, no raw buffers materialised.
7. Registry — every mining subsystem loads, incl. folded_state_engine.

Every gate is executed, not asserted. ``theorem_proven`` stays False.
"""

# LUCAS WIRING: wiring layer — verifies subsystems, does not serve one.
# Substrate route: trace

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

ROOT = Path(__file__).resolve().parent

THEOREM_PROVEN = False

# ----------------------------------------------------------------------
# Wire discipline tables (canonical — tests/wire_discipline.py reuses them)
# ----------------------------------------------------------------------

# Modules any subsystem may import: stdlib + the shared substrates.
SUBSTRATE_MODULES = {
    "numpy",
    "lucas",
    "turing_core",
    # The project's own quantum/algebra substrates — peers of lucas/,
    # not sibling algorithm subsystems.
    "Intelligence.quantum_tensor",
    "Intelligence.lucas_scales",
    "Intelligence.causal_ladder",
    "Intelligence.poincare_golden_11d",
    "Intelligence.poincare_cassini_search",
    "Intelligence.folded_state",
    "Intelligence.hardened_unified_substrate",
    # quantum_algorithms is a primitives substrate (LucasEngine, ExactQFT,
    # GroverSearch, QPE, QuantumWalk, VQE) — peer of quantum_tensor, not a
    # sibling composer. Leaf modules may consume it.
    "Intelligence.quantum_algorithms",
    "Intelligence.safety_constraints",
    # Exact-witness substrate: the F4 field Q(sqrt(2))+iQ(sqrt(2)),
    # ExactStateVector algebra, and ExactTOETensor witness — the canonical
    # in-repo replacement for the platform mla1517.quantum surface.
    "Intelligence.exact_tensor",
    "coremltools",
    "metalcompute",
    "pyopencl",
    "Metal",
    "mlx",
}

# Files that compose subsystems into the loop (may import them).
WIRING_FILES = [
    ROOT / "orchestrator.py",
    ROOT / "registry.py",
    ROOT / "self_test.py",
    ROOT / "Intelligence" / "__init__.py",
    ROOT / "Intelligence" / "orchestrator.py",
    ROOT / "Intelligence" / "registry.py",
    ROOT / "Intelligence" / "self_test.py",
    ROOT / "Intelligence" / "pythia_store.py",
    ROOT / "Intelligence" / "requirements.py",
    ROOT / "Intelligence" / "salamander.py",
    ROOT / "Intelligence" / "mining_bridge.py",
    ROOT / "Intelligence" / "counterfactual_intelligence.py",
    ROOT / "Intelligence" / "neural_plasticity_integration.py",
    ROOT / "Intelligence" / "neural_plasticity_quantum.py",
    ROOT / "Intelligence" / "apple_plasticity.py",
    # Search-ontology wiring layer: the intelligence-facing composers that
    # drive the Poincare-Cassini engine (itself a declared substrate).
    ROOT / "Intelligence" / "intent_compiler.py",
    ROOT / "Intelligence" / "search_api.py",
    ROOT / "Intelligence" / "agentic_controller_search.py",
    ROOT / "Intelligence" / "orchestrator_search.py",
    ROOT / "Intelligence" / "plasticity_search.py",
    ROOT / "Intelligence" / "self_test_search.py",
    ROOT / "Intelligence" / "agentic_controller.py",
    ROOT / "Intelligence" / "hardened_unified_substrate.py",
    ROOT / "Intelligence" / "mining_bridge_ontology.py",
    ROOT / "Intelligence" / "ontology_mining_engine.py",
    ROOT / "Intelligence" / "pathfinder.py",
    ROOT / "Intelligence" / "search_database.py",
    ROOT / "Intelligence" / "salamander_agentic.py",
    ROOT / "Intelligence" / "backend_binding.py",
    ROOT / "Intelligence" / "mining_native.py",
    ROOT / "Intelligence" / "agentic_mining.py",
    ROOT / "Intelligence" / "toe_system.py",
    # TOE expansion envelope: composes TOEBridge + operator compilers +
    # quantum_tensor + the MLA1517 scale controller + 11D certificates into
    # the proof-carrying result — a composer, not a leaf subsystem.
    ROOT / "Intelligence" / "toe_expansion.py",
    # Discovery composer: orchestrates grover_exact_scale runs plus the
    # quantum_tensor substrate — composition, not a leaf subsystem.
    ROOT / "Intelligence" / "mathematical_discovery.py",
    # Coordinator modules — self-declared wiring layer (same class as
    # toe_system/orchestrator): they compose sibling subsystems.
    ROOT / "Intelligence" / "chain_verification.py",
    ROOT / "Intelligence" / "four_layer_stack.py",
    ROOT / "Intelligence" / "igpu_telemetry.py",
    ROOT / "Intelligence" / "unified_manifold_device.py",
    # PULVINI runtime: composes folded_state + prime_memory + coherence_gate
    # + mandelbrot_resonance + phi_grover_v4 + golden_constants into the
    # solve-first hierarchy — a composer, not a leaf subsystem.
    ROOT / "Intelligence" / "pulvini_runtime.py",
    ROOT / "mining" / "hash_pipeline.py",
    ROOT / "mining" / "stratum_bridge.py",
    # Counterfactual harness: composes hash_pipeline + stratum_bridge lane
    # ordering to measure order effects — a composer, not a leaf subsystem.
    ROOT / "mining" / "order_counterfactual.py",
    # Production Stratum V1 miner: composes bitcoin_hasher + stratum_bridge +
    # strict_quantum work-window certificates — a composer, not a leaf.
    ROOT / "mining" / "production_miner.py",
    # Resonance falsification probe: composes stratum_bridge + bitcoin_hasher
    # + search_crystal to measure ordering claims — a composer, not a leaf.
    ROOT / "mining" / "resonance_probe.py",
    # Live handshake probe: composes the production Stratum client to verify
    # real pool connectivity — a composer, not a leaf.
    ROOT / "mining" / "live_handshake.py",
    # Live mining instrument: composes the Stratum client + BitcoinHasher to
    # measure real hashrate on real jobs — a composer, not a leaf.
    ROOT / "mining" / "live_mine.py",
    # Production scaled-execution plane: composes FourLayerMiningStack +
    # strict_quantum certificates + TOESystem + the lucas Hendrix schedule —
    # a composer, not a leaf.
    ROOT / "mining" / "scaled_execution.py",
    # Multi-arm allocation probe: composes resonance_probe statistics +
    # stratum_bridge lane orders + bitcoin_hasher + the Hendrix arm —
    # a composer, not a leaf.
    ROOT / "mining" / "euclid_multarm_probe.py",
]

# Quantum substrates shipped with the mining package — these files are
# the substrate layer (like lucas/ and turing_core), scanned for purity
# but permitted to reference their own substrate package internals.
SHIPPED_SUBSTRATES = [
    ROOT / "core_engine" / "agi_substrate.py",
    ROOT / "core_engine" / "layered_intelligence_substrate.py",
    ROOT / "core_engine" / "quantum_cuda.py",
    ROOT / "src" / "cortex_golden_transform.py",
    ROOT / "python_backend" / "yang_mills_data.py",
]

# Per-package extra allowed imports for subsystem files.
PACKAGE_SUBSTRATES = {
    # Intelligence subsystem files: only the three declared substrates
    # (in SUBSTRATE_MODULES) plus the core_engine substrate layer —
    # any other Intelligence.* import is a sibling violation.
    "Intelligence": {"core_engine"},
    # core_engine / src / python_backend files are the substrate layer;
    # intra-substrate references are legal.
    "core_engine": {"core_engine", "quantum_cuda"},
    # src is the substrate layer: intra-substrate references (src->src)
    # are legal, e.g. cortex_golden_transform -> golden_ontology_transform.
    "src": {"python_backend", "src"},
    "python_backend": set(),
    "mining": set(),
    "lucas": set(),
    "": set(),
}


# Per-file declared external dependencies. The analysis/discovery layer
# legitimately uses scientific packages (declared in pyproject [ml]); the
# gate allows them ONLY on the files that declare them — everywhere else
# they remain forbidden.
FILE_ALLOWED_DEPS = {
    ROOT / "Intelligence" / "discovery.py": {"networkx", "pandas", "scipy"},
    ROOT / "Intelligence" / "mathematical_discovery.py": {"networkx", "scipy"},
    ROOT / "Intelligence" / "empirical_state_controller.py": {"yaml"},
    ROOT / "mining" / "stratum_bridge.py": {"mla1517", "worker_lifecycle"},
    # production_miner emits measured counters through the supervised
    # heartbeat channel when PYTHIA_WORKER_NAME/PYTHIA_EMIT_HEARTBEAT is set.
    ROOT / "mining" / "production_miner.py": {"worker_lifecycle"},
    ROOT / "Intelligence" / "pulvini_runtime.py": set(),
}


# Subsystem files: every package .py that is NOT wiring layer and not a
# package facade (__init__.py is definitionally the facade).
def subsystem_files() -> List[Path]:
    wiring = {p.resolve() for p in WIRING_FILES}
    out: List[Path] = []
    for pkg in ("lucas", "Intelligence", "mining"):
        d = ROOT / pkg
        if d.is_dir():
            out.extend(sorted(d.glob("*.py")))
    out.extend(p for p in SHIPPED_SUBSTRATES if p.exists())
    for f in ("turing_core.py",):
        p = ROOT / f
        if p.exists():
            out.append(p)
    return [p for p in out if p.resolve() not in wiring and p.name != "__init__.py"]


def _dotted_imports(path: Path) -> List[str]:
    """All imports in a file as dotted names (relative resolved).

    Bare ``import x`` / ``from x import y`` where ``x.py`` sits in the
    same package directory is resolved to ``pkg.x`` — files that lift
    their own directory onto sys.path cannot disguise a sibling import.
    """
    pkg = path.parent.name
    mods: set[str] = set()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return ["<syntax-error>"]

    def _resolve(name: str) -> str:
        if "." not in name and (path.parent / f"{name}.py").exists():
            return f"{pkg}.{name}"
        return name

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                mods.add(_resolve(a.name))
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.module:
                mods.add(f"{pkg}.{node.module}")
            elif node.level:
                mods.add(pkg)
            elif node.module:
                mods.add(_resolve(node.module))
    return sorted(mods)


def check_wire_discipline() -> Dict[str, Any]:
    """AST gate: fail on any subsystem -> sibling import."""
    import sys as _sys

    stdlib = set(_sys.stdlib_module_names)
    failures: List[Dict[str, Any]] = []
    checked = 0
    for path in subsystem_files():
        checked += 1
        pkg = path.parent.name if path.parent != ROOT else ""
        allowed = (
            stdlib
            | SUBSTRATE_MODULES
            | PACKAGE_SUBSTRATES.get(pkg, set())
            | FILE_ALLOWED_DEPS.get(path.resolve(), set())
        )
        bad = []
        for mod in _dotted_imports(path):
            root_mod = mod.split(".")[0]
            if mod in allowed or root_mod in allowed:
                continue
            bad.append(mod)
        if bad:
            failures.append({"file": str(path), "forbidden": bad})
    return {
        "checked": checked,
        "failures": failures,
        "passed": not failures,
        "theorem_proven": False,
    }


# ----------------------------------------------------------------------
# Gates
# ----------------------------------------------------------------------


def _gate_lucas() -> Dict[str, Any]:
    from lucas import cassini, core, ladder, pool, trace
    from lucas.bound import bound, paths
    from lucas.native_registry import entries as native_entries

    checks: Dict[str, Any] = {}
    checks["lucas_exact_0_20"] = all(
        core.lucas(n) == v
        for n, v in enumerate(
            [
                2,
                1,
                3,
                4,
                7,
                11,
                18,
                29,
                47,
                76,
                123,
                199,
                322,
                521,
                843,
                1364,
                2207,
                3571,
                5778,
                9349,
                15127,
            ]
        )
    )
    checks["cassini_0_20"] = cassini.verify_range(20)
    Q = np.array([[1, 1], [1, 0]], dtype=object)
    checks["trace_q_equals_lucas"] = all(trace.verify(Q, n)["valid"] for n in range(1, 21))
    checks["ladder"] = ladder.verify_ladder()["valid"] and ladder.FULL_LADDER == [
        10,
        12,
        15,
        18,
        20,
    ]
    checks["seven_kernels"] = sorted(pool.available()) == sorted(
        [
            "mining_kernel",
            "step_kernel",
            "path_kernel",
            "gap_kernel",
            "trace_kernel",
            "amplitude_kernel",
            "folded_kernel",
        ]
    )
    kernel_shape = True
    for name in pool.available():
        k = pool.get(name)
        if name == "trace_kernel":
            r = k(Q, 10)
        elif name == "path_kernel":
            r = k(np.array([[0, 1], [1, 0]], dtype=np.int64), 5)
        elif name == "gap_kernel":
            r = k(np.diag([0.0, 1.0, 3.0]), 10)
        elif name == "amplitude_kernel":
            r = k([1.0, 0.5], 5)
        elif name == "step_kernel":
            r = k({"states": 4}, 10)
        elif name == "mining_kernel":
            r = k(100, 10)
        elif name == "folded_kernel":
            r = k(b"\x00" * 64, 10)
        else:
            kernel_shape = False
            continue
        kernel_shape = (
            kernel_shape
            and all(key in r for key in ("is_lucas_bounded", "bound", "n"))
            and r["theorem_proven"] is False
        )
    checks["kernel_return_shape"] = kernel_shape
    try:
        pool.register("mining_kernel", lambda *a: {})
        checks["pool_rejects_duplicates"] = False
    except (ValueError, KeyError):
        checks["pool_rejects_duplicates"] = True
    try:
        pool.get("no_such_kernel")
        checks["pool_missing_raises"] = False
    except KeyError:
        checks["pool_missing_raises"] = True
    checks["bound_ge_paths_1_20"] = all(bound(n) >= paths(n) for n in range(1, 21))
    checks["native_registry_listed"] = len(native_entries()) >= 1
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "theorem_proven": False,
    }


def _gate_turing_core() -> Dict[str, Any]:
    import turing_core as tc

    det = (tc.M15[0][0] * tc.M15[1][1] - tc.M15[0][1] * tc.M15[1][0]) % 256
    inv_ok = all(
        (sum(tc.M15[i][k] * tc.M15_INV[k][j] for k in range(2)) % 256) == (1 if i == j else 0)
        for i in range(2)
        for j in range(2)
    )
    rt = all(
        tc.t_phi_unfold(tc.t_phi_fold(bytes([x])), 1) == bytes([x]) for x in range(256)
    ) and all(
        tc.t_phi_unfold(tc.t_phi_fold(bytes([x, (x * 7) % 256])), 2) == bytes([x, (x * 7) % 256])
        for x in range(256)
    )
    return {
        "passed": bool(tc.run_self_verification()) and det == 255 and inv_ok and rt,
        "det_M15_mod256": det,
        "integer_inverse": inv_ok,
        "bit_exact_256": rt,
        "theorem_proven": False,
    }


def _gate_purity() -> Dict[str, Any]:
    from lucas import gate

    results: Dict[str, Any] = {}
    ok = True
    for d, extra in (
        ("lucas", ()),
        # asi_system is the declared facade wiring the orchestrator;
        # core_engine is the quantum substrate layer; pyopencl accelerates hashing.
        ("mining", ("Intelligence", "core_engine", "mining", "pyopencl")),
        (
            "Intelligence",
            (
                "Intelligence",
                "core_engine",
                "src",
                "toe",
                "python_backend",
                "quantum_cuda",
                "coremltools",
                "metalcompute",
                "pyopencl",
                "Metal",
                "mlx",
                "hyba",
                "mla1517",
                "mining",
                "pythagoras",
                "intelligences",
            ),
        ),
    ):
        import sys as _sys

        allowed = set(_sys.stdlib_module_names) | {"lucas", "turing_core", "numpy"} | set(extra)
        failures: List[Dict[str, Any]] = []
        files = sorted((ROOT / d).rglob("*.py"))
        for f in files:
            res = gate.purity_check(f, allowed | FILE_ALLOWED_DEPS.get(f.resolve(), set()))
            if not res["passed"]:
                failures.append(res)
        results[d] = {
            "passed": not failures,
            "files": len(files),
            "checks": {str(f["file"]): f["forbidden"] for f in failures},
        }
        if failures:
            ok = False
    checks: Dict[str, Any] = {}
    for d, r in results.items():
        for f, bad in (r.get("checks") or {}).items():
            checks[f] = bad
    return {
        "passed": ok,
        "dirs": results,
        "checks": checks,
        "theorem_proven": False,
    }


def _gate_safety_fsm() -> Dict[str, Any]:
    from mining.safety_fsm import EDGES, MiningState, SafetyFSM

    fsm = SafetyFSM()
    states = [s.value for s in MiningState]
    leg: List[str] = []
    ok = fsm.begin_search()
    fsm.on_winner_found()
    leg.append(fsm.state.value)
    fsm.on_block_accepted(1)
    leg.append(fsm.state.value)
    fsm.on_external_block(2)
    leg.append(fsm.state.value)
    fsm.cooldown_complete()
    leg.append(fsm.state.value)
    full_leg = leg == ["submitting", "waiting_external", "cooldown", "searching"]

    # Edge-table enforcement: an undeclared jump must raise.
    fsm2 = SafetyFSM()
    try:
        fsm2._go(MiningState.COOLDOWN)
        edge_ok = False
    except Exception:
        edge_ok = True

    # Never two consecutive blocks: after accept, mining is denied until
    # an external block is observed.
    fsm3 = SafetyFSM()
    fsm3.on_winner_found()
    fsm3.on_block_accepted(5)
    denied_while_waiting = not fsm3.can_mine()
    prevented_before = fsm3.consecutive_blocks_prevented
    fsm3.begin_search()
    prevented = fsm3.consecutive_blocks_prevented > prevented_before
    fsm3.on_external_block(6)
    fsm3.cooldown_complete()
    allowed_after_external = fsm3.can_mine()

    passed = all(
        [
            states == ["searching", "submitting", "waiting_external", "cooldown"],
            ok,
            full_leg,
            edge_ok,
            denied_while_waiting,
            prevented,
            allowed_after_external,
            set(EDGES) == set(MiningState),
        ]
    )
    return {
        "passed": passed,
        "states": states,
        "full_leg": leg,
        "edge_table_enforced": edge_ok,
        "never_two_consecutive": denied_while_waiting and prevented,
        "theorem_proven": False,
    }


def _gate_folded_state() -> Dict[str, Any]:
    import hashlib

    from Intelligence.folded_state import ExactFoldedStateEngine

    eng = ExactFoldedStateEngine()
    payload = (hashlib.sha256(b"self-test-payload").digest() * 4)[:100]
    key = "st-folded"
    art = eng.encode(payload, key=key)
    checks: Dict[str, Any] = {}
    checks["bit_exact"] = eng.restore(key) == payload
    checks["ratio_measured"] = art.compression_ratio > 0
    raw_sum = sum(payload)
    checks["sum_u8"] = eng.execute(key, eng.compile_query("sum_u8")).value == raw_sum
    w = bytes((i % 7) + 1 for i in range(len(payload)))
    checks["weighted_sum_u8"] = eng.execute(
        key, eng.compile_query("weighted_sum_u8", weights=w)
    ).value == sum(w[i] * payload[i] for i in range(len(payload)))
    checks["modular_dot_u8"] = (
        eng.execute(key, eng.compile_query("modular_dot_u8", weights=w)).value
        == sum(w[i] * payload[i] for i in range(len(payload))) % 256
    )
    hist = [0] * 256
    for b in payload:
        hist[b] += 1
    checks["histogram_u8"] = eng.execute(key, eng.compile_query("histogram_u8")).value == hist
    checks["sha256_equals"] = eng.execute(
        key,
        eng.compile_query("sha256_equals", expected_sha256=hashlib.sha256(payload).hexdigest()),
    ).value
    checks["no_raw_buffers"] = all(
        eng.execute(key, eng.compile_query(op)).raw_buffer_materialized is False
        for op in ("sum_u8", "histogram_u8")
    )
    checks["status_zero_materializations"] = eng.status()["raw_materializations"] == 0
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "theorem_proven": False,
    }


def _gate_registry() -> Dict[str, Any]:
    from registry import build_mining_registry

    reg = build_mining_registry()
    failed = [e.name for e in reg.failed_modules()]
    names = reg.names()
    return {
        "passed": "folded_state_engine" in names and len(failed) == 0,
        "registered": len(names),
        "failed": failed,
        "folded_state_engine": "folded_state_engine" in names,
        "theorem_proven": False,
    }


def run_self_test(verbose: bool = True) -> Dict[str, Any]:
    """Run every gate; OVERALL passes only if all pass."""
    gates = {
        "lucas_substrate": _gate_lucas(),
        "turing_core": _gate_turing_core(),
        "purity": _gate_purity(),
        "wire_discipline": check_wire_discipline(),
        "safety_fsm": _gate_safety_fsm(),
        "folded_state": _gate_folded_state(),
        "registry": _gate_registry(),
    }
    overall = all(g["passed"] for g in gates.values())
    report = {"gates": gates, "overall_passed": overall, "theorem_proven": False}
    if verbose:
        print("=" * 60)
        print("MINING SYSTEM SELF-TEST")
        print("=" * 60)
        for name, g in gates.items():
            detail = ""
            if name == "wire_discipline":
                detail = f" ({g['checked']} files)"
            if name == "registry":
                detail = f" ({g['registered']} subsystems)"
            print(f"  {name:<20} {'PASS' if g['passed'] else 'FAIL'}{detail}")
            for k, v in (g.get("checks") or {}).items():
                if v is not True:
                    print(f"      {k}: {v}")
            if name == "wire_discipline" and g["failures"]:
                for f in g["failures"]:
                    print(f"      {f['file']}: {f['forbidden']}")
        print("=" * 60)
        print(f"  OVERALL: {'PASS' if overall else 'FAIL'}")
        print("=" * 60)
    return report


if __name__ == "__main__":
    sys.exit(0 if run_self_test()["overall_passed"] else 1)
