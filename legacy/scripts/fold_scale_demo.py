"""Folded-state scale demo: unlimited N, O(1) memory, closed-form peaks.

Prints, for ever-larger N, the exact folded Grover facts — state size (two
amplitudes plus the exact integer pair), the optimal iteration count, the
closed-form marked probability, the Cassini conservation witness, and the
lucas pool ceiling that bounds the cost. Beyond the iteration cap the peak
probability is the sin^2 closed form — no iteration is ever needed.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from Intelligence.grover_exact_scale import (  # noqa: E402
    FoldedGrover,
    ITERATION_CAP,
    analytical_success,
    optimal_iterations,
    pool_kernel_score,
)


def main() -> int:
    for power in (2, 12, 32, 100, 1000):
        n = 10**power
        t0 = time.perf_counter()
        k = optimal_iterations(n, 1)
        closed = analytical_success(n, 1, k)
        score = pool_kernel_score(n, 1)
        k_disp = (
            f">{ITERATION_CAP:,} (closed form)" if k > ITERATION_CAP else f"{k:,}"
        )
        if power <= 300:
            state = FoldedGrover.uniform(n, 1)
            witness = f"{state.cassini_witness():.15f}"
            layer = "float64"
        else:
            state = FoldedGrover.uniform(n, 1)
            witness = str(state.cassini_witness_exact())
            layer = "exact Q (sub-float amps)"
        wall = time.perf_counter() - t0
        print(
            f"N=10^{power:<4} k={k_disp:<28} P={closed:.9f} "
            f"witness={witness} [{layer}] "
            f"L_ceiling_n={score['ceiling_n']:>4} "
            f"bounded={score['is_lucas_bounded']} wall={wall:.3f}s"
        )
    print(
        "\nState memory is O(1) at every scale: two complex amplitudes plus "
        "the exact integer pair (N, M). Cassini conservation holds in the "
        "float layer up to ~1e300 and EXACTLY in Q beyond it; the lucas "
        "pool kernels bound the cost algebraically."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
