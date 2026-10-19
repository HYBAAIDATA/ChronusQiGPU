"""TURING's product registry: every module, why it exists, and what it consumes.

Each module is registered with a role and its documented purpose; modules
whose application lies outside the VQC (candidate ordering, accelerator
facades) record the execution paths that use them, because TURING keeps a
module by its purpose and its live callers, not by its name. Modules carved
out of TURING are recorded with their new owner; corrections made while
consolidating are recorded with the test that pins them.

``verify_registry()`` checks that every module file in the package is
registered, that every registered module exists, that every carved-out module
is gone, and that every module imports (optional extras are declared).
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROLES = (
    "core",  # the virtual quantum computer's exact engines and algebra
    "backend",  # backend registry and admission contracts
    "boundary",  # claim boundary, certificates, verification, taxonomy
    "pipeline",  # the production composition path and operator surfaces
    "algorithm",  # quantum algorithms run on the VQC
    "application",  # VQC programs and schedules applied by other products
    "adapter",  # consumption of a sibling product by protocol (lazy import)
    "alias",  # module identity alias of the owning product (dependency)
    "substrate",  # exact arithmetic kernels the VQC computes with
    "research",  # declared research surfaces with optional dependencies
    "compat",  # bounded compatibility adapters for retained facades
)


@dataclass(frozen=True)
class ModuleEntry:
    name: str
    role: str
    purpose: str
    consumes: Tuple[str, ...] = ()
    execution_paths: Tuple[str, ...] = ()
    extras: Tuple[str, ...] = ()


def _m(name: str, role: str, purpose: str, **kw: Any) -> ModuleEntry:
    for key in ("consumes", "execution_paths", "extras"):
        if key in kw:
            kw[key] = tuple(kw[key])
    return ModuleEntry(name, role, purpose, **kw)


MODULES: Tuple[ModuleEntry, ...] = (
    _m("config", "boundary", "Validated native public API configuration and fail-closed unsupported modes."),
    _m("contracts", "boundary", "Immutable typed IR, named finite parameters, artifacts, jobs and estimates."),
    _m("exceptions", "boundary", "Typed input, capability, execution, timeout and provenance failures."),
    _m("interfaces", "boundary", "Compiler/backend/estimator/optimizer/error-plan extension protocols."),
    _m("native_adapter", "adapter", "Typed native admission, local jobs and certified-result Z estimation.",
       consumes=["pipeline", "backends"]),
    _m("optimizer", "algorithm", "Bounded exhaustive finite-ansatz optimizer with exact radical comparison."),
    _m("public_api", "pipeline", "Additive QuantumPipeline facade over the canonical native computation path."),
    _m("lucas_metallic_walk", "research", "Existing Lucas-metallic walk research surface with exact operators over Q(phi)."),
    _m("__init__", "core", "Package surface: eager exact substrate, lazy engines."),
    _m("turing_core", "core", "Exact arithmetic, deterministic scheduling and certification."),
    _m("turing_core.core", "core", "Zero-dependency exact Q[sqrt 5] algebra, Zeckendorf, T_phi fold, "
       "dual-overlay frame (the icosahedron's true dual)."),
    _m("turing_core.ten_thousand", "core", "TenThousandQubitSystem: superposition, entanglement, walks, "
       "annealing, tunnelling, swarms at n = 10,000; manifests to THESEUS custody."),
    _m("turing_core.specification", "core", "Machine-checkable classical Turing-machine specification "
       "and certification."),
    _m("turing_core.inventory", "core", "Content-based discovery of Turing structures in a repository."),
    _m("turing_core.schedule", "application", "Deterministic complete nonce-ordering schedule; ordering "
       "only, SHA-256d stays the authority.",
       execution_paths=["turing_core.core (re-exported)", "chronus/mla1517_platform/python/turing_core.py"]),
    _m("turing_core.discovery", "research", "Mathematical frontier explorer; query-complexity figures "
       "describe algorithms, not measured speedups.", extras=["networkx", "scipy"]),
    _m("hilbert", "core", "QuantumRegister: exact sparse state vector over Q(i, sqrt 2) + cyclotomics."),
    _m("stabilizer", "core", "Exact Aaronson-Gottesman tableau over GF(2) at any width."),
    _m("register_tensor", "core", "Audited QuantumTensor facade over QuantumRegister."),
    _m("exact_state_vector", "core", "Exact finite state-vector algebra (MLA1517 surface)."),
    _m("exact_field_registry", "core", "Registry of the exact cyclotomic field Q(zeta_8)."),
    _m("canonical_serialization", "core", "Canonical, fail-closed serialization for exact evidence."),
    _m("quantum_walk", "core", "Coined cycle walk (sparse exact) and closed-form hypercube walk."),
    _m("quantum_library", "algorithm", "Curated exact algorithm library surface (Grover, QAOA, "
       "VQE/TFIM scans, walks, counting) returning truth-labelled LibraryResults."),
    _m("annealing", "core", "Exact TFIM free-fermion spectrum, adiabatic gap, Landau-Zener."),
    _m("swarm", "core", "Agents sampling exact Born distributions."),
    _m("trotter_simulation", "core", "Trotter-Suzuki evolution, declared approximate with its error."),
    _m("surface_code_exact", "core", "Planar edge surface code: exact CSS algebra, k = 1, exact "
       "distance via Kellogg's CSSCode.", consumes=["kellogg"]),
    _m("backends", "backend", "Backend registry, admission and selection."),
    _m("backends.base", "backend", "Execution/truth classes, Program, Admission, ExecutionResult."),
    _m("backends.algebraic", "backend", "Universal Clifford+T, materialised, exact."),
    _m("backends.exact_algebra", "backend", "Exact closed algebraic field for the backend layer."),
    _m("backends.reference", "backend", "Exact universal statevector over Q(sqrt 2) + iQ(sqrt 2)."),
    _m("backends.native", "backend", "Adapters binding stabilizer, sparse and closed-form engines."),
    _m("backends.mps", "backend", "mps_exact: Clifford+T at any width under a static Schmidt bound "
       "(Kellogg exact MPS).", consumes=["kellogg"]),
    _m("backends.qpu", "backend", "Fail-closed boundary to real quantum hardware; no bundled provider."),
    _m("capabilities", "boundary", "Published capability matrix and fail-closed claim audit."),
    _m("certificates", "boundary", "Verifiable run witnesses and computation certificates."),
    _m("verify", "boundary", "Exact program-unitary verification."),
    _m("taxonomy", "boundary", "Execution-kind and evidence-state taxonomy."),
    _m("property_invariants", "boundary", "Property invariants of the folded execution evidence."),
    _m("representation", "boundary", "Proof-shaped representation planning (WF02), incl. mps_exact."),
    _m("pipeline", "pipeline", "Production composition path: validate, plan, execute, certify, "
       "custody, replay."),
    _m("console", "pipeline", "Operator console (turing-vqc): dense, tableau and MPS registers."),
    _m("phi_gate", "pipeline", "CLI production gate for the 1,000-qubit phi machine."),
    _m("quantum_algorithms", "algorithm", "First-principles quantum algorithms with Lucas scaling.",
       execution_paths=["chronus/mla1517/mining/pythia_authority.py",
                        "chronus/mla1517_platform/python/system_fabric.py"]),
    _m("grover_exact_scale", "algorithm", "Exact Grover amplification, folded, Lucas-Pisot scaled.",
       execution_paths=["chronus/mla1517_platform/python/system_fabric.py"]),
    _m("variational", "algorithm", "Variational quantum circuit plane (phi-Grover).",
       execution_paths=["chronus/mla1517/mining/pythia_agentic_cycle.py",
                        "Intelligence/bitcoin_vqc_training.py",
                        "euclid/organ_adapters/vqc_intelligence.py"]),
    _m("deep_variational", "algorithm", "Deep multi-angle variational ansatz on the 32-face graph."),
    _m("phi_vqc", "application", "Bounded phi-VQC candidate ranking; ordering only, never consensus.",
       execution_paths=["chronus/mla1517/mining/hyba_intelligence.py"]),
    _m("midas_vqc", "application", "32-face MIDAS variational candidate ranker with exact Clifford "
       "skeleton.", execution_paths=["chronus/mla1517/mining/pythia_authority.py"]),
    _m("hendrix", "application", "Hendrix structured-search facade over the Pisot schedule.",
       execution_paths=["chronus/mla1517/mining/pythia_authority.py"]),
    _m("pisot", "application", "Exact Lucas/Pisot scale contracts, Hendrix schedule, Hilbert coverage "
       "plans (used by the VQC itself).",
       execution_paths=["turing_core.ten_thousand", "register_tensor",
                        "chronus/mla1517/mining/hendrix_order.py"]),
    _m("quantum_cuda", "application", "Accelerator facade for the VQC's exact math (iGPU lane).",
       execution_paths=["Intelligence/registry.py", "Intelligence/pythia_tools.py",
                        "chronus/mla1517/mining/pythia_authority.py"]),
    _m("phi_machine", "application", "1,000-logical-qubit Clifford execution profile, QASM subset, "
       "T_phi checkpoint custody.",
       execution_paths=["aethel/enterprise/system_relations.py", "pipeline"]),
    _m("phi_quantum_machine", "application", "Production phi-machine facade.",
       consumes=["python_backend"], execution_paths=["phi_vqc", "phi_verification", "july_compat"]),
    _m("phi_verification", "application", "Evidence gates for the phi machine."),
    _m("golden_quantum", "application", "Golden Quantum profile bound to TenThousandQubitSystem; "
       "orderings stay heuristics.", execution_paths=["turing_core.ten_thousand"]),
    _m("custody", "adapter", "THESEUS custody consumption (WF05).", consumes=["aethel.theseus"]),
    _m("transform", "adapter", "OVID representation-transformation consumption (WF04).",
       consumes=["aethel.ovid"]),
    _m("chronus_lane", "adapter", "CHRONUS execution-lane consumption; gated without hardware.",
       consumes=["aethel.chronus"]),
    _m("exact_tensor", "alias", "Alias of kellogg.exact_tensor.", consumes=["kellogg"]),
    _m("quantum_tensor", "alias", "Alias of kellogg.quantum_tensor.", consumes=["kellogg"]),
    _m("exact_field", "alias", "Alias of kellogg.exact_field.", consumes=["kellogg"]),
    _m("lucas", "substrate", "Lucas power-scaling pool: the shared exact algebraic substrate."),
    _m("lucas.algebra", "substrate", "Exact Lucas algebra over Z[phi]."),
    _m("lucas.bound", "substrate", "Lucas-bounded cost kernels."),
    _m("lucas.cassini", "substrate", "Exact Cassini identity for Lucas/Fibonacci numbers."),
    _m("lucas.core", "substrate", "Exact Lucas and Fibonacci numbers via fast doubling."),
    _m("lucas.ladder", "substrate", "Lucas ladder: the canonical scale sequence."),
    _m("lucas.pool", "substrate", "Lucas pool registry: the only legal shared import."),
    _m("lucas.trace", "substrate", "tr(M^n) = L_n verification and bounding."),
    _m("unified_theory", "research", "Executable unified-theory foundation contract."),
    _m("july_compat", "compat", "Bounded compatibility adapters for retained July facades.",
       consumes=["kellogg"]),
    _m("product_registry", "boundary", "This registry."),
    _m("benchmark", "boundary", "Correctness, cost and meta benchmarks in Kellogg's artifact format.",
       consumes=["kellogg"]),
)

CARVED_OUT: Tuple[Tuple[str, str, str], ...] = (
    ("fault_tolerant_asic", "mining.fault_tolerant_asic", "hashrate/ASIC capacity model"),
    ("deterministic_hashrate", "mining.deterministic_hashrate", "10 EH/s formal-capacity certificates"),
    ("thermodynamics_exact", "mining.thermodynamics_exact", "SHA-256d Landauer boundary"),
    ("scaled_execution", "mining.scaled_execution", "mining execution plane (sha256d grind)"),
    ("four_layer_stack", "mining.four_layer_stack", "four-layer mining stack"),
    ("bitcoin_hasher", "mining.bitcoin_hasher", "older copy of the live owner"),
    ("hash_pipeline", "mining.hash_pipeline", "older copy of the live owner"),
    ("search", "mining.search", "older copy of the live owner"),
    ("turing_adapter", "chronus.mla1517.mining.turing_adapter", "older copy of the live owner"),
    ("toe_system", "toe.system", "older copy of the live owner"),
    ("hardened_unified_substrate", "aethel.hardened_unified_substrate",
     "copy of the live owner; its self-tests moved to tests/test_aethel_hardened_substrate_selftests.py"),
    ("manifold_bridge", "toe.manifold_bridge", "identical copy"),
    ("unified_punch", "Intelligence.unified_punch", "older copy (owner adds device pinning)"),
    ("backend_binding", "Intelligence.backend_binding", "older copy (owner adds multi-device binding)"),
    ("duality", "mtheory.duality", "identical copy"),
    ("kk_spectrum", "mtheory.kk_spectrum", "identical copy"),
    ("extended_algebra", "chronus/mla1517_platform/python/extended_algebra", "identical copy"),
    ("rings", "chronus.mla1517.rings", "identical copy"),
    ("strict_quantum", "toe.strict_quantum", "identical copy"),
    ("intelligences", "toe.intelligences", "copy (owner's counterfactual uses the computed finite "
     "gauge gap, not a hard-coded sqrt 5)"),
    ("kernels", "kernels/ (repository root)", "identical OpenCL sources (sha256d, unified punch, golden "
     "ontology); no TURING module loads them after the carve-out"),
)

CORRECTIONS: Tuple[Tuple[str, str, str], ...] = (
    ("surface_code_k0", "The star-on-every-vertex code encoded k = 0 logical qubits; replaced by "
     "the planar code (k = 1, exact distance d).", "tests/test_surface_code_exact.py"),
    ("dual_frame_mirror", "The dual-overlay dodecahedron was the mirror orientation; it is now the "
     "icosahedron's face centres.", "kellogg.quantum_tensor.dual_frame_is_dual"),
    ("pure_state_entropy", "The forked quantum_tensor gave von Neumann entropy 1 for a pure state; "
     "the Kellogg alias gives 0.", "tests/test_product_boundary.py"),
    ("replay_merge_damage", "pipeline._replay lost its custody binding in a merge (NameError).",
     "tests/test_vqc_custody_durable.py"),
    ("custody_boundary_import", "aethel system_relations used an unimported verifier, so every "
     "TURING custody boundary failed.", "tests/test_shared_system_relations_production.py"),
    ("wide_non_clifford_refused", "Clifford+T programs beyond the dense budget had no backend and no "
     "representation; mps_exact admits them under a static Schmidt bound.",
     "tests/test_mps_exact_backend.py"),
)


def _package_dir() -> Path:
    return Path(__file__).resolve().parent


def _module_files() -> List[str]:
    root = _package_dir()
    names = []
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        rel = path.relative_to(root).with_suffix("")
        parts = list(rel.parts)
        if parts[-1] == "__init__" and len(parts) > 1:
            parts = parts[:-1]
        names.append(".".join(parts))
    return sorted(names)


def verify_registry(*, import_check: bool = True) -> Dict[str, Any]:
    problems: List[str] = []
    registered = {m.name for m in MODULES}
    if len(registered) != len(MODULES):
        problems.append("duplicate module entries")
    files = set(_module_files())
    for name in sorted(files - registered):
        problems.append(f"unregistered module {name}")
    for name in sorted(registered - files):
        problems.append(f"registered module {name} does not exist")
    for name, _home, _reason in CARVED_OUT:
        if name in files or any((_package_dir() / name).glob("*.py")):
            problems.append(f"carved-out module {name} is still present")
    for m in MODULES:
        if m.role not in ROLES:
            problems.append(f"{m.name}: unknown role {m.role}")
        if not m.purpose:
            problems.append(f"{m.name}: no purpose")
    skipped: List[str] = []
    if import_check:
        for m in MODULES:
            target = "turing_universal_quantum_computer" + ("" if m.name == "__init__" else f".{m.name}")
            try:
                importlib.import_module(target)
            except ImportError as exc:
                missing = getattr(exc, "name", "") or ""
                if m.extras and missing.split(".")[0] in m.extras:
                    skipped.append(f"{m.name} (needs extra {missing})")
                else:
                    problems.append(f"{m.name} fails to import: {exc}")
    roles: Dict[str, int] = {}
    for m in MODULES:
        roles[m.role] = roles.get(m.role, 0) + 1
    return {
        "modules": len(MODULES),
        "roles": roles,
        "carved_out": len(CARVED_OUT),
        "corrections": len(CORRECTIONS),
        "skipped_for_extras": skipped,
        "problems": problems,
        "ok": not problems,
    }


def entry(name: str) -> Optional[ModuleEntry]:
    return next((m for m in MODULES if m.name == name), None)


__all__ = ["CARVED_OUT", "CORRECTIONS", "MODULES", "ModuleEntry", "ROLES", "entry", "verify_registry"]
