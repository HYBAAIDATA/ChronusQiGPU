# Euclid Review: The Topological Invariants of Algebraic Varieties

**Treatise ID**: `hodge_1950`  
**Provenance Hash**: `7919e72b7cd0344f562e5e8fa6574cba52f9320cd2a7b9b5528ad12974aa3742`  
**Authors**: William V.D. Hodge (1950)  
**License**: Open Access (ICM Proceedings)  
**Source URL**: [https://www.mathunion.org/icm/proceedings](https://www.mathunion.org/icm/proceedings)  
**Problem Focus**: HODGE  

---

## 1. The Five Euclid Lenses

### 1.1 Predictive Lens (What does the theory forecast?)
Predicts that topological (p,p)-classes carrying integer/rational periods are algebraic cycle classes.

### 1.2 Causal Lens (What invariant structures force the result?)
Hodge decomposition H^k(X, C) = oplus H^(p,q) enforced by the harmonic Laplacian Delta = d delta + delta d on Kähler manifolds.

### 1.3 Counterfactual Lens (What if a key hypothesis is dropped?)
On non-Kähler compact complex manifolds (e.g. Hopf surfaces), the Hodge decomposition fails and Hodge numbers depend on complex structure.

### 1.4 Topological Lens (What is the space/bundle/cohomology structure?)
Compact complex manifold X of dimension n; Betti cohomology H^*(X, Q) and Poincaré duality pairing.

### 1.5 Geometric Lens (What shape, lattice, or metric invariants govern?)
Kähler metric g_ij with closed Kähler form omega = i g_{j k_bar} dz^j wedge dz_bar^k; Ricci curvature and Fubini-Study metrics.

---

## 2. Key Claims & Status Breakdown

| Claim / Theorem | Page / Index | Status | Formulation |
| :--- | :--- | :--- | :--- |
| Hodge Theorem for Compact Kähler Manifolds | Hodge Theorem for Compact Kähler Manifolds | **PROVEN** | De Rham cohomology decomposes into harmonic forms of type (p,q), and Hodge diamond is symmetric. |
| Kähler Identities | Kähler Identities | **PROVEN** | [L, Lambda] = (p+q-n) I and [d, Lambda] = i d^c_* relating Lefschetz operator and dual operator. |
| Lefschetz (1,1) Theorem | Lefschetz (1,1) Theorem | **PROVEN** | Every integral Hodge class of type (1,1) is the first Chern class of a holomorphic line bundle (algebraic cycle). |
| Hodge Conjecture | Hodge Conjecture | **OPEN** | On a projective non-singular complex algebraic variety, every Hodge class in H^(2p)(X, Q) cap H^(p,p)(X) is a rational linear combination of cohomology classes of algebraic subvarieties of codimension p. |
| Integral Hodge Conjecture | Integral Hodge Conjecture | **REFUTED_BY_ATIYAH_HIRZEBRUCH_1962** | Every integral Hodge class is algebraic. |

---

## 3. Finite Computational Handles (What Euclid CAN execute)

- [x] `Exact Hodge diamond calculation for Fermat hypersurfaces and complete intersections.`
- [x] `Intersection form evaluation on H^2 of K3 surfaces (even unimodular lattice II_3,19).`
- [x] `Period matrix computation for abelian varieties and identification of endomorphism algebras.`

---

## 4. Open Gaps & Falsification Conditions

- [!] **GAP**: Atiyah and Hirzebruch (1962) found torsion counterexamples to the integral version, forcing restriction to Q-coefficients.
- [!] **GAP**: For codimension p >= 2, no general analytic inversion mechanism exists to construct algebraic cycles from harmonic (p,p)-forms.

---

## 5. Citations & License Transparency

- **Citation**: Hodge, W.V.D. (1950). The Topological Invariants of Algebraic Varieties, Proc. Int. Congr. Math., Vol. 1, 182-192.  
  URL: [https://www.mathunion.org/icm/proceedings](https://www.mathunion.org/icm/proceedings)
