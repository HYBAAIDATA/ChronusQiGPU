# Euclid Review: Heegner points and derivatives of L-series

**Treatise ID**: `gross_zagier_1986`  
**Provenance Hash**: `98e2a7bef702da4186e10fd3714387dd6bd9e355a8d38550ff3d989f1f3d05f0`  
**Authors**: Benedict H. Gross, Don B. Zagier (1986)  
**License**: Open Access (EuDML / Springer)  
**Source URL**: [https://eudml.org/doc/143346](https://eudml.org/doc/143346)  
**Problem Focus**: BSD  

---

## 1. The Five Euclid Lenses

### 1.1 Predictive Lens (What does the theory forecast?)
Predicts that non-vanishing of the first derivative L'(E, 1) produces an explicit non-torsion rational point on E(Q).

### 1.2 Causal Lens (What invariant structures force the result?)
Rankin-Selberg convolution and the trace of modular Heegner points on modular curves X_0(N).

### 1.3 Counterfactual Lens (What if a key hypothesis is dropped?)
If the root number w_E = +1, L'(E, 1) vanishes identically, requiring second derivatives L''(E, 1) and higher cycles.

### 1.4 Topological Lens (What is the space/bundle/cohomology structure?)
Modular curve X_0(N) = Gamma_0(N) \ H^2 union cusps and its Jacobian J_0(N).

### 1.5 Geometric Lens (What shape, lattice, or metric invariants govern?)
Hyperbolic geometry of modular curves, Petersson inner product (f, f), and canonical Néron-Tate height pairings.

---

## 2. Key Claims & Status Breakdown

| Claim / Theorem | Page / Index | Status | Formulation |
| :--- | :--- | :--- | :--- |
| Gross-Zagier Formula | Gross-Zagier Formula | **PROVEN** | L'(E, 1) * L(E^(D), 1) = (u^2 / (8 pi^2 sqrt(|D|))) * (f, f) * h_hat(P_K) where P_K is the Trace of the Heegner point. |
| Rank 1 BSD Partial Resolution | Rank 1 BSD Partial Resolution | **PROVEN** | If L(E, 1) = 0 and L'(E, 1) != 0, there exists a rational point P in E(Q) of infinite order, so rank E(Q) >= 1. |
| Higher Rank BSD Analogue | Higher Rank BSD Analogue | **OPEN** | Generalization of Gross-Zagier formula to L^((r))(E, 1) for r >= 2 using higher algebraic cycles. |

---

## 3. Finite Computational Handles (What Euclid CAN execute)

- [x] `Numerical evaluation of canonical height h_hat(P) via Tate's series.`
- [x] `CM point construction on X_0(N) via Weber modular functions.`
- [x] `L'(E, 1) high-precision computation via rapid exponential sum.`

---

## 4. Open Gaps & Falsification Conditions

- [!] **GAP**: Heegner points only produce points of rank 1 in E(K); cannot construct rank 2 or higher subspaces directly.

---

## 5. Citations & License Transparency

- **Citation**: Gross, B.H., Zagier, D.B. (1986). Heegner points and derivatives of L-series, Invent. Math., 84, 225-320.  
  URL: [https://eudml.org/doc/143346](https://eudml.org/doc/143346)
