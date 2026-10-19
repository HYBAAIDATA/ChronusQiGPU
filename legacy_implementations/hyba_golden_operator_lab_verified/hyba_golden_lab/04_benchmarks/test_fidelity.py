#!/usr/bin/env python3
"""Fidelity-first tests of the consumable API. Fail closed."""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "api"), str(ROOT / "01_mathematics"), str(ROOT / "02_quantum")]

from quantum_api import QuantumAPI, GoldenScale  # noqa: E402
from golden_transform import PHI, fib, lucas  # noqa: E402


def check(name: str, cond: bool, detail: str = "") -> bool:
    print(f"  [{'OK' if cond else 'FAIL'}] {name}  {detail}")
    return cond


def main() -> int:
    api = QuantumAPI()
    failed = 0

    print("FIDELITY / IDENTITY TESTS")
    h = api.health()
    failed += not check("health", h.ok)

    failed += not check("identities", GoldenScale.identities_hold())

    # unitarity
    for name, op in (("H", api.hadamard()), ("X", api.pauli("x")),
                     ("Y", api.pauli("y")), ("Z", api.pauli("z")),
                     ("CNOT", api.cnot()), ("QFT4", api.qft_op(4)),
                     ("Ry(π/φ)", api.rotation("y", math.pi / PHI))):
        failed += not check(f"unitary {name}", op.is_unitary())

    # completeness
    c = api.completeness(8)
    failed += not check("completeness dim=8", c.ok, f"err={c.data['error']:.2e}")

    # Yang–Baxter
    yb = api.yang_baxter()
    failed += not check("Yang-Baxter", yb.ok, f"err={yb.data['error']:.2e}")

    # Bell / GHZ
    bell = api.bell()
    ghz = api.ghz(3)
    failed += not check("Bell norm", abs(np.linalg.norm(bell.amplitudes) - 1) < 1e-12)
    red = api.reduce(bell, 2, 2)
    failed += not check("Bell reduced rank>1", red.data["rank"] > 1, f"S={red.data['entropy']:.4f}")
    failed += not check("GHZ dim", ghz.dim == 8)

    # QFT inversion fidelity
    psi0 = api.basis(3, 16)
    q = api.qft(psi0)
    failed += not check("QFT inversion F=1", q.fidelity is not None and q.fidelity > 1 - 1e-12,
                        f"F={q.fidelity}")

    # Grover fidelity to unique marked state
    g = api.grover(3, [7], scaled=False)
    failed += not check("Grover finds |111>", g.ok and g.data["found"] == 7,
                        f"P*={g.data['marked_probability']:.6f} F={g.fidelity}")

    # M^n fold roundtrip
    data = np.array([float(fib(k)) for k in range(1, 9)], dtype=float)
    fold = api.fold_Mn(data, 5)
    failed += not check("M^5 fold invertible", fold.ok, f"err={fold.data['roundtrip_error']:.2e}")

    # Zeckendorf unique
    z = api.fold_zeckendorf([1, 4, 15, 50, 100])
    failed += not check("Zeckendorf unique", z.ok)

    # Binet
    bf = api.fold_binet("F", 20)
    bl = api.fold_binet("L", 20)
    failed += not check("Binet F", bf.ok, f"maxerr={bf.data['max_abs_error']:.2e}")
    failed += not check("Binet L", bl.ok, f"maxerr={bl.data['max_abs_error']:.2e}")

    # MPS exact reconstruction
    mps = api.mps(ghz)
    failed += not check("MPS reconstruct GHZ", mps.ok, f"F={mps.fidelity}")

    # QFI closed form
    qfi = api.qfi(0.3, "y")
    failed += not check("QFI Ry|0> = 1", qfi.ok, f"F={qfi.data['qfi']}")

    # Cassini / Lucas / Fib consistency via scale
    failed += not check("L15 nearest Φ^15", abs(lucas(15) - PHI ** 15) < 1e-3)
    failed += not check("Cassini n=8", GoldenScale.cassini(8) == 1)

    # kernel PSD
    X = np.array([[PHI ** i, 1.0 / PHI ** i] for i in range(1, 6)], dtype=float)
    k = api.kernel(X)
    failed += not check("kernel PSD", k.ok, f"min_eig={k.data['min_eig']:.2e}")

    print(f"\n{'PASS' if failed == 0 else 'FAIL'}  failures={failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
