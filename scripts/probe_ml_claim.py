"""Reproduce and characterise the one measured ML claim in the repo.

reports/toe_unified_benchmark.json claims exact_linear_accuracy 0.9933
against a 0.6667 majority-class baseline on UCI Iris.

MEASURED over 20 random 120/30 splits, binary setosa-vs-rest (the task the
benchmark's own baseline string describes):

  REAL kellogg exact_linear : mean 0.9850 (sd 0.0247, min 0.9000, max 1.0000)
  claimed                  : 0.9933
  delta                    : -0.0083

The claim reproduces. 0.9850 mean over 20 splits is consistent with 0.9933
being one favourable split of the same distribution -- the spread runs to
1.0000, so the claimed figure sits inside the observed range.

Two scope facts the collateral does not carry:

1. The task is BINARY. TensorModelAPI.fit raises "tensor model requires
   binary labels", so 3-class Iris is not reachable at all. The 0.9933 is
   setosa-vs-rest, not general multi-class accuracy.

2. The code's own docstring states exact_linear is a nearest-centroid
   classifier expressed as a linear threshold, and that rf/xgb/lgbm/gb all
   construct this SAME object and warn. The 99% is one algorithm, not an
   ensemble. An independent reimplementation of the documented formula
   scored an identical 0.9850 (gap +0.0000), confirming that documentation
   is accurate about what the algorithm does.

This is a real, reproducible result. It is also narrower than "99.9%
accuracy in complex analytical tasks": one binary tabular task, scored by
one nearest-centroid classifier.
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def iris():
    try:
        from sklearn.datasets import load_iris

        d = load_iris()
        return d.data.astype(float), d.target
    except ImportError:
        return None, None


def nearest_centroid_fit_predict(X, y, train_idx, test_idx):
    """Reproduce kellogg exact_linear: w = mu1 - mu0, b = -w . (mu1+mu0)/2.

    Binary form, matching the documented algorithm note.
    """
    classes = np.unique(y)
    mu = {c: X[train_idx][y[train_idx] == c].mean(axis=0) for c in classes}
    accs = []
    for c in classes:
        others = [o for o in classes if o != c]
        m_o = np.mean([mu[o] for o in others], axis=0)
        w = mu[c] - m_o
        b = -float(w @ ((mu[c] + m_o) / 2))
        Xt = X[test_idx]
        pred = np.where(Xt @ w + b > 0, c, others[0])
        accs.append(float((pred == y[test_idx]).mean()))
    return float(np.mean(accs))


if __name__ == "__main__":
    X, y = iris()
    if X is None:
        print("scikit-learn unavailable; cannot reproduce the Iris figure")
        raise SystemExit(0)

    print("=== REPRODUCING reports/toe_unified_benchmark.json ===")
    print(f"  dataset rows       : {X.shape[0]}")
    print("  claimed accuracy   : 0.9933")
    print("  claimed baseline   : 0.6667 (majority class)")
    print()

    # Use the REAL API, not a reimplementation. The documented algorithm
    # note says exact_linear is a nearest-centroid linear threshold; the
    # public fit path may do more, and the benchmark may have used it.
    from kellogg.tensor_ml import exact_linear

    # The benchmark's own baseline string is "majority class on Iris-setosa
    # versus the other two species" -- a BINARY problem. exact_linear
    # requires binary labels, so that is the task to run.
    print("=== BINARY TASK, exactly as the benchmark describes it ===")
    print("  'majority class on Iris-setosa versus the other two species'")
    print()
    binary = (y != 0).astype(int)  # 0 = setosa, 1 = versicolor/virginica
    rng = np.random.default_rng(1517)
    real, mine = [], []
    for _ in range(20):
        idx = rng.permutation(len(binary))
        tr, te = idx[:120], idx[120:]
        m = exact_linear()
        m.fit(X[tr], binary[tr])
        real.append(float((m.predict(X[te]) == binary[te]).mean()))
        mine.append(nearest_centroid_fit_predict(X, binary, tr, te))

    print("  REAL kellogg exact_linear:")
    print(f"    mean accuracy    : {np.mean(real):.4f}")
    print(f"    std deviation    : {np.std(real):.4f}")
    print(f"    min / max        : {np.min(real):.4f} / {np.max(real):.4f}")
    print()
    print("  my reimplementation of the documented formula:")
    print(f"    mean accuracy    : {np.mean(mine):.4f}")
    print()
    print(f"  gap real-vs-mine : {np.mean(real) - np.mean(mine):+.4f}")
    print()
    print("  CLAIMED          : 0.9933")
    print(f"  MEASURED         : {np.mean(real):.4f}")
    print(f"  delta            : {np.mean(real) - 0.9933:+.4f}")
    print()
    maj_all = float(np.bincount(binary).max() / len(binary))
    print(f"  majority-class baseline (whole set) : {maj_all:.4f}")
    print("  claimed baseline                    : 0.6667")
    print()
    print("  NOTE: 3-class Iris is NOT reachable -- exact_linear raises")
    print("  'requires binary labels'. The 99.3% is a binary setosa-vs-rest")
    print("  number. It is a real result; its scope is narrower than")
    print("  '99.9% accuracy in complex analytical tasks'.")
    sys.stdout.flush()
