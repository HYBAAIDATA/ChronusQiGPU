"""Test Grover search with TURING core."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "turing_universal_quantum_computer"))

from turing_universal_quantum_computer.grover_exact_scale import grover_search

# Test 1: 2-qubit Grover search with 2 targets (0 and 3)
idx, dist = grover_search(2, [0, 3])
print(f'Grover search n=2 targets=[0,3]: best={idx}, dist_sum={sum(dist):.4f}')
assert idx in [0, 3], f"Expected 0 or 3, got {idx}"

# Test 2: 6-qubit Grover search with target 42 (42 < 64)
idx2, dist2 = grover_search(6, [42])
print(f'Grover search n=6 targets=[42]: best={idx2}, dist_sum={sum(dist2):.4f}, p_target={dist2[42]:.4f}')
assert idx2 == 42, f"Expected 42, got {idx2}"
assert dist2[42] > 0.9, f"Expected probability > 0.9, got {dist2[42]}"

# Test 3: 3-qubit Grover search with target 5 (5 < 8)
idx3, dist3 = grover_search(3, [5])
print(f'Grover search n=3 targets=[5]: best={idx3}, dist_sum={sum(dist3):.4f}, p_target={dist3[5]:.4f}')
assert idx3 == 5, f"Expected 5, got {idx3}"
assert dist3[5] > 0.9, f"Expected probability > 0.9, got {dist3[5]}"

print('All Grover tests PASSED')
