/** The six names, each doing its own arithmetic.

Zeckendorf folds the Lucas integer. Binet is the ring power in Z[φ], not the
Fibonacci loop. Fibonacci supplies F_n and F_{n+1}. Cassini's seal is the
index parity, and that division is what reads F_{n-1} back. Lucas is the sum
after the φ terms cancel. Pisot is the conjugate automorphism.
*/

import { Frac } from "./algebra.ts";
import { cassiniSeal, fibonacci, lucas, scaleBudget } from "./lucas-scale.ts";

type Ring = { a: bigint; b: bigint };

function mul(p: Ring, q: Ring): Ring {
  return { a: p.a * q.a + p.b * q.b, b: p.a * q.b + p.b * q.a + p.b * q.b };
}

function phiPower(n: number): Ring {
  let result: Ring = { a: 1n, b: 0n };
  let base: Ring = { a: 0n, b: 1n };
  let exponent = n;
  while (exponent > 0) {
    if (exponent & 1) result = mul(result, base);
    base = mul(base, base);
    exponent >>= 1;
  }
  return result;
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
  if (remaining !== 0n) throw new Error("Zeckendorf did not exhaust the payload");
  return indices;
}

function pisotShrinks(n: number): boolean {
  const f = fibonacci(n);
  const l = lucas(n);
  const sign = cassiniSeal(n);
  if (l * l - 5n * f * f !== 4n * sign) return false;
  if (n % 2 === 0) return l <= 2n || (l - 2n) * (l - 2n) < 5n * f * f;
  return 5n * f * f < (l + 2n) * (l + 2n);
}

export function sixReport(n = 15): string {
  if (!Number.isInteger(n) || n < 2) return "REFUSED: the index must be an integer ≥ 2";
  const current = fibonacci(n);
  const later = fibonacci(n + 1);
  const seal = cassiniSeal(n);
  if (later === 0n || (current * current + seal) % later !== 0n) throw new Error("Cassini did not divide");
  const earlier = (current * current + seal) / later;
  if (earlier !== fibonacci(n - 1)) throw new Error("Cassini did not return the earlier Fibonacci word");
  if (later * earlier - current * current !== seal) throw new Error("the read word does not satisfy Cassini");
  const folded = phiPower(n);
  if (folded.a !== earlier || folded.b !== current) throw new Error("Binet left the stored words");
  const pisotA = folded.a + folded.b;
  const pisotB = -folded.b;
  if (pisotA !== later || pisotB !== -current) throw new Error("the Pisot conjugate left F_(n+1) − F_n φ");
  if (folded.b + pisotB !== 0n) throw new Error("the φ terms did not cancel");
  const lucasValue = folded.a + pisotA;
  if (lucasValue !== lucas(n)) throw new Error("the cancelled sum is not the Lucas integer");
  const code = zeckendorf(lucasValue);
  const foldedSum = code.reduce((sum, index) => sum + fibonacci(index), 0n);
  if (foldedSum !== lucasValue) throw new Error("Zeckendorf did not sum back to the Lucas number");
  for (let index = 1; index < code.length; index++) {
    if (code[index - 1] - code[index] < 2) throw new Error("Zeckendorf used an adjacent limb");
  }
  const direct = code.length === 2 && code[0] === n + 1 && code[1] === n - 1;
  const ratio = new Frac(lucasValue, lucas(n - 1));
  if (!pisotShrinks(n)) throw new Error("the Pisot conjugate is not inside the unit interval");
  const sign = seal < 0n ? "−1" : "+1";
  return [
    `six ${n}`,
    "  fold  = Zeckendorf + Binet",
    "  store = Fibonacci + Cassini",
    "  scale = Lucas + Pisot",
    "  theorem_proven = False",
    "",
    "[fold]",
    direct
      ? `  Zeckendorf(L_${n}) = F_${n + 1} + F_${n - 1}`
      : `  L_${n} = F_${n + 1} + F_${n - 1} collapses, so Zeckendorf writes ${code.map((index) => `F_${index}`).join(" + ")}`,
    `  limbs = ${later} + ${earlier}`,
    "  sums back = True    non-adjacent = True",
    `  Binet φ^${n} = ${folded.a} + ${folded.b}φ`,
    "  the coefficients are the ring product, then checked against the store",
    "",
    "[store]",
    `  kept = (F_${n}, F_${n + 1}) = (${current}, ${later})`,
    `  Cassini seal = (${sign}), the index parity`,
    `  read back F_${n - 1} = (F_${n}² + seal) / F_${n + 1} = ${earlier}`,
    "",
    "[scale]",
    `  Lucas L_${n} = ${lucasValue}`,
    `  L_${n} / L_${n - 1} = ${ratio.toString()}`,
    `  Pisot ψ^${n} = ${pisotA} − ${current}φ`,
    "  φ^n + ψ^n cancels φ and leaves L_n",
    "  |ψ^n| < 1 by the Cassini integer, not by a decimal",
  ].join("\n");
}

/** Fold an arbitrary integer. Weights are Binet coefficients. The code is
Zeckendorf. Cassini must accept every weight. Lucas moves the budget.
The payload is not rescaled. */
export function keepData(payload: bigint): { indices: number[]; restored: bigint; allocated: bigint } {
  if (payload < 0n) throw new Error("payload must be non-negative");
  const weight: bigint[] = [0n];
  let ring: Ring = { a: 1n, b: 0n };
  const phi: Ring = { a: 0n, b: 1n };
  for (let index = 1; index <= 48; index++) {
    ring = mul(ring, phi);
    weight.push(ring.b);
  }
  for (let index = 2; index <= 46; index++) {
    const seal = index % 2 === 0 ? 1n : -1n;
    const later = weight[index + 1];
    if (later === 0n || (weight[index] * weight[index] + seal) % later !== 0n) {
      throw new Error("Cassini refused a Binet weight");
    }
    if ((weight[index] * weight[index] + seal) / later !== weight[index - 1]) {
      throw new Error("the Fibonacci store disagreed with the Binet weight");
    }
  }
  const indices: number[] = [];
  let remaining = payload;
  for (let index = weight.length - 1; index >= 2 && remaining > 0n; index--) {
    if (weight[index] <= remaining) {
      indices.push(index);
      remaining -= weight[index];
    }
  }
  if (remaining !== 0n) throw new Error("the fold did not exhaust the payload");
  for (let index = 1; index < indices.length; index++) {
    if (indices[index - 1] - indices[index] < 2) throw new Error("the fold used an adjacent limb");
  }
  if (indices.length > 0 && !pisotShrinks(indices[0])) throw new Error("Pisot refused the top limb");
  const restored = indices.reduce((sum, index) => sum + weight[index], 0n);
  if (restored !== payload) throw new Error("the store did not return the payload");
  const allocated = scaleBudget(15, 17, payload === 0n ? 1n : payload).allocated;
  return { indices, restored, allocated };
}

