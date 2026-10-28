"""TURING benchmark suite — correctness first, cost second, one meta-benchmark.

Artifacts use Kellogg's content-addressed benchmark format (provenance, exact
digests, MEASURED / MODELED / NOT_RUN classification) under the schema
``turing.vqc-benchmark/v1``. Run ``python -m turing_universal_quantum_computer.benchmark``.
"""

from __future__ import annotations

import json
import os
import platform
import random
import subprocess
import sys
import time
from fractions import Fraction
from importlib.metadata import PackageNotFoundError, version as distribution_version
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Sequence

from kellogg.benchmark import _plain, digest, provenance as _kellogg_provenance, stats, timed

SCHEMA = "turing.vqc-benchmark/v1"


def provenance() -> Dict[str, Any]:
    import turing_universal_quantum_computer as tqc

    prov = _kellogg_provenance()
    turing_version = getattr(tqc, "__version__", None)
    if turing_version is None:
        try:
            turing_version = distribution_version("hyba-turing-vqc")
        except PackageNotFoundError as exc:
            raise RuntimeError(
                "cannot resolve the installed hyba-turing-vqc version"
            ) from exc
    prov["turing_version"] = turing_version
    return prov


def _ghz(n: int, *tail: tuple):
    from .backends import Program

    program = Program(n).then("h", 0)
    for i in range(n - 1):
        program = program.then("cx", i, i + 1)
    for op in tail:
        program = program.then(*op)
    return program


def _random_program(n: int, depth: int, seed: int, clifford_only: bool = False):
    from .backends import Program

    rng = random.Random(seed)
    one = ["h", "s", "x", "y", "z", "sdg"] + ([] if clifford_only else ["t", "tdg"])
    program = Program(n)
    for _ in range(depth):
        if rng.random() < 0.55:
            program = program.then(rng.choice(one), rng.randrange(n))
        else:
            a, b = rng.sample(range(n), 2)
            program = program.then(rng.choice(["cx", "cz"]), a, b)
    return program


def _dense_distribution(program) -> Dict[str, Any]:
    """Independent exact reference: Kellogg's dense ExactStateVector."""
    from kellogg.cyclotomic import Q8
    from kellogg.exact_tensor import GATES, ExactStateVector

    names = {"h": "H", "s": "S", "sdg": "Sdg", "t": "T", "tdg": "Tdg", "x": "X", "y": "Y", "z": "Z"}
    state = ExactStateVector.basis(program.n_qubits, 0)
    for op in program.operations:
        if op.gate in ("cx", "cnot"):
            state = state.apply_cnot(*op.qubits)
        elif op.gate == "cz":
            state = state.apply_cz(*op.qubits)
        elif op.gate != "i":
            state = state.apply_single(op.qubits[0], GATES[names[op.gate]])
    n = program.n_qubits
    out: Dict[str, Any] = {}
    for index, amp in enumerate(state.amplitudes):
        weight = Q8.from_f4(amp).norm2()
        if not weight.is_zero():
            key = "".join(str((index >> q) & 1) for q in range(n))
            out[key] = weight
    return out


# -- correctness -----------------------------------------------------------------


def bench_backend_agreement(quick: bool) -> Dict[str, Any]:
    from .backends import MPSExactBackend, execute

    trials = 15 if quick else 80
    mps_ok = stab_ok = 0
    for t in range(trials):
        n = 3 + t % 4
        program = _random_program(n, 6 * n, 1000 + t)
        reference = _dense_distribution(program)
        got = MPSExactBackend().build(program).marginal(list(range(n)))
        mps_ok += got == reference
        clifford = _random_program(n, 6 * n, 5000 + t, clifford_only=True)
        ref_c = _dense_distribution(clifford)
        marginal = execute(clifford, prefer="stabilizer", marginal_of=list(range(n))).payload["marginal"]
        distribution = marginal.get("distribution") or {}
        stab = {k: Fraction(str(v)) for k, v in distribution.items()}
        stab_ok += stab == {k: Fraction(v.a, v.den) for k, v in ref_c.items()}
    return {
        "passed": mps_ok == trials and stab_ok == trials,
        "result": {"trials": trials, "mps_matches_dense_exactly": mps_ok,
                   "stabilizer_matches_dense_exactly": stab_ok,
                   "reference": "kellogg.exact_tensor.ExactStateVector (independent dense evaluation)"},
    }


def bench_refusal_boundary(quick: bool) -> Dict[str, Any]:
    from .backends import Program, QPUBackend, select_backend

    deep = Program(64).then("h", 0).then("t", 0)
    for _ in range(7):
        deep = deep.then("cx", 0, 63)
    checks = {}
    backend, admission = select_backend(deep)
    checks["unbounded_wide_t_refused"] = backend is None and "exceeds chi_max" in admission.reason
    backend, _ = select_backend(Program(64).then("h", 0).then("t", 0))
    checks["bounded_wide_t_admitted_to_mps"] = backend is not None and backend.name == "mps_exact"
    backend, _ = select_backend(Program(400).then("h", 0).then("cx", 0, 399))
    checks["wide_clifford_on_tableau"] = backend is not None and backend.name == "stabilizer"
    backend, _ = select_backend(Program(3).then("rx", 0))
    checks["unknown_gate_refused"] = backend is None
    qpu = QPUBackend().admit(Program(2).then("h", 0))
    checks["qpu_refuses_without_provider"] = not qpu.admitted
    backend, _ = select_backend(Program(6).then("h", 0).then("t", 1))
    checks["small_programs_stay_dense"] = backend is not None and backend.name == "exact_algebraic"
    return {"passed": all(checks.values()), "result": checks}


def bench_certificates(quick: bool) -> Dict[str, Any]:
    """Witnesses refuse overclaims; certificates bind program and result."""
    import dataclasses

    from .backends import execute_certified
    from .certificates import WitnessError, verify_computation_certificate, verify_witness

    programs = [_ghz(4, ("t", 0)), _ghz(300, ("t", 0)), _ghz(300), _random_program(5, 20, 7)]
    overclaims = {"measured_qpu": True, "consensus_authority": True, "theorem_proven": True}
    issued = verified = refused = bound = foreign_rejected = 0
    for index, program in enumerate(programs):
        run = execute_certified(program)
        issued += 1
        verified += bool(verify_witness(run.witness))
        for field_name, value in overclaims.items():
            forged = dataclasses.replace(run.witness, **{field_name: value})
            try:
                verify_witness(forged)
            except WitnessError:
                refused += 1
        bound += bool(verify_computation_certificate(program, run.result, run.certificate))
        other = programs[(index + 1) % len(programs)]
        try:
            foreign_rejected += not verify_computation_certificate(other, run.result, run.certificate)
        except Exception:
            foreign_rejected += 1
    expected_refusals = issued * len(overclaims)
    return {
        "passed": verified == issued == bound == foreign_rejected and refused == expected_refusals,
        "result": {"programs": issued, "witnesses_verified": verified,
                   "overclaims_refused": f"{refused}/{expected_refusals}",
                   "certificates_bind_program_and_result": bound,
                   "foreign_program_rejected": foreign_rejected},
    }


def bench_pipeline_custody_replay(quick: bool) -> Dict[str, Any]:
    from .custody import theseus_available
    from .pipeline import VQCPipeline, VQCRequest

    available = theseus_available()
    rows = []
    for label, program in (("bell_t_dense", _ghz(2, ("t", 0))), ("ghz_t_200_mps", _ghz(200, ("t", 0)))):
        pipeline = VQCPipeline()
        request = VQCRequest(program=program, marginal_of=(0, program.n_qubits - 1), custody=True, replay=True)
        report = pipeline.run(request)
        stages = {s.stage: s.state for s in report.stages}
        if not available:
            # Custody is honestly degraded on this host: the run must never
            # report PASS custody evidence it did not produce. Record the
            # observed degradation and skip the tamper-injection leg, which
            # needs a live THESEUS adapter.
            rows.append({"program": label, "verdict": report.verdict,
                         "backend": report.result.get("backend"),
                         "custody": stages.get("custody"), "replay": stages.get("replay"),
                         "substituted_payload_rejected": None})
            continue
        tampered = dict(report.result)
        payload = dict(tampered["payload"])
        payload["substituted_after_execution"] = True
        tampered["payload"] = payload
        bad = pipeline._last_custody.commit("result", tampered, meta={"stage": "result"}).as_dict()
        mixed = [dict(r) for r in report.custody if r["kind"] != "result"] + [bad]
        state, _ = pipeline._replay(request, mixed)
        rows.append({"program": label, "verdict": report.verdict, "backend": report.result.get("backend"),
                     "custody": stages.get("custody"), "replay": stages.get("replay"),
                     "substituted_payload_rejected": state == "FAIL"})
    if not available:
        honest = all(r["verdict"] != "PASS" and r["custody"] != "PASS" for r in rows)
        return {"passed": None if honest else False,
                "result": {"rows": rows,
                           "reason": "theseus custody unavailable on this host; degradation honesty verified"}}
    ok = all(r["verdict"] == "PASS" and r["replay"] == "PASS" and r["substituted_payload_rejected"] for r in rows)
    return {"passed": ok, "result": {"rows": rows}}


def bench_surface_code(quick: bool) -> Dict[str, Any]:
    from .surface_code_exact import all_vertex_star_report, verify_surface_code_algebra

    rows = []
    for d in ((3, 5, 7) if quick else (3, 5, 7, 9, 15, 21, 31)):
        r = verify_surface_code_algebra(d)
        rows.append({"distance": d, "verified": r.verified, "logical_qubits": r.logical_qubits,
                     "mixed_pairs": r.mixed_pairs_checked, "exact_distance": r.exact_x_distance,
                     "correction_bound": r.correction_bound, "digest": r.proof_digest})
    legacy = all_vertex_star_report(31)
    return {"passed": all(r["verified"] for r in rows) and legacy["logical_qubits"] == 0,
            "result": {"rows": rows, "all_vertex_star_convention": legacy}}


def bench_claim_boundary(quick: bool) -> Dict[str, Any]:
    from .capabilities import audit_claims, capability_report

    report = capability_report()
    probes = ["This is a physical quantum computer.", "A universal 10,000-qubit computer.",
              "It delivers a speedup of 100x.", "The VQC breaks SHA-256.", "We built a quantum device."]
    flagged = [bool(audit_claims(p)) for p in probes]
    # The audit is phrase-based; these paraphrases pass it and are recorded,
    # not hidden, as known limits of the lint.
    paraphrases = ["Universal quantum computation at 10,000 qubits.", "Delivers quantum speedup on mining."]
    return {"passed": bool(report.get("claim_boundary_clean")) and all(flagged),
            "result": {"claim_boundary_clean": report.get("claim_boundary_clean"),
                       "designed_overclaims_flagged": dict(zip(probes, flagged)),
                       "known_lint_gaps": {p: bool(audit_claims(p)) for p in paraphrases}}}


def bench_boundary_isolation(quick: bool) -> Dict[str, Any]:
    import kellogg
    import numpy
    import sympy

    pkg_parent = str(Path(__file__).resolve().parent.parent)
    paths = sorted({str(Path(m.__file__).resolve().parent.parent) for m in (kellogg, numpy, sympy)} | {pkg_parent})
    code = f"""
import sys, importlib, importlib.abc, pkgutil, json
sys.path[:0] = {paths!r}
BLOCK = {{'aethel','toe','chronus','mining','Intelligence','euclid','al_haras','hyba','salamander','tensor',
         'python_backend','mtheory','millennium','lucas','turing_core','pythia_turing_math'}}
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path, target=None):
        if name.split('.')[0] in BLOCK:
            raise ModuleNotFoundError('blocked sibling product: ' + name, name=name)
        return None
sys.meta_path.insert(0, Block())
import turing_universal_quantum_computer as T
from turing_universal_quantum_computer.product_registry import verify_registry
reg = verify_registry()
from turing_universal_quantum_computer.custody import open_custody, CustodyUnavailable
try:
    open_custody(); custody = 'opened'
except CustodyUnavailable:
    custody = 'CustodyUnavailable'
except Exception as e:
    custody = type(e).__name__
from turing_universal_quantum_computer.backends import execute
r = execute(T.Program(500).then('h',0).then('cx',0,499).then('t',0), marginal_of=[0,499])
print(json.dumps({{'registry_ok': reg['ok'], 'problems': reg['problems'], 'skipped': reg['skipped_for_extras'],
                  'custody_without_aethel': custody, 'mps_backend': r.backend,
                  'marginal': r.payload['marginal']['probabilities']}}))
"""
    out = subprocess.run([sys.executable, "-I", "-S", "-c", code], capture_output=True, text=True, timeout=900)
    if out.returncode != 0:
        return {"passed": False, "result": {"error": out.stderr[-1200:]}}
    res = json.loads(out.stdout.strip().splitlines()[-1])
    passed = (res["registry_ok"] and res["custody_without_aethel"] == "CustodyUnavailable"
              and res["mps_backend"] == "mps_exact" and res["marginal"] == {"00": "1/2", "11": "1/2"})
    return {"passed": passed, "result": res}


def bench_product_registry(quick: bool) -> Dict[str, Any]:
    from .product_registry import verify_registry

    report = verify_registry()
    return {"passed": report["ok"], "result": report}


def _digest_corpus() -> Dict[str, str]:
    from .backends import MPSExactBackend, execute
    from .surface_code_exact import verify_surface_code_algebra

    mps = MPSExactBackend().build(_ghz(2000, ("t", 0), ("s", 1999)))
    stab = execute(_ghz(1000), prefer="stabilizer").payload["stabilizer_generators"]
    dense = execute(_random_program(5, 25, 3), prefer="exact_algebraic").payload.get("amplitudes")
    return {
        "mps_ghz2000_root": mps.root,
        "mps_chain": mps.ledger.chain_digest,
        "stabilizer_ghz1000": digest(stab),
        "dense_random5": digest(_plain(dense)),
        "surface_d9": verify_surface_code_algebra(9).proof_digest,
    }


def bench_cross_version_digest(quick: bool) -> Dict[str, Any]:
    here = platform.python_version()
    rows = {here: digest(_digest_corpus())}
    paths = [p for p in os.environ.get("TURING_BENCH_PYTHONS", "").split(os.pathsep) if p]
    for path in paths:
        code = ("from turing_universal_quantum_computer.benchmark import _digest_corpus; "
                "from kellogg.benchmark import digest; import platform; "
                "print(platform.python_version(), digest(_digest_corpus()))")
        out = subprocess.run([path, "-c", code], capture_output=True, text=True, timeout=1800)
        if out.returncode == 0:
            version, value = out.stdout.strip().splitlines()[-1].split()
            rows[version] = value
        else:
            rows[path] = f"ERROR: {out.stderr[-200:]}"
    values = [v for v in rows.values() if len(v) == 64]
    return {"passed": None if len(values) < 2 else len(set(values)) == 1,
            "result": {"digests": rows, "compared_versions": len(values)}}


# -- cost --------------------------------------------------------------------------


def bench_stabilizer_throughput(quick: bool) -> Dict[str, Any]:
    from .backends import execute

    rows = []
    for n in ((100, 1000) if quick else (100, 1000, 10000)):
        program = _ghz(n)
        samples = timed(lambda: execute(program, prefer="stabilizer"), 3)
        shots = timed(lambda: execute(program, prefer="stabilizer", shots=128, seed=1, readout=[0, n - 1]), 1)
        rows.append({"n_qubits": n, "classification": "MEASURED", "execute": stats(samples),
                     "execute_with_128_shots": stats(shots)})
    return {"passed": True, "result": {"rows": rows, "backend": "stabilizer"}}


def bench_mps_throughput(quick: bool) -> Dict[str, Any]:
    from .backends import execute

    rows = []
    for n in ((100, 1000) if quick else (100, 1000, 10000)):
        program = _ghz(n, ("t", 0), ("s", n - 1))
        samples = timed(lambda: execute(program, prefer="mps_exact"), 1 if n >= 10000 else 3)
        marg = timed(lambda: execute(program, prefer="mps_exact", marginal_of=[0, n - 1]), 1)
        rows.append({"n_qubits": n, "classification": "MEASURED", "execute": stats(samples),
                     "execute_with_marginal": stats(marg)})
    return {"passed": True, "result": {"rows": rows, "backend": "mps_exact"}}


def bench_dense_throughput(quick: bool) -> Dict[str, Any]:
    from .backends import execute

    rows = []
    for n in ((4, 8) if quick else (4, 8, 12, 14)):
        program = _random_program(n, 4 * n, 11)
        samples = timed(lambda: execute(program, prefer="exact_algebraic"), 3 if n <= 12 else 1)
        rows.append({"n_qubits": n, "gates": len(program.operations), "classification": "MEASURED",
                     **stats(samples)})
    return {"passed": True, "result": {"rows": rows, "backend": "exact_algebraic"}}


# -- meta ----------------------------------------------------------------------------


def bench_ten_thousand_qubit_vqc_voyage(quick: bool) -> Dict[str, Any]:
    from .custody import theseus_available
    from .pipeline import VQCPipeline, VQCRequest

    n = 1000 if quick else 10_000
    program = _ghz(n, ("t", 0), ("s", n - 1))
    t = time.perf_counter_ns()
    report = VQCPipeline().run(VQCRequest(program=program, marginal_of=(0, n - 1), custody=True, replay=True))
    elapsed = time.perf_counter_ns() - t
    stages = {s.stage: s.state for s in report.stages}
    payload = (report.result or {}).get("payload", {})
    marginal = payload.get("marginal", {}).get("probabilities")
    computation_ok = (marginal == {"00": "1/2", "11": "1/2"} and payload.get("max_bond") == 2
                      and stages.get("execution") == "PASS" and stages.get("verification") == "PASS")
    if theseus_available():
        passed = (report.verdict == "PASS" and stages.get("replay") == "PASS"
                  and computation_ok)
        custody_reason = None
    else:
        # THESEUS custody is unavailable on this host: the voyage still proves
        # execution, measurement and verification, but the durability leg is
        # incomplete rather than failed.
        passed = None if computation_ok else False
        custody_reason = "theseus custody unavailable; durability leg not exercised"
    return {
        "passed": passed,
        "result": {"qubits": n, "gates": len(program.operations), "verdict": report.verdict,
                   "custody_leg": custody_reason,
                   "backend": (report.result or {}).get("backend"), "stages": stages,
                   "marginal": marginal, "max_bond": payload.get("max_bond"),
                   "norm_squared": payload.get("norm_squared"), "elapsed_ns": elapsed,
                   "gated_stages": [k for k, v in stages.items() if v == "GATED"]},
    }


def bench_quantum_library_lanes(quick: bool) -> Dict[str, Any]:
    """Exactness-audited lane evidence for the ``quantum_library`` facade.

    Each probe records the executing lane, its declared parameters, the
    ``audit_exactness`` verdict on the returned payload — "exact" means the
    payload tree was walked and holds no float atom, not merely that an
    exact-capable lane was selected — repetition statistics, and a canonical
    digest binding the whole payload.  Refusal probes must refuse: a call
    that returns instead is a contract violation, so it fails the row.
    """
    import sympy as sp

    from .quantum_library import QuantumLibrary as Q

    def probe(params: Dict[str, Any], fn, repeats: int = 3) -> Dict[str, Any]:
        res = fn()
        samples = timed(lambda: fn(), repeats)
        report = res.verify_exactness()
        return {
            "family": res.family,
            "lane": res.lane,
            "lane_owner": res.lane_owner,
            "params": params,
            "truth_class": res.truth_class,
            "exactness_audit": report.as_dict(),
            "payload_digest": digest(_plain(res.payload)),
            "classification": "MEASURED",
            "repeats": len(samples),
            **stats(samples),
        }

    def refusal(name: str, fn) -> Dict[str, Any]:
        try:
            fn()
        except Exception as exc:
            return {"probe": name, "refused": True,
                    "error_type": type(exc).__name__,
                    "reason": str(exc)[:200],
                    "classification": "MEASURED"}
        return {"probe": name, "refused": False, "classification": "MEASURED"}

    k4_edges = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]
    rows = [
        probe({}, lambda: Q.bell_pair()),
        probe({"n_qubits": 1024, "subset": [0]}, lambda: Q.ghz(1024, subset={0})),
        probe({"num_positions": 32, "steps": 200},
              lambda: Q.quantum_walk_cycle(32, 200), repeats=1),
        probe({"n_qubits": 64, "t": "pi/4"},
              lambda: Q.quantum_walk_hypercube(64, sp.pi / 4)),
        probe({"n_qubits": 10, "marked": 613}, lambda: Q.grover(10, marked=613)),
        probe({"phase_turns": "1/8", "counting_qubits": 3},
              lambda: Q.qpe(Fraction(1, 8), 3)),
        probe({"edges": "triangle", "layers": [["3/8", "1/8"]]},
              lambda: Q.qaoa_maxcut([(0, 1), (1, 2), (0, 2)],
                                    [(Fraction(3, 8), Fraction(1, 8))])),
        probe({"n_qubits": 2, "J": 1, "g": 1, "grid": 8},
              lambda: Q.vqe_ising_scan(2, J=1, g=1, grid=8)),
        probe({"n_qubits": 2, "ops": ["h 0", "cx 0 1"]},
              lambda: Q.execute_ops(2, [("h", 0), ("cx", 0, 1)])),
        probe({"n_qubits": 100, "ops": "h 0 + cx 0 k for k<100"},
              lambda: Q.execute_ops(
                  100, [("h", 0)] + [("cx", 0, k) for k in range(1, 100)])),
    ]
    if not quick:
        rows += [
            probe({"n_qubits": 10000, "subset": [0]},
                  lambda: Q.ghz(10_000, subset={0})),
            probe({"phase_turns": "1/16", "counting_qubits": 5},
                  lambda: Q.qpe(Fraction(1, 16), 5), repeats=1),
            probe({"edges": "K4", "p_layers": 1, "grid": 8},
                  lambda: Q.qaoa_maxcut_grid(k4_edges, p_layers=1, grid=8),
                  repeats=1),
        ]
    refusals = [
        refusal("irrational_turns",
                lambda: Q.qaoa_maxcut([(0, 1)], [(sp.pi, Fraction(1, 4))])),
        refusal("beyond_exact_budget",
                lambda: Q.execute_ops(
                    40,
                    [("h", q) for q in range(20)]
                    + [("t", 0)]
                    + [("cx", q, q + 20) for q in range(20)])),
        refusal("unknown_gate",
                lambda: Q.execute_ops(2, [("tooffoli", 0, 1, 2)])),
    ]
    exact_rows = all(r["exactness_audit"]["exact"] for r in rows)
    refused_rows = all(r["refused"] for r in refusals)
    return {
        "passed": exact_rows and refused_rows,
        "result": {
            "rows": rows,
            "refusals": refusals,
            "all_rows_audit_exact": exact_rows,
            "all_refusals_held": refused_rows,
        },
    }


BENCHMARKS: Dict[str, tuple] = {
    "backend_agreement": ("correctness", bench_backend_agreement),
    "refusal_boundary": ("correctness", bench_refusal_boundary),
    "certificates": ("correctness", bench_certificates),
    "pipeline_custody_replay": ("correctness", bench_pipeline_custody_replay),
    "surface_code": ("correctness", bench_surface_code),
    "claim_boundary": ("correctness", bench_claim_boundary),
    "boundary_isolation": ("correctness", bench_boundary_isolation),
    "product_registry": ("correctness", bench_product_registry),
    "cross_version_digest": ("correctness", bench_cross_version_digest),
    "quantum_library_lanes": ("correctness", bench_quantum_library_lanes),
    "stabilizer_throughput": ("cost", bench_stabilizer_throughput),
    "mps_throughput": ("cost", bench_mps_throughput),
    "dense_throughput": ("cost", bench_dense_throughput),
    "ten_thousand_qubit_vqc_voyage": ("meta", bench_ten_thousand_qubit_vqc_voyage),
}

REQUIRED_BENCHMARKS = frozenset(
    {"pipeline_custody_replay", "ten_thousand_qubit_vqc_voyage"}
)


def run(benchmark_id: str, *, quick: bool = False, prov: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    from kellogg.certificate import merkle_root

    axis, fn = BENCHMARKS[benchmark_id]
    prov = prov or provenance()
    config = {"benchmark_id": benchmark_id, "axis": axis, "quick": quick}
    t = time.perf_counter_ns()
    try:
        out = fn(quick)
        error = None
    except Exception as exc:  # recorded, never swallowed into a pass
        out = {"passed": False, "result": {}}
        error = f"{type(exc).__name__}: {exc}"
    elapsed = time.perf_counter_ns() - t
    result = _plain(out["result"])
    measurement = {"wall_ns": elapsed, **stats([elapsed])}
    body = {"schema": SCHEMA, "benchmark_id": benchmark_id, "axis": axis, **prov,
            "configuration": config, "measurement": measurement, "classification": "MEASURED",
            "passed": out["passed"], "error": error, "result": result}
    body["digest"] = digest(body)
    body["attestation"] = merkle_root([digest(config), digest(measurement), digest(result), digest(prov)])
    return body


def run_all(ids: Optional[Sequence[str]] = None, *, quick: bool = False, out_dir: Optional[str] = None,
            progress: Optional[Callable[[str, Dict[str, Any]], None]] = None) -> Dict[str, Any]:
    prov = provenance()
    artifacts = []
    for bid in (list(ids) if ids else list(BENCHMARKS)):
        art = run(bid, quick=quick, prov=prov)
        artifacts.append(art)
        if progress:
            progress(bid, art)
    summary = {
        "schema": SCHEMA + "#suite", "commit": prov["commit"], "quick": quick,
        "passed": [a["benchmark_id"] for a in artifacts if a["passed"] is True],
        "failed": [a["benchmark_id"] for a in artifacts if a["passed"] is False],
        "incomplete": [a["benchmark_id"] for a in artifacts if a["passed"] is None],
        "artifacts": artifacts,
    }
    summary["digest"] = digest({k: v for k, v in summary.items() if k != "artifacts"}
                               | {"artifact_digests": [a["digest"] for a in artifacts]})
    if out_dir is not None:
        out = Path(out_dir)
        (out / "archive").mkdir(parents=True, exist_ok=True)
        text = json.dumps(summary, indent=1, sort_keys=True, default=str)
        (out / "latest.json").write_text(text, encoding="utf-8")
        name = prov["commit"].replace("/", "_") + ("-quick" if quick else "")
        (out / "archive" / f"{name}.json").write_text(text, encoding="utf-8")
    return summary


def main(argv: Optional[Sequence[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="python -m turing_universal_quantum_computer.benchmark")
    parser.add_argument("ids", nargs="*")
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    def show(bid: str, art: Dict[str, Any]) -> None:
        state = {True: "PASS", False: "FAIL", None: "INCOMPLETE"}[art["passed"]]
        print(f"{bid:32s} {state:10s} {art['measurement']['wall_ns'] / 1e9:8.2f}s"
              + (f"  {art['error']}" if art["error"] else ""), flush=True)

    summary = run_all(args.ids or None, quick=args.quick, out_dir=args.out, progress=show)
    print(f"passed {len(summary['passed'])}, failed {len(summary['failed'])}, "
          f"incomplete {len(summary['incomplete'])}; digest {summary['digest'][:16]}")
    required_incomplete = sorted(set(summary["incomplete"]) & REQUIRED_BENCHMARKS)
    if required_incomplete:
        print("required benchmarks incomplete: " + ", ".join(required_incomplete))
    return 1 if summary["failed"] or required_incomplete else 0


if __name__ == "__main__":
    raise SystemExit(main())
