# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
# Chronus is a HYBA Data product.
"""Fleet kernel plugin used by the multi-process tests (loaded via CHRONUS_FLEET_KERNELS).

``m15_fold_paced`` computes exactly what ``m15_fold`` computes. When
CHRONUS_FLEET_TEST_PACE_MS is set (only in worker processes) each tile also
waits that long, so a test can stop a worker while it holds a lease.
"""

from __future__ import annotations

import os
import time

from chronus.fleet.kernels import M15FoldKernel

PACE_ENV = "CHRONUS_FLEET_TEST_PACE_MS"


def _pace() -> None:
    pace = int(os.environ.get(PACE_ENV, "0"))
    if pace > 0:
        time.sleep(pace / 1000)


class PacedM15FoldKernel(M15FoldKernel):
    name = "m15_fold_paced"
    description = "m15_fold with an optional per-tile pause (tests only)."

    def known_answers(self):
        return M15FoldKernel().known_answers()

    def run_reference(self, ctx, params, tile, start, stop):
        _pace()
        return super().run_reference(ctx, params, tile, start, stop)

    def run_simd(self, ctx, params, tile, start, stop):
        _pace()
        return super().run_simd(ctx, params, tile, start, stop)


FLEET_KERNELS = [PacedM15FoldKernel()]
