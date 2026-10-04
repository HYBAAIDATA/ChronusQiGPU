/** Golden meets Fourier at the 5-fold cosine. It does not replace it.

η = ζ_5 + ζ_5^{-1} lies in Z[φ]. ζ_5 does not: its degree is 4.
The QFT this console executes uses ζ_8, whose real subfield is Q(√2), not Q(φ).
*/

import { Frac } from "./algebra.ts";

type Ring = { a: bigint; b: bigint };

function mul(p: Ring, q: Ring): Ring {
  return { a: p.a * q.a + p.b * q.b, b: p.a * q.b + p.b * q.a + p.b * q.b };
}

function resultant(): Frac {
  const matrix = [
    [1n, -1n, -1n, 0n],
    [0n, 1n, -1n, -1n],
    [1n, 0n, -2n, 0n],
    [0n, 1n, 0n, -2n],
  ].map((row) => row.map((entry) => new Frac(entry)));
  let sign = 1n;
  let det = new Frac(1n);
  for (let col = 0; col < 4; col++) {
    let pivot = col;
    while (pivot < 4 && matrix[pivot][col].isZero()) pivot += 1;
    if (pivot === 4) return new Frac(0n);
    if (pivot !== col) {
      [matrix[col], matrix[pivot]] = [matrix[pivot], matrix[col]];
      sign = -sign;
    }
    const lead = matrix[col][col];
    det = det.mul(lead);
    for (let row = col + 1; row < 4; row++) {
      const factor = matrix[row][col].div(lead);
      for (let j = col; j < 4; j++) matrix[row][j] = matrix[row][j].sub(factor.mul(matrix[col][j]));
    }
  }
  return sign < 0n ? det.neg() : det;
}

let cached: string | null = null;

export function ontologyReport(): string {
  if (cached) return cached;
  const eta: Ring = { a: -1n, b: 1n };
  const square = mul(eta, eta);
  const value = { a: square.a + eta.a - 1n, b: square.b + eta.b };
  if (value.a !== 0n || value.b !== 0n) throw new Error("φ − 1 does not satisfy η^2 + η − 1");
  const shared = resultant();
  if (shared.isZero()) throw new Error("the golden polynomial and x^2 - 2 share a root");
  cached = [
    "ontology",
    "  claim = golden replaces Fourier",
    "  verdict = REFUSED",
    "  theorem_proven = False",
    "",
    "[where they are the same number]",
    "  Φ_5(ζ) = 0 gives ζ^2 + ζ + 1 + ζ^{-1} + ζ^{-2} = 0",
    "  η = ζ + ζ^{-1}",
    "  ζ^2 + ζ^{-2} = η^2 − 2",
    "  so η^2 + η − 1 = 0",
    "  η = φ − 1 = −1 + φ",
    "  the order-5 cosine is an element of Z[φ]",
    "  ζ_5 is not: Φ_5 has degree 4 and Q(φ) has degree 2",
    "",
    "[where the replacement leaves the field]",
    "  the executed QFT uses ζ_8",
    "  2 cos(2π/8) = √2",
    "  √2 satisfies x^2 − 2 = 0",
    `  resultant of (x^2 − x − 1, x^2 − 2) = ${shared}`,
    "  the resultant is not zero, so the polynomials share no root",
    "  an amplitude of the QFT is not a golden integer",
    "",
    "[what the console keeps]",
    "  a golden operator has coordinates in Z[φ]",
    "  a Fourier operator commutes with a cycle shift",
    "  the cycle Laplacian does; the path Laplacian does not",
    "  Fourier is that special case",
    "  golden is the 5-fold cosine, not a substitute for the root of unity",
  ].join("\n");
  return cached;
}
