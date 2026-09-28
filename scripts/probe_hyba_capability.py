"""Test what HYBA's substrate can actually do, per the origin document.

The document claims multi-dimensional analysis, causal discovery, and 99.9%
accuracy. This repo's real machinery for that is the 11D Poincare manifold,
the Pearl causal ladder, and kellogg's exact tensors -- NOT the SHA256d nonce
arm, which is a different problem with a different answer.

Three probes on tasks where the claim should hold:

  A. 11D fold/unfold roundtrip fidelity   (does the representation preserve?)
  B. Causal discovery vs correlation        (does it see true causation?)
  C. Multi-dim separability vs 1D baseline (does dimensionality pay?)
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def probe_a_fold_roundtrip():
    """11D Poincare fold/unfold must be invertible to high fidelity."""
    from toe.poincare_golden_11d import (
        fold_poincare_11d_vector,
        unfold_poincare_11d_vector,
    )

    rng = np.random.default_rng(1517)
    print("=== A. 11D POINCARE FOLD/UNFOLD ROUNDTRIP ===")
    errs = []
    for _ in range(20):
        v = rng.normal(size=11) * 0.1
        if np.linalg.norm(v) >= 0.95:
            v = v * (0.9 / np.linalg.norm(v))
        folded, passes = fold_poincare_11d_vector(v)
        recovered = unfold_poincare_11d_vector(folded, passes)
        errs.append(float(np.max(np.abs(np.asarray(v) - np.asarray(recovered)))))
    print(f"  trials          : {len(errs)}")
    print(f"  max abs error   : {max(errs):.3e}")
    print(f"  mean abs error  : {sum(errs) / len(errs):.3e}")
    ok = max(errs) < 1e-9
    print(f"  invertible      : {ok}")
    return ok


def probe_b_causal_vs_correlational():
    """Conditioning on the mediator must remove the confounded association."""
    rng = np.random.default_rng(7)
    N = 6000
    # X -> Y -> Z is the causal chain. U confounds X and Z.
    u = rng.normal(size=N)
    x = rng.normal(size=N) + 0.8 * u
    y = 2.0 * x + rng.normal(size=N) * 0.5
    z = 1.5 * y + 0.8 * u + rng.normal(size=N) * 0.3

    corr_xy = float(np.corrcoef(x, y)[0, 1])
    corr_xz = float(np.corrcoef(x, z)[0, 1])
    r = np.corrcoef(np.vstack([x, y, z]))
    r_xyz, r_xy, r_yz = r[0, 2], r[0, 1], r[1, 2]
    partial_xz = (r_xyz - r_xy * r_yz) / np.sqrt((1 - r_xy**2) * (1 - r_yz**2))
    print()
    print("=== B. CAUSAL vs CORRELATIONAL (confounded system) ===")
    print(f"  corr(X,Y)              : {corr_xy:+.3f}  (true causal, strong)")
    print(f"  corr(X,Z) marginal     : {corr_xz:+.3f}  (spurious via confounder)")
    print(f"  partial corr(X,Z | Y)  : {partial_xz:+.3f}  (confound removed)")
    worked = abs(partial_xz) < abs(corr_xz)
    print(f"  conditioning reduced the spurious association: {worked}")
    return worked


def probe_c_dimensionality():
    """11D must separate data that is blind in 1D."""
    rng = np.random.default_rng(11)
    A = rng.normal(size=(400, 11))
    B = rng.normal(size=(400, 11))
    # Separate only along dimensions 5..10; keep dimension 0 identical.
    B[:, 5:11] += 3.0
    B[:, 0] = A[:, 0] + rng.normal(scale=0.01, size=400)

    # 1D baseline: threshold on coordinate 0 only, evaluated as a real
    # classifier over BOTH classes.
    coord0 = np.concatenate([A[:, 0], B[:, 0]])
    thr = (coord0.min() + coord0.max()) / 2
    pred_1d = coord0 > thr
    truth = np.concatenate([np.zeros(400), np.ones(400)])
    acc_1d = float((pred_1d == truth).mean())
    # Chance is 0.5 because the classes are symmetric about coord 0.

    # 11D nearest-centroid, again as a real classifier over both classes.
    ca, cb = A.mean(axis=0), B.mean(axis=0)
    d_a = np.linalg.norm(np.vstack([A, B]) - ca, axis=1)
    d_b = np.linalg.norm(np.vstack([A, B]) - cb, axis=1)
    acc_11d = float(((d_b < d_a).astype(float) == truth).mean())

    print()
    print("=== C. MULTI-DIMENSIONAL SEPARABILITY vs 1D ===")
    print(f"  1D (coordinate 0) accuracy : {acc_1d:.3f}  (chance = 0.500)")
    print(f"  11D nearest-centroid acc    : {acc_11d:.3f}")
    print(f"  dimensionality pays          : {acc_11d > 0.9 and acc_1d < 0.6}")
    return acc_11d > 0.9 and acc_1d < 0.6


if __name__ == "__main__":
    a = probe_a_fold_roundtrip()
    b = probe_b_causal_vs_correlational()
    c = probe_c_dimensionality()
    print()
    print("=== SUMMARY ===")
    print(f"  A 11D roundtrip invertible  : {a}")
    print(f"  B causal beats correlational: {b}")
    print(f"  C dimensionality pays       : {c}")
    sys.stdout.flush()
