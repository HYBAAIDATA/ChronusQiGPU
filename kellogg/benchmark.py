"""Kellogg benchmark suite — correctness first, cost second, one meta-benchmark.

Every result is a content-addressed ``TensorBenchmark`` artifact bound to the
commit, hardware and software it ran on. Each measured row is classified:

    MEASURED     timed or counted on this host, this run
    MODELED      computed from a declared model (e.g. bytes = n chi^2 d s)
    NOT_RUN      a grid cell outside the run's time or memory budget

Never TFLOPs, never hashrate, never "unlimited", never a theoretical value
reported as measured. Run ``python -m kellogg.benchmark [--quick] [ids...]``.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import random
import subprocess
import sys
import time
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

SCHEMA = "kellogg.tensor-benchmark/v1"


# -- provenance ----------------------------------------------------------------


def _git(args: Sequence[str]) -> Optional[str]:
    root = Path(__file__).resolve().parent.parent
    try:
        out = subprocess.run(
            ["git", "-C", str(root), *args], capture_output=True, text=True, timeout=10
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def commit_id() -> str:
    head = _git(["rev-parse", "HEAD"])
    if not head:
        return "UNAVAILABLE"
    dirty = _git(["status", "--porcelain", "--", "kellogg"])
    return head + ("-dirty" if dirty else "")


def _ram_gb() -> Optional[float]:
    try:
        if sys.platform == "win32":
            import ctypes

            class _Mem(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            mem = _Mem()
            mem.dwLength = ctypes.sizeof(_Mem)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))
            return round(mem.ullTotalPhys / 2**30, 2)
        return round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2**30, 2)
    except (AttributeError, OSError, ValueError):
        return None


def provenance() -> Dict[str, Any]:
    import numpy

    import kellogg

    return {
        "commit": commit_id(),
        "kellogg_version": kellogg.__version__,
        "hardware": {
            "cpu": platform.processor() or os.environ.get("PROCESSOR_IDENTIFIER") or "UNAVAILABLE",
            "cores": os.cpu_count(),
            "ram_gb": _ram_gb(),
            "gpu": None,
        },
        "software": {
            "os": platform.platform(),
            "python": platform.python_version(),
            "numpy": numpy.__version__,
        },
    }


# -- canonical encoding --------------------------------------------------------


def _plain(value: Any) -> Any:
    from .cyclotomic import Q8
    from .scales import Zphi
    from .substrate import QPhi

    if isinstance(value, bool) or value is None or isinstance(value, (int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    if isinstance(value, Fraction):
        return f"{value.numerator}/{value.denominator}"
    if isinstance(value, Q8):
        return f"q8:{value.canonical()}"
    if isinstance(value, Zphi):
        return f"zphi:{value.a},{value.b}"
    if isinstance(value, QPhi):
        return f"qphi:{value.a},{value.b}"
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if hasattr(value, "item"):
        return _plain(value.item())
    return str(value)


def _digest_bytes(value: Any) -> bytes:
    def hexfloat(v: Any) -> Any:
        if isinstance(v, float):
            return {"f": v.hex()}
        if isinstance(v, dict):
            return {k: hexfloat(x) for k, x in v.items()}
        if isinstance(v, list):
            return [hexfloat(x) for x in v]
        return v

    return json.dumps(hexfloat(value), sort_keys=True, separators=(",", ":")).encode()


def digest(value: Any) -> str:
    return hashlib.sha256(b"kellogg.benchmark/v1\0" + _digest_bytes(value)).hexdigest()


def stats(samples_ns: Sequence[int]) -> Dict[str, Any]:
    if not samples_ns:
        return {"samples": 0}
    ordered = sorted(int(s) for s in samples_ns)
    n = len(ordered)

    def rank(p: float) -> int:
        return ordered[min(n - 1, max(0, math.ceil(p * n) - 1))]

    return {
        "samples": n,
        "median_ns": rank(0.5),
        "p50_ns": rank(0.5),
        "p95_ns": rank(0.95),
        "p99_ns": rank(0.99),
        "min_ns": ordered[0],
        "max_ns": ordered[-1],
    }


def timed(fn: Callable[[], Any], repeats: int) -> List[int]:
    out = []
    for _ in range(max(1, repeats)):
        t = time.perf_counter_ns()
        fn()
        out.append(time.perf_counter_ns() - t)
    return out


# -- correctness (Axis 1) --------------------------------------------------------


def bench_fold_roundtrip(quick: bool) -> Dict[str, Any]:
    import numpy as np

    from .custody import CustodyError, FoldStoreCustody, ResidentCustody, default_custody
    from .cyclotomic import Q8
    from .dphi_transform import dphi_transform, golden_lifting_step, idphi_transform, inverse_golden_lifting_step
    from .exact_network import ExactTensorTrain

    rng = random.Random(20261007)
    providers = [ResidentCustody()]
    resolved = default_custody()
    if isinstance(resolved, FoldStoreCustody):
        providers.append(resolved)
    custody_rows = []
    for prov in providers:
        ok = 0
        trials = 40 if quick else 300
        for _ in range(trials):
            payload = bytes(rng.getrandbits(8) for _ in range(rng.randint(1, 4000)))
            ref = prov.put(payload)
            same = prov.get(ref) == payload
            prov.release(ref)
            try:
                prov.get(ref)
                fail_closed = False
            except CustodyError:
                fail_closed = True
            prov.regenerate(ref, payload)
            ok += same and fail_closed and prov.get(ref) == payload
        custody_rows.append({"provider": prov.provider, "trials": trials, "bit_exact": ok})
    nrng = np.random.default_rng(7)
    lift_ok = all(
        np.array_equal(a, inverse_golden_lifting_step(*golden_lifting_step(a, b))[0])
        for a, b in (
            (nrng.integers(-(2**40), 2**40, 233), nrng.integers(-(2**40), 2**40, 233))
            for _ in range(50)
        )
    )
    dphi_ok = all(
        np.array_equal(np.asarray(idphi_transform(dphi_transform(s, depth=d), depth=d)), s)
        for d in (1, 2, 3, 4)
        for s in [nrng.integers(-(2**30), 2**30, 610)]
    )

    def q() -> Q8:
        return Q8(rng.randint(-3, 3), rng.randint(-2, 2), rng.randint(-3, 3), rng.randint(-1, 1), rng.choice((1, 2, 4)))

    tt_ok = 0
    shapes = [(2, 3, 2, 2), (4, 4, 4), (2, 2, 2, 2, 2)]
    for dims in shapes:
        total = math.prod(dims)
        values = [q() for _ in range(total)]
        tt = ExactTensorTrain.from_dense(values, dims, custody=ResidentCustody())
        tt_ok += tt.to_dense() == values
    passed = (
        all(r["bit_exact"] == r["trials"] for r in custody_rows)
        and lift_ok
        and dphi_ok
        and tt_ok == len(shapes)
    )
    return {
        "passed": passed,
        "result": {
            "custody": custody_rows,
            "golden_lifting_bit_exact": lift_ok,
            "dphi_transform_bit_exact": dphi_ok,
            "exact_tt_roundtrip": f"{tt_ok}/{len(shapes)}",
            "note": "custody fold is a lossless partition; exact TT is lossless rank factorization",
        },
    }


def bench_tt_svd_error_bound(quick: bool) -> Dict[str, Any]:
    import numpy as np

    from .tensor_network import TensorTrain, tt_svd

    rng = np.random.default_rng(1)
    rows = []
    shapes = [(4, 4, 4, 4), (8, 8, 8), (16, 16, 4), (2,) * 12, (3, 5, 7, 2, 4)]
    if not quick:
        shapes += [(6, 6, 6, 6), (2,) * 16, (32, 32, 8)]
    for shape in shapes:
        x = rng.standard_normal(shape)
        for eps in (0.5, 1e-1, 1e-2, 1e-4, 1e-8):
            _, rec = tt_svd(x, eps)
            rows.append({"shape": list(shape), "eps": eps, "rel_error": rec["relative_error"],
                         "ranks": rec["ranks"], "holds": rec["bound_holds"]})
    s = np.array([1.0] + [0.099] * 99)
    u, _ = np.linalg.qr(rng.standard_normal((100, 100)))
    v, _ = np.linalg.qr(rng.standard_normal((100, 100)))
    adversarial = (u * s) @ v.T
    _, rec = tt_svd(adversarial, 0.1)
    legacy = TensorTrain(adversarial, max_rank=100, tolerance=0.1).relative_error(adversarial)
    return {
        "passed": all(r["holds"] for r in rows) and rec["bound_holds"],
        "result": {
            "cases": len(rows),
            "worst_error_over_eps": max(r["rel_error"] / r["eps"] for r in rows),
            "adversarial_tt_svd": {"rel_error": rec["relative_error"], "holds": rec["bound_holds"]},
            "legacy_TensorTrain_tolerance_0.1_rel_error": legacy,
            "rows": rows,
        },
    }


def _random_circuit(n: int, depth: int, seed: int, custody: Any):
    from .exact_network import ExactMPS

    rng = random.Random(seed)
    psi = ExactMPS.zeros(n, custody=custody)
    ops = []
    for _ in range(depth):
        if rng.random() < 0.55:
            q, g = rng.randrange(n), rng.choice(["H", "S", "T", "X", "Z", "Tdg", "Y"])
            psi.apply_1q(q, g)
            ops.append(("1q", q, g))
        else:
            a = rng.randrange(n - 1)
            psi.apply_2q(a, rng.choice(["CNOT", "CZ", "SWAP"]))
            ops.append(("2q", a))
    return psi, ops


def bench_mpo_preservation(quick: bool) -> Dict[str, Any]:
    from .channels import pauli_rotation
    from .custody import ResidentCustody
    from .cyclotomic import ONE8, ZERO8
    from .exact_network import ExactMPO, _gate_matrix

    rng = random.Random(3)
    trials = 6 if quick else 24
    preserved = unitary = 0
    for t in range(trials):
        n = rng.randint(3, 6)
        cust = ResidentCustody()
        psi, _ = _random_circuit(n, 4 * n, 100 + t, cust)
        if t % 2:
            ops = [_gate_matrix(rng.choice(["H", "S", "T", "X", "Y", "Z"]), 2) for _ in range(n)]
            mpo = ExactMPO.from_local([[list(r) for r in g] for g in ops], custody=cust)
        else:
            word = "".join(rng.choice("XYZ") for _ in range(n))
            mpo = pauli_rotation(word, Fraction(rng.randrange(8), 4), custody=cust)
        out = mpo.apply(psi)
        preserved += out.norm2() == psi.norm2()
        unitary += mpo.is_unitary()
    shear = ExactMPO.from_local([[[ONE8, ONE8], [ZERO8, ONE8]]] * 3, custody=ResidentCustody())
    negative = not shear.is_unitary()
    return {
        "passed": preserved == trials and unitary == trials and negative,
        "result": {
            "trials": trials,
            "norm_exactly_preserved": preserved,
            "is_unitary_exact": unitary,
            "non_unitary_detected": negative,
            "field": "Q(zeta8)",
        },
    }


def bench_kraus_trace(quick: bool) -> Dict[str, Any]:
    from .channels import (
        KrausChannel,
        amplitude_damping_half,
        channel_mpo,
        dephasing_half,
        depolarizing_full,
    )
    from .custody import ResidentCustody
    from .cyclotomic import ONE8, ZERO8

    chans = {
        "amplitude_damping_1/2": amplitude_damping_half(),
        "dephasing_1/2": dephasing_half(),
        "depolarizing_full": depolarizing_full(),
    }
    chans["ad_after_dephasing"] = chans["amplitude_damping_1/2"].compose(chans["dephasing_1/2"])
    chans["dep_after_ad"] = chans["depolarizing_full"].compose(chans["amplitude_damping_1/2"])
    rows = {
        name: {
            "trace_preserving": c.is_trace_preserving(),
            "stinespring_isometry": c.is_isometric_dilation(),
            "kraus_operators": len(c.ops),
            "kraus_rank": c.kraus_rank(),
        }
        for name, c in chans.items()
    }
    bad = KrausChannel.of([[[ONE8, ZERO8], [ZERO8, ONE8]], [[ZERO8, ONE8], [ZERO8, ZERO8]]])
    mpo = channel_mpo(list(chans.values())[:3], custody=ResidentCustody())
    passed = (
        all(r["trace_preserving"] and r["stinespring_isometry"] for r in rows.values())
        and not bad.is_trace_preserving()
        and not bad.is_isometric_dilation()
        and max(mpo.bonds()) == 1
    )
    return {
        "passed": passed,
        "result": {
            "channels": rows,
            "non_trace_preserving_rejected": not bad.is_trace_preserving(),
            "local_channel_mpo_bonds": mpo.bonds(),
            "check": "sum K^dagger K == I by exact equality",
        },
    }


def _digest_corpus() -> Dict[str, str]:
    from .custody import ResidentCustody
    from .exact_network import ghz_circuit
    from .substrate import cassini_step, lucas_wind
    from .surface_code import PlanarSurfaceCode

    psi = ghz_circuit(32, custody=ResidentCustody())
    circ, _ = _random_circuit(6, 30, 9, ResidentCustody())
    return {
        "ghz32_root": psi.root,
        "ghz32_chain": psi.ledger.chain_digest,
        "circuit_root": circ.root,
        "lucas": digest([lucas_wind(n) for n in range(300)]),
        "cassini": digest([cassini_step(n)["lucas_cassini"] for n in range(1, 200)]),
        "surface_d9": PlanarSurfaceCode(9).verify().digest,
    }


def bench_cross_version_digest(quick: bool) -> Dict[str, Any]:
    here = platform.python_version()
    corpus = _digest_corpus()
    mine = digest(corpus)
    rows = {here: mine}
    root = str(Path(__file__).resolve().parent.parent)
    extra = [p for p in os.environ.get("KELLOGG_BENCH_PYTHONS", "").split(os.pathsep) if p]
    targets = [(m, None) for m in ("3.11", "3.12", "3.13")] + [(None, p) for p in extra]
    for minor, path in targets:
        if minor is not None and here.startswith(minor):
            continue
        if path is not None:
            candidates = [[path]]
        elif sys.platform == "win32":
            candidates = [["py", f"-{minor}"]]
        else:
            candidates = [[f"python{minor}"]]
        found = None
        for cmd in candidates:
            try:
                probe = subprocess.run(
                    cmd + ["-c", "import sys; print(sys.version.split()[0])"],
                    capture_output=True, text=True, timeout=30,
                )
            except (OSError, subprocess.SubprocessError):
                continue
            if probe.returncode == 0:
                found = cmd
                label = probe.stdout.strip()
                break
        if found is None:
            rows[minor or path] = "NOT_RUN: interpreter not installed"
            continue
        if label == here:
            continue
        code = (
            f"import sys; sys.path.insert(0, {root!r}); "
            "from kellogg.benchmark import _digest_corpus, digest; print(digest(_digest_corpus()))"
        )
        out = subprocess.run(found + ["-c", code], capture_output=True, text=True, timeout=600)
        rows[label] = out.stdout.strip() if out.returncode == 0 else f"ERROR: {out.stderr[-200:]}"
    compared = [v for v in rows.values() if len(v) == 64]
    return {
        "passed": None if len(compared) < 2 else len(set(compared)) == 1,
        "result": {"digests": rows, "corpus": corpus, "compared_versions": len(compared)},
    }


def bench_determinism(quick: bool) -> Dict[str, Any]:
    import numpy as np

    from .attest import attest
    from .certificate import compose
    from .custody import ResidentCustody
    from .exact_network import ghz_circuit
    from .tensor_network import tt_svd

    a = ghz_circuit(64, custody=ResidentCustody())
    b = ghz_circuit(64, custody=ResidentCustody())
    c1, _ = _random_circuit(6, 40, 77, ResidentCustody())
    c2, _ = _random_circuit(6, 40, 77, ResidentCustody())
    x = np.random.default_rng(5).standard_normal((8, 8, 8))
    t1, _ = tt_svd(x, 1e-3)
    t2, _ = tt_svd(x, 1e-3)
    tt_same = all(np.array_equal(p, q) for p, q in zip(t1.cores, t2.cores))
    entries = a.ledger.entries
    composed = compose(entries[1], entries[2])
    checks = {
        "ghz_root": a.root == b.root,
        "ghz_ledger_chain": a.ledger.chain_digest == b.ledger.chain_digest,
        "circuit_root": c1.root == c2.root,
        "samples": a.sample(11) == b.sample(11),
        "tt_svd_cores": tt_same,
        "attest": attest({"x": 1}) == attest({"x": 1}),
        "compose_boundaries": composed.input_boundary == entries[1].input_boundary
        and composed.output_boundary == entries[2].output_boundary,
        "ledger_verifies": a.ledger.verify_chain(),
    }
    return {"passed": all(checks.values()), "result": checks}


def bench_boundary_isolation(quick: bool) -> Dict[str, Any]:
    import numpy

    pkg_parent = str(Path(__file__).resolve().parent.parent)
    np_parent = str(Path(numpy.__file__).resolve().parent.parent)
    code = f"""
import sys, importlib, importlib.abc, pkgutil, json
sys.path[:0] = [{pkg_parent!r}, {np_parent!r}]
BLOCK = {{'aethel','lucas','turing_core','toe','chronus','mining','Intelligence','pythia_turing_math',
         'turing_universal_quantum_computer','euclid','al_haras','hyba','salamander','tensor'}}
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path, target=None):
        if name.split('.')[0] in BLOCK:
            raise ModuleNotFoundError('blocked sibling product: ' + name)
        return None
sys.meta_path.insert(0, Block())
import kellogg
mods = sorted(m.name for m in pkgutil.iter_modules(kellogg.__path__))
failed = {{}}
for m in mods:
    try:
        importlib.import_module('kellogg.' + m)
    except Exception as e:
        failed[m] = type(e).__name__ + ': ' + str(e)[:120]
bad = [n for n in kellogg.__all__ if not hasattr(kellogg, n)]
from kellogg.custody import default_custody
from kellogg.phi_tensor_core import PhiTensorCore, FoldCustodyUnavailable, MetricTensor
try:
    PhiTensorCore(); core = 'constructed'
except FoldCustodyUnavailable:
    core = 'FoldCustodyUnavailable'
from kellogg.exact_network import ghz_circuit
psi = ghz_circuit(16)
print(json.dumps({{'modules': len(mods), 'failed': failed, 'unresolved_all': bad,
    'custody': default_custody().provider, 'phi_tensor_core_without_aethel': core,
    'metric_tensor': MetricTensor.phi_scaled(3) is not None, 'ghz16_bonds': psi.bonds()}}))
"""
    out = subprocess.run([sys.executable, "-I", "-S", "-c", code], capture_output=True, text=True, timeout=600)
    if out.returncode != 0:
        return {"passed": False, "result": {"error": out.stderr[-800:]}}
    res = json.loads(out.stdout.strip().splitlines()[-1])
    passed = (
        not res["failed"]
        and not res["unresolved_all"]
        and res["custody"] == "kellogg.resident"
        and res["phi_tensor_core_without_aethel"] == "FoldCustodyUnavailable"
    )
    return {"passed": passed, "result": res}


def bench_substrate_identities(quick: bool) -> Dict[str, Any]:
    from .scales import Zphi, lucas
    from .substrate import (
        QPhi,
        beta_expansion_value,
        cassini_step,
        cat_map,
        cat_map_inverse,
        cat_map_period,
        korobov_point,
        lucas_wind,
        parry_admissible,
        phi_beta_expansion,
        pisot_contracts,
        star_discrepancy_2d,
    )
    from .scales import fibonacci

    top = 200 if quick else 600
    lucas_ok = all(lucas_wind(n) == lucas(n) for n in range(top))
    cassini_ok = all(cassini_step(n)["fibonacci_holds"] and cassini_step(n)["lucas_holds"] for n in range(1, top))
    pisot_ok = all(pisot_contracts(n) for n in range(top // 3))
    rng = random.Random(2)
    beta_ok = True
    for _ in range(100 if quick else 400):
        x = Fraction(rng.randint(0, 999), 1000)
        d, r = phi_beta_expansion(x, 30)
        beta_ok &= parry_admissible(d) and beta_expansion_value(d, r) == QPhi(x)
    sign_ok = all(
        Zphi(a, b).sign() == ((a + b * 1.618033988749895 > 0) - (a + b * 1.618033988749895 < 0))
        for a, b in ((rng.randint(-10**6, 10**6), rng.randint(-10**6, 10**6)) for _ in range(2000))
    )
    q = 89
    cat_ok = len({cat_map((x, y), q) for x in range(q) for y in range(q)}) == q * q and all(
        cat_map_inverse(cat_map((x, y), q), q) == (x, y) for x in range(q) for y in range(q)
    )
    korobov = []
    for k in (range(8, 12) if quick else range(8, 15)):
        pts = [korobov_point(i, k) for i in range(fibonacci(k))]
        dstar = star_discrepancy_2d(pts)
        n = len(pts)
        korobov.append({"k": k, "N": n, "D*": dstar, "D*N/lnN": float(dstar) * n / math.log(n)})
    return {
        "passed": lucas_ok and cassini_ok and pisot_ok and beta_ok and sign_ok and cat_ok,
        "result": {
            "lucas_trace_n_lt": top,
            "lucas_trace": lucas_ok,
            "cassini_fibonacci_and_lucas": cassini_ok,
            "lucas_cassini_sign": "5(-1)^(n+1); the 5(-1)^n form fails at n=1",
            "pisot_contraction": pisot_ok,
            "beta_expansion_exact_and_parry": beta_ok,
            "zphi_sign_vs_float": sign_ok,
            "cat_map_bijection_q89": cat_ok,
            "pisano_period_10": cat_map_period(10),
            "korobov": korobov,
        },
    }


def bench_zeckendorf_roundtrip(quick: bool) -> Dict[str, Any]:
    from .scales import fibonacci, lucas, zeckendorf, zeckendorf_is_legal

    top = 10**4 if quick else 10**6
    fibs = [fibonacci(k) for k in range(64)]
    ok = 0
    for n in range(1, top + 1):
        idx = zeckendorf(n)
        ok += zeckendorf_is_legal(idx) and sum(fibs[k] for k in idx) == n
    return {"passed": ok == top and lucas(15) == 1364, "result": {"n_max": top, "roundtrip": ok, "L15": lucas(15)}}


def bench_surface_code_algebra(quick: bool) -> Dict[str, Any]:
    from .surface_code import PlanarSurfaceCode, edge_star_report

    rows = []
    for d in ((3, 5, 7) if quick else (3, 5, 7, 9, 15, 31)):
        t = time.perf_counter_ns()
        r = PlanarSurfaceCode(d).verify()
        row = dict(r.__dict__)
        row["elapsed_ns"] = time.perf_counter_ns() - t
        rows.append(row)
    legacy = edge_star_report(31 if not quick else 7)
    return {
        "passed": all(r["verified"] for r in rows) and legacy["logical_qubits"] == 0,
        "result": {"codes": rows, "all_vertex_star_convention": legacy},
    }


def bench_surface_code_correction(quick: bool) -> Dict[str, Any]:
    import itertools

    from .surface_code import PlanarSurfaceCode

    rows = []
    for d in (3, 5):
        c = PlanarSurfaceCode(d)
        t_max = (d - 1) // 2
        total = exact_ok = uf_ok = 0
        for w in range(1, t_max + 1):
            for qs in itertools.combinations(range(c.n), w):
                e = sum(1 << q for q in qs)
                s = c.syndrome(c.hz, e)
                total += 1
                exact_ok += c.corrected(e, c.decode_exact(s))
                uf_ok += c.corrected(e, c.decode_union_find(s))
        rows.append({"distance": d, "mode": "exhaustive", "errors": total,
                     "exact_mwpm": exact_ok, "union_find": uf_ok})
    c7 = PlanarSurfaceCode(7)
    rows.append(dict(c7.correction_trials(3, 300 if quick else 3000, 11), mode="random", decoder="union_find"))
    c31 = PlanarSurfaceCode(31)
    trials = 10 if quick else 200
    t = time.perf_counter_ns()
    r31 = c31.correction_trials(15, trials, 2026)
    per = (time.perf_counter_ns() - t) // trials
    rows.append(dict(r31, mode="random", decoder="union_find", ns_per_decode=per))
    exhaustive_ok = all(r["exact_mwpm"] == r["errors"] == r["union_find"] for r in rows[:2])
    random_ok = all(r["corrected"] == r["trials"] for r in rows[2:])
    return {
        "passed": exhaustive_ok and random_ok,
        "result": {
            "rows": rows,
            "theorem": "exact distance d implies every minimum-weight decoder corrects weight <= (d-1)//2",
        },
    }


def _frame_directions():
    from .substrate import QPhi

    p = QPhi(0, 1)
    ip = p.inverse()
    ico, dod = [], []
    for s1 in (-1, 1):
        for s2 in (-1, 1):
            ico += [(QPhi(0), QPhi(s1), s2 * p), (QPhi(s1), s2 * p, QPhi(0)), (s1 * p, QPhi(0), QPhi(s2))]
    for s1 in (-1, 1):
        for s2 in (-1, 1):
            for s3 in (-1, 1):
                dod.append((QPhi(s1), QPhi(s2), QPhi(s3)))
    for s1 in (-1, 1):
        for s2 in (-1, 1):
            dod += [(QPhi(0), s1 * p, s2 * ip), (s1 * p, s2 * ip, QPhi(0)), (s1 * ip, QPhi(0), s2 * p)]
    return ico + dod


def bench_vector11_fold(quick: bool) -> Dict[str, Any]:
    from .vector11 import fold, fold_certificate, lift, unit_lift
    from .substrate import QPhi

    phi = (1 + 5**0.5) / 2
    dirs = _frame_directions()
    ok = 0
    worst = 0.0
    for d in dirs:
        v = unit_lift(d)
        cert = fold_certificate(v)
        ok += cert["inside_unit_ball"] and cert["roundtrip_exact"]
        f = [float(x.a) + float(x.b) * phi for x in d]
        nrm = math.sqrt(sum(x * x for x in f))
        lifted = [f[i % 3] / nrm * phi ** (-(i // 3)) for i in range(11)]
        wn = sum(phi ** (-(i + 1)) * x * x for i, x in enumerate(lifted))
        ref = [x / math.sqrt(1 + wn) for x in lifted]
        worst = max(worst, max(abs(a - b) for a, b in zip(fold(v).to_float(), ref)))
    rng = random.Random(4)
    big = 0
    for _ in range(50):
        v = lift([QPhi(rng.randint(-10**6, 10**6), rng.randint(-50, 50)) for _ in range(3)])
        big += fold_certificate(v)["roundtrip_exact"] and fold(v).inside_unit_ball()
    return {
        "passed": ok == len(dirs) and big == 50 and worst < 1e-12,
        "result": {"frame_directions": len(dirs), "exact_roundtrip_and_ball": ok,
                   "random_large_vectors": big, "max_abs_vs_float_formula": worst, "field": "Q(phi)"},
    }


def bench_fisher_exact(quick: bool) -> Dict[str, Any]:
    from . import exact_linalg as la
    from .channels import (
        PauliHamiltonian,
        fisher_matrix,
        heisenberg_bound_holds,
        quantum_fisher_information,
        total_z_half,
    )
    from .custody import ResidentCustody
    from .cyclotomic import Q8
    from .exact_network import ExactMPS, ghz_circuit

    rows = []
    for n in ((2, 4, 8) if quick else (2, 4, 8, 16, 32)):
        g = ghz_circuit(n, custody=ResidentCustody())
        f = quantum_fisher_information(g, total_z_half(n, custody=ResidentCustody()))
        p = ExactMPS.zeros(n, custody=ResidentCustody())
        for i in range(n):
            p.apply_1q(i, "H")
        fp = quantum_fisher_information(p, total_z_half(n, custody=ResidentCustody()))
        rows.append({"n": n, "ghz_qfi": f, "ghz_equals_n2": f == Q8(n * n), "product_qfi": fp,
                     "product_equals_n": fp == Q8(n), "heisenberg_bound": heisenberg_bound_holds(f, n)})
    gens = [total_z_half(3, custody=ResidentCustody()),
            PauliHamiltonian.of(3, [(1, "XII")]).mpo(custody=ResidentCustody())]
    fm = fisher_matrix(ghz_circuit(3, custody=ResidentCustody()), gens)
    return {
        "passed": all(r["ghz_equals_n2"] and r["product_equals_n"] and r["heisenberg_bound"] for r in rows)
        and la.is_psd(fm),
        "result": {"rows": rows, "fisher_matrix_psd": la.is_psd(fm), "field": "Q(sqrt2)"},
    }


def bench_hamiltonian_exact(quick: bool) -> Dict[str, Any]:
    from functools import reduce

    import numpy as np

    from .channels import PauliHamiltonian, pauli_rotation
    from .custody import ResidentCustody
    from .exact_network import ExactMPO, heisenberg_mpo, ising_mpo
    from .exact_tensor import NotInF4
    from .tensor_network import HeisenbergHamiltonianMPO

    h = PauliHamiltonian.of(4, [(1, "ZZII"), (1, "IZZI"), (1, "IIZZ"), (Fraction(1, 2), "XIII"),
                                (Fraction(1, 2), "IXII"), (Fraction(1, 2), "IIXI"), (Fraction(1, 2), "IIIX")])
    mp = h.mpo(custody=ResidentCustody())
    full = ExactMPO.from_matrix(h.matrix(), 4, custody=ResidentCustody())
    hs = mp.hs_inner(mp) - mp.hs_inner(full) - full.hs_inner(mp) + full.hs_inner(full)
    rot = [pauli_rotation("XZY", Fraction(k, 4), custody=ResidentCustody()).is_unitary() for k in range(8)]
    try:
        pauli_rotation("Z", Fraction(1, 7))
        refused = False
    except NotInF4:
        refused = True
    sx = 0.5 * np.array([[0, 1], [1, 0]], complex)
    sy = 0.5 * np.array([[0, -1j], [1j, 0]])
    sz = 0.5 * np.diag([1, -1]).astype(complex)
    eye = np.eye(2)

    def explicit(n: int) -> Any:
        out = np.zeros((2**n, 2**n), complex)
        for i in range(n - 1):
            for s in (sx, sy, sz):
                out += reduce(np.kron, [s if k in (i, i + 1) else eye for k in range(n)])
        return out

    heis_fixed = all(np.allclose(HeisenbergHamiltonianMPO(n).to_full_matrix(), explicit(n), atol=1e-14)
                     for n in (2, 3, 5, 7))
    checks = {
        "pauli_sum_mpo_equals_matrix_mpo": hs.is_zero(),
        "pauli_sum_hermitian": mp.is_hermitian(),
        "ising_mpo_hermitian": ising_mpo(5, custody=ResidentCustody()).is_hermitian(),
        "heisenberg_mpo_hermitian": heisenberg_mpo(4, custody=ResidentCustody()).is_hermitian(),
        "rotations_unitary_on_pi_over_4_grid": all(rot),
        "pi_over_7_refused": refused,
        "float_heisenberg_mpo_equals_explicit_sum": heis_fixed,
    }
    return {"passed": all(checks.values()), "result": checks}


def bench_dmrg_vs_dense(quick: bool) -> Dict[str, Any]:
    from .dmrg import chain_mpo, dense_ground_energy, dmrg

    cases = [("heisenberg", 8, {}), ("ising", 10, {"coupling": 1.0, "field": 1.0})]
    if not quick:
        cases += [("heisenberg", 10, {}), ("ising", 12, {"coupling": 1.0, "field": 0.5})]
    rows = []
    for kind, n, kw in cases:
        m = chain_mpo(kind, n, **kw)
        t = time.perf_counter_ns()
        r = dmrg(m, chi_max=32, sweeps=10)
        rows.append({"model": kind, "n": n, "params": kw, "dmrg": r.energy, "dense": dense_ground_energy(m),
                     "abs_diff": abs(r.energy - dense_ground_energy(m)), "sweeps": r.sweeps,
                     "max_bond": max(r.bonds), "truncation_weight": r.max_truncation_weight,
                     "elapsed_ns": time.perf_counter_ns() - t})
    return {"passed": all(r["abs_diff"] < 1e-9 for r in rows), "result": {"rows": rows, "plane": "float64"}}


# -- cost (Axis 2) -----------------------------------------------------------------


def _uniform_mps(n: int, chi: int, seed: int, custody: Any):
    """Uniform random MPS: one bulk core repeated (one custody block)."""
    from .cyclotomic import Q8
    from .exact_network import Core, ExactMPS

    rng = random.Random(seed)

    def q() -> Q8:
        return Q8(rng.randint(-3, 3), rng.randint(-2, 2), rng.randint(-3, 3), rng.randint(-2, 2), 1)

    bulk = Core(chi, 2, chi, tuple(q() for _ in range(chi * 2 * chi)))
    first = Core(1, 2, chi, tuple(q() for _ in range(2 * chi)))
    last = Core(chi, 2, 1, tuple(q() for _ in range(2 * chi)))
    cores = [first] + [bulk] * (n - 2) + [last]
    return ExactMPS(cores, custody=custody, genesis={"uniform": [n, chi, seed]})


def _grid(quick: bool):
    if quick:
        return (50, 200), (2, 4, 8)
    return (100, 1000, 10000), (16, 64, 256, 1024)


def _guarded_sweep(
    chis: Sequence[int],
    sample: Callable[[int], int],
    repeats: int,
    cell_budget_ns: float,
    label: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Measure ascending chi; once one sample exceeds the cell budget, stop the sweep.

    The first sample of every cell is timed alone. A cell whose first sample
    already exceeds the budget keeps that single MEASURED sample, and every
    larger chi in the row is NOT_RUN with the reason recorded. Exact
    arithmetic on random cores grows its integers with the work done, so
    cost is measured, never extrapolated into a MEASURED row.
    """
    rows: List[Dict[str, Any]] = []
    stopped: Optional[int] = None
    for chi in chis:
        if stopped is not None:
            rows.append({**label, "chi": chi, "classification": "NOT_RUN",
                         "reason": f"chi={stopped} exceeded the {cell_budget_ns / 1e9:.0f}s cell budget"})
            continue
        first = sample(chi)
        samples = [first]
        if first <= cell_budget_ns / max(1, repeats):
            samples += [sample(chi) for _ in range(repeats - 1)]
        else:
            stopped = chi
        rows.append({**label, "chi": chi, "classification": "MEASURED", **stats(samples),
                     "operations_per_second": 1e9 / stats(samples)["median_ns"]})
    return rows


def bench_mps_gate_throughput(quick: bool) -> Dict[str, Any]:
    from .custody import ResidentCustody

    ns, chis = _grid(quick)
    budget = 3e9 if quick else 60e9
    rows: List[Dict[str, Any]] = []
    for n in ns:
        site = n // 2
        cache: Dict[int, Any] = {}

        def one_q(chi: int) -> int:
            psi = cache.get(chi)
            if psi is None:
                psi = cache[chi] = _uniform_mps(n, chi, 1, ResidentCustody())
            t = time.perf_counter_ns()
            psi.apply_1q(site, "T")
            return time.perf_counter_ns() - t

        def two_q(chi: int, _k: List[int] = [0]) -> int:
            _k[0] += 1
            psi = _uniform_mps(n, chi, 2 + _k[0], ResidentCustody())
            t = time.perf_counter_ns()
            psi.apply_2q(site - 1, "CNOT")
            return time.perf_counter_ns() - t

        rows += _guarded_sweep(chis, one_q, 7 if quick else 21, budget, {"n": n, "gate": "1q T"})
        rows += _guarded_sweep(chis, two_q, 3 if quick else 5, budget, {"n": n, "gate": "2q CNOT"})
    return {"passed": True, "result": {
        "rows": rows, "field": "Q(zeta8)",
        "state": "uniform MPS with a random bulk core (worst case for exact elimination)",
        "note": "a gate touches one or two cores, so its cost depends on chi, not n; the 2q split "
                "is an exact rank factorization whose integers grow with chi",
    }}


def bench_mps_contraction_throughput(quick: bool) -> Dict[str, Any]:
    from .custody import ResidentCustody

    ns, chis = _grid(quick)
    budget = 3e9 if quick else 60e9
    rows: List[Dict[str, Any]] = []
    previous: Optional[tuple] = None
    for n in ns:
        if previous is not None:
            prev_n, prev_ns = previous
            predicted = prev_ns * (n / prev_n) ** 2
            if predicted > 4 * budget:
                rows += [{"n": n, "operation": "<psi|psi>", "chi": chi, "classification": "NOT_RUN",
                          "modeled_ns_at_smallest_chi": int(predicted) if chi == chis[0] else None,
                          "model": "exact integers grow with n: cost ~ n^2 chi^3, scaled from "
                                   f"n={prev_n}"} for chi in chis]
                continue

        def contract(chi: int) -> int:
            psi = _uniform_mps(n, chi, 3, ResidentCustody())
            psi.window = n + 2
            t = time.perf_counter_ns()
            psi.inner(psi)
            return time.perf_counter_ns() - t

        row = _guarded_sweep(chis, contract, 3, budget, {"n": n, "operation": "<psi|psi>"})
        rows += row
        if row and row[0]["classification"] == "MEASURED":
            previous = (n, row[0]["median_ns"])
    from .exact_network import ghz_circuit

    structured = []
    for n in ns:
        psi = ghz_circuit(n, custody=ResidentCustody())
        samples = timed(lambda: psi.inner(psi), 3)
        structured.append({"n": n, "state": "ghz", "chi": 2, "classification": "MEASURED", **stats(samples)})
    return {"passed": True, "result": {
        "rows": rows, "structured_rows": structured, "field": "Q(zeta8)",
        "note": "exact contraction of a random MPS yields an exact norm whose size grows with n; "
                "structured states (GHZ) stay small",
    }}


def bench_tt_svd_cost(quick: bool) -> Dict[str, Any]:
    import numpy as np

    from .tensor_network import tt_svd

    rng = np.random.default_rng(6)
    rows = []
    sizes = (4, 16, 64) if quick else (4, 16, 64, 256)
    for size in sizes:
        x = rng.standard_normal((size, size))
        for rank in (2, 4, 8, 16, 32, 64):
            if rank > size:
                continue
            samples = timed(lambda: tt_svd(x, 0.0, max_rank=rank), 5)
            _, rec = tt_svd(x, 0.0, max_rank=rank)
            rows.append({"shape": [size, size], "rank": rank, "classification": "MEASURED", **stats(samples),
                         "relative_error": rec["relative_error"]})
    return {"passed": True, "result": {"rows": rows, "plane": "float64"}}


def bench_compression_fidelity(quick: bool) -> Dict[str, Any]:
    import numpy as np

    from .custody import ResidentCustody
    from .exact_network import ExactTensorTrain, ghz_circuit
    from .tensor_network import tt_svd

    n = 10 if quick else 14
    rng = np.random.default_rng(8)
    product = np.ones(1)
    for _ in range(n):
        v = rng.standard_normal(2) + 1j * rng.standard_normal(2)
        product = np.kron(product, v / np.linalg.norm(v))
    ghz = np.zeros(2**n, complex)
    ghz[0] = ghz[-1] = 2**-0.5
    cores = [rng.standard_normal((1 if i == 0 else 4, 2, 1 if i == n - 1 else 4)) for i in range(n)]
    rmps = cores[0]
    for c in cores[1:]:
        rmps = np.tensordot(rmps, c, axes=([-1], [0]))
    rmps = rmps.reshape(-1)
    rmps /= np.linalg.norm(rmps)
    dense = rng.standard_normal(2**n) + 1j * rng.standard_normal(2**n)
    dense /= np.linalg.norm(dense)
    rows = []
    for name, state in (("product", product), ("ghz", ghz), ("random_mps_chi4", rmps), ("random_dense", dense)):
        for eps in (1e-3, 1e-6, 1e-9, 1e-12):
            train, rec = tt_svd(state.reshape((2,) * n), eps)
            approx = train.reconstruct().reshape(-1)
            fidelity = float(abs(np.vdot(state, approx)) ** 2 / (np.vdot(approx, approx).real or 1.0))
            params = sum(c.size for c in train.cores)
            rows.append({"state": name, "eps": eps, "plane": "float64", "max_rank": max(rec["ranks"]),
                         "representation_ratio": 2**n / params, "relative_error": rec["relative_error"],
                         "fidelity": fidelity, "bound_holds": rec["bound_holds"]})
    exact_rows = []
    for name, psi in (("ghz", ghz_circuit(n, custody=ResidentCustody())),):
        exact_rows.append({"state": name, "plane": "Q(zeta8)", "relative_error": 0,
                           "representation_ratio": 2**n / psi.parameter_count(), "bonds": psi.bonds(),
                           "custody_blocks": psi.unique_blocks()})
    from .cyclotomic import Q8

    vals = [Q8(int(round(v.real * 8)), 0, int(round(v.imag * 8)), 0, 8) for v in rmps * 8]
    ett = ExactTensorTrain.from_dense(vals, [2] * n, custody=ResidentCustody())
    exact_rows.append({"state": "random_mps_chi4 (rounded to Q(i)/8)", "plane": "Q(zeta8)",
                       "relative_error": 0 if ett.to_dense() == vals else "MISMATCH",
                       "representation_ratio": 2**n / ett.parameter_count(), "bonds": ett.bonds()})
    return {
        "passed": all(r["bound_holds"] for r in rows),
        "result": {"qubits": n, "rows": rows, "exact_rows": exact_rows,
                   "claim_boundary": "representation ratio = 2^n / stored parameters; not physical compression"},
    }


def bench_exact_field_cost(quick: bool) -> Dict[str, Any]:
    from .cyclotomic import Q8
    from .exact_tensor import F4
    from .scales import Zphi
    from .substrate import QPhi

    reps = 2000 if quick else 100000
    a, b = Fraction(7, 3), Fraction(-5, 11)
    fields = {
        "Q (Fraction)": (a, b, lambda x: x, lambda x: x * x),
        "Q(i) (Q8)": (Q8(7, 0, 2, 0, 3), Q8(-5, 0, 3, 0, 11), Q8.conjugate, Q8.norm2),
        "Q(sqrt2) (Q8)": (Q8(7, 2, 0, 0, 3), Q8(-5, 3, 0, 0, 11), Q8.conjugate, Q8.norm2),
        "Q(zeta8) (Q8)": (Q8(7, 2, 1, -3, 3), Q8(-5, 3, 2, 1, 11), Q8.conjugate, Q8.norm2),
        "Q(zeta8) (F4)": (F4(a, b, Fraction(1, 3), Fraction(-1)), F4(b, a, Fraction(2, 11), Fraction(1, 11)),
                          F4.conjugate, F4.norm2),
        "Z[phi] (Zphi)": (Zphi(7, 3), Zphi(-5, 2), Zphi.conjugate, Zphi.norm),
        "Q(phi) (QPhi)": (QPhi(a, b), QPhi(b, a), QPhi.conjugate, QPhi.norm),
    }
    rows = []
    for name, (x, y, cj, nm) in fields.items():
        ops = {"add": lambda: x + y, "mul": lambda: x * y, "conj": lambda: cj(x), "norm": lambda: nm(x)}
        if not name.startswith("Z[phi]"):
            ops["div"] = lambda: x / y
        for op, fn in ops.items():
            t = time.perf_counter_ns()
            for _ in range(reps):
                fn()
            per = (time.perf_counter_ns() - t) / reps
            rows.append({"field": name, "op": op, "classification": "MEASURED", "mean_ns": round(per, 1),
                         "repeats": reps})
    return {"passed": True, "result": {"rows": rows,
                                       "note": "Z[phi] is a ring: division leaves it, so no div row"}}


def bench_certificate_emission(quick: bool) -> Dict[str, Any]:
    from .certificate import MerkleTree, cex, certify
    from .custody import ResidentCustody
    from .exact_network import ghz_circuit

    rows = []
    for n in ((100, 1000) if quick else (100, 1000, 10000)):
        psi = ghz_circuit(n, custody=ResidentCustody())
        psi.compress()
        samples_by_op: Dict[str, Any] = {}
        for cert in psi.ledger.entries:
            samples_by_op.setdefault(cert.op, cert)
        for op, cert in samples_by_op.items():
            samples = timed(
                lambda: certify(cert.op, cert.field, cert.machine_type, cert.input_boundary,
                                cert.output_boundary, cert.parameters, cert.invariants),
                200 if quick else 1000,
            )
            rows.append({"n_qubits": n, "operation": op, "classification": "MEASURED", **stats(samples),
                         "size_bytes": len(cex(cert.to_dict()))})
        tree = MerkleTree(psi.refs)
        leaf = psi.refs[0]
        samples = timed(lambda: tree.update(n // 2, leaf), 500)
        rows.append({"n_qubits": n, "operation": "state_root_update", "classification": "MEASURED",
                     **stats(samples), "model": "O(log n) Merkle path"})
        rows.append({"n_qubits": n, "operation": "ledger_total", "classification": "MEASURED",
                     "certificates": psi.ledger.count,
                     "ledger_bytes": sum(len(cex(c.to_dict())) for c in psi.ledger.entries)})
    return {"passed": True, "result": {"rows": rows}}


def bench_memory_footprint(quick: bool) -> Dict[str, Any]:
    import numpy as np

    from .custody import ResidentCustody
    from .exact_network import encode_core, ghz_circuit

    rows = []
    for n in ((100, 1000) if quick else (100, 1000, 10000)):
        cust = ResidentCustody()
        psi = ghz_circuit(n, custody=cust)
        acc = cust.accounting()
        window = sum(len(encode_core(c)) for c in psi._cache.values())
        rows.append({"state": f"ghz_{n}", "plane": "Q(zeta8)", "classification": "MEASURED",
                     "parameters": psi.parameter_count(), "custody_blocks": psi.unique_blocks(),
                     "custody_resident_bytes": acc["resident_bytes"],
                     "custody_released_bytes": acc["released_bytes"],
                     "resident_window_payload_bytes": window, "certificates": psi.ledger.count})
    for chi in ((4, 16) if quick else (16, 64, 256)):
        psi = _uniform_mps(64, chi, 5, ResidentCustody())
        bulk = len(encode_core(psi.core(1)))
        rows.append({"state": f"uniform_random_chi{chi}", "plane": "Q(zeta8)", "classification": "MEASURED",
                     "bytes_per_bulk_core": bulk, "bytes_per_param": bulk / (chi * 2 * chi)})
    float_rows = []
    for n in (100, 1000, 10000):
        for chi in (16, 64, 256, 1024):
            model = n * chi * chi * 2 * 16
            row = {"n_qubits": n, "chi": chi, "plane": "float64 complex128", "bytes": model,
                   "bytes_per_param": 16}
            if model <= 64 * 2**20:
                cores = [np.empty((chi, 2, chi), complex) for _ in range(n)]
                row["bytes"] = sum(c.nbytes for c in cores)
                row["classification"] = "MEASURED"
                del cores
            else:
                row["classification"] = "MODELED"
                row["model"] = "n * chi^2 * d * 16 bytes"
            float_rows.append(row)
    return {"passed": True, "result": {"exact_rows": rows, "float_rows": float_rows}}


# -- meta-benchmark ----------------------------------------------------------------


def _voyage_circuit(n: int) -> List[tuple]:
    ops: List[tuple] = [("1q", 0, "H")]
    ops += [("2q", i, "CNOT") for i in range(n - 1)]
    ops += [("1q", 0, "T"), ("1q", n - 1, "S")]
    return ops


def _run_circuit(n: int, ops: Sequence[tuple], custody: Any):
    from .exact_network import ExactMPS

    psi = ExactMPS.zeros(n, custody=custody)
    for op in ops:
        if op[0] == "1q":
            psi.apply_1q(op[1], op[2])
        else:
            psi.apply_2q(op[1], op[2])
    return psi


def bench_ten_thousand_qubit_voyage(quick: bool) -> Dict[str, Any]:
    from .certificate import aggregate
    from .custody import default_custody
    from .cyclotomic import I8, INV_SQRT2_8, ONE8, Q8, ZETA8_8

    n = 1000 if quick else 10000
    ops = _voyage_circuit(n)
    custody = default_custody()
    phases: Dict[str, int] = {}
    t = time.perf_counter_ns()
    psi = _run_circuit(n, ops, custody)
    phases["build_and_execute_ns"] = time.perf_counter_ns() - t
    half = Q8(1, 0, 0, 0, 2)
    t = time.perf_counter_ns()
    norm = psi.norm2()
    zero = psi.entry([0] * n)
    ones = psi.entry([1] * n)
    probs = {k: psi.probability(k, 0) for k in (0, n // 2, n - 1)}
    purity = psi.cut_purity(n // 2)
    samples = [psi.sample(seed) for seed in range(5)]
    phases["measure_ns"] = time.perf_counter_ns() - t
    expected_ones = ZETA8_8 * I8 * INV_SQRT2_8
    state_checks = {
        "max_bond_is_2": max(psi.bonds()) == 2,
        "schmidt_rank_2_every_cut": all(b == 2 for b in psi.bonds()[1:-1]),
        "norm_is_exactly_1": norm == ONE8,
        "amp_0..0_is_1/sqrt2": zero == INV_SQRT2_8,
        "amp_1..1_is_zeta8*i/sqrt2": ones == expected_ones,
        "marginals_exactly_1/2": all(p == half for p in probs.values()),
        "cut_purity_exactly_1/2": purity == half,
        "samples_all_equal_bits": all(len(set(s)) == 1 for s in samples),
    }
    t = time.perf_counter_ns()
    chain_ok = psi.ledger.verify_chain()
    agg = aggregate(psi.ledger.entries)
    phases["certificate_verify_ns"] = time.perf_counter_ns() - t
    custody_certs = custody.accounting()["certificates"]
    t = time.perf_counter_ns()
    replay = _run_circuit(n, ops, default_custody())
    phases["replay_ns"] = time.perf_counter_ns() - t
    cert_checks = {
        "every_certificate_reverified": chain_ok,
        "aggregate_valid": agg.valid,
        "custody_holds_every_certificate": custody_certs >= psi.ledger.count,
        "certificates": psi.ledger.count,
    }
    replay_checks = {
        "final_root_bit_for_bit": replay.root == psi.root,
        "execution_chain_bit_for_bit": [c.digest for c in replay.ledger.entries]
        == [c.digest for c in psi.ledger.entries[: replay.ledger.count]],
    }
    acc = custody.accounting()
    passed = (
        all(state_checks.values())
        and chain_ok
        and agg.valid
        and cert_checks["custody_holds_every_certificate"]
        and all(replay_checks.values())
    )
    return {
        "passed": passed,
        "result": {
            "qubits": n,
            "gates": len(ops),
            "circuit": "H(0); CNOT chain; T(0); S(n-1)",
            "custody_provider": acc["provider"],
            "custody": acc,
            "state_checks": state_checks,
            "certificate_checks": cert_checks,
            "replay_checks": replay_checks,
            "state_root": psi.root,
            "aggregate_root": agg.merkle_root,
            "phases": phases,
            "questions": {
                "did_the_mps_represent_the_exact_state": state_checks["schmidt_rank_2_every_cut"]
                and state_checks["amp_1..1_is_zeta8*i/sqrt2"],
                "did_the_circuit_execute_exactly": state_checks["norm_is_exactly_1"],
                "did_the_certificate_bind_the_full_context": chain_ok and agg.valid,
                "did_the_replay_reproduce_bit_for_bit": all(replay_checks.values()),
            },
        },
    }


BENCHMARKS: Dict[str, tuple] = {
    "fold_roundtrip": ("correctness", bench_fold_roundtrip),
    "tt_svd_error_bound": ("correctness", bench_tt_svd_error_bound),
    "mpo_preservation": ("correctness", bench_mpo_preservation),
    "kraus_trace": ("correctness", bench_kraus_trace),
    "cross_version_digest": ("correctness", bench_cross_version_digest),
    "determinism": ("correctness", bench_determinism),
    "boundary_isolation": ("correctness", bench_boundary_isolation),
    "substrate_identities": ("correctness", bench_substrate_identities),
    "zeckendorf_roundtrip": ("correctness", bench_zeckendorf_roundtrip),
    "surface_code_algebra": ("correctness", bench_surface_code_algebra),
    "surface_code_correction": ("correctness", bench_surface_code_correction),
    "vector11_fold": ("correctness", bench_vector11_fold),
    "fisher_exact": ("correctness", bench_fisher_exact),
    "hamiltonian_exact": ("correctness", bench_hamiltonian_exact),
    "dmrg_vs_dense": ("correctness", bench_dmrg_vs_dense),
    "mps_gate_throughput": ("cost", bench_mps_gate_throughput),
    "mps_contraction_throughput": ("cost", bench_mps_contraction_throughput),
    "tt_svd_cost": ("cost", bench_tt_svd_cost),
    "compression_fidelity": ("cost", bench_compression_fidelity),
    "exact_field_cost": ("cost", bench_exact_field_cost),
    "certificate_emission": ("cost", bench_certificate_emission),
    "memory_footprint": ("cost", bench_memory_footprint),
    "ten_thousand_qubit_voyage": ("meta", bench_ten_thousand_qubit_voyage),
}


def run(benchmark_id: str, *, quick: bool = False, prov: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    from .certificate import merkle_root

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
    body = {
        "schema": SCHEMA,
        "benchmark_id": benchmark_id,
        "axis": axis,
        "commit": prov["commit"],
        "kellogg_version": prov["kellogg_version"],
        "hardware": prov["hardware"],
        "software": prov["software"],
        "configuration": config,
        "measurement": measurement,
        "classification": "MEASURED",
        "passed": out["passed"],
        "error": error,
        "result": result,
    }
    body["digest"] = digest(body)
    body["attestation"] = merkle_root(
        [digest(config), digest(measurement), digest(result), digest(prov)]
    )
    return body


def run_all(
    ids: Optional[Sequence[str]] = None,
    *,
    quick: bool = False,
    out_dir: Optional[str | Path] = None,
    progress: Optional[Callable[[str, Dict[str, Any]], None]] = None,
) -> Dict[str, Any]:
    prov = provenance()
    chosen = list(ids) if ids else list(BENCHMARKS)
    artifacts = []
    for bid in chosen:
        art = run(bid, quick=quick, prov=prov)
        artifacts.append(art)
        if progress:
            progress(bid, art)
    summary = {
        "schema": SCHEMA + "#suite",
        "commit": prov["commit"],
        "quick": quick,
        "passed": [a["benchmark_id"] for a in artifacts if a["passed"] is True],
        "failed": [a["benchmark_id"] for a in artifacts if a["passed"] is False],
        "incomplete": [a["benchmark_id"] for a in artifacts if a["passed"] is None],
        "artifacts": artifacts,
    }
    summary["digest"] = digest({k: v for k, v in summary.items() if k != "artifacts"} | {
        "artifact_digests": [a["digest"] for a in artifacts]})
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

    parser = argparse.ArgumentParser(prog="python -m kellogg.benchmark")
    parser.add_argument("ids", nargs="*", help="benchmark ids (default: all)")
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--out", default=None, help="results directory (latest.json, archive/)")
    args = parser.parse_args(argv)

    def show(bid: str, art: Dict[str, Any]) -> None:
        state = {True: "PASS", False: "FAIL", None: "INCOMPLETE"}[art["passed"]]
        print(f"{bid:32s} {state:10s} {art['measurement']['wall_ns'] / 1e9:8.2f}s"
              + (f"  {art['error']}" if art["error"] else ""), flush=True)

    summary = run_all(args.ids or None, quick=args.quick, out_dir=args.out, progress=show)
    print(f"passed {len(summary['passed'])}, failed {len(summary['failed'])}, "
          f"incomplete {len(summary['incomplete'])}; digest {summary['digest'][:16]}")
    return 1 if summary["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
