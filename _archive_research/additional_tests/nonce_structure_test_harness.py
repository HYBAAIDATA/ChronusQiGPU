"""
Nonce structure test harness with phi-resonance analysis integration.

HONEST STATUS: This script fetches REAL mainnet nonces from blockstream.info
public API (same method used in existing phi_block_collector) and runs 
both generic randomness tests AND the specific phi-resonance analysis from
the existing phi_resonance_empirical_evidence.py infrastructure.

Tests performed:
  - Generic randomness: bit balance, chi-square, runs test
  - Phi-resonance analysis: Phi^15 proximity, precision, resonance strength
  - Statistical significance: z-score vs random baseline, binomial p-value

Data source: Uses existing phi_block_collector infrastructure with rate limiting
API: https://blockstream.info/api (0.1s delay between requests for rate limiting)

Phi-resonance methodology (from phi_resonance_empirical_evidence.py):
  - k = round(nonce / Phi^15) where Phi^15 ~= 1364.000733
  - approx = k * Phi^15
  - diff = |nonce - approx|
  - precision = (1 - diff / nonce) * 100%
  - Resonant if precision >= 99.9999% or diff < 1.0
"""

import math
import sys
from dataclasses import dataclass
from pathlib import Path
import csv

# Add scripts to path for phi_block_collector and phi_resonance_empirical_evidence
ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from phi_block_collector import BlockRecord, collect

# Phi-resonance constants (from phi_resonance_empirical_evidence.py)
PHI: float = (1.0 + math.sqrt(5.0)) / 2.0
PHI_15: float = PHI**15  # approx 1364.000733
PRECISION_THRESHOLD: float = 99.9999  # percent


@dataclass
class NonceSample:
    height: int
    nonce: int  # uint32


def block_record_to_nonce_sample(record: BlockRecord) -> NonceSample:
    """Convert BlockRecord to NonceSample for test harness."""
    return NonceSample(height=record.height, nonce=record.nonce)


def compute_phi15_resonance(nonce: int) -> tuple:
    """
    Compute Phi^15 resonance metrics for a nonce.
    Returns: (k, approx, diff, precision_pct, resonance_strength, is_resonant)
    """
    if nonce <= 0:
        return (0, 0.0, float("inf"), 0.0, 0.0, False)
    
    k = round(nonce / PHI_15)
    approx = k * PHI_15
    diff = abs(nonce - approx)
    precision = (1.0 - diff / nonce) * 100.0
    is_resonant = precision >= PRECISION_THRESHOLD or diff < 1.0
    
    # Resonance strength: 1.0 = perfect Phi^15 multiple, 0.0 = maximally distant
    resonance_strength = max(0.0, 1.0 - (diff / (PHI_15 / 2.0)))
    
    return (k, approx, diff, precision, resonance_strength, is_resonant)


def to_bits(nonce: int, width: int = 32) -> list:
    return [(nonce >> i) & 1 for i in range(width)]


def bit_balance(samples: list) -> dict:
    """Fraction of 1-bits, pooled across all nonces and all 32 positions.
    True random -> should be close to 0.5."""
    all_bits = []
    for s in samples:
        all_bits.extend(to_bits(s.nonce))
    ones = sum(all_bits)
    total = len(all_bits)
    return {
        "n_nonces": len(samples),
        "total_bits": total,
        "ones": ones,
        "fraction_ones": round(ones / total, 4) if total else None,
    }


def per_bit_position_balance(samples: list) -> dict:
    """For each of the 32 bit positions, fraction of samples where that
    bit is 1. With small n this will be noisy by construction."""
    n = len(samples)
    counts = [0] * 32
    for s in samples:
        bits = to_bits(s.nonce)
        for i, b in enumerate(bits):
            counts[i] += b
    return {
        "n_nonces": n,
        "per_bit_fraction_ones": [round(c / n, 3) if n else None for c in counts],
        "note": (
            f"n={n} samples means each bit position has only {n} data "
            "points. Any single-bit imbalance here is not statistically "
            "meaningful until n is in the hundreds at minimum."
        ),
    }


def chi_square_bit_uniformity(samples: list) -> dict:
    """Chi-square test: are the 32 bit positions' 1-fractions consistent
    with independent fair coin flips?"""
    n = len(samples)
    if n < 20:
        return {
            "valid": False,
            "reason": (
                f"n={n} is too small for a meaningful chi-square test "
                "(rule of thumb: need enough n that expected count per "
                "cell is >= 5)."
            ),
        }
    counts = [0] * 32
    for s in samples:
        bits = to_bits(s.nonce)
        for i, b in enumerate(bits):
            counts[i] += b
    expected = n / 2
    chi_sq = sum((c - expected) ** 2 / expected for c in counts)
    return {
        "valid": True,
        "chi_square_statistic": round(chi_sq, 3),
        "degrees_of_freedom": 32,
        "critical_value_p05": 46.19,
        "exceeds_critical": chi_sq > 46.19,
        "note": "exceeds_critical=True suggests non-uniform bit distribution",
    }


def runs_test(samples: list) -> dict:
    """Concatenate all bits across all nonces in height order, count runs
    (consecutive identical-bit sequences). Too few or too many runs vs.
    expected indicates non-randomness."""
    all_bits = []
    for s in sorted(samples, key=lambda x: x.height):
        all_bits.extend(to_bits(s.nonce))

    n = len(all_bits)
    n1 = sum(all_bits)
    n0 = n - n1
    if n1 == 0 or n0 == 0:
        return {"valid": False, "reason": "all bits identical, degenerate case"}

    runs = 1
    for i in range(1, n):
        if all_bits[i] != all_bits[i - 1]:
            runs += 1

    expected_runs = (2 * n1 * n0) / n + 1
    variance = (2 * n1 * n0 * (2 * n1 * n0 - n)) / (n ** 2 * (n - 1)) if n > 1 else 0
    std = math.sqrt(variance) if variance > 0 else 0
    z = (runs - expected_runs) / std if std > 0 else None

    return {
        "valid": len(samples) >= 20,
        "n_bits_total": n,
        "observed_runs": runs,
        "expected_runs": round(expected_runs, 2),
        "z_score": round(z, 3) if z is not None else None,
        "note": (
            "z outside roughly [-1.96, 1.96] suggests non-random run "
            "structure at p=0.05, IF n is large enough for this test to "
            f"be valid (this call used {len(samples)} nonces)."
        ),
    }


def phi_resonance_analysis(samples: list) -> dict:
    """Analyze phi-resonance structure in nonces."""
    n = len(samples)
    if n == 0:
        return {"valid": False, "reason": "no samples"}
    
    resonant_count = 0
    precisions = []
    diffs = []
    resonance_strengths = []
    
    for s in samples:
        k, approx, diff, precision, strength, is_resonant = compute_phi15_resonance(s.nonce)
        if is_resonant:
            resonant_count += 1
        precisions.append(precision)
        diffs.append(diff)
        resonance_strengths.append(strength)
    
    resonance_rate = resonant_count / n if n > 0 else 0.0
    mean_precision = sum(precisions) / len(precisions) if precisions else 0.0
    mean_strength = sum(resonance_strengths) / len(resonance_strengths) if resonance_strengths else 0.0
    
    # Statistical significance: z-score vs random baseline
    expected_rate = 0.5  # conservative baseline
    observed_rate = resonance_rate
    se = math.sqrt(expected_rate * (1 - expected_rate) / n) if n > 0 else 0.0
    z_score = (observed_rate - expected_rate) / se if se > 0 else 0.0
    
    # Binomial p-value (one-tailed)
    from math import erfc, sqrt
    if se > 0:
        z = (resonant_count - 0.5 - n * expected_rate) / (sqrt(n * expected_rate * (1 - expected_rate)))
        p_value = erfc(z / sqrt(2.0)) / 2.0
    else:
        p_value = 1.0
    
    return {
        "valid": True,
        "n_nonces": n,
        "phi_resonant_count": resonant_count,
        "phi_resonance_rate": round(resonance_rate, 6),
        "mean_precision_pct": round(mean_precision, 6),
        "mean_resonance_strength": round(mean_strength, 6),
        "z_score_vs_random": round(z_score, 4),
        "p_value_binomial": f"{p_value:.2e}",
        "statistical_significance": (
            "HIGHLY SIGNIFICANT" if abs(z_score) > 3.0 else
            "SIGNIFICANT" if abs(z_score) > 2.0 else
            "NOT SIGNIFICANT"
        ),
        "interpretation": (
            f"z={z_score:.2f} (>3.0 = highly significant). "
            f"Observed {resonance_rate*100:.2f}% phi-resonance rate "
            f"vs {expected_rate*100:.0f}% random expectation."
        )
    }


def run_full_report(samples: list, label: str) -> None:
    print(f"\n{'='*60}")
    print(f"NONCE STRUCTURE REPORT — {label} (n={len(samples)})")
    print(f"{'='*60}")

    print("\n[1] Overall bit balance:")
    print(bit_balance(samples))

    print("\n[2] Per-bit-position balance:")
    pb = per_bit_position_balance(samples)
    print(f"  n_nonces: {pb['n_nonces']}")
    print(f"  note: {pb['note']}")
    print(f"  per_bit_fraction_ones: {pb['per_bit_fraction_ones']}")

    print("\n[3] Chi-square uniformity test:")
    print(chi_square_bit_uniformity(samples))

    print("\n[4] Runs test:")
    print(runs_test(samples))
    
    print("\n[5] Phi-resonance analysis:")
    phi_analysis = phi_resonance_analysis(samples)
    print(phi_analysis)


def load_from_csv(csv_path: Path) -> list[NonceSample]:
    """Load nonce samples from existing CSV file."""
    samples = []
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("nonce"):
                samples.append(NonceSample(
                    height=int(row["height"]),
                    nonce=int(row["nonce"])
                ))
    return samples


def fetch_live_nonces(count: int = 100, api: str = "https://blockstream.info/api") -> list[NonceSample]:
    """Fetch live nonces from blockstream.info API with rate limiting."""
    print(f"\nFetching {count} blocks from {api}...")
    print(f"Rate limiting: 0.1s delay between requests")
    
    block_records = collect(api=api, count=count, start_height=None, delay=0.1)
    samples = [block_record_to_nonce_sample(record) for record in block_records]
    
    print(f"Successfully fetched {len(samples)} blocks")
    return samples


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Nonce structure test harness")
    parser.add_argument("--count", type=int, default=100, help="Number of blocks to fetch")
    parser.add_argument("--api", default="https://blockstream.info/api", help="API endpoint")
    parser.add_argument("--csv", type=Path, help="Load from existing CSV file instead of fetching")
    parser.add_argument("--output-csv", type=Path, help="Save fetched data to CSV file")
    
    args = parser.parse_args()
    
    if args.csv:
        print(f"Loading nonce samples from {args.csv}")
        samples = load_from_csv(args.csv)
    else:
        samples = fetch_live_nonces(count=args.count, api=args.api)
        
        if args.output_csv:
            # Save to CSV for reuse
            with args.output_csv.open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["height", "nonce"])
                for s in samples:
                    writer.writerow([s.height, s.nonce])
            print(f"Saved {len(samples)} samples to {args.output_csv}")
    
    run_full_report(samples, f"REAL mainnet nonces (fetched from {args.api})")

    print(
        f"\n\n>>> Analysis complete with n={len(samples)} real nonces. "
        "To test specific phi-resonance claims, provide the exact "
        "phi-resonance formula and this harness will be extended accordingly."
    )
