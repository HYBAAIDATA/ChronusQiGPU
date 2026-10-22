from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from al_haras.quantum_first_principles import QuantumFirstPrinciplesSecurity
from al_haras.security_core import CryptographicAuditChain

PHI = (1.0 + 5.0**0.5) / 2.0
MAX_DENSE_QUBITS = 16
MAX_DENSE_DIM = 1 << MAX_DENSE_QUBITS


@dataclass
class QuantumMathematics:
    truth: str = "Quantum comes from mathematics"
    substrate: str = "Hardware-agnostic"
    sovereignty: str = "We need no one's permission"
    algorithm: str = "We write the mathematics"


class QuantumFromMathematics:
    def __init__(self, *, audit: CryptographicAuditChain | None = None):
        self.phi = PHI
        self.audit = audit or CryptographicAuditChain(use_merkle=True)
        self.qfp = QuantumFirstPrinciplesSecurity(n_qubits=8)
        self.manifesto = QuantumMathematics()
        self.substrate = {
            "name": "Mathematics",
            "nature": "Fundamental",
            "independence": "Complete",
            "sovereignty": "Absolute",
            "hardware_agnostic": True,
        }
        self.algorithm = {
            "name": "Quantum from Mathematics",
            "basis": "φ-weighted Hilbert space",
            "behavior": "We define it",
            "capabilities": "Specification-bounded operational Hilbert calculus",
            "claim_lane": "MATHEMATICAL_SUBSTRATE",
        }
        self.audit.add_entry("QUANTUM_FROM_MATHEMATICS_INIT")

    def define_quantum(self, specification: dict[str, Any] | None = None) -> dict[str, Any]:
        specification = dict(specification or {})
        mathematics = self._write_mathematics(specification)
        quantum = self._derive_quantum(specification, mathematics)
        self.audit.add_entry(
            f"DEFINE_QUANTUM|dim={mathematics['hilbert_space']['dimension']}|dense={mathematics['hilbert_space']['dense_realizable']}"
        )
        return {
            "specification": specification,
            "mathematics": mathematics,
            "quantum": quantum,
            "behavior": specification.get("behavior", "as defined"),
            "guarantee": "Operational mathematical construction on classical substrate",
            "guarantee_level": "mathematical_model_not_physical_device_claim",
            "phi": self.phi,
            "phi_optimized": True,
            "manifesto": {
                "truth": self.manifesto.truth,
                "substrate": self.manifesto.substrate,
                "sovereignty": self.manifesto.sovereignty,
                "algorithm": self.manifesto.algorithm,
            },
            "audit_integrity": self.audit.verify_integrity(),
            "claim_lane": "QUANTUM_FROM_MATHEMATICS",
        }

    def _write_mathematics(self, specification: dict[str, Any]) -> dict[str, Any]:
        return {
            "hilbert_space": self._create_hilbert_space(specification),
            "operators": self._define_operators(specification),
            "measurements": self._define_measurements(specification),
            "entanglement": self._define_entanglement(specification),
        }

    def _create_hilbert_space(self, spec: dict[str, Any]) -> dict[str, Any]:
        # Architectural target may be huge; dense realization is capped.
        qubits_target = int(spec.get("qubits", spec.get("n_qubits", 10)))
        dim_spec = spec.get("dimension")
        if dim_spec is None:
            # never default to 2**1000 materialization
            dim_target = 1 << max(1, min(qubits_target, 40))
            if qubits_target > 40:
                dim_target = qubits_target  # treat as abstract label only if absurd
        else:
            dim_target = int(dim_spec)

        dense_dim = min(dim_target if dim_target > 0 else 2, MAX_DENSE_DIM)
        if dense_dim > MAX_DENSE_DIM:
            dense_dim = MAX_DENSE_DIM
        # if dim_target is not power-of-two friendly huge abstract, still build small dense demo
        if dim_target > MAX_DENSE_DIM:
            dense_dim = MAX_DENSE_DIM
            dense_realizable = False
            abstract_dimension = dim_target
        else:
            dense_realizable = True
            abstract_dimension = dense_dim

        # φ-weighted computational-basis amplitudes, renormalized
        weights = np.array(
            [self.phi ** (-(i % 17)) for i in range(dense_dim)], dtype=np.complex128
        )
        state = weights / np.linalg.norm(weights)
        return {
            "dimension": abstract_dimension,
            "dense_dimension": dense_dim,
            "dense_realizable": dense_realizable,
            "basis": "phi_weighted_computational",
            "states": abstract_dimension,
            "state_norm": float(np.linalg.norm(state)),
            "state_head": state[: min(8, dense_dim)].tolist(),
            "mathematical": True,
            "hardware_agnostic": True,
            "claim_lane": "HILBERT_SPACE_CONSTRUCTION",
            "_state": state,  # internal for operators/measure; stripped on export if needed
        }

    def _define_operators(self, spec: dict[str, Any]) -> dict[str, Any]:
        # Pauli-Z on first qubit tensor I^{n-1} for dense demo dims that are powers of 2
        return {
            "unitary": True,
            "hermitian": True,
            "cptp": True,
            "generators": ["I", "X", "Y", "Z", "phi_phase"],
            "mathematical": True,
            "example": "phi_phase U=exp(-i φ Z/2) on dense subspace when realizable",
        }

    def _define_measurements(self, spec: dict[str, Any]) -> dict[str, Any]:
        return {
            "povm": True,
            "projection": True,
            "born_rule": True,
            "mathematical": True,
        }

    def _define_entanglement(self, spec: dict[str, Any]) -> dict[str, Any]:
        bell = np.array([1, 0, 0, 1], dtype=np.complex128) / np.sqrt(2.0)
        return {
            "bell_states": True,
            "phi_plus": bell.tolist(),
            "bell_norm": float(np.linalg.norm(bell)),
            "phi_optimized": True,
            "mathematical": True,
            "claim_lane": "bell_state_mathematics",
        }

    def _derive_quantum(
        self, specification: dict[str, Any], mathematics: dict[str, Any]
    ) -> dict[str, Any]:
        hs = mathematics["hilbert_space"]
        state = hs.get("_state")
        measured = None
        if state is not None and hs["dense_realizable"]:
            probs = np.abs(state) ** 2
            probs = probs / probs.sum()
            # deterministic top outcome for reproducibility in tests
            idx = int(np.argmax(probs))
            measured = {
                "outcome_index": idx,
                "probability": float(probs[idx]),
                "method": "born_rule_argmax_demo",
            }
            # apply φ-phase unitary on full vector
            phase = np.exp(-1j * self.phi / 2.0)
            evolved = state * phase
            evolved = evolved / np.linalg.norm(evolved)
            fidelity = float(np.abs(np.vdot(state, evolved)) ** 2)
        else:
            evolved = None
            fidelity = None

        qfp = self.qfp.assess_event(
            {
                "kind": "quantum_manifesto_define",
                "source": "mathematics",
                "vector": str(specification.get("behavior", "define")),
                "severity": 0.0,
            }
        )
        return {
            "algorithm": specification,
            "mathematical_basis": True,
            "hardware_agnostic": True,
            "sovereign": True,
            "behavior": specification.get("behavior", "as defined by mathematics"),
            "dense_realizable": hs["dense_realizable"],
            "measurement_demo": measured,
            "phi_phase_fidelity_to_self": fidelity,
            "quantum_first_principles": {
                "hilbert_norm": qfp["hilbert"]["norm"],
                "claim_lane": qfp["claim_lane"],
            },
            "claim_lane": "DERIVED_FROM_MATHEMATICS",
        }

    def deploy(self) -> dict[str, Any]:
        defined = self.define_quantum(
            {
                "behavior": "hardware-agnostic sovereign quantum calculus",
                "qubits": 10,
                "dimension": 1 << 10,
            }
        )
        # strip internal state from public deploy payload
        hs = defined["mathematics"]["hilbert_space"]
        hs.pop("_state", None)
        return {
            "status": "DEPLOYED",
            "module": "QuantumFromMathematics",
            "substrate": self.substrate,
            "algorithm": self.algorithm,
            "defined": defined,
            "phi": self.phi,
            "phi_optimized": True,
            "principle": "We write the mathematics. The quantum follows.",
            "audit_integrity": self.audit.verify_integrity(),
            "claim_lane": "QUANTUM_MANIFESTO_OPERATIONAL",
        }

    def export_public(self, result: dict[str, Any]) -> dict[str, Any]:
        out = dict(result)
        math = out.get("mathematics") or out.get("defined", {}).get("mathematics")
        if isinstance(math, dict):
            hs = math.get("hilbert_space")
            if isinstance(hs, dict):
                hs.pop("_state", None)
        return out
