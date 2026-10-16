"""
THE GOLDEN QUANTUM FRAMEWORK
=============================
A reusable Python library for 8 φ-based mathematical families, each tested
for its actual computational purpose.

FAMILY REGISTRY:
  1. φ + Lucas           → SCALING      (non-binary bases)
  2. φ + Binet/Pisot     → FOLDING      (continuous ↔ discrete bridge)
  3. φ + Fibonacci       → STORING      (Zeckendorf, Fibonacci coding)
  4. φ + Cassini         → SIGNAL       (parity, orientation, integrity)
  5. φ + Eigenstructure  → TRANSFORM    (spectral basis)
  6. φ + Continued Frac   → SAMPLING     (most irrational)
  7. φ + Golden Angle    → LAYOUT       (spatial coverage)
  8. φ + KAM             → STABILITY    (resonance avoidance)

Usage:
    from golden_quantum.runner import run_all
    results = run_all()

    # Or via CLI:
    # python -m golden_quantum.runner
    # python -m golden_quantum.runner --json
    # gqf --max-n 10000 --bases 2,10,12,15,18,20
"""

__version__ = "1.0.0"
__all__ = ["constants", "sequences", "coding", "matrices", "continued_fraction",
           "results", "registry", "runner", "families"]
