#!/usr/bin/env python3
"""Nonce sunflower / golden-angle distribution analysis.

Embeds winning nonces into the golden-angle representation and compares
angular statistics against a uniform null and a synthetic sunflower control.

Usage:
  python scripts/analyze_nonce_sunflower.py \
      --input artifacts/pythia_training/real_nonces_200.csv \
      --output artifacts/pythia_training/nonce_sunflower_analysis.json

Requires a CSV with a 'nonce' column (integer). Larger corpora recommended;
the existing 200-row set is labelled underpowered.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
from pathlib import Path
from typing import Any

PHI = (1 + math.sqrt(5)) / 2
GOLDEN_ANGLE_DEG = 360.0 / (PHI ** 2)  # ≈ 137.507764°
GOLDEN_ANGLE_RAD = math.radians(GOLDEN_ANGLE_DEG)


def load_nonces(path: Path) -> list[int]:
    nonces: list[int] = []
    with path.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            if "nonce" in row and row["nonce"]:
                nonces.append(int(row["nonce"]))
    return nonces


def embed(nonce: int) -> tuple[float, float]:
    """Golden-angle embedding: r = sqrt(nonce / 2**32), θ in [0, 2π)."""
    r = math.sqrt(nonce / (2**32))
    theta = (nonce * GOLDEN_ANGLE_RAD) % (2 * math.pi)
    return r, theta


def angular_spacings(thetas: list[float]) -> list[float]:
    """Nearest-neighbour angular spacing (radians), circular."""
    if len(thetas) < 2:
        return []
    sorted_t = sorted(thetas)
    spacings = []
    n = len(sorted_t)
    for i in range(n):
        d = sorted_t[(i + 1) % n] - sorted_t[i]
        if d < 0:
            d += 2 * math.pi
        spacings.append(min(d, 2 * math.pi - d))
    return spacings


def mean_spacing(spacings: list[float]) -> float:
    return sum(spacings) / len(spacings) if spacings else 0.0


def synthetic_sunflower(n: int, seed: int = 0x9E3779B9) -> list[int]:
    """Synthetic nonces placed at successive golden-angle steps."""
    rng = random.Random(seed)
    return [int((i * GOLDEN_ANGLE_RAD * (2**32) / (2 * math.pi)) % (2**32)) for i in range(n)]


def analyze(nonces: list[int]) -> dict[str, Any]:
    if not nonces:
        return {"error": "no nonces"}
    embeddings = [embed(n) for n in nonces]
    thetas = [t for _, t in embeddings]
    spacings = angular_spacings(thetas)
    mean_nn = mean_spacing(spacings)

    # Uniform null
    uniform = [random.Random(0x9E3779B9).randint(0, 2**32 - 1) for _ in nonces]
    u_thetas = [embed(u)[1] for u in uniform]
    u_spacings = angular_spacings(u_thetas)
    u_mean = mean_spacing(u_spacings)

    # Synthetic sunflower control
    synth = synthetic_sunflower(len(nonces))
    s_thetas = [embed(s)[1] for s in synth]
    s_spacings = angular_spacings(s_thetas)
    s_mean = mean_spacing(s_spacings)

    return {
        "n": len(nonces),
        "golden_angle_deg": GOLDEN_ANGLE_DEG,
        "mean_nearest_angular_spacing_rad": mean_nn,
        "uniform_null_mean_spacing_rad": u_mean,
        "synthetic_sunflower_mean_spacing_rad": s_mean,
        "delta_vs_uniform": mean_nn - u_mean,
        "delta_vs_synthetic": mean_nn - s_mean,
        "note": "Smaller spacing than uniform is consistent with clustering; compare to synthetic sunflower control. n=200 is underpowered.",
        "theorem_proven": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Nonce sunflower distribution analysis")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    nonces = load_nonces(args.input)
    result = analyze(nonces)
    result["input"] = str(args.input)
    result["artifact"] = "nonce_sunflower_analysis"

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2))
    print(f"Wrote {args.output} (n={result.get('n', 0)})")


if __name__ == "__main__":
    main()
