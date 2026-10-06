"""The TURING VQC console — operate the machine.

This is the operator surface of the virtual quantum computer.  It allocates a
register, applies gates, samples shots, reports exact measurement
distributions and expectation values, measures entanglement, draws the
circuit, publishes the capability matrix, and issues a verifiable run witness.

Two state representations, both exact, both first class
-------------------------------------------------------
A quantum computer does not show you its amplitudes — for 64 qubits it cannot,
and neither can anything else.  It holds a state, lets you apply gates, and
answers questions.  This machine works the same way:

* **dense algebraic** — universal Clifford+T, every amplitude an exact element
  of ``Q(sqrt(2)) + i*Q(sqrt(2))``.  Used while ``2**n`` fits the
  materialisation budget; this is the register-wide *inspection* view.
* **tableau** — the Clifford state as its stabilizer tableau, ``2n`` bits,
  exact at any width including ``n = 10,000``.  Gates, shots, measurement
  distributions, marginals, expectation values and entanglement are all
  available here.

The tableau is not a fallback or a degraded mode.  It is the correct
representation for that state class, and it is what makes the wide register
real.  What it does not have is an amplitude list, and neither does hardware.

Refusal is part of the interface.  A program outside the exact domain is
refused with the backend that refused it and why, rather than answered
approximately.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Sequence

from .backends import (
    DEFAULT_MAX_AMPLITUDES,
    DomainError,
    Exact,
    ExactStatevector,
    Program,
    Q2,
    QPUBackend,
    QPUUnavailableError,
    StatevectorTooLargeError,
    execute as execute_program,
    execute_certified,
    select_backend,
)
from .capabilities import capability_report, render_matrix
from .certificates import (
    VQCComputationCertificate,
    issue_witness,
    verify_computation_certificate,
    verify_witness,
)

__all__ = ["QuantumConsole", "main", "render_circuit", "render_amplitudes", "DEMO_SCRIPT"]

BANNER = r"""
  ████████╗██╗   ██╗██████╗ ██╗███╗   ██╗ ██████╗
  ╚══██╔══╝██║   ██║██╔══██╗██║████╗  ██║██╔════╝
     ██║   ██║   ██║██████╔╝██║██╔██╗ ██║██║  ███╗
     ██║   ██║   ██║██╔══██╗██║██║╚██╗██║██║   ██║
     ██║   ╚██████╔╝██║  ██║██║██║ ╚████║╚██████╔╝
     ╚═╝    ╚═════╝ ╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝ ╚═════╝
        V I R T U A L   Q U A N T U M   C O M P U T E R
"""

SUBTITLE = (
    "exact algebra on a classical substrate · Clifford+T over Q(√2) + iQ(√2)\n"
    "register-native at any width · no physical QPU bound · refusals are deliberate"
)

_ONE_QUBIT = ("i", "x", "y", "z", "h", "s", "sdg", "t", "tdg")
_TWO_QUBIT = ("cx", "cnot", "cz", "swap")
_BLOCK = "█"

#: Readout width the console uses automatically for wide registers.
DEFAULT_READOUT_WIDTH = 64


def _bar(value: float, width: int = 24) -> str:
    filled = max(0, min(width, round(value * width)))
    return _BLOCK * filled + "·" * (width - filled)


def _states_label(n_qubits: int) -> str:
    """Compact label for a Hilbert-space dimension.

    Printing ``2**10000`` as a decimal is a 3,010-digit number; the exponent is
    the informative form.
    """
    if n_qubits <= 40:
        return f"{1 << n_qubits} basis states"
    return f"2^{n_qubits} basis states"


def _readout_label(qubits: Sequence[int]) -> str:
    """Compact label for a readout set, e.g. ``q0..q63 (64)``."""
    ordered = sorted(qubits)
    if len(ordered) <= 8:
        return " ".join(f"q{q}" for q in ordered)
    contiguous = ordered == list(range(ordered[0], ordered[0] + len(ordered)))
    if contiguous:
        return f"q{ordered[0]}..q{ordered[-1]} ({len(ordered)})"
    return f"{len(ordered)} qubits: " + " ".join(f"q{q}" for q in ordered[:8]) + " …"


def render_amplitudes(state: ExactStatevector, *, max_rows: int = 32) -> str:
    """Render the amplitude table with exact values and a display-only bar."""
    lines = [
        f"{'basis':>10}  {'amplitude (exact)':<28} {'probability':<12} {'|amp|':>6}  magnitude",
        f"{'-' * 10}  {'-' * 28} {'-' * 12} {'-' * 6}  {'-' * 24}",
    ]
    shown = 0
    for row in state.amplitude_table():
        probability = row["probability_approx"]
        if probability <= 0.0 and shown >= max_rows:
            continue
        lines.append(
            f"{row['bitstring']:>10}  {row['amplitude_exact']:<28} "
            f"{row['probability_exact']:<12} {abs(row['amplitude_approx']):6.3f}  "
            f"{_bar(probability)}"
        )
        shown += 1
        if shown >= max_rows:
            lines.append(f"{'…':>10}  ({len(state.support())} non-zero amplitudes total)")
            break
    return "\n".join(lines)


def render_circuit(program: Program) -> str:
    """Render the program as an ASCII circuit diagram."""
    if not program.operations:
        return "(empty circuit)"
    columns: list[dict[int, str]] = []
    for operation in program.operations:
        column: dict[int, str] = {}
        gate = operation.gate.upper()
        if gate in ("CX", "CNOT"):
            column[operation.qubits[0]] = "●"
            column[operation.qubits[1]] = "⊕"
        elif gate == "CZ":
            column[operation.qubits[0]] = "●"
            column[operation.qubits[1]] = "Z"
        elif gate == "SWAP":
            column[operation.qubits[0]] = "×"
            column[operation.qubits[1]] = "×"
        else:
            column[operation.qubits[0]] = gate
        columns.append(column)
    rows = []
    for qubit in range(program.n_qubits):
        cells = [column.get(qubit, "").center(3, "─") for column in columns]
        rows.append(f"q{qubit:<4}─" + "".join(cells) + "─")
    return "\n".join(rows)


def _reduced_bloch(state: ExactStatevector, qubit: int) -> tuple[Exact, Exact, Exact, Q2]:
    """Exact Bloch vector and purity for one qubit of a materialised state."""
    bit = 1 << qubit
    rho00 = Exact()
    rho11 = Exact()
    rho01 = Exact()
    rho10 = Exact()
    for index, amplitude in enumerate(state.amplitudes):
        if index & bit:
            rho11 = rho11 + amplitude * amplitude.conjugate()
            continue
        rho00 = rho00 + amplitude * amplitude.conjugate()
        partner = index | bit
        mate = state.amplitudes[partner]
        rho01 = rho01 + amplitude * mate.conjugate()
        rho10 = rho10 + mate * amplitude.conjugate()
    x = rho01 + rho10
    y = Exact(rho10.im, -rho10.re) + Exact(-rho01.im, rho01.re)
    z = rho00 - rho11
    purity = rho00 * rho00 + rho01 * rho10 + rho10 * rho01 + rho11 * rho11
    return x, y, z, purity


def _bloch_sphere(x: float, y: float, z: float, *, width: int = 21, height: int = 11) -> str:
    """A small ASCII Bloch sphere with the vector projected onto X-Z."""
    grid = [[" " for _ in range(width)] for _ in range(height)]
    cx, cy = (width - 1) / 2, (height - 1) / 2
    radius = min(cx, cy)
    for row in range(height):
        for col in range(width):
            dx = (col - cx) / radius
            dy = (row - cy) / radius
            if abs((dx * dx + dy * dy) ** 0.5 - 1.0) < 0.14:
                grid[row][col] = "·"
    for row, col in ((0, int(cx)), (height - 1, int(cx)), (int(cy), 0), (int(cy), width - 1)):
        grid[row][col] = "+"
    px = max(0, min(width - 1, int(round(cx + x * radius * 0.92))))
    pz = max(0, min(height - 1, int(round(cy - z * radius * 0.92))))
    grid[pz][px] = "@"
    header = f"  Bloch vector  x={x:+.3f}  y={y:+.3f}  z={z:+.3f}   (display floats; ρ is exact)"
    return header + "\n" + "\n".join("  " + "".join(row) for row in grid)


@dataclass
class ConsoleState:
    """The console's working set.

    ``state`` is populated when the selected backend materialises a dense
    algebraic state vector.  For wide Clifford registers the exact state lives
    in the engine's tableau and ``tableau`` holds its payload — a complete,
    exact description of the register, just not an amplitude list.
    """

    n_qubits: int = 0
    program: Program | None = None
    state: ExactStatevector | None = None
    tableau: dict[str, Any] | None = None
    last_result: Any = None
    history: list[str] = field(default_factory=list)

    @property
    def representation(self) -> str:
        if self.state is not None:
            return "dense_algebraic"
        return "tableau" if self.tableau else "none"

    @property
    def dense(self) -> bool:
        return self.state is not None


class QuantumConsole:
    """A scriptable virtual quantum computer."""

    def __init__(self, *, max_amplitudes: int = DEFAULT_MAX_AMPLITUDES, echo: bool = True) -> None:
        self.max_amplitudes = int(max_amplitudes)
        self.echo = echo
        self.session = ConsoleState()
        self._commands: dict[str, Callable[[list[str]], str]] = {
            "init": self._cmd_init,
            "qalloc": self._cmd_init,
            "reset": self._cmd_reset,
            "psi": self._cmd_psi,
            "state": self._cmd_psi,
            "amps": self._cmd_amps,
            "prob": self._cmd_prob,
            "measure": self._cmd_measure,
            "run": self._cmd_measure,
            "shots": self._cmd_measure,
            "generators": self._cmd_generators,
            "gen": self._cmd_generators,
            "expect": self._cmd_measurement,
            "measurement": self._cmd_measurement,
            "m": self._cmd_measurement,
            "entropy": self._cmd_entropy,
            "product": self._cmd_product,
            "bloch": self._cmd_bloch,
            "diagram": self._cmd_diagram,
            "circuit": self._cmd_diagram,
            "backends": self._cmd_backends,
            "capabilities": self._cmd_capabilities,
            "certify": self._cmd_certify,
            "qpu": self._cmd_qpu,
            "status": self._cmd_status,
            "help": self._cmd_help,
            "?": self._cmd_help,
        }
        for gate in _ONE_QUBIT + _TWO_QUBIT:
            self._commands.setdefault(gate, self._make_gate_command(gate))

    # -- gates --------------------------------------------------------------
    def _make_gate_command(self, gate: str) -> Callable[[list[str]], str]:
        def command(args: list[str]) -> str:
            return self._apply_gate(gate, args)
        return command

    def _apply_gate(self, gate: str, args: list[str]) -> str:
        if self.session.program is None:
            return self._need_register()
        arity = 2 if gate in _TWO_QUBIT else 1
        if len(args) < arity:
            return f"usage: {gate} " + " ".join(f"<q{i}>" for i in range(arity))
        try:
            qubits = tuple(int(a) for a in args[:arity])
        except ValueError:
            return f"{gate}: qubit indices must be integers"
        program = self.session.program
        for qubit in qubits:
            if not 0 <= qubit < program.n_qubits:
                return f"{gate}: qubit {qubit} outside 0..{program.n_qubits - 1}"
        try:
            new_program = Program(program.n_qubits, program.operations).then(gate, *qubits)
        except ValueError as exc:
            return f"{gate}: {exc}"
        try:
            result = execute_program(new_program, max_amplitudes=self.max_amplitudes)
        except StatevectorTooLargeError as exc:
            return self._refusal(gate, new_program, str(exc))
        except DomainError as exc:
            return f"{gate}: {exc}"
        self.session.program = new_program
        dense = result.payload.get("state")
        self.session.state = dense
        self.session.tableau = None if dense is not None else result.payload
        self.session.last_result = result
        self.session.history.append(f"{gate} {' '.join(str(q) for q in qubits)}")
        if dense is not None:
            detail = f"‖ψ‖² = {result.payload.get('norm_sq_exact', 'n/a')}"
        else:
            detail = f"tableau {result.payload.get('tableau_bits')} bits"
        return (
            f"applied {gate} {' '.join(str(q) for q in qubits)}  "
            f"[{result.backend} · {result.truth_class.value} · {detail}]"
        )

    def _refusal(self, gate: str, program: Program, reason: str) -> str:
        _, admission = select_backend(program, max_amplitudes=self.max_amplitudes)
        return (
            f"REFUSED {gate}: {reason}\n"
            f"  backend verdict: {admission.backend} — {admission.reason}\n"
            "  this machine will not approximate a state it cannot represent exactly."
        )

    # -- session ------------------------------------------------------------
    def _cmd_init(self, args: list[str]) -> str:
        if not args:
            return "usage: init <n_qubits>"
        try:
            n = int(args[0])
        except ValueError:
            return "init: n_qubits must be an integer"
        if n < 1:
            return "init: n_qubits must be >= 1"
        self.session = ConsoleState(n_qubits=n, program=Program(n))
        if (1 << n) <= self.max_amplitudes:
            representation = (
                f"dense_algebraic — universal Clifford+T, {1 << n} exact amplitudes"
            )
        else:
            representation = (
                f"tableau — exact Clifford state in {2 * n} bits; "
                "non-Clifford gates will be refused, not approximated"
            )
        return f"allocated |q{n}⟩\n  representation  {representation}"

    def _cmd_reset(self, args: list[str]) -> str:
        if self.session.n_qubits == 0:
            return "nothing to reset"
        return self._cmd_init([str(self.session.n_qubits)])

    def _cmd_status(self, args: list[str]) -> str:
        if self.session.program is None:
            return "no register allocated"
        program = self.session.program
        backend, admission = select_backend(program, max_amplitudes=self.max_amplitudes)
        return (
            f"register        |q{program.n_qubits}⟩  ({_states_label(program.n_qubits)})\n"
            f"representation  {self.session.representation}\n"
            f"gates           {program.gate_counts()}\n"
            f"clifford        {program.is_clifford()}\n"
            f"program sha256  {program.digest()}\n"
            f"selected        {backend.name if backend else 'none'}\n"
            f"verdict         {admission.reason}"
        )

    # -- state readout ------------------------------------------------------
    def _cmd_psi(self, args: list[str]) -> str:
        if self.session.program is None:
            return self._need_register()
        if self.session.state is None:
            return self._tableau_psi(args)
        state = self.session.state
        limit = int(args[0]) if args else 8
        return (
            f"|ψ⟩ = {state.dirac(max_terms=limit)}\n"
            f"  register        |q{state.n_qubits}⟩   ({1 << state.n_qubits} basis states, "
            f"{len(state.support())} non-zero)\n"
            f"  representation  dense_algebraic\n"
            f"  field           Q(√2) + iQ(√2)\n"
            f"  ‖ψ‖²            {state.norm_sq()}   (exact)\n"
            f"  normalised      {state.is_normalised()}"
        )

    def _tableau_psi(self, args: list[str]) -> str:
        program = self.session.program
        assert program is not None
        payload = self.session.tableau or {}
        generators = payload.get("stabilizer_generators") or []
        limit = int(args[0]) if args else 6
        lines = [
            f"|ψ⟩ on |q{program.n_qubits}⟩ — {_states_label(program.n_qubits)}",
            "  representation  tableau "
            f"({payload.get('tableau_bits', 2 * program.n_qubits)} bits, exact)",
            f"  field           GF(2) Pauli group (Clifford)",
            f"  generators      {len(generators)} — showing {min(limit, len(generators))}",
        ]
        for generator in generators[:limit]:
            shown = generator if len(generator) <= 44 else generator[:41] + "..."
            lines.append(f"    {shown}")
        if len(generators) > limit:
            lines.append(f"    … {len(generators) - limit} more  (see `generators`)")
        lines.append(
            "  This is the complete state. A dense amplitude vector over "
            f"{_states_label(program.n_qubits)} does not exist on this machine or "
            "on hardware; use `measure`, `expect`, `prob` or `entropy` to query it."
        )
        return "\n".join(lines)

    def _cmd_generators(self, args: list[str]) -> str:
        if self.session.program is None:
            return self._need_register()
        if self.session.tableau is None:
            return (
                "this register uses the dense algebraic representation; "
                "use `psi` or `amps` for its amplitudes, or `bloch <q>`"
            )
        generators = self.session.tableau.get("stabilizer_generators") or []
        limit = int(args[0]) if args else 32
        lines = [f"stabilizer generators ({len(generators)} total, exact)"]
        for generator in generators[:limit]:
            lines.append(f"  {generator}")
        if len(generators) > limit:
            lines.append(f"  … {len(generators) - limit} more")
        return "\n".join(lines)

    def _cmd_amps(self, args: list[str]) -> str:
        if self.session.program is None:
            return self._need_register()
        if self.session.state is None:
            return (
                f"this register spans {_states_label(self.session.program.n_qubits)} "
                "and uses the tableau representation, so there is no amplitude list "
                "to print — the same is true of any 64+ qubit device.\n"
                "  available exact queries: `psi`, `generators`, `measure`, `expect <q>`, "
                "`prob <q...>`, `entropy <q...>`"
            )
        return render_amplitudes(self.session.state)

    def _cmd_prob(self, args: list[str]) -> str:
        if self.session.program is None:
            return self._need_register()
        if self.session.state is not None:
            probabilities = self.session.state.probabilities()
            lines = ["index  bitstring  probability (exact)"]
            for index, probability in enumerate(probabilities):
                if probability.is_zero():
                    continue
                lines.append(
                    f"{index:>5}  {self.session.state.bitstring(index):>9}  {probability}"
                )
            return "\n".join(lines)
        program = self.session.program
        subset = [int(a) for a in args] if args else list(range(min(program.n_qubits, 8)))
        try:
            result = execute_program(
                program, max_amplitudes=self.max_amplitudes, marginal_of=subset
            )
        except (StatevectorTooLargeError, DomainError, ValueError) as exc:
            return f"REFUSED: {exc}"
        marginal = result.payload.get("marginal", {})
        lines = [
            f"exact marginal on {_readout_label(subset)}",
            f"  uniform over {marginal.get('outcomes')} outcome(s), "
            f"{marginal.get('free_bits')} free bit(s)",
        ]
        distribution = marginal.get("distribution")
        if distribution:
            for bitstring, probability in sorted(distribution.items()):
                lines.append(
                    f"  |{bitstring}⟩  {probability}  {_bar(float(probability), 28)}"
                )
        else:
            lines.append(f"  {marginal.get('note', '')}")
        lines.append("  marginal probabilities are exact Q(√2) values.")
        return "\n".join(lines)

    def _cmd_measure(self, args: list[str]) -> str:
        if self.session.program is None:
            return self._need_register()
        program = self.session.program
        shots, seed, readout, positional = 1024, None, None, []
        index = 0
        while index < len(args):
            token = args[index]
            if token in ("--seed", "-s") and index + 1 < len(args):
                index += 1
                seed = int(args[index])
            elif token.startswith("--seed="):
                seed = int(token.split("=", 1)[1])
            elif token in ("--readout", "-r") and index + 1 < len(args):
                index += 1
                readout = [int(q) for q in args[index].replace(",", " ").split()]
            elif token.startswith("--readout="):
                readout = [int(q) for q in token.split("=", 1)[1].replace(",", " ").split()]
            else:
                positional.append(token)
            index += 1
        if positional:
            shots = int(positional[0])
        auto = False
        if readout is None:
            if program.n_qubits <= DEFAULT_READOUT_WIDTH:
                readout = list(range(program.n_qubits))
            else:
                readout = list(range(DEFAULT_READOUT_WIDTH))
                auto = True
        try:
            result = execute_program(
                program,
                max_amplitudes=self.max_amplitudes,
                shots=shots,
                seed=seed,
                readout=readout,
            )
        except (StatevectorTooLargeError, DomainError, ValueError) as exc:
            return f"REFUSED: {exc}"
        counts = result.payload.get("counts", {})
        used = result.payload.get("readout_qubits", readout)
        total = sum(counts.values()) or 1
        lines = [
            f"job  {shots} shots   backend {result.backend}   seed {seed}",
            f"readout  {_readout_label(used)}"
            + (f"   (auto: first {len(used)} of {program.n_qubits})" if auto else ""),
        ]
        for bitstring, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:20]:
            lines.append(
                f"  |{bitstring}⟩  {count:>7}  {count / total:7.4f}  {_bar(count / total, 28)}"
            )
        if len(counts) > 20:
            lines.append(f"  … {len(counts) - 20} further outcomes")
        lines.append(
            "  the distribution is exact; the draw is a labelled classical sampling of it."
        )
        return "\n".join(lines)

    def _cmd_measurement(self, args: list[str]) -> str:
        if self.session.program is None:
            return self._need_register()
        if not args:
            return "usage: expect <q>"
        qubit = int(args[0])
        program = self.session.program
        if self.session.tableau is not None:
            result = execute_program(
                program, max_amplitudes=self.max_amplitudes, bloch_of=qubit
            )
            values = result.payload.get("expectation_values", {})
            return (
                f"exact expectation values for q{qubit} (any width)\n"
                f"  ⟨X⟩ = {values.get('x')}\n"
                f"  ⟨Y⟩ = {values.get('y')}\n"
                f"  ⟨Z⟩ = {values.get('z')}\n"
                "  computed by exact Clifford maps X→HZH, Y→HS†ZSH† — not sampled"
            )
        x, y, z, purity = _reduced_bloch(self.session.state, qubit)
        return (
            f"exact expectation values for q{qubit}\n"
            f"  ⟨X⟩ = {x}\n  ⟨Y⟩ = {y}\n  ⟨Z⟩ = {z}\n"
            f"  purity tr(ρ²) = {purity}"
        )

    def _cmd_entropy(self, args: list[str]) -> str:
        if self.session.program is None:
            return self._need_register()
        if not args:
            return "usage: entropy <q> [q ...]"
        subset = [int(a) for a in args]
        if self.session.tableau is not None:
            result = execute_program(
                self.session.program, max_amplitudes=self.max_amplitudes, entropy_of=subset
            )
            value = result.payload.get("entanglement_entropy_bits")
            return (
                f"cut {subset} | rest   S = {value} e-bits (exact integer)\n"
                "  stabilizer entanglement is an exact integer; no float is involved."
            )
        state = self.session.state
        lines = [
            f"cut {subset} | rest   S = {state.entropy_bits(subset):.6f} bits",
            "  exact marginal probabilities:",
        ]
        for key, value in sorted(state.marginal_probabilities(subset).items()):
            lines.append(f"    {key}  {value}")
        lines.append("  marginals are exact; the entropy value is a display float.")
        return "\n".join(lines)

    def _cmd_product(self, args: list[str]) -> str:
        if self.session.program is None:
            return self._need_register()
        if len(args) < 2:
            return "usage: product <q> <q> [q ...]"
        subset = [int(a) for a in args]
        if self.session.tableau is not None:
            result = execute_program(
                self.session.program, max_amplitudes=self.max_amplitudes, entropy_of=subset
            )
            value = result.payload.get("entanglement_entropy_bits")
            verdict = "SEPARABLE (product)" if value == 0 else f"ENTANGLED (S = {value} e-bits)"
            return f"subsystem {subset} is {verdict} — exact integer, no tolerance"
        separable = self.session.state.is_product_state(subset)
        return (
            f"subsystem {subset} is {'SEPARABLE (product)' if separable else 'ENTANGLED'} "
            "— decided by exact marginal comparison, not a tolerance"
        )

    def _cmd_bloch(self, args: list[str]) -> str:
        if self.session.program is None:
            return self._need_register()
        if self.session.state is None:
            return (
                "a Bloch sphere needs a materialised reduced density matrix; on this "
                "register use `expect <q>` for exact ⟨X⟩, ⟨Y⟩, ⟨Z⟩."
            )
        qubit = int(args[0]) if args else 0
        x, y, z, purity = _reduced_bloch(self.session.state, qubit)
        # Bloch components are Hermitian expectation values: real by construction.
        return (
            _bloch_sphere(x.re.approx(), y.re.approx(), z.re.approx())
            + f"\n  purity tr(ρ²) = {purity}   (exact; 1 means pure)"
            + f"\n  ⟨X⟩={x}  ⟨Y⟩={y}  ⟨Z⟩={z}   (exact)"
        )

    def _cmd_diagram(self, args: list[str]) -> str:
        if self.session.program is None:
            return self._need_register()
        return render_circuit(self.session.program)

    # -- machine-level ------------------------------------------------------
    def _cmd_backends(self, args: list[str]) -> str:
        return render_matrix(max_amplitudes=self.max_amplitudes)

    def _cmd_capabilities(self, args: list[str]) -> str:
        report = capability_report(max_amplitudes=self.max_amplitudes)
        lines = [
            "LOGICAL REGISTER",
            "  " + report["statements"]["logical_register"],
            "",
            "EXACTNESS",
            "  " + report["statements"]["exactness"],
            "",
            "HARDWARE",
            "  " + report["statements"]["hardware"],
            "",
            "NOT AVAILABLE",
        ]
        for entry in report["unavailable"]:
            lines.append(f"  ✗ {entry['item']}")
            lines.append(f"      {entry['why']}")
        lines.append("")
        lines.append(f"claim boundary clean: {report['claim_boundary_clean']}")
        return "\n".join(lines)

    def _cmd_certify(self, args: list[str]) -> str:
        if self.session.program is None or self.session.last_result is None:
            return "nothing to certify: apply at least one gate first"
        result = execute_program(self.session.program, max_amplitudes=self.max_amplitudes)
        witness = issue_witness(
            self.session.program, result, notes="issued from the VQC console"
        )
        verified = verify_witness(witness)
        if result.certificate is None:
            return "certificate boundary failure: public execution returned no certificate"
        certificate = VQCComputationCertificate.from_dict(result.certificate)
        certificate_verified = verify_computation_certificate(
            self.session.program,
            result,
            certificate,
        )
        return (
            "computation certificate and run witness issued and verified\n"
            + json.dumps(certificate.to_dict(), sort_keys=True, indent=2)
            + f"\ncertificate digest: {certificate.certificate_digest}"
            + f"\ncertificate verified: {certificate_verified}\n"
            + witness.to_json()
            + f"\nwitness digest: {witness.digest()}\nverified: {verified}"
        )

    def _cmd_qpu(self, args: list[str]) -> str:
        backend = QPUBackend()
        available, reason = backend.available()
        lines = [
            f"QPU boundary   available={available}   measured_qpu=False",
            f"  {reason}",
        ]
        if self.session.program is not None:
            try:
                execution = execute_certified(
                    self.session.program,
                    prefer="qpu",
                    max_amplitudes=self.max_amplitudes,
                )
                lines[0] = "QPU boundary   available=True   measured_qpu=True"
                lines.append(
                    "  certified hardware result: "
                    + execution.certificate.certificate_digest
                )
            except QPUUnavailableError:
                lines.append("  submission attempt: REFUSED")
        if not available:
            lines.append(
                "  Exact classical quantum algebra is not relabelled as measured hardware."
            )
        return "\n".join(lines)

    def _cmd_help(self, args: list[str]) -> str:
        groups = [
            ("register", "init <n> | reset | status"),
            ("gates", " ".join(_ONE_QUBIT) + " <q>  |  " + " ".join(_TWO_QUBIT) + " <q> <q>"),
            ("readout", "psi | amps | prob [q...] | diagram"),
            (
                "quantum",
                "measure [shots] [--seed s] [--readout q,q] | expect <q> | "
                "entropy <q...> | product <q> <q>",
            ),
            ("tableau", "generators [n]"),
            ("machine", "backends | capabilities | certify | qpu"),
            ("session", "help | quit"),
        ]
        lines = ["commands"]
        for name, body in groups:
            lines.append(f"  {name:<9} {body}")
        return "\n".join(lines)

    def _need_register(self) -> str:
        return "no register: run `init <n>` first"

    # -- driver -------------------------------------------------------------
    def do(self, line: str) -> str:
        """Execute one console line and return its output."""
        text = line.strip()
        if not text or text.startswith("#"):
            return ""
        parts = text.split()
        name = parts[0].lower()
        args = parts[1:]
        if name in ("quit", "exit", "q!"):
            return "__QUIT__"
        command = self._commands.get(name)
        if command is None:
            return f"unknown command {name!r} — try `help`"
        try:
            return command(args)
        except StatevectorTooLargeError as exc:
            return f"REFUSED: {exc}"
        except DomainError as exc:
            return f"REFUSED: {exc}"
        except (ValueError, IndexError) as exc:
            return f"{name}: {exc}"

    def run_script(self, lines: Iterable[str]) -> list[tuple[str, str]]:
        """Run a list of console lines, returning ``(line, output)`` pairs."""
        output = []
        for line in lines:
            text = self.do(line)
            if text == "__QUIT__":
                break
            output.append((line, text))
        return output

    def banner(self) -> str:
        return f"{BANNER}\n{SUBTITLE}\n\n{self._cmd_help([])}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="turing-vqc",
        description="TURING Virtual Quantum Computer — exact-algebra console.",
    )
    parser.add_argument("--script", help="run a console script instead of a REPL")
    parser.add_argument(
        "--max-amplitudes",
        type=int,
        default=DEFAULT_MAX_AMPLITUDES,
        help="materialisation budget for the dense algebraic representation",
    )
    parser.add_argument("--quiet", action="store_true", help="suppress the banner")
    parser.add_argument("--demo", action="store_true", help="run the demonstration and exit")
    args = parser.parse_args(argv)

    console = QuantumConsole(max_amplitudes=args.max_amplitudes)
    if not args.quiet:
        print(console.banner())

    if args.demo:
        for line in DEMO_SCRIPT:
            print(f"\n> {line}")
            output = console.do(line)
            if output == "__QUIT__":
                break
            if output:
                print(output)
        return 0

    if args.script:
        with open(args.script, "r", encoding="utf-8") as handle:
            lines = handle.readlines()
        for line, output in console.run_script(lines):
            print(f"\n> {line.strip()}")
            if output:
                print(output)
        return 0

    while True:
        try:
            line = input("vqc⟩ ")
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        output = console.do(line)
        if output == "__QUIT__":
            return 0
        if output:
            print(output)


DEMO_SCRIPT: tuple[str, ...] = (
    "init 3",
    "h 0",
    "cx 0 1",
    "cx 1 2",
    "psi",
    "diagram",
    "measure 2048 --seed 7",
    "expect 0",
    "bloch 0",
    "entropy 0",
    "certify",
    "init 10000",
    "h 0",
    "cx 0 9999",
    "status",
    "psi 2",
    "expect 0",
    "prob 0 9999",
    "entropy 0",
    "measure 128 --seed 3 --readout 0,9999",
    "capabilities",
    "qpu",
)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
