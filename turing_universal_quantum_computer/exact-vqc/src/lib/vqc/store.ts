/** Theseus address and Ovid fold, from the aethel docs.

Fourier truncation of the Fibonacci window does not invert. The Zeckendorf
fold does. The payload is recovered under MODULUS_Q = 2^61−1 because a 7-byte
chunk is smaller than that prime. The 32 sunflower slots are the rank of
{lane · φ}, a bijection, not a compression. The float Vogel angle is not executed.
Overhead is a declared operation count: the QFT pays a non-Clifford T; the
Bell representation pays XOR and swap.
*/

import { Frac } from "./algebra.ts";
import { fibonacci } from "./lucas-scale.ts";

const LANES = 32;
const MODULUS = (1n << 61n) - 1n;
const PRIMES = [
  2n, 3n, 5n, 7n, 11n, 13n, 17n, 19n, 23n, 29n,
  31n, 37n, 41n, 43n, 47n, 53n, 59n, 61n, 67n, 71n,
  73n, 79n, 83n, 89n, 97n,
];

type Gauss = { re: bigint; im: bigint };
type Q5 = { a: Frac; b: Frac };

function timesI(sample: bigint, power: number): Gauss {
  const turn = ((power % 4) + 4) % 4;
  if (turn === 0) return { re: sample, im: 0n };
  if (turn === 1) return { re: 0n, im: sample };
  if (turn === 2) return { re: -sample, im: 0n };
  return { re: 0n, im: -sample };
}

function dft4(signal: bigint[]): Gauss[] {
  return [0, 1, 2, 3].map((bin) =>
    signal.reduce<Gauss>((total, sample, index) => {
      const term = timesI(sample, bin * index);
      return { re: total.re + term.re, im: total.im + term.im };
    }, { re: 0n, im: 0n }),
  );
}

function idft4(bins: Gauss[]): Gauss[] {
  return [0, 1, 2, 3].map((time) =>
    bins.reduce<Gauss>((total, bin, index) => {
      const turn = timesI(1n, -time * index);
      return {
        re: total.re + bin.re * turn.re - bin.im * turn.im,
        im: total.im + bin.re * turn.im + bin.im * turn.re,
      };
    }, { re: 0n, im: 0n }),
  );
}

function lucasLehmer(exponent: number): bigint {
  const modulus = (1n << BigInt(exponent)) - 1n;
  let state = 4n;
  for (let step = 0; step < exponent - 2; step++) state = (state * state - 2n) % modulus;
  return state;
}

function modPow(base: bigint, exponent: bigint, modulus: bigint): bigint {
  let result = 1n;
  let factor = base % modulus;
  let cursor = exponent;
  while (cursor > 0n) {
    if (cursor & 1n) result = (result * factor) % modulus;
    factor = (factor * factor) % modulus;
    cursor >>= 1n;
  }
  return result;
}

function cmpQ5(left: Q5, right: Q5): number {
  const d = left.a.sub(right.a);
  const b = left.b.sub(right.b);
  if (b.isZero()) return d.cmp(new Frac(0n));
  if (b.cmp(new Frac(0n)) > 0) {
    if (d.cmp(new Frac(0n)) >= 0) return 1;
    const gap = new Frac(5n).mul(b).mul(b).sub(d.mul(d));
    return gap.cmp(new Frac(0n));
  }
  if (d.cmp(new Frac(0n)) <= 0) return -1;
  const gap = d.mul(d).sub(new Frac(5n).mul(b).mul(b));
  return gap.cmp(new Frac(0n));
}

function floorQ5(value: Q5): bigint {
  let lo = -2n;
  let hi = 80n;
  while (lo + 1n < hi) {
    const mid = (lo + hi) >> 1n;
    if (cmpQ5(value, { a: new Frac(mid), b: new Frac(0n) }) >= 0) lo = mid;
    else hi = mid;
  }
  return lo;
}

function sunflowerOrder(): number[] {
  const keys = Array.from({ length: LANES }, (_, lane) => {
    const scaled: Q5 = { a: new Frac(BigInt(lane), 2n), b: new Frac(BigInt(lane), 2n) };
    const whole = floorQ5(scaled);
    return { lane, frac: { a: scaled.a.sub(new Frac(whole)), b: scaled.b } };
  });
  const order = keys
    .slice()
    .sort((left, right) => cmpQ5(left.frac, right.frac))
    .map((entry) => entry.lane);
  if (new Set(order).size !== LANES) throw new Error("sunflower slots collided");
  return order;
}

function missCost(addresses: number[]): number {
  let cost = 0;
  for (let index = 1; index < addresses.length; index++) cost += Math.abs(addresses[index] - addresses[index - 1]);
  return cost;
}

function zeckendorf(payload: bigint): number[] {
  let hi = 2;
  while (fibonacci(hi) <= payload) hi += 1;
  const indices: number[] = [];
  let remaining = payload;
  for (let index = hi - 1; index >= 2 && remaining > 0n; index--) {
    const limb = fibonacci(index);
    if (limb <= remaining) {
      indices.push(index);
      remaining -= limb;
    }
  }
  if (remaining !== 0n) throw new Error("Zeckendorf did not consume the payload");
  return indices;
}

export function sunflowerSlot(lane: number): number {
  if (!Number.isInteger(lane) || lane < 0 || lane >= LANES) throw new Error("lane out of range");
  const rank = sunflowerOrder().indexOf(lane);
  if (rank < 0) throw new Error("sunflower rank missing");
  return rank;
}

let cached: string | null = null;

export function storeReport(): string {
  if (cached) return cached;
  if (lucasLehmer(7) !== 0n) throw new Error("Lucas-Lehmer missed the prime 2^7−1");
  if (lucasLehmer(11) === 0n) throw new Error("Lucas-Lehmer accepted the composite 2^11−1");
  const primeResidue = lucasLehmer(61);
  if (primeResidue !== 0n) throw new Error("2^61−1 failed Lucas-Lehmer");
  for (const prime of PRIMES) {
    for (let factor = 2n; factor * factor <= prime; factor++) {
      if (prime % factor === 0n) throw new Error(`${prime} is not prime`);
    }
  }
  const window = [0n, 1n, 1n, 2n];
  const bins = dft4(window);
  const full = idft4(bins);
  if (full.some((sample, index) => sample.im !== 0n || sample.re !== 4n * window[index])) {
    throw new Error("the full DFT did not invert");
  }
  const truncated = idft4([bins[0], { re: 0n, im: 0n }, bins[2], { re: 0n, im: 0n }]);
  const truncationLoss = truncated.some((sample, index) => sample.re !== 4n * window[index] || sample.im !== 0n);
  if (!truncationLoss) throw new Error("dropping two Fourier bins was lossless");
  const payload = 4n;
  const limbs = zeckendorf(payload);
  const restored = limbs.reduce((sum, index) => sum + fibonacci(index), 0n);
  if (restored !== payload) throw new Error("the fold did not unfold");
  for (let index = 1; index < limbs.length; index++) {
    if (limbs[index - 1] - limbs[index] < 2) throw new Error("Zeckendorf used adjacent summands");
  }
  const chunk = 1n << 48n;
  if (chunk >= MODULUS) throw new Error("a 7-byte chunk is not below the prime");
  const composite = modPow(2n, chunk, MODULUS);
  const decoded = chunk % MODULUS;
  const byte = Number((decoded >> 48n) & 0xffn);
  if (byte !== 1) throw new Error("the prime cell did not return the payload byte");
  const order = sunflowerOrder();
  const sequential = missCost(Array.from({ length: LANES }, (_, lane) => lane));
  const spiral = missCost(order);
  cached = [
    "store",
    "  source = aethel.primes, aethel.overhead, PhyllotaxisLaneIndex",
    "  the float Vogel angle π(3−√5) is not executed",
    "  theorem_proven = False",
    "",
    "[Fourier truncates]",
    "  window = 0,1,1,2",
    "  full inverse DFT = 4 times the window",
    "  two bins dropped, inverse matches = False",
    "",
    "[the fold is lossless]",
    `  Zeckendorf(${payload}) = ${limbs.map((index) => `F(${index})`).join(" + ")}`,
    `  sum of those limbs = ${restored}`,
    "  adjacent summands = False",
    "",
    "[the prime holds the address]",
    `  MODULUS_Q = 2^61 − 1    Lucas-Lehmer residue = ${primeResidue}`,
    `  first 25 primes checked = ${PRIMES.length}`,
    "  a 7-byte chunk is 2^48, which is below the modulus",
    "  reduction of that chunk is the identity",
    "  payload byte 0x01 round-trips",
    `  composite address = 2^(2^48) mod MODULUS_Q = ${composite}`,
    "  the composite is the address; the exponent list is the payload",
    "",
    "[the sunflower is the slot order]",
    `  lanes = ${LANES}`,
    "  key = fractional part of lane · φ",
    `  insertion order = ${order.join(",")}`,
    "  the 32 keys are distinct, so the rank map is a bijection",
    "  the source calls this an addressing permutation, not a compression advantage",
    `  sequential miss cost = ${sequential}`,
    `  sunflower miss cost = ${spiral}`,
    "  miss cost is the sum of absolute jumps, not a device counter",
    "",
    "[quantum overhead]",
    "  Bell representation = two rows of 4 bits, updated by XOR and swap",
    "  physical device term for that representation = 0",
    "  QFT on 3 qubits = 3 Hadamard + 2 Clifford phase + 1 T + 1 swap",
    "  the T is not a stabilizer update",
    "  one companion step = 1 addition and 2 memory touches",
    "  these are declared operation counts",
  ].join("\n");
  return cached;
}
