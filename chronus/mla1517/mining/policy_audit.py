"""Quantum-cross-checked, Kellogg-attested audit of operating decisions.

The hot path picks a window by classical argmin over the Lucas candidates.
Periodically this auditor re-selects it on the Turing VQC by Durr-Hoyer
minimum finding: exact Grover amplitude amplification on a
``QuantumRegister`` with a phase oracle marking every candidate whose loss
is below the current threshold, measured by the register's seeded Born-rule
sampler. The quantum choice must equal the classical one; the inputs, both
choices and the verdict are bound in a Kellogg attestation.

A disagreement is recorded and never acted on: the classical argmin stays
authoritative. The VQC is part of the miner (a declared dependency); a broken
install is reported by the audit, which still attests the classical decision.
Nothing here touches SHA256d.
"""

from __future__ import annotations

import math
from typing import Any, Sequence

from chronus.mla1517.quantum import classical_simulation_provenance
from .operating_policy import PolicyDecision

# The VQC register is exact state-vector algebra on the host CPU; its
# ``measure(seed)`` draws from the exact Born distribution with a seeded PRNG.
VQC_PROVENANCE = classical_simulation_provenance(
    "turing_universal_quantum_computer.hilbert.QuantumRegister",
    arithmetic="exact Q(zeta_8) / sympy cyclotomics",
    sampling="seeded PRNG draw from the exact Born distribution",
)


def _load_register():
    """The VQC's exact register: the miner's declared dependency, as installed."""
    try:
        from turing_universal_quantum_computer.hilbert import QuantumRegister
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"
    return QuantumRegister, None


def grover_minimum(losses: Sequence[float], *, seed: int, register_cls=None) -> dict[str, Any]:
    """Durr-Hoyer minimum finding over ``losses`` on the exact VQC register."""
    if not losses:
        raise ValueError("no candidates")
    if register_cls is None:
        register_cls, error = _load_register()
        if register_cls is None:
            raise RuntimeError(error)
    k = len(losses)
    qubits = max(1, math.ceil(math.log2(k)))
    threshold = seed % k
    rounds, oracle_calls = 0, 0
    trace = []
    for round_seed in range(seed, seed + 4 * k):
        marked = {i for i, loss in enumerate(losses) if loss < losses[threshold]}
        if not marked:
            break
        n = 1 << qubits
        iterations = max(0, round(math.pi / 4 * math.sqrt(n / len(marked)) - 0.5))
        register = register_cls(qubits)
        register.uniform_superposition()
        for _ in range(iterations):
            register.apply_grover_oracle(marked)
            register.diffusion()
        oracle_calls += iterations
        measured = register.measure(seed=round_seed)
        rounds += 1
        trace.append(
            {
                "threshold": threshold,
                "marked": len(marked),
                "iterations": iterations,
                "measured": measured,
            }
        )
        if measured < k and losses[measured] < losses[threshold]:
            threshold = measured
    return {
        "index": threshold,
        "rounds": rounds,
        "oracle_calls": oracle_calls,
        "qubits": qubits,
        "trace": trace,
    }


class PolicyAuditor:
    def __init__(self, *, every: int = 64) -> None:
        self.every = max(1, every)
        self.audits = 0
        self.disagreements = 0
        self.last: dict[str, Any] | None = None
        self._seen = 0
        self._register_cls, self._vqc_error = _load_register()

    def maybe_audit(self, decision: PolicyDecision) -> dict[str, Any] | None:
        if decision.source not in ("model", "measured") or not decision.candidates:
            return None
        self._seen += 1
        if self._seen % self.every:
            return None
        return self.audit(decision)

    def audit(self, decision: PolicyDecision) -> dict[str, Any]:
        from kellogg.attest import attest

        candidates = list(decision.candidates)
        losses = [float(c["loss"]) for c in candidates]
        classical = min(range(len(candidates)), key=lambda i: (losses[i], -candidates[i]["window"]))
        vqc: dict[str, Any]
        if self._register_cls is None:
            vqc = {"available": False, "reason": self._vqc_error}
            agree = None
        else:
            result = grover_minimum(losses, seed=self.audits + 1, register_cls=self._register_cls)
            chosen = result["index"]
            # Equal losses are the same minimum; the tie-break only orders them.
            agree = math.isclose(losses[chosen], losses[classical], rel_tol=0.0, abs_tol=1e-15)
            vqc = {
                "available": True,
                "provenance": dict(VQC_PROVENANCE),
                "window": candidates[chosen]["window"],
                "rounds": result["rounds"],
                "oracle_calls": result["oracle_calls"],
                "qubits": result["qubits"],
                "classical_evaluations": len(candidates),
            }
        self.audits += 1
        if agree is False:
            self.disagreements += 1
        record = {
            "schema": "pythia.policy_audit/1",
            "inputs": dict(decision.expected),
            "candidates": [{"window": c["window"], "loss": c["loss"]} for c in candidates],
            "classical_window": candidates[classical]["window"],
            "decided_window": decision.window,
            "vqc": vqc,
            "agree": agree,
        }
        record["attestation"] = attest(
            record,
            float_boundaries=("world-model estimates", "expected-loss evaluation"),
            notes=("operating policy audit; SHA256d and pool outcomes are outside its authority",),
        )
        self.last = record
        return record

    def snapshot(self) -> dict[str, Any]:
        last = self.last
        return {
            "audits": self.audits,
            "disagreements": self.disagreements,
            "vqc_available": self._register_cls is not None,
            "last": (
                None
                if last is None
                else {
                    "decided_window": last["decided_window"],
                    "classical_window": last["classical_window"],
                    "vqc": last["vqc"],
                    "agree": last["agree"],
                    "digest": last["attestation"]["digest"],
                }
            ),
        }
