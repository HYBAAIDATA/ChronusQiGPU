/** Exact closed forms from the Turing VQC. No decimal evaluation. */

export type AlgebraicTime = "0" | "pi/4" | "pi/2";

const TIMES = new Set<AlgebraicTime>(["0", "pi/4", "pi/2"]);

export function isAlgebraicTime(value: string): value is AlgebraicTime {
  return TIMES.has(value as AlgebraicTime);
}

function binom(n: number, k: number): bigint {
  if (k < 0 || k > n) return 0n;
  if (k > n - k) k = n - k;
  let value = 1n;
  for (let i = 1; i <= k; i++) value = (value * BigInt(n - k + i)) / BigInt(i);
  return value;
}

function phase(n: number): string {
  return ["1", "−i", "−1", "i"][((n % 4) + 4) % 4];
}

/** Continuous-time walk on the n-cube. H = −∑ X_j, propagator ⊗ e^{−it X}. */
export function hypercube(n: number, time?: string): string {
  if (!Number.isInteger(n) || n < 1) throw new Error("n must be an integer >= 1");
  const lines = [
    `hypercube walk   n = ${n}   materialised = False`,
    "  H = −∑_j X_j",
    "  ⟨x|e^{−i A t}|0⟩ = cos(t)^{n−w(x)} (−i sin t)^{w(x)}",
    "  P(w) = C(n, w) cos(t)^{2(n−w)} sin(t)^{2w}",
    "  E[w] = n sin(t)^2",
    "  Var[w] = n sin(t)^2 cos(t)^2",
  ];
  if (time === undefined) {
    lines.push("  time left symbolic; a decimal t is refused, not approximated");
    return lines.join("\n");
  }
  if (!isAlgebraicTime(time)) {
    throw new Error(`time ${time} is not an algebraic point of this family; use 0, pi/4, or pi/2, or omit t`);
  }
  if (time === "0") {
    lines.push("  t = 0");
    lines.push("  E[w] = 0");
    lines.push("  Var[w] = 0");
    lines.push("  P(w = 0) = 1");
    lines.push("  ⟨0|U|0⟩ = 1");
  } else if (time === "pi/2") {
    lines.push("  t = π/2");
    lines.push(`  E[w] = ${n}`);
    lines.push("  Var[w] = 0");
    lines.push(`  P(w = ${n}) = 1`);
    lines.push(`  amplitude of |1…1⟩ = ${phase(n)}`);
  } else {
    lines.push("  t = π/4");
    lines.push(`  E[w] = ${n}/2`);
    lines.push(`  Var[w] = ${n}/4`);
    lines.push(`  P(w) = C(${n}, w) / 2^${n}`);
    if (n <= 12) {
      for (let w = 0; w <= n; w++) {
        lines.push(`    w = ${w}    ${binom(n, w)}/2^${n}`);
      }
    } else {
      lines.push("  weights not listed: the binomial coefficient is the exact probability");
    }
  }
  return lines.join("\n");
}

/** Jordan–Wigner spectrum of the critical transverse-field Ising chain. */
export function tfim(n: number): string {
  if (!Number.isInteger(n) || n < 2) throw new Error("n must be an integer >= 2");
  return [
    `TFIM   n = ${n}   materialised = False`,
    "  H = −∑ Z_i Z_{i+1} − ∑ X_i",
    "  k_m = (2m+1) π / n",
    "  ε_k = 2 √(1 + g^2 − 2 g cos k)",
    "  Δ(g) = 2 √((1−g)^2 + 4 g sin^2(π/(2n)))",
    `  critical gap g = 1:  4 sin(π/(2·${n}))`,
    `  leading gap:  2π/${n}`,
    "  not a Trotter product; the spectrum is the free-fermion sum",
  ].join("\n");
}

export function landauZener(): string {
  return [
    "Landau–Zener",
    "  P = 1 − exp(−π Δ^2 / (2 v))",
    "  kept symbolic; the exponential is not replaced by a decimal",
  ].join("\n");
}
