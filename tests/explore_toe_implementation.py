#!/usr/bin/env python3
"""Exploratory diagnostic for the TOE implementation.

Not a pass/fail test. Initializes ``TOEBridge``, ``TOEExpansionEngine``, and
``TOESystem`` with no Stratum socket and no SHA256d check, then prints the
state vectors, causal-ladder decisions, algebraic-family residuals, and
resource measurements those objects actually produce.

Run from the repository root:

    PYTHONPATH=.:chronus/mla1517_platform/python \\
        python3 tests/explore_toe_implementation.py
"""

from __future__ import annotations

import math
import os
import sys
import time
import tracemalloc
from decimal import Decimal
from typing import Any

# Repository root on path when the file is launched as a script.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MLA = os.path.join(_ROOT, "chronus/mla1517_platform", "python")
for _p in (_ROOT, _MLA):
    if _p not in sys.path:
        sys.path.insert(0, _p)

LADDER = (10, 12, 15, 18, 20, 31, 50, 76)


def _flatten(value: Any) -> list[float]:
    """Mirror ``encode_data_to_state`` so truncation is visible.

    The encoder is deterministic and keeps only the first ``hilbert_dim``
    flattened numbers. Key names are UTF-8 bytes and are emitted before the
    values of each key, in sorted-key order. Anything past that prefix never
    enters the state vector.
    """
    if isinstance(value, bool):
        return [1.0 if value else 0.0]
    if isinstance(value, (int, float)):
        return [float(value)]
    if isinstance(value, str):
        return [float(b) for b in value.encode("utf-8")]
    if isinstance(value, (bytes, bytearray)):
        return [float(b) for b in value]
    if isinstance(value, dict):
        out: list[float] = []
        for key in sorted(value, key=lambda item: str(item)):
            out.extend(_flatten(str(key)))
            out.extend(_flatten(value[key]))
        return out
    if isinstance(value, (list, tuple)):
        out = []
        for item in value:
            out.extend(_flatten(item))
        return out
    return []


def _scrub(value: Any, *, depth: int = 0) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, float):
        if not math.isfinite(value):
            return str(value)
        return round(value, 8)
    if isinstance(value, dict):
        if depth > 5:
            return {"_truncated": True, "keys": list(value)[:12]}
        return {str(k): _scrub(v, depth=depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        if depth > 4 and len(value) > 16:
            return [_scrub(v, depth=depth + 1) for v in value[:16]] + ["…", len(value)]
        return [_scrub(v, depth=depth + 1) for v in value]
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    return str(value)


def _preload_scale_controller() -> None:
    """Load ``chronus.mla1517.scale`` without executing ``chronus/mla1517/__init__.py``.

    The package initializer imports the mining stack, and that stack requires
    ``enum.StrEnum`` (Python 3.11+). The scale controller does not. Preloading
    the submodule lets ``TOEExpansionEngine`` call the real controller on 3.10
    instead of reporting it missing.
    """
    import importlib.util
    import types
    from pathlib import Path

    if getattr(sys.modules.get("chronus.mla1517.scale"), "ScaleController", None) is not None:
        return
    root = Path(_ROOT) / "chronus" / "mla1517"
    pkg = types.ModuleType("mla1517")
    pkg.__path__ = [str(root)]  # type: ignore[attr-defined]
    pkg.__package__ = "mla1517"
    sys.modules["mla1517"] = pkg
    for name in ("core", "scale"):
        path = root / f"{name}.py"
        spec = importlib.util.spec_from_file_location(f"chronus.mla1517.{name}", path)
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load {path}")
        module = importlib.util.module_from_spec(spec)
        module.__package__ = "mla1517"
        sys.modules[f"chronus.mla1517.{name}"] = module
        spec.loader.exec_module(module)


def _banner(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def _kv(label: str, value: Any) -> None:
    print(f"  {label}: {_scrub(value)}")


def _recurrence(kind: str, length: int = 18) -> list[float]:
    if kind == "golden":
        a, b = 2, 1  # Lucas
        seq = [a, b]
        while len(seq) < length:
            a, b = b, a + b
            seq.append(b)
        return [float(x) for x in seq]
    if kind == "plastic":
        # Perrin: P(n) = P(n-2) + P(n-3), P(0..2) = 3, 0, 2
        seq = [3, 0, 2]
        while len(seq) < length:
            seq.append(seq[-2] + seq[-3])
        return [float(x) for x in seq]
    if kind == "supergolden":
        # Narayana cows: a(n) = a(n-1) + a(n-3)
        seq = [1, 1, 1]
        while len(seq) < length:
            seq.append(seq[-1] + seq[-3])
        return [float(x) for x in seq]
    if kind == "tribonacci":
        seq = [0, 0, 1]
        while len(seq) < length:
            seq.append(seq[-1] + seq[-2] + seq[-3])
        return [float(x) for x in seq]
    if kind == "silver":
        # Pell companion, not a template inside detect_family_signature.
        a, b = 2, 2
        seq = [a, b]
        while len(seq) < length:
            a, b = b, 2 * b + a
            seq.append(b)
        return [float(x) for x in seq]
    if kind == "noise":
        # Deterministic LCG, not a Pisot recurrence.
        x = 17
        seq = []
        for _ in range(length):
            x = (1103515245 * x + 12345) & 0x7FFFFFFF
            seq.append(float((x % 1000) - 500))
        return seq
    if kind == "constant":
        return [1.0] * length
    raise KeyError(kind)


def _cascading_failure() -> dict[str, list[float]]:
    """Thermal/latency/error cascade. Late channels are past the 32-cap."""
    n = 48
    latency = [12.0 + 0.4 * i + (80.0 if i > 30 else 0.0) for i in range(n)]
    temperature = [55.0 + 0.35 * i + (25.0 if i > 30 else 0.0) for i in range(n)]
    error_rate = [0.001 * (1.2**i) for i in range(n)]
    queue_depth = [float(2**min(i, 16)) for i in range(n)]
    recovery = [max(0.0, 40.0 - 1.5 * i) for i in range(n)]
    return {
        "error_rate": error_rate,
        "latency_ms": latency,
        "queue_depth": queue_depth,
        "recovery_margin": recovery,
        "temperature_c": temperature,
    }


def _nonlinear_matrix() -> dict[str, list[float]]:
    """Coupled logistic map. Deterministic, chaotic, not a linear recurrence."""
    x, y = 0.21, 0.73
    xs, ys, zs = [], [], []
    for _ in range(36):
        x = 3.9 * x * (1.0 - x)
        y = 3.7 * y * (1.0 - y) + 0.05 * x
        y = min(0.999, max(0.001, y))
        xs.append(x)
        ys.append(y)
        zs.append(x * y)
    return {"drive": xs, "response": ys, "coupling": zs}


def _timed(label: str, fn):
    tracemalloc.start()
    t0 = time.perf_counter()
    try:
        value = fn()
        err = None
    except Exception as exc:  # diagnostic must report the failure, not hide it
        value = None
        err = f"{type(exc).__name__}: {exc}"
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    print(f"\n[{label}] {elapsed_ms:.2f} ms   tracemalloc_peak={peak} bytes")
    if err:
        print(f"  EXCEPTION: {err}")
    return value, elapsed_ms, peak, err


def _print_tomography(bridge, name: str, data: Any) -> None:
    flat = _flatten(data)
    dim = bridge._dim
    print(f"\n-- tomography :: {name}")
    _kv("flattened_length", len(flat))
    _kv("hilbert_dim", dim)
    _kv("truncated_samples", max(0, len(flat) - dim))
    _kv("prefix_that_enters_the_state", [round(v, 4) for v in flat[:dim]])
    tomo = bridge.state_tomography(data)
    _kv("available", tomo.available)
    _kv("confidence", tomo.confidence)
    _kv("energy_<H>", tomo.energy)
    _kv("momentum_<p>", tomo.momentum)
    _kv("volatility", tomo.volatility)
    _kv("fidelity_vs_uniform", tomo.fidelity)
    _kv("von_neumann_entropy_bits", tomo.entropy)
    _kv("purity_Tr_rho2", tomo.coherence)
    _kv("fisher_information", tomo.fisher_info)
    _kv("diagnostics", tomo.diagnostics)
    probs = tomo.state_vector or []
    print("  born_probabilities_reported_by_tomography (API keeps 20 of dim):")
    print("   ", [round(p, 6) for p in probs])
    # Full frame, including amplitudes the dataclass summary drops.
    state = bridge._encode_state(data)
    full = state.probabilities()
    mass = sum(full)
    occupied = sum(1 for p in full if p > 1e-8)
    print(f"  full_{dim}_face_born (sum={mass:.6f}, occupied={occupied}/{dim}):")
    for i in range(0, dim, 8):
        row = [round(p, 6) for p in full[i : i + 8]]
        print(f"    [{i:02d}:{i+len(row):02d}] {row}")


def _print_trajectory(bridge, name: str, data: Any) -> None:
    print(f"\n-- trajectory :: {name}")
    traj = bridge.predict_trajectory(data)
    _kv("available", traj.available)
    _kv("public_horizon", traj.time_horizon)
    _kv("public_times", (traj.diagnostics or {}).get("times"))
    _kv("trend", traj.trend)
    _kv("trend_rate_E_final_minus_E0", traj.trend_rate)
    _kv("forecast_3_step_energy", traj.forecast_3_step)
    _kv("forecast_6_step_energy", traj.forecast_6_step)
    _kv("confidence", traj.confidence)
    _kv("time_sensitivity", traj.time_sensitivity)
    energies = (traj.diagnostics or {}).get("energies") or []
    e0 = traj.current_state
    if energies:
        drift = max(abs(e - e0) for e in energies)
        print(f"  max_|E(t)-E(0)| on the public grid: {drift:.6e}")
        print("  note: exact Schrödinger evolution generated by H conserves <H>.")
        print("        a nonzero drift here is Taylor/scaling error, not a forecast of recovery.")
    print("  intervention_points (fisher on the position operator):")
    for point in traj.intervention_points:
        print(
            f"    t={point['time']:.2f}  fisher={point['fisher_info']:.6f}"
            f"  energy={point['energy']:.6f}  is_optimal={point['is_optimal']}"
        )

    # The public method stops at t=3. Walk the same propagator further.
    print("  extended propagator probe (same U(t), not a new model):")
    state = bridge._encode_state(data)
    h = bridge._hamiltonian()
    e_ref = state.expectation(h)
    worst = 0.0
    deadline = time.perf_counter() + 8.0
    for t in (0.25, 0.5, 1.0, 2.0, 3.0, 4.0, 6.0, 8.0, 12.0):
        if time.perf_counter() > deadline:
            print("    stopped: 8s probe budget")
            break
        evolved = state.apply_unitary(bridge._propagator(t))
        energy = evolved.expectation(h)
        norm = math.sqrt(sum(evolved.probabilities()))
        gap = abs(energy - e_ref)
        worst = max(worst, gap)
        probs = evolved.probabilities()
        top = max(range(len(probs)), key=lambda i: probs[i])
        print(
            f"    t={t:5.2f}  <H>={energy:.6f}  |dE|={gap:.3e}"
            f"  prob_sum={norm:.6f}  mode={top}  p_mode={probs[top]:.4f}"
        )
    _kv("worst_abs_energy_drift", f"{worst:.3e}")


def _print_ladder(bridge, name: str, data: Any, observed: dict | None) -> None:
    print(f"\n-- causal ladder :: {name}")
    ladder = bridge.causal_ladder(data, observed=observed)
    body = ladder.as_dict()
    _kv("available", body.get("available"))
    _kv("confidence", body.get("confidence"))
    _kv("diagnostics", body.get("diagnostics"))
    graph = body.get("causal_graph") or {}
    print("  causal_graph:")
    _kv("  nodes", graph.get("nodes") or graph.get("order") or list(graph)[:12])
    edges = graph.get("edges") or graph.get("adjacency")
    _kv("  edges", edges)
    print("  rung_1_association:")
    _kv("  P", body.get("rung_1_association"))
    rung2 = body.get("rung_2_intervention") or {}
    print("  rung_2_intervention:")
    _kv("  identifiable", rung2.get("identifiable"))
    _kv("  backdoor", rung2.get("backdoor_set"))
    _kv("  frontdoor", rung2.get("frontdoor_set"))
    _kv("  distribution", rung2.get("distribution"))
    diag = rung2.get("diagnostics") or {}
    # Drop bulky matrices if a backend attached them.
    slim = {k: v for k, v in diag.items() if k not in {"state", "amplitudes", "matrix"}}
    _kv("  diagnostics", slim)
    rung3 = body.get("rung_3_counterfactual") or {}
    print("  rung_3_counterfactual:")
    _kv("  value", rung3.get("value"))
    _kv("  diagnostics", rung3.get("diagnostics"))
    causal = bridge.explain_causality(data)
    print("  factor ranking by |<A>| (explain_causality):")
    for name_i, weight in causal.key_factors:
        print(f"    {name_i}: {weight:.6f}")
    _kv("recommendations", causal.recommendations)
    _kv("causal_confidence", causal.confidence)
    _kv("data_quality", causal.data_quality)
    _kv("model_agreement", causal.model_agreement)


def _family_table(bridge) -> None:
    print("\n-- algebraic family detector (turing_core.detect_family_signature)")
    print("  templates implemented: golden lag-12, plastic lag-23, supergolden lag-13, tribonacci lag-123")
    print("  silver/Pell is intentionally absent from the detector.")
    print(f"  {'planted':<14} {'detected':<14} {'confidence':>12}  residuals")
    for kind in ("golden", "plastic", "supergolden", "tribonacci", "silver", "noise", "constant"):
        series = _recurrence(kind)
        sig = bridge.algebraic_signature(series)
        residuals = sig.get("residuals") or {}
        shown = {k: str(v) for k, v in residuals.items()} if isinstance(residuals, dict) else residuals
        conf = sig.get("confidence")
        print(
            f"  {kind:<14} {str(sig.get('family')):<14} {str(conf):>12}  {_scrub(shown)}"
        )
        if not sig.get("available", False):
            _kv("unavailable_reason", sig.get("reason"))


def _scale_program(expansion) -> None:
    print("\n-- Lucas / Pisot scale program")
    print(f"  policy indices (static, not inferred from data): {LADDER}")
    print(f"  policy families: {expansion.policy.scale_families}")
    cascade = _cascading_failure()
    golden = _recurrence("golden")
    programs = {}
    for label, payload in (("cascade", cascade), ("golden_series", golden), ("noise", _recurrence("noise"))):
        result, *_ = _timed(f"expansion:{label}", lambda p=payload: expansion.collapse(p, domain="diagnostic"))
        if result is None:
            continue
        digest_bits = []
        print(f"  input={label}  expansion.available={result.available}")
        sig = result.algebraic_signature
        print(f"    algebraic_signature.family={sig.get('family')} confidence={sig.get('confidence')}")
        accepted = 0
        for item in result.scale_program:
            point = item["point"]
            ok = item["accepted"]
            accepted += int(bool(ok))
            if point["family"] == "golden":
                digest_bits.append((point["index"], point["family"], ok, item["reason"], item["estimate"]["logical_state_bits"]))
        print(f"    scale decisions accepted {accepted}/{len(result.scale_program)}")
        print("    golden-family rungs only (the other families repeat the same index set):")
        for index, family, ok, reason, bits in digest_bits:
            print(f"      L-index {index:>3}  family={family:<12} accepted={ok}  reason={reason}  logical_bits={bits}")
        programs[label] = tuple(
            (i["point"]["index"], i["point"]["family"], i["accepted"], i["reason"])
            for i in result.scale_program
        )
        cert = result.state_certificate
        print(f"    11d certificate keys={list(cert)[:8]} theorem_proven={result.proof_boundary.get('theorem_proven')}")
        env = result.execution_envelope
        _kv("execution_envelope", {k: env[k] for k in ("math_scale", "logical_state_size", "physical_state_bytes", "performance_claim") if k in env})
    if len(programs) >= 2:
        unique = {programs[k] for k in programs}
        print(f"  distinct scale programs across inputs: {len(unique)}")
        print("  if this is 1, the ladder did not move when the series changed.")


def _theorem_block(system) -> None:
    from toe.manifold_bridge import PrecomputedCandidate

    print("\n-- TOESystem 12-theorem matrix (no pool, no header hash)")
    print("  Several checks do not read the candidate. They are identities of the")
    print("  constants, or literals. The harness prints each one so that is visible.")
    low = PrecomputedCandidate(
        nonce=0,
        header_template=b"",
        zeckendorf_mask=0b10101,
        galois_composite=1,
        sector_id=0,
        born_probability=0.2,
        cassini_valid=True,
        zeckendorf_valid=True,
    )
    high = PrecomputedCandidate(
        nonce=1364,
        header_template=b"\x00" * 80,
        zeckendorf_mask=0b10101,
        galois_composite=1,
        sector_id=3,
        born_probability=0.95,
        cassini_valid=True,
        zeckendorf_valid=True,
    )
    for label, cand in (("born_0.2_nonce_0", low), ("born_0.95_nonce_1364", high)):
        ok, results = system.verify_12_theorems_candidate(cand, n_anchor=15)
        print(f"  candidate={label}  all_passed={ok}")
        for key, flag in results.items():
            print(f"    {key}: {flag}")
    system.record_decision("diagnostic", "causal", "observe", {"n": 1}, 8, True)
    system.record_decision("diagnostic", "counterfactual", "project", {"n": 2}, 8, True)
    system.learn_coordination_pattern("dynamic_throttle", 1.4)
    _kv("dynamic_throttle_after_up", system.active_coordination_patterns["dynamic_throttle"])
    system.learn_coordination_pattern("dynamic_throttle", 0.2)
    _kv("dynamic_throttle_after_down", system.active_coordination_patterns["dynamic_throttle"])
    system.escalate_anomaly("synthetic_cascade", {"source": "explore_toe_implementation"})
    _kv("provenance_chain_ok", system.verify_provenance())
    _kv("ledger_len", len(system.provenance_ledger))
    _kv("coordination_patterns", system.active_coordination_patterns)
    _kv("escalations", len(system.escalations_logged))


def _profile(bridge_factory) -> None:
    print("\n-- load sweep")
    payload = _cascading_failure()
    for dim in (8, 16, 32):
        bridge = bridge_factory(dim)
        _timed(
            f"predict dim={dim}",
            lambda b=bridge: b.predict(payload),
        )
        evidence = bridge.execution_evidence()
        _kv("backend", evidence.get("backend"))
        _kv("propagator_cache", evidence.get("propagator_cache_entries"))
    # Wider factor dict. Encoding still truncates; this measures graph construction.
    wide = {f"ch_{i:02d}": [float((i * 17 + k) % 50) for k in range(8)] for i in range(24)}
    bridge = bridge_factory(32)
    _timed("causal_ladder 24-factor", lambda: bridge.causal_ladder(wide, observed={"ch_00": 1.0, "ch_23": 40.0}))
    _timed("tomography 24-factor", lambda: bridge.state_tomography(wide))


def _ablation(bridge) -> None:
    print("\n-- truncation ablation")
    base = {"alpha": [1.0, 2.0, 3.0, 4.0], "zeta": [0.0] * 40}
    spiked = {"alpha": [1.0, 2.0, 3.0, 4.0], "zeta": [0.0] * 39 + [1.0e6]}
    a = bridge.state_tomography(base)
    b = bridge.state_tomography(spiked)
    same = (
        a.energy == b.energy
        and a.momentum == b.momentum
        and a.state_vector == b.state_vector
    )
    print(f"  late 1e6 spike changes tomography: {not same}")
    print(f"  energy base={a.energy:.8f} spiked={b.energy:.8f}")
    print("  a True 'does not change' means the sample never reached the 32-face state.")


def _healing_loop(bridge) -> None:
    print("\n-- repeated intervention loop (same ladder, shrinking shock)")
    print("  This does not edit the bridge. It only re-queries it.")
    for step, shock in enumerate((80.0, 40.0, 10.0, 0.0)):
        data = {
            "latency_ms": [10.0 + shock, 10.0 + 0.5 * shock, 10.0],
            "temperature_c": [60.0 + 0.2 * shock, 60.0, 58.0],
            "error_rate": [0.01 * (1.0 + shock), 0.01, 0.001],
        }
        observed = {"latency_ms": 10.0 + shock, "error_rate": 0.05}
        ladder = bridge.causal_ladder(
            data,
            intervention_node="latency_ms",
            intervention_value=10.0,
            observed=observed,
        )
        print(
            f"  step={step} shock={shock:.1f}"
            f"  available={ladder.available}"
            f"  confidence={ladder.confidence:.4f}"
            f"  counterfactual={ladder.counterfactual_value}"
            f"  node={ladder.diagnostics.get('intervention_node')}"
            f"  identifiable={ladder.identifiable}"
        )


def main() -> None:
    _banner("TOE IMPLEMENTATION DIAGNOSTIC")
    print("standalone: no Stratum, no SHA256d, no device.")
    print("numbers below are outputs of the current source, not targets.")

    from toe.bridge import TOEBridge

    _preload_scale_controller()
    from toe.expansion import TOEExpansionEngine
    from toe.system import TOESystem

    bridge = TOEBridge()
    _kv("status", bridge.status())
    _kv("execution_evidence", bridge.execution_evidence())
    _kv("has_expand_method", hasattr(bridge, "expand"))
    print("  expand() is what the mining adapter calls. Absence means that call fails closed.")

    _banner("1. STATE TOMOGRAPHY  (32-dimensional encoding, not the mining M32 lanes)")
    print("  Mining M32 is a 32-lane nonce partition in chronus.mla1517.mining.geometry.")
    print("  This frame is hilbert_dim=32 inside TOEBridge. They are different objects.")
    cascade = _cascading_failure()
    _print_tomography(bridge, "cascading_failure", cascade)
    _print_tomography(bridge, "logistic_coupling", _nonlinear_matrix())
    _print_tomography(bridge, "golden_lucas_series", _recurrence("golden"))
    _ablation(bridge)

    _banner("2. PREDICTIVE HORIZON")
    _print_trajectory(bridge, "cascading_failure", cascade)
    _print_trajectory(bridge, "logistic_coupling", _nonlinear_matrix())

    _banner("3. CAUSAL LADDER AND COUNTERFACTUALS")
    _print_ladder(
        bridge,
        "cascade",
        cascade,
        observed={"latency_ms": 90.0, "temperature_c": 82.0, "error_rate": 0.4},
    )
    _print_ladder(bridge, "logistic", _nonlinear_matrix(), observed={"drive": 0.2, "response": 0.8})
    _healing_loop(bridge)

    _banner("4. ALGEBRAIC FAMILY")
    _family_table(bridge)

    _banner("5. SCALE LADDER 10..76")
    expansion = TOEExpansionEngine(bridge)
    _scale_program(expansion)

    _banner("6. TOESystem COORDINATOR")
    system, *_rest = _timed("TOESystem()", TOESystem)
    if system is not None:
        _theorem_block(system)
        predict, *_ = _timed("bridge.predict(cascade)", lambda: bridge.predict(cascade))
        if isinstance(predict, dict):
            _kv("predict.available", predict.get("available"))
            _kv("predict.confidence", predict.get("confidence"))
            _kv("section_flags", {k: (predict.get(k) or {}).get("available") for k in (
                "state_tomography", "trajectory_prediction", "causal_analysis", "causal_ladder", "exact_tensor"
            )})
            exact = predict.get("exact_tensor") or {}
            _kv("exact_tensor", {k: exact.get(k) for k in (
                "available", "exact", "num_qubits", "amplitude_count", "normalized_exact", "theorem_proven", "field"
            )})

    _banner("7. LATENCY AND MEMORY")
    _profile(lambda dim: TOEBridge({"hilbert_dim": dim}))

    _banner("BOUNDARIES OBSERVED FROM THIS RUN")
    print("  * Public trajectory grid is t = 0.5,1.0,1.5,2.0,2.5,3.0. There is no adaptive horizon.")
    print("  * <H> drift on that grid is propagator error. The generator cannot trend energy.")
    print("  * encode_data_to_state keeps 32 numbers. Later channels are dropped before any ladder.")
    print("  * The Lucas index set is TOEExpansionPolicy, identical for every input.")
    print("  * detect_family_signature has four templates. It does not contain silver, and it does")
    print("    not walk indices 10,12,15,18,20,31,50,76.")
    print("  * exact_tensor is a 5-qubit basis state indexed by a digest, then a Z quarter-turn.")
    print("  * effective_dimension is 1/sum(p^2) after projecting only the first three")
    print("    Born weights onto a fixed 32-direction frame. It is not the rank of the state.")
    print("  * Full `import chronus.mla1517` fails on Python 3.10 (enum.StrEnum). The scale")
    print("    controller is loaded directly so the ladder still executes.")
    print("  * theorem_proven is false on the exact tensor and on the expansion envelope.")
    print("  * TOESystem flags T6, T7, T9, and T10 do not read the candidate.")


if __name__ == "__main__":
    main()
