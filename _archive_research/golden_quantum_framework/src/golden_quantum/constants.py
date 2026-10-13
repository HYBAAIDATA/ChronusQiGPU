"""
Core mathematical constants for the Golden Quantum Framework.

Uses Python's arbitrary-precision Decimal for irrational computations.
Precision is set high enough for Binet's formula at n up to 50000.
"""

from decimal import Decimal, getcontext
import math
import sys

# Allow large Fibonacci number string conversion
if hasattr(sys, 'set_int_max_str_digits'):
    sys.set_int_max_str_digits(200000)

# Precision: F(5000) has ~1045 digits, φ^5000 needs similar.
# 10000 digits of precision covers n up to ~50000 comfortably.
getcontext().prec = 10000

# ─── Golden ratio and conjugate as Decimal ───
SQRT5_D = Decimal(5).sqrt()
PHI_D = (Decimal(1) + SQRT5_D) / Decimal(2)   # φ = (1+√5)/2 ≈ 1.618...
PSI_D = (Decimal(1) - SQRT5_D) / Decimal(2)   # ψ = (1-√5)/2 ≈ -0.618...

# Float versions for applications where exact precision is not needed
PHI_F = float(PHI_D)
PSI_F = float(PSI_D)

# ─── Bases ───
# φ works with ALL integer bases — nature doesn't discriminate.
# Binary is included alongside non-binary bases.
INTEGER_BASES = [2, 10, 12, 15, 18, 20]
NON_BINARY_BASES = [10, 12, 15, 18, 20]

# ─── Golden Angle ───
# 360° × (1 - 1/φ) = 360°/φ² ≈ 137.50776°
GOLDEN_ANGLE_DEG = 360.0 * (1.0 - 1.0 / PHI_F)  # ≈ 137.50776°
GOLDEN_ANGLE_RAD = 2.0 * math.pi * (1.0 - 1.0 / PHI_F)
GOLDEN_ANGLE_FRACTION = 1.0 - 1.0 / PHI_F  # ≈ 0.38196...

# ─── Exact identity: 1 - 1/φ = 1/φ² ───
# Proof: 1/φ = φ - 1, so 1 - 1/φ = 1 - (φ-1) = 2 - φ = 1/φ²
# since φ² = φ + 1, so 1/φ² = 1/(φ+1) = (φ-1)/((φ+1)(φ-1)) = (φ-1)/(φ²-1) = (φ-1)/φ = 1 - 1/φ. ✓
