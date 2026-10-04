/** Where a Fourier call folds, and where a golden recurrence folds.

A length-4 Fibonacci window has four nonzero DFT bins and a 2-coordinate
companion. The determinant of two consecutive states is ±1, so two is the
dimension of the solution space. A period-2 window is the other way round:
its DFT has two nonzero bins, and it does not obey the Fibonacci recurrence.
*/

import { fibonacci } from "./lucas-scale.ts";

type Gauss = { re: bigint; im: bigint };

function timesRoot(sample: bigint, power: number): Gauss {
  const turn = ((power % 4) + 4) % 4;
  if (turn === 0) return { re: sample, im: 0n };
  if (turn === 1) return { re: 0n, im: sample };
  if (turn === 2) return { re: -sample, im: 0n };
  return { re: 0n, im: -sample };
}

function dft4(signal: bigint[]): Gauss[] {
  if (signal.length !== 4) throw new Error("this fold comparison is the length-4 transform");
  return [0, 1, 2, 3].map((bin) =>
    signal.reduce<Gauss>(
      (total, sample, index) => {
        const term = timesRoot(sample, bin * index);
        return { re: total.re + term.re, im: total.im + term.im };
      },
      { re: 0n, im: 0n },
    ),
  );
}

function support(bins: Gauss[]): number {
  return bins.filter((bin) => bin.re !== 0n || bin.im !== 0n).length;
}

let cached: string | null = null;

export function signalReport(): string {
  if (cached) return cached;
  const window = [0, 1, 2, 3].map((index) => fibonacci(index));
  const recurrenceBins = support(dft4(window));
  const left = fibonacci(3);
  const mid = fibonacci(4);
  const right = fibonacci(5);
  const det = left * right - mid * mid;
  if (det === 0n) throw new Error("two Fibonacci states were dependent");
  if (recurrenceBins !== 4) throw new Error("the Fibonacci window was unexpectedly sparse in the DFT");
  const period = [1n, 0n, 1n, 0n];
  const periodBins = support(dft4(period));
  if (periodBins >= period.length) throw new Error("the period-2 window did not fold under the DFT");
  const recurrenceHolds = period[2] === period[1] + period[0] && period[3] === period[2] + period[1];
  if (recurrenceHolds) throw new Error("the period-2 window obeyed Fibonacci");
  cached = [
    "signal",
    "  claim = wherever Fourier is used, a golden fold is better",
    "  verdict = SPLIT",
    "  theorem_proven = False",
    "",
    "[a recurrence is a golden fold]",
    `  window F(0)..F(3) = ${window.join(",")}`,
    `  nonzero DFT bins = ${recurrenceBins}`,
    "  companion coordinates = 2",
    `  Cassini determinant F(3)F(5) − F(4)^2 = ${det}`,
    "  the determinant is not zero, so one coordinate cannot carry the state",
    "  two is the dimension of the solution space",
    "  on this window the DFT does not fold",
    "",
    "[a period is a Fourier fold]",
    "  window = 1,0,1,0",
    `  nonzero DFT bins = ${periodBins}`,
    "  Fibonacci recurrence on that window = False",
    "  the executed QFT is this kind of signal",
    "  a golden coordinate is not one of its amplitudes",
    "",
    "[the rule]",
    "  fold a recurrence with the companion",
    "  fold a root-of-unity period with the Fourier transform",
    "  neither one is better at the other's window",
    "  bin counts are not the overhead ledger; prime, sunflower and gate counts are `store`",
  ].join("\n");
  return cached;
}
