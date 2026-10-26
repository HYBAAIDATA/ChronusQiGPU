# Euclid Review: Euler systems

**Treatise ID**: `kolyvagin_1990`  
**Provenance Hash**: `84ce37a1e98f9d0ab8f58717045911838c27485b5217b3bdb365917340bd8e79`  
**Authors**: Victor A. Kolyvagin (1990)  
**License**: Academic Research Fair Use  
**Source URL**: [https://link.springer.com/chapter/10.1007/978-0-8176-4576-2_11](https://link.springer.com/chapter/10.1007/978-0-8176-4576-2_11)  
**Problem Focus**: BSD  

---

## 1. The Five Euclid Lenses

### 1.1 Predictive Lens (What does the theory forecast?)
Predicts that when analytic rank <= 1, the Tate-Shafarevich group Sha(E/Q) is finite.

### 1.2 Causal Lens (What invariant structures force the result?)
Euler system relation Cor(c_{mp}) = P(Frob_p^(-1)) c_m systematically annihilating the dual Selmer group.

### 1.3 Counterfactual Lens (What if a key hypothesis is dropped?)
For curves of analytic rank >= 2, Heegner point systems fail to provide non-trivial cohomology classes.

### 1.4 Topological Lens (What is the space/bundle/cohomology structure?)
Galois cohomology groups H^1(Q, E[p^k]) and local completions H^1(Q_v, E).

### 1.5 Geometric Lens (What shape, lattice, or metric invariants govern?)
Lattice of Selmer conditions at Archimedean and non-Archimedean places.

---

## 2. Key Claims & Status Breakdown

| Claim / Theorem | Page / Index | Status | Formulation |
| :--- | :--- | :--- | :--- |
| Kolyvagin's Theorem | Kolyvagin's Theorem | **PROVEN** | If L(E, 1) != 0, then rank E(Q) = 0 and Sha(E/Q) is finite. If L(E, 1) = 0 and L'(E, 1) != 0, then rank E(Q) = 1 and Sha(E/Q) is finite. |
| Selmer Group Annihilation | Selmer Group Annihilation | **PROVEN** | Euler system classes annihilate the dual Selmer group, bounding the size of Sha(E/Q). |
| Finiteness of Sha(E/Q) | Finiteness of Sha(E/Q) | **OPEN** | Sha(E/Q) is finite for all elliptic curves E/Q of arbitrary rank r. |

---

## 3. Finite Computational Handles (What Euclid CAN execute)

- [x] `Upper bounding 2-Selmer group dim_F2 Sel^(2)(E/Q).`
- [x] `Verification of triviality or order of Sha(E) via analytic quotient.`
- [x] `Evaluation of local Tamagawa numbers c_p via Tate's algorithm.`

---

## 4. Open Gaps & Falsification Conditions

- [!] **GAP**: Euler systems constructed from Heegner points control Selmer groups only when analytic rank is 0 or 1. No Euler system is known for rank >= 2.

---

## 5. Citations & License Transparency

- **Citation**: Kolyvagin, V.A. (1990). Euler systems, The Grothendieck Festschrift, Vol. II, Progr. Math., 87, Birkhäuser, 435-483.  
  URL: [https://link.springer.com/chapter/10.1007/978-0-8176-4576-2_11](https://link.springer.com/chapter/10.1007/978-0-8176-4576-2_11)
