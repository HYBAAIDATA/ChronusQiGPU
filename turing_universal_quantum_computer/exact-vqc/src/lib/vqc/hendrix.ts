/** Algorithms since Grover and Shor, as algebra.

The mathematics does not name a device. Hendrix is the coprime-stride
schedule from PhiMiner `pisot.py`: position i visits (i · stride) mod n,
with the preferred stride a Lucas number. It is an order, not an amplitude.
A fixed bijection does not change the uniform first-hit law, so a speedup
is refused. Graph spectra, Hadamard, and entanglement are executed in the
exact field or as integer characteristic polynomials.
*/

import { Exact, Frac, HALF_SQRT2, ONE } from "./algebra.ts";
import { hypercube, landauZener, tfim } from "./closed-form.ts";
import { ExactStatevector } from "./exact-state.ts";
import { lucas } from "./lucas-scale.ts";

const WINDOW = 30n;
const WORKERS = 4n;
const SCALE_INDEX = 76;

function gcd(a: bigint, b: bigint): bigint {
  let x = a < 0n ? -a : a;
  let y = b < 0n ? -b : b;
  while (y !== 0n) {
    const next = x % y;
    x = y;
    y = next;
  }
  return x;
}

function extended(a: bigint, modulus: bigint): bigint {
  let oldR = a;
  let r = modulus;
  let oldS = 1n;
  let s = 0n;
  while (r !== 0n) {
    const q = oldR / r;
    [oldR, r] = [r, oldR - q * r];
    [oldS, s] = [s, oldS - q * s];
  }
  if (oldR !== 1n) throw new Error("stride is not a unit");
  return ((oldS % modulus) + modulus) % modulus;
}

function coprimeStride(count: bigint, preferred: bigint): bigint {
  if (count <= 1n) return 1n;
  let stride = preferred % count;
  if (stride === 0n) stride = 1n;
  let steps = 0n;
  while (gcd(stride, count) !== 1n) {
    stride = (stride + 1n) % count;
    if (stride === 0n) stride = 1n;
    steps += 1n;
    if (steps > count) throw new Error("no coprime stride");
  }
  return stride;
}

function nonceAt(position: bigint, stride: bigint, count: bigint): bigint {
  return (position * stride) % count;
}

export function hendrixReport(count = WINDOW, workers = WORKERS): string {
  if (count < 1n || workers < 1n || workers > count) return "REFUSED: Hendrix needs 1 ≤ workers ≤ window";
  const preferred = lucas(SCALE_INDEX);
  const stride = coprimeStride(count, preferred);
  if (gcd(stride, count) !== 1n) throw new Error("Hendrix stride is not coprime");
  const inverse = extended(stride, count);
  if ((stride * inverse) % count !== 1n) throw new Error("Hendrix inverse failed");
  const seen = new Set<bigint>();
  for (let position = 0n; position < count; position++) seen.add(nonceAt(position, stride, count));
  if (BigInt(seen.size) !== count) throw new Error("Hendrix map is not bijective");
  const owner = new Map<bigint, bigint>();
  for (let worker = 0n; worker < workers; worker++) {
    for (let position = worker; position < count; position += workers) {
      if (owner.has(position)) throw new Error("Hendrix workers overlap");
      owner.set(position, worker);
    }
  }
  if (BigInt(owner.size) !== count) throw new Error("Hendrix workers miss a position");
  const expectation = new Frac(count + 1n, 2n);
  return [
    "Hendrix",
    "  kind = coprime stride",
    "  quantum_claim = False",
    "  consensus_authority = False",
    "  hardware = not a parameter",
    "  theorem_proven = False",
    `  window = ${count}`,
    `  workers = ${workers}`,
    `  preferred stride = L_${SCALE_INDEX}`,
    `  stride = ${stride}`,
    `  gcd(stride, window) = 1`,
    `  inverse = ${inverse}`,
    "  i ↦ (i · stride) mod window is a bijection",
    "  worker classes are the residues modulo workers",
    "  the classes are disjoint and cover the window",
    `  one uniform winner, any bijection: E[probes] = ${expectation}`,
    "  sequential has the same expectation",
    "  ratio = 1",
    "  630x = refused",
    "  a Monte Carlo of the ratio is not a proof and is not run",
  ].join("\n");
}

function bellExecuted(): { separable: boolean; probability: string } {
  const state = new ExactStatevector(2);
  state.apply("h", 0);
  state.applyControlled("x", 0, 1);
  const root = new Exact(HALF_SQRT2);
  const at = (index: number) => state.amplitudes[index];
  if (!at(0).sub(root).isZero() || !at(3).sub(root).isZero()) throw new Error("Bell amplitudes left (|00⟩ + |11⟩)/√2");
  if (!at(1).isZero() || !at(2).isZero()) throw new Error("Bell state has a product term");
  const half = at(0).normSq();
  if (!half.q.isZero() || half.p.toString() !== "1/2") throw new Error("Bell probability left 1/2");
  return { separable: false, probability: half.p.toString() };
}

function hadamardExecuted(): string {
  const state = new ExactStatevector(1);
  state.apply("h", 0);
  const root = new Exact(HALF_SQRT2);
  if (!state.amplitudes[0].sub(root).isZero() || !state.amplitudes[1].sub(root).isZero()) {
    throw new Error("Hadamard left the equal superposition");
  }
  return state.probabilities()[0].p.toString();
}

/** det(λI − L) for the path on three vertices, by evaluating the cubic. */
function pathGap(): { polynomial: string; gap: bigint } {
  const values = [0, 1, 2, 3, 4].map((lambda) => {
    const matrix = [
      [BigInt(lambda) - 1n, 1n, 0n],
      [1n, BigInt(lambda) - 2n, 1n],
      [0n, 1n, BigInt(lambda) - 1n],
    ];
    return (
      matrix[0][0] * (matrix[1][1] * matrix[2][2] - matrix[1][2] * matrix[2][1]) -
      matrix[0][1] * (matrix[1][0] * matrix[2][2] - matrix[1][2] * matrix[2][0]) +
      matrix[0][2] * (matrix[1][0] * matrix[2][1] - matrix[1][1] * matrix[2][0])
    );
  });
  const expected = [0n, 0n, -2n, 0n, 12n];
  if (values.some((value, index) => value !== expected[index])) throw new Error("path Laplacian left λ(λ−1)(λ−3)");
  return { polynomial: "λ(λ−1)(λ−3)", gap: 1n };
}

let advancesCached: string | null = null;

export function advancesReport(): string {
  if (advancesCached) return advancesCached;
  const hadamard = hadamardExecuted();
  const bell = bellExecuted();
  const path = pathGap();
  const cube = hypercube(4, "pi/2");
  if (!cube.includes("P(w = 4) = 1")) throw new Error("hypercube walk left the algebraic point");
  const anneal = tfim(4);
  if (!anneal.includes("not a Trotter product")) throw new Error("anneal left the free-fermion spectrum");
  const tunnel = landauZener();
  if (!tunnel.includes("not replaced by a decimal")) throw new Error("tunnel replaced the exponential");
  advancesCached = [
    "advances",
    "  substrate = the algebra",
    "  hardware = not a parameter",
    "  theorem_proven = False",
    "",
    "[Hadamard]",
    "  H|0⟩ = (|0⟩ + |1⟩)/√2",
    `  P(0) = ${hadamard}`,
    "  superposition is this state, not a device",
    "",
    "[entanglement]",
    "  CNOT · (H ⊗ I) |00⟩ = (|00⟩ + |11⟩)/√2",
    `  P(00) = ${bell.probability}`,
    `  product state = ${bell.separable ? "True" : "False"}`,
    "",
    "[Hendrix]",
    hendrixReport(),
    "",
    "[graph walk]",
    "  path on 3 vertices, Laplacian spectrum",
    `  characteristic polynomial = ${path.polynomial}`,
    `  gap = ${path.gap}`,
    "  hypercube H = −∑ X_j at t = π/2: P(w = n) = 1",
    "  a decimal time is refused",
    "  coined cycle: command `walk cycle`",
    "",
    "[anneal]",
    "  transverse-field Ising gap is the free-fermion expression",
    "  not a Trotter product",
    "  Landau–Zener stays symbolic",
    "",
    "[since Grover and Shor]",
    "  amplitude amplification = the folded recurrence, doubled by `cure`",
    "  order finding = `shor 15`, and nowhere outside Q(ζ₈)",
    "  phase estimation = `qft` for n ≤ 3",
    "  Hendrix does not replace either",
    "  a float angle, a wider QFT, and a hardware speedup are refused",
  ].join("\n");
  return advancesCached;
}
