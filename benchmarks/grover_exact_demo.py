"""Benchmark 2 — Grover on the exact F4 = Q(zeta_8) substrate, n in {1,2,3}.

Every amplitude is an exact element of Q(sqrt(2)) + i Q(sqrt(2)): oracle
and diffusion are applied as real gates (H, X, Z, CZ, Toffoli). After each
iteration the exact marked Born weight is compared against the closed form
sin^2((2k+1)theta) — which is rational whenever sin^2(theta) = M/N is
rational — and the whole amplitude vector is folded into a SHA-256 digest
so an independent run can check equality bit-for-bit.

The classical-silicon limit table reports dense complex128 state memory
(analytic), measured per-iteration cost on this machine where feasible,
and extrapolated cost where not — extrapolated rows are labeled.
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
import time
from fractions import Fraction

from benchmarks.common import ROOT, SEED, env_fingerprint, write_report

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "turing_universal_quantum_computer"))


def _closed_form_probs(n: int, m: int, k_max: int) -> list[Fraction]:
    """P_k = sin^2((2k+1)theta), theta = asin(sqrt(M/N)) — exact rationals.

    A_k = sin((2k+1)theta) = s * B_k with s = sqrt(M/N),
    B_{-1} = -1, B_0 = 1, B_{k+1} = 2(1 - 2 M/N) B_k - B_{k-1}.
    """
    N = 1 << n
    s2 = Fraction(m, N)
    c = 2 * (1 - 2 * s2)  # 2*cos(2*theta), rational
    b_prev, b_cur = Fraction(-1), Fraction(1)
    out = [s2]
    for _ in range(k_max):
        b_next = c * b_cur - b_prev
        out.append(s2 * b_next * b_next)
        b_prev, b_cur = b_cur, b_next
    return out


def grover_f4(n: int, marked: list[int]) -> dict:
    """Exact Grover on kellogg.exact_tensor.ExactStateVector (gates only)."""
    from kellogg.exact_tensor import (
        GATES,
        ExactStateVector,
        MINUS_ONE,
        Qsqrt2,
    )

    N = 1 << n
    k_opt = max(1, int(math.floor(math.pi / 4.0 / math.asin(math.sqrt(len(marked) / N)))))

    def multi_cz(s: ExactStateVector) -> ExactStateVector:
        if n == 1:
            return s.apply_single(0, GATES["Z"])
        if n == 2:
            return s.apply_cz(0, 1)
        s = s.apply_single(2, GATES["H"])
        s = s.apply_toffoli(0, 1, 2)
        return s.apply_single(2, GATES["H"])

    def oracle(s: ExactStateVector, w: int) -> ExactStateVector:
        zeros = [q for q in range(n) if not (w >> q) & 1]
        for q in zeros:
            s = s.apply_single(q, GATES["X"])
        s = multi_cz(s)
        for q in zeros:
            s = s.apply_single(q, GATES["X"])
        return s

    def diffusion(s: ExactStateVector) -> ExactStateVector:
        for q in range(n):
            s = s.apply_single(q, GATES["H"])
        for q in range(n):
            s = s.apply_single(q, GATES["X"])
        s = multi_cz(s)
        for q in range(n):
            s = s.apply_single(q, GATES["X"])
        for q in range(n):
            s = s.apply_single(q, GATES["H"])
        # Global -1: circuit above computes -(2|s><s| - I); rescale to the
        # canonical iterate so the digest matches the textbook sequence.
        return ExactStateVector(n, tuple(a * MINUS_ONE for a in s.amplitudes))

    state = ExactStateVector.basis(n, 0)
    for q in range(n):
        state = state.apply_single(q, GATES["H"])
    assert state.normalized_exact()

    exact_p = _closed_form_probs(n, len(marked), k_opt)
    seq_hash = hashlib.sha256()
    steps = []
    for k in range(k_opt + 1):
        probs = state.probabilities_exact()
        p_marked = sum((probs[w] for w in marked), Qsqrt2())
        steps.append(
            {
                "k": k,
                "p_marked_exact": {
                    "a": str(p_marked.a),
                    "b": str(p_marked.b),
                },
                "p_marked_float": p_marked.to_float(),
                "closed_form": str(exact_p[k]),
                "closed_form_float": float(exact_p[k]),
                "exact_match": p_marked == Qsqrt2(exact_p[k]),
                "normalized": state.normalized_exact(),
            }
        )
        seq_hash.update(json.dumps([a.to_json() for a in state.amplitudes]).encode())
        if k < k_opt:
            for w in marked:
                state = oracle(state, w)
            state = diffusion(state)
    return {
        "n": n,
        "marked": marked,
        "k_opt": k_opt,
        "steps": steps,
        "state_seq_sha256": seq_hash.hexdigest(),
    }


def limit_table() -> list[dict]:
    """Memory is analytic; time is measured at n<=12 then extrapolated."""
    rows = []
    measured = {}
    for n in (10, 12):
        from kellogg.exact_tensor import ExactStateVector, GATES

        state = ExactStateVector.basis(n, 0, max_amplitudes=1 << 22)
        t0 = time.perf_counter()
        for q in range(n):
            state = state.apply_single(q, GATES["H"])
        wall = time.perf_counter() - t0
        measured[n] = wall
    # Per-iteration cost ~ c * 2^n; total ~ k* * c * 2^n ~ c' * 2^(3n/2).
    if 10 in measured and 12 in measured:
        per_amp = measured[12] / (4.0 * (1 << 12))
    else:
        per_amp = float("nan")
    for n in (10, 15, 20, 25):
        dim = 1 << n
        k = int(math.floor(math.pi / 4.0 * math.sqrt(dim)))
        row = {
            "n": n,
            "dimension": dim,
            "grover_k": k,
            "state_bytes_complex128": dim * 16,
            "state_gib": dim * 16 / (1 << 30),
            "per_iter_s_measured": measured.get(n),
        }
        if n in measured:
            row["total_s"] = k * measured[n] * 4  # diffusion ~ H-pass x4
            row["basis"] = "measured"
        else:
            row["total_s"] = k * per_amp * 4 * dim if per_amp == per_amp else None
            row["basis"] = "extrapolated from n=12 measurement"
        rows.append(row)
    return rows


def _subprocess_digest(n: int, marked: list[int]) -> str:
    # Subprocess runs the same module's grover_f4 in a fresh interpreter.
    code = (
        "import sys, json, math\n"
        f"sys.path.insert(0, {str(ROOT)!r})\n"
        "from benchmarks.grover_exact_demo import grover_f4\n"
        f"print(grover_f4({n}, {list(marked)})['state_seq_sha256'])\n"
    )
    env = {"PYTHONHASHSEED": "1234", "PATH": __import__("os").environ.get("PATH", "")}
    out = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=env,
        cwd=ROOT,
    )
    return out.stdout.strip()


def run() -> dict:
    runs = {n: grover_f4(n, [N - 1] if (N := 1 << n) else []) for n in (1, 2, 3)}
    # Second environment: separate interpreter process, different hash seed.
    replica = {}
    for n, marked in ((1, [1]), (2, [3]), (3, [7])):
        replica[n] = _subprocess_digest(n, marked)
    results = {
        "seed": SEED,
        "env": env_fingerprint(),
        "runs": {str(n): r for n, r in runs.items()},
        "replica_digests": {str(n): d for n, d in replica.items()},
        "limit_table": limit_table(),
    }
    return results


def render(results: dict) -> str:
    lines = [
        "# Grover exact-on-classical — F4 = Q(zeta_8) substrate",
        "",
        "Exact Born weights (Fraction arithmetic, no floats) vs closed form "
        "sin^2((2k+1)theta) at every iteration. Digest = SHA-256 over the "
        "serialized amplitude sequence.",
        "",
        "## Per-iteration exact equality",
        "",
    ]
    for n_str, r in results["runs"].items():
        ok = all(s["exact_match"] and s["normalized"] for s in r["steps"])
        lines.append(
            f"### n={n_str}, marked={r['marked']}, k*={r['k_opt']} — "
            f"{'EXACT at every iteration' if ok else 'MISMATCH'}"
        )
        lines.append("")
        lines.append("| k | P_marked (exact) | sin^2((2k+1)θ) | float |")
        lines.append("|---|---|---|---|")
        for s in r["steps"]:
            pe = s["p_marked_exact"]
            exact_repr = pe["a"] if pe["b"] == "0" else f"{pe['a']} + {pe['b']}√2"
            lines.append(
                f"| {s['k']} | {exact_repr} | {s['closed_form']} | " f"{s['p_marked_float']:.15f} |"
            )
        lines.append("")
    lines += [
        "## State-sequence digests (machine-invariance witness)",
        "",
        "| n | primary | replica (fresh interpreter) | match |",
        "|---|---|---|---|",
    ]
    for n_str, r in results["runs"].items():
        rep = results["replica_digests"].get(n_str, "")
        lines.append(
            f"| {n_str} | `{r['state_seq_sha256'][:24]}…` | `{rep[:24]}…` | "
            f"{'yes' if rep == r['state_seq_sha256'] else 'NO'} |"
        )
    lines += [
        "",
        "Replica = second Python interpreter (PYTHONHASHSEED=1234). Both "
        "digests ran on this machine — independent-machine replication is "
        "open; the digest is the value any second machine must reproduce.",
        "",
        "## Classical-silicon limit table (dense state vector)",
        "",
        "| n | dimension | Grover k* | complex128 state | est. total time | basis |",
        "|---|---|---|---|---|---|",
    ]
    for row in results["limit_table"]:
        total = "n/a" if row["total_s"] is None else _human_seconds(row["total_s"])
        lines.append(
            f"| {row['n']} | {row['dimension']:,} | {row['grover_k']:,} | "
            f"{row['state_gib']:.4f} GiB | {total} | {row['basis']} |"
        )
    lines += [
        "",
        "Memory is exact (16 B/amplitude). Time is measured at n=10,12 "
        "(exact-substrate H^{⊗n} pass) and extrapolated as ~2^(3n/2) "
        "elsewhere. n=20 sits exactly on the default 2^20 fail-closed "
        "amplitude bound; n=25 exceeds it — the substrate refuses rather "
        "than approximates.",
        "",
        f"Environment: {json.dumps(results['env'])}",
        "",
        "Data: `reports/data/grover_exact_demo.json`.",
    ]
    return "\n".join(lines) + "\n"


def _human_seconds(s: float) -> str:
    if s < 1:
        return f"{s*1e3:.1f} ms"
    if s < 3600:
        return f"{s:.1f} s"
    if s < 86400:
        return f"{s/3600:.1f} h"
    return f"{s/86400:.1f} d"


def main() -> None:
    results = run()
    path = write_report("grover_exact_demo", results, render(results))
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
