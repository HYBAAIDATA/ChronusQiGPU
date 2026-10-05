/** Exact Lucas scale. Memory and storage move by a rung, or they are refused.

Ported from `lucas/core.py`, `lucas/ladder.py`, and `chronus/mla1517/lucas_scale.py`.
L_n is an integer. A transition carries the exact ratio L_target/L_source.
Cassini must hold at both ends. There is no float rescaling.
*/

import { Frac } from "./algebra.ts";

export const CURRICULUM_RUNGS = [10, 12, 15, 18, 20] as const;
export const SCALE_RUNGS = [10, 12, 15, 18, 20, 31, 50, 76] as const;
/** Canonical rungs plus 17, the first declared transition target. */
export const LADDER = [10, 12, 15, 17, 18, 20, 31, 50, 76] as const;
export const FIRST_SOURCE_SCALE = 15;
export const FIRST_TARGET_SCALE = 17;
export const PISOT_EXACT_N = 76;

const NAMES: Record<number, string> = {
  10: "curriculum",
  12: "curriculum",
  15: "curriculum",
  17: "first declared target",
  18: "curriculum",
  20: "curriculum",
  31: "mining",
  50: "enterprise",
  76: "Pisot collapse index",
};

function half(value: bigint): bigint {
  if (value % 2n !== 0n) throw new Error("Lucas doubling was not an integer");
  return value / 2n;
}

/** Exact (F_n, L_n) by the simultaneous doubling identities. */
export function fibLucasPair(n: number): [bigint, bigint] {
  if (!Number.isInteger(n) || n < 0) throw new Error("index must be a non-negative integer");
  if (n === 0) return [0n, 2n];
  if (n === 1) return [1n, 1n];
  const [f, l] = fibLucasPair(n >> 1);
  const doubledF = f * l;
  const doubledL = l * l - 2n * ((n & 2) === 0 ? 1n : -1n);
  if ((n & 1) === 0) return [doubledF, doubledL];
  return [half(doubledF + doubledL), half(5n * doubledF + doubledL)];
}

export function lucas(n: number): bigint {
  return fibLucasPair(n)[1];
}

export function fibonacci(n: number): bigint {
  return fibLucasPair(n)[0];
}

/** Expected Cassini sign, +1 or −1. Zero is not a seal. */
export function cassiniSeal(n: number): bigint {
  if (!Number.isInteger(n) || n < 0) throw new Error("index must be a non-negative integer");
  return n % 2 === 0 ? 1n : -1n;
}

export function cassiniHolds(n: number): boolean {
  const [f, l] = fibLucasPair(n);
  return l * l - 5n * f * f === 4n * cassiniSeal(n);
}

export type ScaleTransition = {
  source: number;
  target: number;
  accepted: boolean;
  reason: string | null;
  evaluated: boolean;
  lucasSource: bigint;
  lucasTarget: bigint;
  fibSource: bigint;
  fibTarget: bigint;
  cassiniBefore: bigint;
  cassiniAfter: bigint;
  ratio: Frac | null;
};

export function transition(source: number, target: number): ScaleTransition {
  if (!Number.isInteger(source) || !Number.isInteger(target) || source < 0 || target < 0) {
    throw new Error("scale indices must be non-negative integers");
  }
  const [fibSource, lucasSource] = fibLucasPair(source);
  const [fibTarget, lucasTarget] = fibLucasPair(target);
  const cassiniBefore = cassiniSeal(source);
  const cassiniAfter = cassiniSeal(target);
  const holds =
    lucasSource * lucasSource - 5n * fibSource * fibSource === 4n * cassiniBefore &&
    lucasTarget * lucasTarget - 5n * fibTarget * fibTarget === 4n * cassiniAfter;
  return {
    source,
    target,
    accepted: holds && target > 0,
    reason: holds ? null : "cassini_identity_failed",
    lucasSource,
    lucasTarget,
    fibSource,
    fibTarget,
    cassiniBefore,
    cassiniAfter,
    ratio: lucasSource === 0n ? null : new Frac(lucasTarget, lucasSource),
    evaluated: true,
  };
}

export function authorise(
  source: number,
  target: number,
  limits: { maxIndex?: number; maxBitLength?: number; allowOffLadder?: boolean } = {},
): ScaleTransition {
  const maxIndex = limits.maxIndex ?? 1_000_000;
  const maxBitLength = limits.maxBitLength ?? 1 << 20;
  if (source < 0 || target <= 0 || target > maxIndex || source > maxIndex) {
    return {
      source,
      target,
      accepted: false,
      reason: "index_out_of_bounds",
      evaluated: false,
      lucasSource: 0n,
      lucasTarget: 0n,
      fibSource: 0n,
      fibTarget: 0n,
      cassiniBefore: 0n,
      cassiniAfter: 0n,
      ratio: null,
    };
  }
  const current = transition(source, target);
  const refuse = (reason: string): ScaleTransition => ({ ...current, accepted: false, reason });
  if (target <= 0 || target > maxIndex) return refuse("index_out_of_bounds");
  if (!limits.allowOffLadder && !LADDER.includes(target as (typeof LADDER)[number])) return refuse("family_not_allowed");
  if (BigInt(target).toString(2).length > maxBitLength) return refuse("bit_budget_exceeded");
  return current;
}

export function nextRung(index: number): number | null {
  for (const rung of LADDER) if (rung > index) return rung;
  return null;
}

export function climb(index: number): number {
  return nextRung(index) ?? index;
}

/** floor(base · L_target / L_source), plus the unreduced exact ratio. */
export function scaleBudget(source: number, target: number, base: bigint): { transition: ScaleTransition; allocated: bigint } {
  if (base < 0n) throw new Error("budget base must be non-negative");
  const gate = authorise(source, target);
  if (!gate.accepted || gate.lucasSource === 0n) {
    throw new Error(gate.reason ?? "scale transition refused");
  }
  return { transition: gate, allocated: (base * gate.lucasTarget) / gate.lucasSource };
}

export function ladderReport(): string {
  const rows = LADDER.map((index) => {
    const [f, l] = fibLucasPair(index);
    const seal = cassiniSeal(index);
    const holds = l * l - 5n * f * f === 4n * seal;
    if (!holds) throw new Error(`Cassini failed at rung ${index}`);
    return `  L_${index} = ${l}    F_${index} = ${f}    seal = ${seal > 0n ? "+1" : "−1"}    ${NAMES[index]}`;
  });
  const values = LADDER.map((index) => lucas(index));
  const monotonic = values.every((value, index) => index === 0 || value > values[index - 1]);
  return [
    "Lucas scale   arithmetic = exact integer   float rescaling = refused",
    `  ladder = ${LADDER.join(" ")}`,
    `  monotonic = ${monotonic ? "True" : "False"}`,
    "  theorem_proven = False",
    "  fold = Zeckendorf + Binet    store = Fibonacci + Cassini    scale = Lucas + Pisot",
    "  a fold that drops the exact integer is refused, not approximated",
    ...rows,
    `  first transition = ${FIRST_SOURCE_SCALE} → ${FIRST_TARGET_SCALE}`,
  ].join("\n");
}

export function transitionReport(source: number, target: number): string {
  const gate = authorise(source, target);
  if (!gate.evaluated) {
    return [`${gate.source} → ${gate.target}   accepted = False`, `  reason = ${gate.reason}`, "  exactness = refused"].join("\n");
  }
  const lines = [
    `${gate.source} → ${gate.target}   accepted = ${gate.accepted ? "True" : "False"}`,
    `  L = ${gate.lucasSource} → ${gate.lucasTarget}`,
    `  F = ${gate.fibSource} → ${gate.fibTarget}`,
    `  ratio = ${gate.ratio ? gate.ratio.toString() : "undefined"}`,
    `  Cassini = ${gate.cassiniBefore > 0n ? "+1" : "−1"} → ${gate.cassiniAfter > 0n ? "+1" : "−1"}`,
    `  reason = ${gate.reason ?? "none"}`,
    "  exactness = " + (gate.accepted ? "exact" : "refused"),
  ];
  return lines.join("\n");
}
