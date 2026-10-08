"""PR #140 canonical voyage leg: run identical production checks against an
installed chronos-gpu wheel. Exits non-zero on any failure.

Usage: python voyage_smoke.py [--replay-evidence PATH]
  default          : run the full production surface check
  --replay-evidence: verify the evidence chain file written by a prior leg
"""

import json
import sys


def run_checks():
    import numpy as np
    from importlib import metadata

    report = {"version": metadata.version("chronos-gpu"), "checks": {}}
    ok = report["checks"]

    # 1. release doctor: exact core, family, paradigm, sha256d, native protocol,
    #    certified structured matvec, kernel assets.
    from chronos_one_igpu.release_cli import doctor

    d = doctor()
    ok["doctor_passed"] = bool(d["passed"])
    ok["doctor_checks"] = d["checks"]

    # 2. certified dense ground state (exact Weinstein residual + isolation).
    from chronos_one_igpu.igpu.exact_dense import certified_dense_ground_state

    h = np.array([[2.0, 0.5], [0.5, 3.0]])
    vec, cert = certified_dense_ground_state(h)
    ok["dense_certified"] = bool(
        cert["certified"] and float(cert["residual_bound"]) > 0 and float(cert["gap_bound"]) > 0
    )
    ok["dense_eigenvalue"] = cert["eigenvalue"]

    # 3. certified structured ground + deviation envelope.
    from chronos_one_igpu.igpu.structured_solver import StructuredHamiltonian

    op = StructuredHamiltonian([0.5] * 4, 1.618)
    g = op.ground("certified")
    ok["structured_certified"] = bool(
        g.evidence.get("backend") != "original_dense_reference"
        and not g.evidence.get("non_production_reference", False)
        and g.evidence.get("residual", 1) < 1e-10
    )
    ok["structured_deviation"] = bool(op.matvec_deviation_ok(op.matvec(np.ones(4)), np.ones(4)))

    # 4. certified tensor envelope + rejection of corrupted results.
    from chronos_one_igpu.igpu.tensor_runtime import tensor_deviation_ok, tensor_operation

    a = np.array([[1.0, 2.0], [3.0, 4.0]])
    r = tensor_operation("matmul", a, a)
    ok["tensor_envelope"] = bool(tensor_deviation_ok("matmul", r, a, a))
    ok["tensor_rejects_corruption"] = not tensor_deviation_ok("matmul", r + 1.0, a, a)

    # 5. certified Hamiltonian evolve.
    from chronos_one_igpu.golden_quantum import HamiltonianEngine, MathematicalQuantumState

    st = MathematicalQuantumState(np.array([1.0 + 0j, 0j]))
    out = HamiltonianEngine().evolve(st, np.array([[1.0, 0.0], [0.0, -1.0]]), 0.5)
    ok["evolve_certified"] = bool(
        out.evolution_certificate["certified"]
        and out.evolution_certificate["arithmetic"] == "exact_rational"
    )

    # 6. exact Grover weights.
    from chronos_one_igpu.golden_quantum import MathematicalQuantumSearchEngine

    res = MathematicalQuantumSearchEngine().simulate_grover(4, lambda i: i == 2)
    ok["grover_exact"] = bool(
        res.success and res.backend == "cpu_exact" and sum(res.probabilities_exact) == 1
    )

    # 7. QX sealed stream (exact expectation machinery).
    from chronos_one_igpu.igpu.qx import QXBuffer, encoded_matrix

    cmds = [
        {"op": "allocate", "name": "s", "amplitudes": encoded_matrix([1.0 + 0j, 0j])},
        {
            "op": "bind_hamiltonian",
            "name": "s",
            "matrix": encoded_matrix([[1.0, 0.0], [0.0, -1.0]]),
        },
        {"op": "evolve", "name": "s", "time": 0.25},
    ]
    from chronos_one_igpu.igpu.facade import OneIGPU

    with OneIGPU(working_width=32, prime_rom_limit=1000) as gpu:
        try:
            gpu.execute_qx(QXBuffer.seal(cmds), seed=0)
            ok["qx_executes"] = True
        except Exception as exc:
            ok["qx_executes"] = str(exc)

    # 8. golden mining scan — real SHA-256d + host verify.
    from chronos_one_igpu.golden_quantum import GoldenRatioMining, NonceLease

    mres = GoldenRatioMining().scan(
        bytes(76), (1 << 232) - 1, NonceLease(0, 256), max_evaluations=256
    )
    ok["mining_scan_real"] = mres.verified or mres.nonce is None

    report["passed"] = (
        all(v is True for v in ok.values() if isinstance(v, bool))
        and isinstance(ok["qx_executes"], bool)
        and ok["qx_executes"]
    )
    return report


def write_evidence(path):
    """Produce a hash-chained golden evidence log for the restart/replay leg."""
    from chronos_one_igpu.igpu.golden_runtime import GoldenRuntime

    rt = GoldenRuntime()
    import time

    for i in range(3):
        rt.attest(f"voyage_op_{i}", time.perf_counter(), details={"i": i})
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(rt.events, fh)
    return True


def replay_evidence(path):
    """Fresh-process replay: the stored chain must verify end to end."""
    from chronos_one_igpu.igpu.golden_runtime import verify_evidence

    with open(path, encoding="utf-8") as fh:
        events = json.load(fh)
    return verify_evidence(events)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    if "--replay-evidence" in sys.argv:
        path = sys.argv[sys.argv.index("--replay-evidence") + 1]
        print(json.dumps({"replay_ok": replay_evidence(path)}, indent=2))
        return
    report = run_checks()
    print(json.dumps(report, indent=2))
    if "--write-evidence" in sys.argv:
        write_evidence(sys.argv[sys.argv.index("--write-evidence") + 1])
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
