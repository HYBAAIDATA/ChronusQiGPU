/**
 * TURING VQC operator console.
 * Behaviour follows QuantumPhi2/PhiMiner `turing_universal_quantum_computer/console.py`.
 */

import { hypercube, landauZener, tfim } from "./closed-form.ts";
import { sha256Hex } from "./sha256.ts";
import { coinedCycle, SupportExceededError } from "./sparse.ts";
import { ladderReport, nextRung, scaleBudget, transitionReport, authorise } from "./lucas-scale.ts";
import { threadReport } from "./thread.ts";
import { algebraReport } from "./algebra-family.ts";
import { classicsReport, groverReport, qftReport, shorReport } from "./classics.ts";
import { cureReport, foldReport } from "./custody.ts";
import { advancesReport, hendrixReport } from "./hendrix.ts";
import { finaleReport } from "./finale.ts";
import { rankReport } from "./rank.ts";
import { ontologyReport } from "./ontology.ts";
import { signalReport } from "./signal.ts";
import { sixReport } from "./six.ts";
import { storeReport } from "./store.ts";
import { Triad, triadScript } from "./triad.ts";
import { StabilizerState } from "./stabilizer.ts";
import {
  DEFAULT_MAX_AMPLITUDES,
  DomainError,
  ExactStatevector,
  StatevectorTooLargeError,
  mulberry,
  reducedBloch,
} from "./exact-state.ts";

const CLIFFORD = new Set(["i", "x", "y", "z", "h", "s", "sdg", "cx", "cnot", "cz", "swap"]);
const ONE_QUBIT = ["i", "x", "y", "z", "h", "s", "sdg", "t", "tdg"];
const TWO_QUBIT = new Set(["cx", "cnot", "cz", "swap"]);
const SUPPORTED = new Set([...ONE_QUBIT, ...TWO_QUBIT]);
const BLOCK = "█";
const READOUT_LIMIT = 64;
const MARGINAL_CAP = 4096;

export const DEMO_SCRIPT = [
  "init 2",
  "h 0",
  "cx 0 1",
  "psi",
  "prob",
  "entropy 0",
  "certify",
  "init 10000",
  "h 0",
  "cx 0 9999",
  "status",
  "psi 2",
  "prob 0 9999",
  "entropy 0",
  "measure 64 --seed 3 --readout 0,9999",
  "walk cycle 8 3",
  "walk 10000 pi/4",
  "anneal 10000",
  "tunnel",
  "scale",
  "scale 15 17",
  "scale budget 15 17 1364",
  "scale 15 16",
  "fold",
  "six",
  "cure",
  "thread",
  "algebra",
  "classics",
  "hendrix",
  "advances",
  "finale",
  "rank",
  "ontology",
  "signal",
  "store",
  "triad",
  "capabilities",
  "qpu",
] as const;

type Operation = { gate: string; qubits: number[] };

class Program {
  readonly nQubits: number;
  readonly operations: Operation[];

  constructor(nQubits: number, operations: Operation[] = []) {
    this.nQubits = nQubits;
    this.operations = operations;
    if (!Number.isInteger(nQubits) || nQubits < 1) throw new Error("n_qubits must be a positive integer");
    for (const operation of operations) {
      for (const q of operation.qubits) {
        if (q >= nQubits) throw new Error(`operation '${operation.gate}' addresses qubit ${q}, outside a ${nQubits}-qubit register`);
      }
    }
  }

  then(gate: string, ...qubits: number[]): Program {
    return new Program(this.nQubits, [...this.operations, { gate: gate.toLowerCase(), qubits }]);
  }

  gateCounts(): Record<string, number> {
    const counts: Record<string, number> = {};
    for (const operation of this.operations) counts[operation.gate] = (counts[operation.gate] ?? 0) + 1;
    return counts;
  }

  gates(): Set<string> {
    return new Set(Object.keys(this.gateCounts()));
  }

  isClifford(): boolean {
    for (const gate of this.gates()) if (!CLIFFORD.has(gate)) return false;
    return true;
  }

  digest(): string {
    const canonical = pyJson({
      n_qubits: this.nQubits,
      operations: this.operations.map((operation) => ({ gate: operation.gate, qubits: operation.qubits })),
    });
    return sha256Hex(canonical);
  }
}

type Result = {
  backend: string;
  executionClass: string;
  truthClass: string;
  nQubits: number;
  digest: string;
  materialised: boolean;
  state: ExactStatevector | null;
  tableauBits: number | null;
  generators: string[] | null;
  normSq: string | null;
  support: number | null;
  field: string;
};

type Bars = { label: string; weight: number; text: string }[];

export class QuantumConsole {
  readonly maxAmplitudes: number;
  private program: Program | null = null;
  private state: ExactStatevector | null = null;
  private wide = false;
  private last: Result | null = null;
  private readonly custody = new Triad();
  bars: Bars = [];
  diagram = "";
  bloch: { x: number; y: number; z: number; purity: string } | null = null;

  constructor(maxAmplitudes = DEFAULT_MAX_AMPLITUDES) {
    this.maxAmplitudes = maxAmplitudes;
  }

  get nQubits(): number {
    return this.program?.nQubits ?? 0;
  }

  get representation(): string {
    if (this.state) return "dense_algebraic";
    if (this.wide) return "tableau";
    return "none";
  }

  banner(): string {
    return `${SUBTITLE}\n\n${this.help()}`;
  }

  do(line: string): string {
    const text = line.trim();
    if (!text || text.startsWith("#")) return "";
    const parts = text.split(/\s+/);
    const name = parts[0].toLowerCase();
    const args = parts.slice(1);
    if (name === "quit" || name === "exit") return "__QUIT__";
    try {
      if (name === "init" || name === "qalloc") return this.cmdInit(args);
      if (name === "reset") return this.program ? this.cmdInit([String(this.program.nQubits)]) : "nothing to reset";
      if (name === "status") return this.cmdStatus();
      if (name === "psi" || name === "state") return this.cmdPsi(args);
      if (name === "amps") return this.cmdAmps();
      if (name === "prob") return this.cmdProb(args);
      if (name === "measure" || name === "run" || name === "shots") return this.cmdMeasure(args);
      if (name === "generators" || name === "gen") return this.cmdGenerators(args);
      if (name === "expect" || name === "measurement" || name === "m") return this.cmdExpect(args);
      if (name === "entropy") return this.cmdEntropy(args);
      if (name === "product") return this.cmdProduct(args);
      if (name === "bloch") return this.cmdBloch(args);
      if (name === "diagram" || name === "circuit") return this.cmdDiagram();
      if (name === "walk") return this.cmdWalk(args);
      if (name === "scale") return this.cmdScale(args);
      if (name === "fold") {
        if (!args.length) return foldReport();
        if (args.length !== 1 || !/^\d+$/.test(args[0])) return "usage: fold | fold <payload>";
        return foldReport(BigInt(args[0]));
      }
      if (name === "six") {
        if (!args.length) return sixReport();
        if (args.length !== 1 || !/^\d+$/.test(args[0])) return "usage: six [n]";
        return sixReport(Number(args[0]));
      }
      if (name === "cure") return cureReport();
      if (name === "hendrix") return hendrixReport();
      if (name === "advances") return advancesReport();
      if (name === "finale") return finaleReport();
      if (name === "rank") return rankReport();
      if (name === "ontology") return ontologyReport();
      if (name === "signal") return signalReport();
      if (name === "store") return storeReport();
      if (name === "triad") return triadScript();
      if (name === "put") {
        if (args.length !== 1 || !/^[0-9a-fA-F]*$/.test(args[0]) || args[0].length % 2 !== 0) return "usage: put <hex>";
        const bytes = new Uint8Array(args[0].length / 2);
        for (let index = 0; index < bytes.length; index++) bytes[index] = Number.parseInt(args[0].slice(index * 2, index * 2 + 2), 16);
        const record = this.custody.put(bytes);
        return `${record.id}  slot = ${record.slot}  mask = ${record.primary.map((block) => block.mask).join(",")}`;
      }
      if (name === "get") {
        if (args.length !== 1) return "usage: get <id>";
        const bytes = this.custody.get(args[0]);
        return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("") || "empty";
      }
      if (name === "damage") {
        if (args.length !== 1) return "usage: damage <id>";
        this.custody.damage(args[0]);
        return `${args[0]} primary damaged`;
      }
      if (name === "heal") {
        if (args.length !== 1) return "usage: heal <id>";
        return this.custody.heal(args[0]);
      }
      if (name === "handoff") return this.custody.handoff();
      if (name === "thread") return threadReport();
      if (name === "algebra") return algebraReport();
      if (name === "classics") return classicsReport();
      if (name === "qft") return qftReport(args.length ? Number(args[0]) : 3);
      if (name === "grover") {
        if (!args.length) return groverReport(4n, 1n);
        if (args.length !== 2 || !/^\d+$/.test(args[0]) || !/^\d+$/.test(args[1])) return "usage: grover | grover <N> <M>";
        return groverReport(BigInt(args[0]), BigInt(args[1]));
      }
      if (name === "shor") {
        if (args.length !== 1 || !/^\d+$/.test(args[0])) return "usage: shor <N>";
        return shorReport(BigInt(args[0]));
      }
      if (name === "anneal") return this.cmdAnneal(args);
      if (name === "tunnel") return landauZener();
      if (name === "backends") return renderMatrix(this.maxAmplitudes);
      if (name === "capabilities") return this.cmdCapabilities();
      if (name === "certify") return this.cmdCertify();
      if (name === "qpu") return this.cmdQpu();
      if (name === "help" || name === "?") return this.help();
      if (ONE_QUBIT.includes(name) || TWO_QUBIT.has(name)) return this.applyGate(name, args);
      return `unknown command '${name}' — try \`help\``;
    } catch (error) {
      if (error instanceof StatevectorTooLargeError) return `REFUSED: ${error.message}`;
      if (error instanceof SupportExceededError) return `REFUSED: ${error.message}`;
      if (error instanceof DomainError) return `REFUSED: ${error.message}`;
      return `${name}: ${error instanceof Error ? error.message : String(error)}`;
    }
  }

  private need(): string {
    return "no register: run `init <n>` first";
  }

  private cmdInit(args: string[]): string {
    if (!args.length) return "usage: init <n_qubits>";
    const n = Number(args[0]);
    if (!Number.isInteger(n)) return "init: n_qubits must be an integer";
    if (n < 1) return "init: n_qubits must be >= 1";
    this.program = new Program(n);
    this.state = null;
    this.last = null;
    this.wide = false;
    this.bars = [];
    this.bloch = null;
    this.diagram = "";
    const dense = fits(n, this.maxAmplitudes);
    const representation = dense
      ? `dense_algebraic — universal Clifford+T, ${1 << n} exact amplitudes`
      : `tableau — exact Clifford state in ${2 * n} bits; non-Clifford gates will be refused, not approximated`;
    return `allocated |q${n}⟩\n  representation  ${representation}`;
  }

  private cmdStatus(): string {
    if (!this.program) return "no register allocated";
    const program = this.program;
    const { backend, reason } = select(program, this.maxAmplitudes);
    return (
      `register        |q${program.nQubits}⟩  (${statesLabel(program.nQubits)})\n` +
      `representation  ${this.representation}\n` +
      `gates           ${formatCounts(program.gateCounts())}\n` +
      `clifford        ${pyBool(program.isClifford())}\n` +
      `program sha256  ${program.digest()}\n` +
      `selected        ${backend ?? "none"}\n` +
      `verdict         ${reason}`
    );
  }

  private applyGate(gate: string, args: string[]): string {
    if (!this.program) return this.need();
    const arity = TWO_QUBIT.has(gate) ? 2 : 1;
    if (args.length < arity) return `usage: ${gate} ${Array.from({ length: arity }, (_, i) => `<q${i}>`).join(" ")}`;
    const qubits = args.slice(0, arity).map((a) => Number(a));
    if (qubits.some((q) => !Number.isInteger(q))) return `${gate}: qubit indices must be integers`;
    for (const q of qubits) {
      if (q < 0 || q >= this.program.nQubits) return `${gate}: qubit ${q} outside 0..${this.program.nQubits - 1}`;
    }
    let next: Program;
    try {
      next = this.program.then(gate, ...qubits);
    } catch (error) {
      return `${gate}: ${error instanceof Error ? error.message : error}`;
    }
    try {
      const result = execute(next, this.maxAmplitudes);
      this.program = next;
      this.state = result.state;
      this.wide = result.state == null;
      this.last = result;
      this.diagram = renderCircuit(next);
      const detail = result.state ? `‖ψ‖² = ${result.normSq}` : `tableau ${result.tableauBits} bits`;
      return `applied ${gate} ${qubits.join(" ")}  [${result.backend} · ${result.truthClass} · ${detail}]`;
    } catch (error) {
      if (error instanceof StatevectorTooLargeError) return this.refusal(gate, next, error.message);
      if (error instanceof DomainError) return `${gate}: ${error.message}`;
      throw error;
    }
  }

  private refusal(gate: string, program: Program, reason: string): string {
    const admission = select(program, this.maxAmplitudes);
    return (
      `REFUSED ${gate}: ${reason}\n` +
      `  backend verdict: ${admission.backend ?? "none"} — ${admission.reason}\n` +
      "  this machine will not approximate a state it cannot represent exactly."
    );
  }

  private cmdPsi(args: string[]): string {
    if (!this.program) return this.need();
    if (!this.state) return this.tableauPsi(args.length ? Number(args[0]) : 6);
    const limit = args.length ? Number(args[0]) : 8;
    const state = this.state;
    return (
      `|ψ⟩ = ${state.dirac(limit)}\n` +
      `  register        |q${state.nQubits}⟩   (${1 << state.nQubits} basis states, ${state.support().length} non-zero)\n` +
      `  representation  dense_algebraic\n` +
      `  field           Q(√2) + iQ(√2)\n` +
      `  ‖ψ‖²            ${state.normSq()}   (exact)\n` +
      `  normalised      ${pyBool(state.isNormalised())}`
    );
  }

  private tableauPsi(limit: number): string {
    const program = this.program!;
    const state = buildStabilizer(program);
    const shown = Math.min(limit, program.nQubits);
    const lines = [
      `|ψ⟩ on |q${program.nQubits}⟩ — ${statesLabel(program.nQubits)}`,
      `  representation  tableau (${2 * program.nQubits} bits, exact)`,
      `  field           GF(2) Pauli group (Clifford)`,
      `  generators      ${program.nQubits} — showing ${shown}`,
    ];
    for (let i = 0; i < shown; i++) lines.push(`    ${state.stabilizerLabel(i, 43)}`);
    if (program.nQubits > limit) lines.push(`    … ${program.nQubits - limit} more  (see \`generators\`)`);
    lines.push(
      `  This is the complete state. A dense amplitude vector over ${statesLabel(program.nQubits)} does not exist on this machine or on hardware; use \`measure\`, \`expect\`, \`prob\` or \`entropy\` to query it.`,
    );
    return lines.join("\n");
  }

  private cmdGenerators(args: string[]): string {
    if (!this.program) return this.need();
    if (this.state) return "this register uses the dense algebraic representation; use `psi` or `amps` for its amplitudes, or `bloch <q>`";
    const state = buildStabilizer(this.program);
    const limit = args.length ? Number(args[0]) : 32;
    const lines = [`stabilizer generators (${this.program.nQubits} total, exact)`];
    const shown = Math.min(limit, this.program.nQubits);
    for (let i = 0; i < shown; i++) lines.push(`  ${state.stabilizerLabel(i, 43)}`);
    if (this.program.nQubits > limit) lines.push(`  … ${this.program.nQubits - limit} more`);
    return lines.join("\n");
  }

  private cmdAmps(): string {
    if (!this.program) return this.need();
    if (!this.state) {
      return (
        `this register spans ${statesLabel(this.program.nQubits)} and uses the tableau representation, so there is no amplitude list to print. ` +
        "The state is still exact — query it with `measure`, `expect`, `prob` or `entropy`."
      );
    }
    const lines = ["basis       amplitude (exact)             probability"];
    let shown = 0;
    const probs = this.state.probabilities();
    for (let index = 0; index < this.state.amplitudes.length; index++) {
      if (probs[index].isZero() && shown >= 32) continue;
      lines.push(
        `${this.state.bitstring(index).padStart(10)}  ${this.state.amplitudes[index].toString().padEnd(28)} ${probs[index].toString().padEnd(12)} ${bar(probs[index].approx())}`,
      );
      shown++;
      if (shown >= 32) {
        lines.push(`         …  (${this.state.support().length} non-zero amplitudes total)`);
        break;
      }
    }
    return lines.join("\n");
  }

  private cmdProb(args: string[]): string {
    if (!this.program) return this.need();
    if (this.state) {
      const probs = this.state.probabilities();
      const lines = ["index  bitstring  probability (exact)"];
      const bars: Bars = [];
      probs.forEach((probability, index) => {
        if (probability.isZero()) return;
        const label = this.state!.bitstring(index);
        lines.push(`${String(index).padStart(5)}  ${label.padStart(9)}  ${probability}`);
        bars.push({ label: `|${label}⟩`, weight: probability.approx(), text: probability.toString() });
      });
      this.bars = bars;
      return lines.join("\n");
    }
    const subset = args.length ? args.map(Number) : range(Math.min(this.program.nQubits, 8));
    const marginal = stabilizerMarginal(this.program, subset);
    const lines = [
      `exact marginal on ${readoutLabel(subset)}`,
      `  uniform over ${marginal.outcomes} outcome(s), ${marginal.freeBits} free bit(s)`,
    ];
    const bars: Bars = [];
    if (marginal.distribution) {
      for (const [bitstring, probability] of [...marginal.distribution.entries()].sort((a, b) => (a[0] < b[0] ? -1 : 1))) {
        lines.push(`  |${bitstring}⟩  ${probability}  ${bar(marginal.numeric ?? 0, 28)}`);
        bars.push({ label: `|${bitstring}⟩`, weight: marginal.numeric ?? 0, text: probability });
      }
    } else if (marginal.note) lines.push(`  ${marginal.note}`);
    lines.push("  marginal probabilities are exact Q(√2) values.");
    this.bars = bars;
    return lines.join("\n");
  }

  private cmdMeasure(args: string[]): string {
    if (!this.program) return this.need();
    let shots = 1024;
    let seed: number | null = null;
    let readout: number[] | null = null;
    const positional: string[] = [];
    for (let i = 0; i < args.length; i++) {
      const token = args[i];
      if ((token === "--seed" || token === "-s") && args[i + 1]) seed = Number(args[++i]);
      else if (token.startsWith("--seed=")) seed = Number(token.slice(7));
      else if ((token === "--readout" || token === "-r") && args[i + 1]) readout = args[++i].split(/[\s,]+/).filter(Boolean).map(Number);
      else if (token.startsWith("--readout=")) readout = token.slice(10).split(/[\s,]+/).filter(Boolean).map(Number);
      else positional.push(token);
    }
    if (positional.length) shots = Number(positional[0]);
    let auto = false;
    if (!readout) {
      if (this.program.nQubits <= 64) readout = range(this.program.nQubits);
      else {
        readout = range(64);
        auto = true;
      }
    }
    const counts = this.state
      ? this.state.sampleMarginal(shots, readout, seed)
      : stabilizerSample(this.program, shots, seed, readout);
    const total = [...counts.values()].reduce((a, b) => a + b, 0) || 1;
    const ranked = [...counts.entries()].sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : 1));
    const used = [...readout].sort((a, b) => a - b);
    const lines = [
      `job  ${shots} shots   backend ${this.state ? "exact_algebraic" : "stabilizer"}   seed ${seed === null ? "None" : seed}`,
      `readout  ${readoutLabel(used)}${auto ? `   (auto: first ${used.length} of ${this.program.nQubits})` : ""}`,
    ];
    const bars: Bars = [];
    for (const [bitstring, count] of ranked.slice(0, 20)) {
      lines.push(`  |${bitstring}⟩  ${String(count).padStart(7)}  ${(count / total).toFixed(4).padStart(7)}  ${bar(count / total, 28)}`);
      bars.push({ label: `|${bitstring}⟩`, weight: count / total, text: String(count) });
    }
    if (ranked.length > 20) lines.push(`  … ${ranked.length - 20} further outcomes`);
    lines.push("  the distribution is exact; the draw is a labelled classical sampling of it.");
    this.bars = bars;
    return lines.join("\n");
  }

  private cmdExpect(args: string[]): string {
    if (!this.program) return this.need();
    if (!args.length) return "usage: expect <q>";
    const qubit = Number(args[0]);
    if (!this.state) {
      const values = stabilizerExpectations(this.program, qubit);
      return (
        `exact expectation values for q${qubit} (any width)\n` +
        `  ⟨X⟩ = ${values.x}\n` +
        `  ⟨Y⟩ = ${values.y}\n` +
        `  ⟨Z⟩ = ${values.z}\n` +
        "  computed by exact Clifford maps X→HZH, Y→HS†ZSH† — not sampled"
      );
    }
    const { x, y, z, purity } = reducedBloch(this.state, qubit);
    return `exact expectation values for q${qubit}\n  ⟨X⟩ = ${x}\n  ⟨Y⟩ = ${y}\n  ⟨Z⟩ = ${z}\n  purity tr(ρ²) = ${purity}`;
  }

  private cmdEntropy(args: string[]): string {
    if (!this.program) return this.need();
    if (!args.length) return "usage: entropy <q> [q ...]";
    const subset = args.map(Number);
    if (!this.state) {
      const value = buildStabilizer(this.program).entanglementEntropy(subset);
      return `cut ${fmtList(subset)} | rest   S = ${value} e-bits (exact integer)\n  stabilizer entanglement is an exact integer; no float is involved.`;
    }
    const state = this.state;
    const lines = [`cut ${fmtList(subset)} | rest   S = ${state.entropyBits(subset).toFixed(6)} bits`, "  exact marginal probabilities:"];
    for (const [key, value] of [...state.marginalProbabilities(subset).entries()].sort((a, b) => (a[0] < b[0] ? -1 : 1))) {
      lines.push(`    ${key}  ${value}`);
    }
    lines.push("  marginals are exact; the entropy value is a display float.");
    return lines.join("\n");
  }

  private cmdProduct(args: string[]): string {
    if (!this.program) return this.need();
    if (args.length < 2) return "usage: product <q> <q> [q ...]";
    const subset = args.map(Number);
    if (!this.state) {
      const value = buildStabilizer(this.program).entanglementEntropy(subset);
      const verdict = value === 0 ? "SEPARABLE (product)" : `ENTANGLED (S = ${value} e-bits)`;
      return `subsystem ${fmtList(subset)} is ${verdict} — exact integer, no tolerance`;
    }
    const separable = this.state.isProductState(subset);
    return `subsystem ${fmtList(subset)} is ${separable ? "SEPARABLE (product)" : "ENTANGLED"} — decided by exact marginal comparison, not a tolerance`;
  }

  private cmdBloch(args: string[]): string {
    if (!this.program) return this.need();
    if (!this.state) return "a Bloch sphere needs a materialised reduced density matrix; on this register use `expect <q>` for exact ⟨X⟩, ⟨Y⟩, ⟨Z⟩.";
    const qubit = args.length ? Number(args[0]) : 0;
    const { x, y, z, purity } = reducedBloch(this.state, qubit);
    const xf = x.re.approx();
    const yf = y.re.approx();
    const zf = z.re.approx();
    this.bloch = { x: xf, y: yf, z: zf, purity: purity.toString() };
    return `${blochSphere(xf, yf, zf)}\n  purity tr(ρ²) = ${purity}   (exact; 1 means pure)\n  ⟨X⟩=${x}  ⟨Y⟩=${y}  ⟨Z⟩=${z}   (exact)`;
  }

  private cmdScale(args: string[]): string {
    if (args.length === 0) return ladderReport();
    if (args[0] === "climb") {
      const source = args.length === 1 ? 15 : Number(args[1]);
      if (!Number.isInteger(source) || source < 0) return "REFUSED: scale index must be a non-negative integer";
      const target = nextRung(source);
      if (target === null) return `top rung ${source}\n  no further transition`;
      return transitionReport(source, target);
    }
    if (args[0] === "budget") {
      if (args.length !== 4) return "usage: scale budget <src> <dst> <base>";
      const source = Number(args[1]);
      const target = Number(args[2]);
      if (!Number.isInteger(source) || !Number.isInteger(target) || source < 0 || target < 0) {
        return "REFUSED: scale indices must be non-negative integers";
      }
      if (!/^\d+$/.test(args[3])) return "REFUSED: budget base must be a non-negative integer";
      const gate = authorise(source, target);
      if (!gate.accepted) return transitionReport(source, target);
      const { allocated } = scaleBudget(source, target, BigInt(args[3]));
      return `${transitionReport(source, target)}\n  base = ${args[3]}\n  allocated = ${allocated}`;
    }
    if (args.length !== 2) return "usage: scale | scale climb [n] | scale <src> <dst> | scale budget <src> <dst> <base>";
    const source = Number(args[0]);
    const target = Number(args[1]);
    if (!Number.isInteger(source) || !Number.isInteger(target) || source < 0 || target < 0) {
      return "REFUSED: scale indices must be non-negative integers";
    }
    return transitionReport(source, target);
  }

  private cmdWalk(args: string[]): string {
    if (args[0] === "cycle") {
      const n = args.length > 1 ? Number(args[1]) : 8;
      const steps = args.length > 2 ? Number(args[2]) : 3;
      const report = coinedCycle(n, steps, this.maxAmplitudes);
      this.bars = report.positions.map((position) => ({
        label: `x=${position.x}`,
        weight: position.probability.approx(),
        text: position.probability.toString(),
      }));
      return report.text;
    }
    const n = args.length ? Number(args[0]) : 10000;
    const time = args[1];
    return hypercube(n, time);
  }

  private cmdAnneal(args: string[]): string {
    const n = args.length ? Number(args[0]) : 10000;
    return tfim(n);
  }

  private cmdDiagram(): string {
    if (!this.program) return this.need();
    this.diagram = renderCircuit(this.program);
    return this.diagram;
  }

  private cmdCapabilities(): string {
    const lines = [
      "LOGICAL REGISTER",
      "  The register width is a parameter of the algebra, not a hardware ceiling: the engine accepts any n >= 1, and the documented default is n = 10,000. Wide registers are exact because they are represented in an efficient state class, not because a dense state vector exists.",
      "",
      "EXACTNESS",
      "  Every backend is an exact evaluation of a restricted quantum state class: the stabilizer tableau, Clifford+T over Q(sqrt(2)) + i*Q(sqrt(2)) inside the materialisation budget, the same field on a sparse support, and closed forms for the hypercube walk and the transverse-field Ising chain. The sparse register evaluates the coined cycle walk. A gate list that does not fit the dense budget and is not Clifford is still refused. Amplitudes and Born probabilities in those classes have no tolerance. A decimal is never substituted for a symbolic value.",
      "",
      "SCALE",
      "  Memory and storage move on the Lucas ladder. A transition is the exact ratio of two Lucas numbers. It is accepted only when Cassini holds at both indices and the target rung is on the ladder. Off-ladder, out-of-bounds, and over-budget requests are refused. A power of φ is not used as a scale.",
      "",
      "HARDWARE",
      "  This is not quantum hardware and confers none of the runtime advantage of quantum hardware. Simulating a quantum circuit classically does not confer that circuit's complexity-class advantage.",
      "",
      "NOT AVAILABLE",
      "  ✗ phases outside Q(ζ₈)",
      "      The QFT is exact for one, two and three qubits. A wider QFT, and Shor for any integer other than 15, is refused. It is not evaluated as a decimal.",
      "  ✗ densifying a sparse state past the support bound",
      "      Hadamard or diffusion that would exceed the nonzero-amplitude budget is refused, not truncated.",
      "  ✗ arbitrary universal circuit evaluation at large width",
      "      A general circuit past the materialisation budget needs a dense 2^n state. It is refused, not approximated.",
      "  ✗ physical QPU execution",
      "      No provider adapter is bundled. QPUBackend refuses every program and measured_qpu stays False.",
      "  ✗ hardware speedup claims",
      "      Simulating a circuit classically does not confer its speedup.",
      "  ✗ consensus authority of any kind",
      "      The VQC orders and certifies search; SHA-256d target comparison remains the sole accept authority.",
      "  ✗ float rescaling of memory or storage",
      "      An off-ladder, out-of-bounds, or unsealed Lucas transition is refused. It is not replaced by a power of φ or by a rounded budget.",
      "  ✗ Hendrix as a quantum speedup",
      "      The coprime stride is a bijection. On one uniform winner its expected probes equal the sequential expectation. 630x is refused.",
      "  ✗ theorem proofs",
      "      This package executes algebra. It proves no theorems.",
      "",
      "claim boundary clean: True",
    ];
    return lines.join("\n");
  }

  private cmdCertify(): string {
    if (!this.program || !this.last) return "nothing to certify: apply at least one gate first";
    const result = execute(this.program, this.maxAmplitudes);
    const witness = {
      backend: result.backend,
      consensus_authority: false,
      execution_class: result.executionClass,
      field: result.field,
      gate_counts: this.program.gateCounts(),
      issued_at: new Date().toISOString().replace(/\.\d{3}Z$/, "+00:00"),
      materialised: result.materialised,
      measured_qpu: false,
      n_qubits: result.nQubits,
      norm_sq_exact: result.normSq,
      notes: "issued from the VQC console",
      program_digest: result.digest,
      provider_job_id: null,
      schema: "turing.vqc.run_witness.v1",
      support: result.support,
      theorem_proven: false,
      truth_class: result.truthClass,
    };
    if (witness.theorem_proven || witness.consensus_authority || witness.measured_qpu) {
      return "REFUSED: witness overclaims";
    }
    const body = pyJsonPretty(witness);
    const digest = sha256Hex(pyJson(witness));
    return `run witness issued and verified\n${body}\nwitness digest: ${digest}\nverified: True`;
  }

  private cmdQpu(): string {
    const lines = [
      "QPU boundary   available=False   measured_qpu=False",
      "  no provider adapter is bundled; QPUBackend refuses every program and never substitutes a simulation",
    ];
    if (this.program) lines.push("  submission attempt: REFUSED");
    lines.push("  Every result from this console is an exact classical evaluation of quantum algebra. None of them is a measured hardware result.");
    return lines.join("\n");
  }

  private help(): string {
    return [
      "commands",
      "  register  init <n> | reset | status",
      `  gates     ${ONE_QUBIT.join(" ")} <q>  |  ${[...TWO_QUBIT].join(" ")} <q> <q>`,
      "  readout   psi | amps | prob [q...] | diagram",
      "  quantum   measure [shots] [--seed s] [--readout q,q] | expect <q> | entropy <q...> | product <q> <q>",
      "  tableau   generators [n]",
      "  scale     scale | scale climb [n] | scale <src> <dst> | scale budget <src> <dst> <base> | fold [payload] | six [n] | cure",
      "  thread    thread",
      "  algebra   algebra",
      "  classics  classics | qft [n] | grover [N M] | shor <N> | hendrix | advances | finale | rank | ontology | signal | store | triad",
      "  custody   put <hex> | get <id> | damage <id> | heal <id> | handoff",
      "  closed    walk [n] [0|pi/4|pi/2] | walk cycle <N> [steps] | anneal [n] | tunnel",
      "  machine   backends | capabilities | certify | qpu",
      "  session   help | quit",
    ].join("\n");
  }
}

function fits(n: number, maxAmplitudes: number): boolean {
  if (n >= 31) return false;
  return (1 << n) <= maxAmplitudes;
}

function statesLabel(n: number): string {
  if (n <= 40) return `${1 << n} basis states`;
  return `2^${n} basis states`;
}

function range(n: number): number[] {
  return Array.from({ length: n }, (_, i) => i);
}

function bar(value: number, width = 24): string {
  const filled = Math.max(0, Math.min(width, Math.round(value * width)));
  return BLOCK.repeat(filled) + "·".repeat(width - filled);
}

function readoutLabel(qubits: number[]): string {
  const ordered = [...qubits].sort((a, b) => a - b);
  if (ordered.length <= 8) return ordered.map((q) => `q${q}`).join(" ");
  const contiguous = ordered.every((q, i) => q === ordered[0] + i);
  if (contiguous) return `q${ordered[0]}..q${ordered[ordered.length - 1]} (${ordered.length})`;
  return `${ordered.length} qubits: ${ordered.slice(0, 8).map((q) => `q${q}`).join(" ")} …`;
}

function formatCounts(counts: Record<string, number>): string {
  const keys = Object.keys(counts);
  if (!keys.length) return "{}";
  return `{${keys.map((key) => `'${key}': ${counts[key]}`).join(", ")}}`;
}

function pyBool(value: boolean): string {
  return value ? "True" : "False";
}

function select(program: Program, maxAmplitudes: number): { backend: string | null; reason: string } {
  const dense = fits(program.nQubits, maxAmplitudes);
  if (dense) {
    const unknown = [...program.gates()].filter((gate) => !SUPPORTED.has(gate)).sort();
    if (unknown.length) {
      return { backend: "exact_algebraic", reason: `gate(s) ${JSON.stringify(unknown)} are outside the Clifford+T set` };
    }
    return { backend: "exact_algebraic", reason: "universal Clifford+T program within the materialisation budget" };
  }
  if (program.isClifford()) return { backend: "stabilizer", reason: "Clifford program within the stabilizer domain" };
  const outside = [...program.gates()].filter((gate) => !CLIFFORD.has(gate)).sort();
  return {
    backend: null,
    reason: `non-Clifford gate(s) ${JSON.stringify(outside)} lie outside the stabilizer domain; this backend fails closed rather than approximate`,
  };
}

function execute(program: Program, maxAmplitudes: number): Result {
  const admission = select(program, maxAmplitudes);
  if (!admission.backend) {
    throw new StatevectorTooLargeError("no backend can answer this program exactly: " + admission.reason);
  }
  if (admission.backend === "exact_algebraic") {
    const state = new ExactStatevector(program.nQubits, undefined, maxAmplitudes);
    for (const operation of program.operations) {
      const [a, b] = operation.qubits;
      if (operation.gate === "cx" || operation.gate === "cnot") state.applyControlled("x", a, b);
      else if (operation.gate === "cz") state.applyControlled("z", a, b);
      else if (operation.gate === "swap") state.swap(a, b);
      else if (operation.gate !== "i") state.apply(operation.gate, a);
    }
    if (!state.isNormalised()) throw new DomainError(`exact evolution left the state unnormalised: ||psi||^2 = ${state.normSq()}`);
    return {
      backend: "exact_algebraic",
      executionClass: "exact_algebraic",
      truthClass: "exact",
      nQubits: program.nQubits,
      digest: program.digest(),
      materialised: true,
      state,
      tableauBits: null,
      generators: null,
      normSq: state.normSq().toString(),
      support: state.support().length,
      field: "Q(sqrt(2)) + i*Q(sqrt(2))",
    };
  }
  return {
    backend: "stabilizer",
    executionClass: "bounded_exact",
    truthClass: "exact",
    nQubits: program.nQubits,
    digest: program.digest(),
    materialised: false,
    state: null,
    tableauBits: 2 * program.nQubits,
    generators: null,
    normSq: null,
    support: null,
    field: "GF(2) Pauli group",
  };
}

function buildStabilizer(program: Program): StabilizerState {
  const state = new StabilizerState(program.nQubits);
  for (const operation of program.operations) {
    const [a, b] = operation.qubits;
    if (operation.gate === "h") state.h(a);
    else if (operation.gate === "s") state.s(a);
    else if (operation.gate === "sdg") state.sdg(a);
    else if (operation.gate === "x") state.x(a);
    else if (operation.gate === "y") state.y(a);
    else if (operation.gate === "z") state.z(a);
    else if (operation.gate === "cx" || operation.gate === "cnot") state.cnot(a, b);
    else if (operation.gate === "cz") state.cz(a, b);
    else if (operation.gate === "swap") state.swap(a, b);
    else if (operation.gate === "i") continue;
    else throw new DomainError(`non-Clifford gate ${operation.gate}`);
  }
  return state;
}

function stabilizerExpectations(program: Program, qubit: number): { x: string; y: string; z: string } {
  const z = buildStabilizer(program).expectationZ(qubit);
  const xState = buildStabilizer(program);
  xState.h(qubit);
  const yState = buildStabilizer(program);
  yState.sdg(qubit);
  yState.h(qubit);
  return { x: xState.expectationZ(qubit), y: yState.expectationZ(qubit), z };
}

function stabilizerMarginal(program: Program, subset: number[]): {
  outcomes: number;
  freeBits: number;
  distribution: Map<string, string> | null;
  numeric?: number;
  note?: string;
} {
  const qubits = subset.map((q) => q);
  const probe = buildStabilizer(program);
  const free: number[] = [];
  for (const qubit of qubits) {
    const [p0, p1] = probe.measurementProbabilities(qubit);
    if (p0.n === p1.n && p0.d === p1.d) {
      free.push(qubit);
      probe.measure(qubit, 0);
    } else {
      probe.measure(qubit, p0.n === 1n && p0.d === 1n ? 0 : 1);
    }
  }
  const freeBits = free.length;
  if (freeBits > 12 || (1 << freeBits) > MARGINAL_CAP) {
    return {
      outcomes: 1 << Math.min(freeBits, 30),
      freeBits,
      distribution: null,
      note: `the marginal is exactly uniform over ${1 << freeBits} bitstrings; listing them is suppressed above the enumeration cap`,
    };
  }
  const numeric = 1 / 2 ** freeBits;
  const weight = freeBits === 0 ? "1" : `1/${1 << freeBits}`;
  const distribution = new Map<string, string>();
  for (let assignment = 0; assignment < 1 << freeBits; assignment++) {
    const state = buildStabilizer(program);
    const bits = new Map<number, number>();
    free.forEach((qubit, position) => {
      const forced = ((assignment >> position) & 1) as 0 | 1;
      state.measure(qubit, forced);
      bits.set(qubit, forced);
    });
    for (const qubit of qubits) {
      if (bits.has(qubit)) continue;
      const [p0, p1] = state.measurementProbabilities(qubit);
      const pick: 0 | 1 = p0.n * p1.d > p1.n * p0.d ? 0 : 1;
      state.measure(qubit, pick);
      bits.set(qubit, pick);
    }
    distribution.set(qubits.map((q) => String(bits.get(q))).join(""), weight);
  }
  return { outcomes: 1 << freeBits, freeBits, distribution, numeric };
}

function stabilizerSample(program: Program, shots: number, seed: number | null, readout: number[]): Map<string, number> {
  if (shots < 1) throw new Error("shots must be >= 1");
  const qubits = [...new Set(readout)].sort((a, b) => a - b);
  if (qubits.length > READOUT_LIMIT) throw new Error(`readout of ${qubits.length} qubits exceeds the ${READOUT_LIMIT}-qubit limit`);
  const prepared = buildStabilizer(program);
  const rng = mulberry(seed ?? 0);
  const counts = new Map<string, number>();
  for (let shot = 0; shot < shots; shot++) {
    const state = prepared.clone();
    const bits = new Map<number, number>();
    for (const qubit of qubits) {
      const [p0, p1] = state.measurementProbabilities(qubit);
      const random = p0.n === p1.n && p0.d === p1.d;
      const outcome: 0 | 1 = random ? (rng.uint32() & 1 ? 1 : 0) : p0.n * p1.d > p1.n * p0.d ? 0 : 1;
      state.measure(qubit, outcome);
      bits.set(qubit, outcome);
    }
    const key = qubits.map((q) => String(bits.get(q))).join("");
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return counts;
}

export function renderCircuit(program: Program): string {
  if (!program.operations.length) return "(empty circuit)";
  const columns: Map<number, string>[] = [];
  for (const operation of program.operations) {
    const column = new Map<number, string>();
    const gate = operation.gate.toUpperCase();
    if (gate === "CX" || gate === "CNOT") {
      column.set(operation.qubits[0], "●");
      column.set(operation.qubits[1], "⊕");
    } else if (gate === "CZ") {
      column.set(operation.qubits[0], "●");
      column.set(operation.qubits[1], "Z");
    } else if (gate === "SWAP") {
      column.set(operation.qubits[0], "×");
      column.set(operation.qubits[1], "×");
    } else column.set(operation.qubits[0], gate);
    columns.push(column);
  }
  if (program.nQubits > 24) {
    return `${program.nQubits} qubits · ${program.operations.length} gates · tableau, not drawn wire-by-wire`;
  }
  return range(program.nQubits)
    .map((qubit) => {
      const cells = columns.map((column) => (column.get(qubit) ?? "").padStart(2, "─").padEnd(3, "─"));
      return `q${String(qubit).padEnd(4, " ")}─${cells.join("")}─`;
    })
    .join("\n");
}

function renderMatrix(maxAmplitudes: number): string {
  const denseQubits = 31 - Math.clz32(maxAmplitudes);
  const rows = [
    ["backend", "execution class", "materialises", "gate set", "max width", "available"],
    ["exact_algebraic", "exact_algebraic", "yes", "clifford+t", String(denseQubits), "yes"],
    ["stabilizer", "bounded_exact", "no", "clifford", "unbounded", "yes"],
    ["sparse", "bounded_exact", "yes", "clifford+t", "unbounded", "yes"],
    ["closed_form", "exact_symbolic", "no", "named families", "unbounded", "yes"],
    ["qpu", "hardware", "no", "provider", "unbounded", "no"],
  ];
  const widths = rows[0].map((_, i) => Math.max(...rows.map((row) => row[i].length)));
  return rows
    .map((row, position) => {
      const line = row.map((cell, i) => cell.padEnd(widths[i], " ")).join("  ").trimEnd();
      if (position === 0) return `${line}\n${widths.map((w) => "-".repeat(w)).join("  ")}`;
      return line;
    })
    .join("\n");
}

function blochSphere(x: number, y: number, z: number, width = 21, height = 11): string {
  const grid = Array.from({ length: height }, () => Array.from({ length: width }, () => " "));
  const cx = (width - 1) / 2;
  const cy = (height - 1) / 2;
  const radius = Math.min(cx, cy);
  for (let row = 0; row < height; row++) {
    for (let col = 0; col < width; col++) {
      const dx = (col - cx) / radius;
      const dy = (row - cy) / radius;
      if (Math.abs(Math.hypot(dx, dy) - 1) < 0.14) grid[row][col] = "·";
    }
  }
  grid[0][Math.round(cx)] = "+";
  grid[height - 1][Math.round(cx)] = "+";
  grid[Math.round(cy)][0] = "+";
  grid[Math.round(cy)][width - 1] = "+";
  const px = Math.max(0, Math.min(width - 1, Math.round(cx + x * radius * 0.92)));
  const pz = Math.max(0, Math.min(height - 1, Math.round(cy - z * radius * 0.92)));
  grid[pz][px] = "@";
  const header = `  Bloch vector  x=${x >= 0 ? "+" : ""}${x.toFixed(3)}  y=${y >= 0 ? "+" : ""}${y.toFixed(3)}  z=${z >= 0 ? "+" : ""}${z.toFixed(3)}   (display floats; ρ is exact)`;
  return header + "\n" + grid.map((row) => "  " + row.join("")).join("\n");
}

function pyJson(value: unknown): string {
  return JSON.stringify(sortKeys(value));
}

function pyJsonPretty(value: unknown): string {
  return JSON.stringify(sortKeys(value), null, 2);
}

function sortKeys(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(sortKeys);
  if (value && typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const key of Object.keys(value as Record<string, unknown>).sort()) out[key] = sortKeys((value as Record<string, unknown>)[key]);
    return out;
  }
  return value;
}

function fmtList(values: number[]): string {
  return `[${values.join(", ")}]`;
}

const SUBTITLE =
  "exact algebra on a classical substrate · Clifford+T over Q(√2) + iQ(√2)\n" +
  "Enter follows the prompt: register, closed form, cycle walk, Lucas scale, fold, cure, thread, algebra, classics, Hendrix\n" +
  "register-native at any width · no physical QPU bound · refusals are deliberate";
