"""Measured SHA-256d hashrate through the active hasher.

Observed facts only: wall-clock H/s, the backend/device that physically ran,
and kernel/launch counts. No projections, no Lucas scaling, no extrapolation.

Usage:
    python scripts/bench_hashrate.py [duration_s] [hasher_backend]
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mining.hash_pipeline import HashPipeline  # noqa: E402


def main() -> int:
    duration = float(sys.argv[1]) if len(sys.argv) > 1 else 12.0
    backend = sys.argv[2] if len(sys.argv) > 2 else "auto"
    pipe = HashPipeline(hasher_backend=backend)
    rep = pipe.benchmark_hashrate(
        bytes(80), b"\xff" * 31 + b"\x7f", nonce_count=10**9, duration_s=duration
    )
    print(f"backend       : {rep['backend']}")
    print(f"device        : {rep['device']}")
    print(f"measured_hps  : {rep['measured_hps']:,.0f}")
    print(f"hashes        : {rep['hashes']:,}")
    print(f"kernel_ms     : {rep['kernel_ms']:.1f}")
    print(f"launches      : {rep['launches']}")
    print(f"elapsed_s     : {rep['elapsed_seconds']:.2f}")
    print(f"scoring_backend: {rep['scoring_backend']}")
    print("truth_class   :", rep["truth_class"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
