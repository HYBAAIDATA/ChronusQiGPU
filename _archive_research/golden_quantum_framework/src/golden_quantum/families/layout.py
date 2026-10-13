"""
FAMILY 7: φ + GOLDEN ANGLE → LAYOUT
=====================================
Golden angle ≈ 137.508°. Provides optimal spatial coverage.

THEOREMS:
  - Golden angle identity: 2π(1 - 1/φ) = 2π/φ²
  - Golden angle fraction = 1 - 1/φ = 1/φ²

INVARIANTS:
  - No short periodic repeats in the golden angle sequence

DEMONSTRATIONS:
  - Angular distribution coverage
  - Low-discrepancy property
  - Phyllotaxis layout quality
"""

import math
from decimal import Decimal
from ..results import CheckRegistry
from ..constants import PHI_D, PHI_F, GOLDEN_ANGLE_RAD, GOLDEN_ANGLE_DEG, GOLDEN_ANGLE_FRACTION


def run(registry: CheckRegistry, max_n: int = 10000) -> None:
    family = "FAMILY 7: φ + Golden Angle"
    purpose = "LAYOUT"

    # ── 7A: Golden angle identity 1 - 1/φ = 1/φ² ──
    # Proof: 1/φ = φ - 1 (since φ² = φ + 1, so 1/φ = φ²⁻¹ = (φ+1)⁻¹ = φ - 1)
    # So 1 - 1/φ = 1 - (φ - 1) = 2 - φ
    # And 1/φ² = 1/(φ+1). Since φ(φ-1) = φ² - φ = 1, we get 1/φ = φ - 1,
    # so 1/φ² = (φ-1)² = φ² - 2φ + 1 = (φ+1) - 2φ + 1 = 2 - φ. ✓
    one_minus_inv_phi = Decimal(1) - Decimal(1) / PHI_D
    inv_phi_sq = Decimal(1) / (PHI_D ** 2)
    identity_ok = abs(one_minus_inv_phi - inv_phi_sq) < Decimal("1e-100")
    registry.add_check(
        family, purpose,
        "7A: Golden angle identity 1 - 1/φ = 1/φ²",
        identity_ok, "theorem",
        "Both equal 2 - φ ≈ 0.38197",
    )

    # ── 7B: Golden angle ≈ 137.50776° ──
    angle_ok = abs(GOLDEN_ANGLE_DEG - 137.50776) < 0.001
    registry.add_check(
        family, purpose,
        f"7B: Golden angle = 360°/φ² ≈ 137.508° (got {GOLDEN_ANGLE_DEG:.5f}°)",
        angle_ok, "theorem",
    )

    # ── 7C: No short periodic repeats ──
    # The sequence {n · golden_angle mod 2π} has no period ≤ max_period
    # This follows from the irrationality of the golden angle fraction
    n_points = min(max_n, 10000)
    max_period = min(1000, n_points - 1)
    angles = [(i * GOLDEN_ANGLE_RAD) % (2 * math.pi) for i in range(n_points)]
    no_period = True
    for period in range(1, max_period + 1):
        # Check if angle[period] ≈ angle[0] (within tolerance)
        diff = abs(angles[period] - angles[0])
        diff = min(diff, 2 * math.pi - diff)
        if diff < 1e-6:
            no_period = False
            registry.add_check(
                family, purpose,
                f"7C: No period ≤ {max_period}",
                False, "invariant",
                f"Found period at {period}",
            )
            break
    if no_period:
        registry.add_check(
            family, purpose,
            f"7C: No periodic repeat with period ≤ {max_period} in golden angle sequence",
            True, "demonstration",
            "Follows from irrationality of 1/φ² — bounded numeric verification",
        )

    # ── 7D: Angular coverage (demonstration) ──
    # Divide [0, 2π) into bins and check uniform coverage
    num_bins = 36  # 10° bins
    bin_counts = [0] * num_bins
    for angle in angles:
        bin_idx = int(angle / (2 * math.pi) * num_bins) % num_bins
        bin_counts[bin_idx] += 1
    # Check all bins have at least 50% of the expected count
    expected = n_points / num_bins
    min_count = min(bin_counts)
    coverage_ok = min_count >= 0.5 * expected
    registry.add_check(
        family, purpose,
        f"7D: Angular coverage — all {num_bins} bins have ≥50% of expected ({expected:.0f})",
        coverage_ok, "demonstration",
        f"Min bin: {min_count}, Max bin: {max(bin_counts)}, Expected: {expected:.0f}",
    )

    # ── 7E: Low discrepancy (demonstration) ──
    # The star discrepancy D_N* measures how uniform a sequence is.
    # For the golden angle sequence, D_N* = O(log N / N) — better than random.
    # Compare with a uniform random sequence.
    N = min(n_points, 5000)
    ga_seq = sorted([(i * GOLDEN_ANGLE_FRACTION) % 1.0 for i in range(N)])

    # Compute star discrepancy D_N* = sup |empirical_CDF(x) - x|
    max_dev = 0
    for i, x in enumerate(ga_seq):
        # empirical CDF at x = (i+1)/N
        dev = max(abs((i + 1) / N - x), abs(i / N - x))
        if dev > max_dev:
            max_dev = dev

    # For comparison, generate a random sequence
    import random
    random.seed(42)
    rand_seq = sorted([random.random() for _ in range(N)])
    rand_max_dev = 0
    for i, x in enumerate(rand_seq):
        dev = max(abs((i + 1) / N - x), abs(i / N - x))
        if dev > rand_max_dev:
            rand_max_dev = dev

    low_disc = max_dev < rand_max_dev
    registry.add_check(
        family, purpose,
        f"7E: Low discrepancy — golden angle beats random (D_N*={max_dev:.6f} < random={rand_max_dev:.6f})",
        low_disc, "demonstration",
        f"Golden angle discrepancy: {max_dev:.6f}, Random: {rand_max_dev:.6f}",
    )

    # ── 7F: Phyllotaxis point generation ──
    # Points at (r, θ) = (√(n/N), n · golden_angle) should be well-distributed
    N_pts = min(n_points, 300)
    points = []
    for n in range(N_pts):
        r = math.sqrt(n / N_pts)
        theta = n * GOLDEN_ANGLE_RAD
        x = r * math.cos(theta)
        y = r * math.sin(theta)
        points.append((x, y))

    # Check nearest-neighbor distances have low coefficient of variation
    # (indicating uniform spacing, not clumping)
    nn_dists = []
    for i in range(min(N_pts, 500)):
        min_dist = float('inf')
        for j in range(N_pts):
            if i == j:
                continue
            dx = points[i][0] - points[j][0]
            dy = points[i][1] - points[j][1]
            dist = dx * dx + dy * dy
            if dist < min_dist:
                min_dist = dist
        nn_dists.append(math.sqrt(min_dist))

    mean_dist = sum(nn_dists) / len(nn_dists)
    var_dist = sum((d - mean_dist) ** 2 for d in nn_dists) / len(nn_dists)
    cv = math.sqrt(var_dist) / mean_dist if mean_dist > 0 else 999

    uniform_spacing = cv < 0.5  # Low CV means uniform spacing
    registry.add_check(
        family, purpose,
        f"7F: Phyllotaxis spacing uniform (CV={cv:.4f} < 0.5)",
        uniform_spacing, "demonstration",
        f"Mean NN distance: {mean_dist:.4f}, CV: {cv:.4f}",
    )

    # ── 7G: Golden angle is irrational ──
    # The golden angle fraction 1/φ² is irrational (since φ is irrational)
    # This is the foundation of why it works for layout
    # φ is irrational → φ² is irrational → 1/φ² is irrational
    ga_fraction_decimal = Decimal(1) / (PHI_D ** 2)
    # Check it's not a simple rational
    is_irrational = True
    for q in range(1, 1000):
        p = int((ga_fraction_decimal * q).to_integral_value())
        if abs(ga_fraction_decimal - Decimal(p) / Decimal(q)) < Decimal("1e-30"):
            is_irrational = False
            break
    registry.add_check(
        family, purpose,
        "7G: Golden angle fraction 1/φ² is irrational (no rational p/q with q<1000)",
        is_irrational, "demonstration",
        "Bounded numeric check — exact proof follows from φ being irrational",
    )
