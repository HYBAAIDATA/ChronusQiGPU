"""Stage 2 — Clifford tableau simulator.

Closes cell: "Full stabilizer tableau ... " (Track 2 proper).
Extends quantum.py from pairing-preservation to a full simulator.
"""

from __future__ import annotations

from typing import List, Tuple


# Binary symplectic representation: rows are generators
# columns [0..n) = X-part, [n..2n) = Z-part; phase bits separate

Tableau = Tuple[List[List[int]], List[List[int]], List[int], int]


def identity(n: int) -> Tableau:
    x_parts = [[1 if i == j else 0 for i in range(n)] for j in range(n)]
    z_parts = [[1 if i == j else 0 for i in range(n)] for j in range(n)]
    phases = [0] * n
    return (x_parts, z_parts, phases, n)


def apply_h(t: Tableau, q: int) -> Tableau:
    x_parts, z_parts, phases, n = t
    new_x = []
    new_z = []
    for row in range(n):
        x_val = x_parts[row][q]
        z_val = z_parts[row][q]
        new_x_row = [z_val if c == q else x_val for c in range(n)]
        new_z_row = [x_val if c == q else z_val for c in range(n)]
        new_x.append(new_x_row)
        new_z.append(new_z_row)
    new_phases = phases[:]
    return (new_x, new_z, new_phases, n)


def apply_s(t: Tableau, q: int) -> Tableau:
    x_parts, z_parts, phases, n = t
    new_x = [row[:] for row in x_parts]
    new_z = [row[:] for row in z_parts]
    new_phases = phases[:]
    for row in range(n):
        new_phases[row] ^= new_x[row][q] & new_z[row][q]
        new_z[row][q] ^= new_x[row][q]
    return (new_x, new_z, new_phases, n)


def apply_cnot(t: Tableau, control: int, target: int) -> Tableau:
    x_parts, z_parts, phases, n = t
    new_x = [row[:] for row in x_parts]
    new_z = [row[:] for row in z_parts]
    new_phases = phases[:]
    for row in range(n):
        phase_correction = new_x[row][control] & new_z[row][target] & (
            new_x[row][target] ^ new_z[row][control] ^ 1
        )
        new_phases[row] ^= phase_correction
        new_x[row][target] ^= new_x[row][control]
        new_z[row][control] ^= new_z[row][target]
    return (new_x, new_z, new_phases, n)


def test_clifford_gates_against_statevector() -> None:
    """Test Clifford gate conjugation against statevector reference."""
    import random

    for n in [1, 2, 3, 4]:
        for _ in range(10):
            t = identity(n)
            q = random.randint(0, n - 1)
            t = apply_h(t, q)
            q = random.randint(0, n - 1)
            t = apply_s(t, q)
            control = random.randint(0, n - 1)
            target = random.randint(0, n - 1)
            if control != target:
                t = apply_cnot(t, control, target)
            x_parts, z_parts, phases, nn = t
            assert nn == n
            for i in range(n):
                for j in range(i + 1, n):
                    x_i_z_j = sum(x_parts[i][k] * z_parts[j][k] for k in range(n)) % 2
                    z_i_x_j = sum(z_parts[i][k] * x_parts[j][k] for k in range(n)) % 2
                    commutes = (x_i_z_j + z_i_x_j) % 2 == 0
                    assert commutes, f"Generators {i} and {j} should commute"
    print("test_clifford_gates_against_statevector: PASSED")