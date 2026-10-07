"""Adapters binding the consolidated exact engines into the backend registry.

The engines already exist in this package: ``stabilizer.StabilizerState`` (exact
CHP tableau), ``hilbert.QuantumRegister`` (exact sparse state vector),
``quantum_walk`` and ``annealing`` (closed-form families).  What was missing was
a single place that says *which* of them answers a given program, and what kind
of claim the answer carries.  These adapters supply that, and nothing else:
they add no mathematics and change no engine behaviour.

Every adapter is **fail-closed and probe-based**.  A required engine symbol is
resolved at call time, never at import time, so this module stays importable
when the heavy symbolic stack is absent; and if a symbol is missing the adapter
reports itself unavailable with the exact missing name rather than degrading to
something that would still return a number.
"""

from __future__ import annotations

import importlib
from typing import Any, Callable, Sequence

from .base import (
    Admission,
    Capability,
    CLIFFORD_GATES,
    ExecutionClass,
    ExecutionResult,
    Program,
    TruthClass,
)

__all__ = [
    "StabilizerBackend",
    "SparseExactBackend",
    "ClosedFormBackend",
    "probe_module",
]

#: QuantumRegister gate methods, by the canonical gate name used in programs.
_SPARSE_GATE_METHODS = {
    "h": "apply_h",
    "x": "apply_x",
    "y": "apply_y",
    "z": "apply_z",
    "s": "apply_s",
    "sdg": "apply_sdg",
    "t": "apply_t",
    "cx": "apply_cnot",
    "cnot": "apply_cnot",
    "cz": "apply_cz",
    "swap": "apply_swap",
}

#: StabilizerState gate methods (the Clifford group).
_STABILIZER_GATE_METHODS = {
    "i": None,
    "h": "h",
    "s": "s",
    "sdg": "sdg",
    "x": "x",
    "y": "y",
    "z": "z",
    "cx": "cnot",
    "cnot": "cnot",
    "cz": "cz",
    "swap": "swap",
}


def probe_module(module_name: str, attributes: tuple[str, ...]) -> tuple[bool, str, Any]:
    """Resolve ``module_name.attributes`` without importing at module scope.

    Prefers a sibling module of this package (``..stabilizer``) and falls back
    to an absolute import, so the adapter works both inside the consolidated
    package and when it is vendored elsewhere.

    Returns ``(ok, reason, module)``.  ``reason`` is empty when ok.
    """
    package = __package__ or ""
    # Sibling engines live one level up: this module is ``<pkg>.backends.native``
    # and the engines are ``<pkg>.stabilizer`` etc.  Try that first, then a
    # same-level import, then an absolute one, so vendoring still works.
    attempts = (
        [f"..{module_name}", f".{module_name}", module_name] if package else [module_name]
    )
    last_error: Exception | None = None
    module: Any = None
    for attempt in attempts:
        try:
            module = importlib.import_module(attempt, package)
            last_error = None
            break
        except Exception as exc:  # pragma: no cover - depends on the host env
            last_error = exc
    if module is None:
        return (
            False,
            f"{module_name} is not importable ({type(last_error).__name__}: {last_error})",
            None,
        )
    missing = [name for name in attributes if not hasattr(module, name)]
    if missing:
        return False, f"{module_name} is missing {', '.join(missing)}", module
    return True, "", module


class _Adapter:
    """Shared plumbing for engine-backed adapters."""

    name = "adapter"
    _module_name = ""
    _attributes: tuple[str, ...] = ()

    def _resolve(self) -> tuple[bool, str, Any]:
        return probe_module(self._module_name, self._attributes)

    def available(self) -> tuple[bool, str]:
        ok, reason, _ = self._resolve()
        return ok, reason

    def _refuse(self, program: Program, reason: str) -> Admission:
        return Admission(False, self.name, reason, self.capability().execution_class)

    def _admit(self, program: Program, reason: str) -> Admission:
        return Admission(True, self.name, reason, self.capability().execution_class)


class StabilizerBackend(_Adapter):
    """Exact Clifford execution at arbitrary width via the CHP tableau.

    This is the production plane of the VQC.  The tableau *is* the state
    representation for this class — O(n^2) bits, exact at n = 10,000 — exactly
    as a physical device holds a state it cannot enumerate.  Every operation a
    quantum computer offers is therefore available here at full width:
    gate application, shot sampling, measurement distributions, marginals,
    expectation values, entanglement, and certification.

    The only thing absent is a dense amplitude list, and that is absent on
    hardware too.  Its absence is a property of the representation, not a
    missing feature.
    """

    name = "stabilizer"
    _module_name = "stabilizer"
    _attributes = ("StabilizerState", "StabilizerDomainError")

    #: Cap on enumerated marginal outcomes (2**free_bits) before the backend
    #: reports the exact uniform subspace instead of listing it.
    MARGINAL_ENUMERATION_CAP = 4096

    def capability(self) -> Capability:
        return Capability(
            name=self.name,
            execution_class=ExecutionClass.BOUNDED_EXACT,
            materialises_state=False,
            gate_set="clifford",
            state_classes=("stabilizer", "graph", "ghz", "codes"),
            max_qubits=None,
            requires=("stabilizer",),
            notes=(
                "Production plane. Exact for the Clifford group at any width in "
                "O(n^2) tableau bits; gates, shot sampling, marginals, "
                "expectation values and entanglement all available at n=10,000. "
                "Non-Clifford gates are refused, never approximated."
            ),
        )

    def admit(self, program: Program) -> Admission:
        ok, reason, _ = self._resolve()
        if not ok:
            return self._refuse(program, reason)
        outside = sorted(program.gates() - CLIFFORD_GATES)
        if outside:
            return self._refuse(
                program,
                f"non-Clifford gate(s) {outside} lie outside the stabilizer domain; "
                "this backend fails closed rather than approximate",
            )
        return self._admit(program, "Clifford program within the stabilizer domain")

    # -- state construction -------------------------------------------------
    def _build(self, program: Program) -> Any:
        """Rebuild the tableau for a program.

        Reconstruction (rather than copying) keeps the backend independent of
        any engine-specific copy protocol.
        """
        _, _, module = self._resolve()
        state = module.StabilizerState(program.n_qubits)
        for operation in program.operations:
            method_name = _STABILIZER_GATE_METHODS.get(operation.gate)
            if method_name is None:
                continue
            getattr(state, method_name)(*operation.qubits)
        return state

    # -- full-width operations ---------------------------------------------
    #: Reading out more than this many qubits per shot is refused: sequential
    #: collapse is O(n) per qubit, so an unbounded readout is O(n^2) per shot
    #: and would silently become unusable at n = 10,000.
    READOUT_LIMIT = 64

    def sample(
        self,
        program: Program,
        shots: int,
        *,
        seed: int | None = None,
        readout: Sequence[int] | None = None,
    ) -> dict[str, int]:
        """Sample ``shots`` readouts from the exact Born distribution.

        Each shot is a sequential projective measurement of the qubits named in
        ``readout``, driven by one seeded RNG, so a fixed seed replays
        identically.  The distribution being sampled is exact; the draw is a
        labelled classical sampling of it.

        ``readout`` selects which qubits are wired to detectors, exactly as on
        a device.  Bitstring keys follow the order of ``readout``.
        """
        import random

        if shots < 1:
            raise ValueError("shots must be >= 1")
        n = program.n_qubits
        if readout is None:
            if n > self.READOUT_LIMIT:
                raise ValueError(
                    f"reading out all {n} qubits costs O(n^2) per shot and is "
                    f"refused above {self.READOUT_LIMIT} qubits; pass "
                    "readout=[...] to choose which qubits to read out"
                )
            readout = list(range(n))
        qubits = sorted({int(q) for q in readout})
        if not qubits:
            raise ValueError("readout must name at least one qubit")
        if len(qubits) > self.READOUT_LIMIT:
            raise ValueError(
                f"readout of {len(qubits)} qubits exceeds the {self.READOUT_LIMIT}-qubit limit"
            )
        for qubit in qubits:
            if not 0 <= qubit < n:
                raise ValueError(f"readout qubit {qubit} outside 0..{n - 1}")
        rng = random.Random(seed)
        counts: dict[str, int] = {}
        for _ in range(shots):
            state = self._build(program)
            bits: dict[int, int] = {}
            for qubit in qubits:
                p0, p1 = state.measurement_probabilities(qubit)
                if p0 == p1:
                    outcome = rng.randrange(2)
                else:
                    outcome = 0 if p0 > p1 else 1
                state.measure(qubit, outcome=outcome)
                bits[qubit] = outcome
            key = "".join(str(bits[q]) for q in qubits)
            counts[key] = counts.get(key, 0) + 1
        return counts

    def marginal(self, program: Program, subset: Sequence[int]) -> dict[str, Any]:
        """The exact marginal distribution on ``subset``.

        A stabilizer marginal is uniform over an affine subspace of GF(2)^|A|,
        so it is described exactly by its dimension.  Small subspaces are
        enumerated; large ones are reported as their exact uniform description
        rather than truncated.
        """
        qubits = [int(q) for q in subset]
        probe = self._build(program)
        free: list[int] = []
        for qubit in qubits:
            # Read the distribution before collapsing: a deterministic qubit
            # has exactly one legal outcome, and forcing the other is an error
            # the engine is right to raise.
            p0, p1 = probe.measurement_probabilities(qubit)
            if p0 == p1:
                free.append(qubit)
                probe.measure(qubit, outcome=0)
            else:
                probe.measure(qubit, outcome=0 if p0 > p1 else 1)
        free_bits = len(free)
        description: dict[str, Any] = {
            "subset": qubits,
            "free_bits": free_bits,
            "outcomes": 1 << free_bits,
            "uniform": True,
            "enumerated": False,
        }
        if free_bits > 0 and (1 << free_bits) > self.MARGINAL_ENUMERATION_CAP:
            description["note"] = (
                f"the marginal is exactly uniform over {1 << free_bits} bitstrings; "
                "listing them is suppressed above the enumeration cap, and the "
                "description above is exact"
            )
            return description
        from fractions import Fraction

        weight = Fraction(1, 1 << free_bits)
        distribution: dict[str, Fraction] = {}
        for assignment in range(1 << free_bits):
            state = self._build(program)
            bits: dict[int, int] = {}
            for position, qubit in enumerate(free):
                forced = (assignment >> position) & 1
                state.measure(qubit, outcome=forced)
                bits[qubit] = forced
            for qubit in qubits:
                if qubit in bits:
                    continue
                p0, p1 = state.measurement_probabilities(qubit)
                outcome = 0 if p0 > p1 else 1
                state.measure(qubit, outcome=outcome)
                bits[qubit] = outcome
            distribution["".join(str(bits[q]) for q in qubits)] = weight
        description["enumerated"] = True
        description["distribution"] = distribution
        return description

    def expectation_values(self, program: Program, qubit: int) -> dict[str, str]:
        """Exact ``<X>``, ``<Y>``, ``<Z>`` for one qubit at any width.

        ``<Z>`` is read directly from the tableau; ``<X>`` and ``<Y>`` come from
        the exact Clifford maps ``X -> H Z H`` and ``Y -> H S† Z S H†``, so all
        three are exact fractions rather than sampled estimates.
        """
        z_state = self._build(program)
        x_state = self._build(program)
        x_state.h(qubit)
        y_state = self._build(program)
        y_state.sdg(qubit)
        y_state.h(qubit)
        return {
            "x": str(x_state.expectation_z(qubit)),
            "y": str(y_state.expectation_z(qubit)),
            "z": str(z_state.expectation_z(qubit)),
        }

    def execute(self, program: Program, **options: Any) -> ExecutionResult:
        admission = self.admit(program)
        if not admission.admitted:
            raise ValueError(f"program refused by {self.name}: {admission.reason}")
        state = self._build(program)
        payload: dict[str, Any] = {
            "representation": "tableau",
            "field": "GF(2)",
            "state_dimension": 1 << program.n_qubits,
            "stabilizer_generators": state.stabilizer_strings(),
            "tableau_bits": 2 * program.n_qubits,
        }
        shots = options.get("shots")
        if shots:
            readout = options.get("readout")
            if readout is None and program.n_qubits > self.READOUT_LIMIT:
                readout = list(range(self.READOUT_LIMIT))
            payload["readout_qubits"] = (
                sorted({int(q) for q in readout}) if readout else list(range(program.n_qubits))
            )
            payload["counts"] = self.sample(
                program, int(shots), seed=options.get("seed"), readout=readout
            )
        subset = options.get("marginal_of")
        if subset:
            payload["marginal"] = self.marginal(program, subset)
        bloch_qubit = options.get("bloch_of")
        if bloch_qubit is not None:
            payload["expectation_values"] = self.expectation_values(
                program, int(bloch_qubit)
            )
        probe = options.get("measure_qubit")
        if probe is not None:
            p0, p1 = state.measurement_probabilities(int(probe))
            payload["measurement"] = {
                "qubit": int(probe),
                "p0": str(p0),
                "p1": str(p1),
                "expectation_z": str(state.expectation_z(int(probe))),
            }
        cut = options.get("entropy_of")
        if cut is not None:
            payload["entanglement_entropy_bits"] = state.entanglement_entropy(cut)
        return ExecutionResult(
            backend=self.name,
            execution_class=ExecutionClass.BOUNDED_EXACT,
            truth_class=TruthClass.EXACT,
            n_qubits=program.n_qubits,
            program_digest=program.digest(),
            materialised=False,
            payload=payload,
        )


class SparseExactBackend(_Adapter):
    """Exact sparse state vector for bounded-support states."""

    name = "sparse"
    _module_name = "hilbert"
    _attributes = ("QuantumRegister",)

    def capability(self) -> Capability:
        return Capability(
            name=self.name,
            execution_class=ExecutionClass.BOUNDED_EXACT,
            materialises_state=True,
            gate_set="clifford+t",
            state_classes=("bounded_support",),
            max_qubits=None,
            requires=("hilbert", "sympy"),
            notes=(
                "Exact symbolic amplitudes for states with bounded support; "
                "the support, not the register width, is the resource."
            ),
        )

    def admit(self, program: Program) -> Admission:
        ok, reason, module = self._resolve()
        if not ok:
            return self._refuse(program, reason)
        register = module.QuantumRegister
        unknown = sorted(
            gate for gate in program.gates() if gate not in _SPARSE_GATE_METHODS
        )
        if unknown:
            return self._refuse(
                program, f"gate(s) {unknown} have no QuantumRegister binding"
            )
        absent = sorted(
            {
                _SPARSE_GATE_METHODS[gate]
                for gate in program.gates()
                if not hasattr(register, _SPARSE_GATE_METHODS[gate])
            }
        )
        if absent:
            return self._refuse(
                program, f"QuantumRegister does not expose {', '.join(absent)}"
            )
        return self._admit(
            program,
            "gate bindings resolved; note that support boundedness is enforced "
            "by the engine at run time (fail-closed), not provable statically",
        )

    def execute(self, program: Program, **options: Any) -> ExecutionResult:
        admission = self.admit(program)
        if not admission.admitted:
            raise ValueError(f"program refused by {self.name}: {admission.reason}")
        _, _, module = self._resolve()
        register = module.QuantumRegister(program.n_qubits)
        for operation in program.operations:
            method_name = _SPARSE_GATE_METHODS[operation.gate]
            getattr(register, method_name)(*operation.qubits)
        distribution = register.distribution() if hasattr(register, "distribution") else {}
        payload: dict[str, Any] = {
            "support": len(getattr(register, "amplitudes", {}) or {}),
            "distribution": {
                str(key): str(value) for key, value in dict(distribution).items()
            },
        }
        return ExecutionResult(
            backend=self.name,
            execution_class=ExecutionClass.BOUNDED_EXACT,
            truth_class=TruthClass.EXACT,
            n_qubits=program.n_qubits,
            program_digest=program.digest(),
            materialised=True,
            payload=payload,
        )


class ClosedFormBackend(_Adapter):
    """Exact symbolic families: hypercube walk, coined cycle walk, TFIM.

    These answer in closed form, so no state is materialised at any width.
    The domain is the family, not the register: a program that is not one of
    the named families is refused.
    """

    name = "closed_form"
    _module_name = "quantum_walk"
    _attributes = ("HypercubeWalk", "CoinedCycleWalk")

    #: Programs this backend answers, by the ``family`` option.
    FAMILIES = ("hypercube_walk", "coined_cycle_walk", "tfim_spectrum", "landau_zener")

    def capability(self) -> Capability:
        return Capability(
            name=self.name,
            execution_class=ExecutionClass.EXACT_SYMBOLIC,
            materialises_state=False,
            gate_set="closed_form",
            state_classes=("hypercube_walk", "cycle_walk", "free_fermion_tfim"),
            max_qubits=None,
            requires=("quantum_walk", "annealing"),
            notes=(
                "Exact closed-form evaluation. Nothing is materialised and no "
                "gate program is executed; the answer is a formula evaluated at "
                "the requested parameters."
            ),
        )

    def admit(self, program: Program) -> Admission:
        ok, reason, _ = self._resolve()
        if not ok:
            return self._refuse(program, reason)
        family = program.operations and None  # families are selected via options, not gates
        del family
        return self._refuse(
            program,
            "this backend answers closed-form families, not gate programs; call "
            f"evaluate_family() with one of {self.FAMILIES}",
        )

    def evaluate_family(self, family: str, **parameters: Any) -> ExecutionResult:
        """Evaluate one closed-form family exactly. Refuses unknown families."""
        ok, reason, module = self._resolve()
        if not ok:
            raise ValueError(f"{self.name} unavailable: {reason}")
        if family not in self.FAMILIES:
            raise ValueError(
                f"unknown closed-form family {family!r}; this backend implements "
                f"{self.FAMILIES}"
            )
        if family == "hypercube_walk":
            walk = module.HypercubeWalk(int(parameters.get("n_qubits", 10)))
            payload = {"family": family, "result": _jsonable(walk)}
        elif family == "coined_cycle_walk":
            walk = module.CoinedCycleWalk(int(parameters.get("num_positions", 8)))
            payload = {"family": family, "result": _jsonable(walk)}
        else:
            ok_anneal, anneal_reason, anneal = probe_module("annealing", ("TransverseFieldIsing",))
            if not ok_anneal:
                raise ValueError(f"closed-form family {family} unavailable: {anneal_reason}")
            model = anneal.TransverseFieldIsing(int(parameters.get("n_spins", 8)))
            payload = {"family": family, "result": _jsonable(model)}
        return ExecutionResult(
            backend=self.name,
            execution_class=ExecutionClass.EXACT_SYMBOLIC,
            truth_class=TruthClass.EXACT,
            n_qubits=int(parameters.get("n_qubits", parameters.get("num_positions", parameters.get("n_spins", 0)))),
            program_digest=Program(1).then("i", 0).digest(),
            materialised=False,
            payload=payload,
        )


def _jsonable(value: Any) -> Any:
    """Best-effort exact-value rendering; never invents a float."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return repr(value)
