# HYBA Infrastructure (Corrected v1.1.0)

**φ-Substrate Compute Layer** — all 5 original bugs fixed plus 3 additional issues.

## Bug Fixes

| # | Bug | Fix |
|---|-----|-----|
| 1 | HYBACore class not defined | Already fixed |
| 2 | Cassini accepts impostor matrices | Full structural validation + exponent recovery |
| 3 | struct.pack overflow on negative deltas | Signed 64-bit (`<q`) |
| 4 | Memory allocation underflow | `gap >= size` instead of `gap² >= size` |
| 5 | Float drift in lifting | Integer-only enforcement + round-half-away-from-zero |
| 6 | Odd-length fold breaks roundtrip | Pass-through trailing element |
| 7 | bits_per_value +1 waste | Removed +1 |
| 8 | Pisot verification used floats | Migrated to Decimal |

## Quick Start

```python
from hyba import HYBAInfrastructure

hyba = HYBAInfrastructure()
hyba.initialize()  # Verifies Cassini, Binet, and integrity checks

# Compress data
compressed = hyba.process([1, 2, 3, 4, 5], "compress")
decompressed = hyba.process(compressed, "decompress")
assert decompressed == [1, 2, 3, 4, 5]

# Pisot precision
multiplies = hyba.process(None, "precision", precision=1e-6)  # Returns 12
```

## Running the Comparison

```bash
pip install -e .
python scripts/compare_with_gqf.py
```

See `COMPARISON_WITH_GQF.md` for full results.

## License

MIT
