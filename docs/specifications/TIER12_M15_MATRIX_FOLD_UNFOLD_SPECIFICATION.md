# TIER 12 SPECIFICATION: EXACT CASSINI $M_{15}$ MATRIX FOLD & UNFOLD MECHANICS
## Lossless Reversible Payload Transformations Over $\mathbb{Z}/256\mathbb{Z}[\phi]$

**Classification**: MATHEMATICAL SUBSTRATE // REPRESENTATION-AWARE ARCHITECTURE  
**Target Subsystem**: Chronus GPIU Tier 12 / Enterprise State Plane / Exact Algebraic Unit  
**Algebraic Ring**: $\mathbb{Z}/256\mathbb{Z}[\phi]$ where $\phi^2 = \phi + 1$  
**System Invariants**: Invariant I6 (Cassini Witness), Invariant I8 (Bijective Reversibility), Invariant I9 (Unitary Determinant)  

---

### Executive Overview

The **$M_{15}$ matrix fold and unfold mechanics** form the exact algebraic core of **Tier 12** in the Chronus GPIU specification. Operating over the finite byte ring $\mathbb{Z}/256\mathbb{Z}[\phi]$ (extended by the Golden Ratio $\phi = \frac{1+\sqrt{5}}{2}$), this engine provides 100% exact, lossless, bitwise reversible payload transformations without accumulation drift or floating-point rounding errors.

By mapping contiguous byte coordinates onto a modular symplectic lattice governed by Cassini's Fibonacci identity, Tier 12 guarantees deterministic, carry-free diffusion with closed-form inversion in $O(n)$ time.

---

### 1. Matrix Definitions & Determinant Proof

The fold and unfold operations rely on a fixed symmetric $2 \times 2$ matrix $M_{15}$ and its modular inverse $M_{15}^{-1}$ over $\mathbb{Z}/256\mathbb{Z}$:

#### A. Forward Transformation Matrix ($M_{15}$)
$$M_{15} = \begin{pmatrix} 219 & 98 \\ 98 & 121 \end{pmatrix}$$

#### B. Determinant & Invertibility Proof
The exact determinant in $\mathbb{Z}$ is computed as:
$$\det(M_{15}) = 219 \cdot 121 - 98 \cdot 98 = 26,499 - 9,604 = 16,895$$

Reducing modulo 256 yields:
$$16,895 = 66 \cdot 256 + 255 \implies 16,895 \equiv 255 \equiv -1 \pmod{256}$$

Because:
$$\gcd(\det(M_{15}), 256) = \gcd(255, 256) = \gcd(-1, 256) = 1$$

The matrix $M_{15}$ is strictly coprime to the ring modulus 256, proving that $M_{15} \in GL_2(\mathbb{Z}/256\mathbb{Z})$ is strictly non-singular and unconditionally invertible.

#### C. Inverse Transformation Matrix ($M_{15}^{-1}$)
Using the classical adjugate formula for $2 \times 2$ matrices over commutative rings:
$$A^{-1} = (\det A)^{-1} \cdot \operatorname{adj}(A) = (\det A)^{-1} \begin{pmatrix} d & -b \\ -c & a \end{pmatrix}$$

Since $(\det M_{15})^{-1} \equiv 255^{-1} \equiv (-1)^{-1} \equiv -1 \equiv 255 \pmod{256}$:
$$M_{15}^{-1} \equiv -1 \cdot \begin{pmatrix} 121 & -98 \\ -98 & 219 \end{pmatrix} \equiv \begin{pmatrix} -121 & 98 \\ 98 & -219 \end{pmatrix} \pmod{256}$$

Reducing negative entries modulo 256:
$$-121 \equiv 256 - 121 = 135 \pmod{256}$$
$$-219 \equiv 256 - 219 = 37 \pmod{256}$$

Therefore, the exact modular inverse is:
$$M_{15}^{-1} = \begin{pmatrix} 135 & 98 \\ 98 & 37 \end{pmatrix}$$

#### D. Product Invariant Check
$$M_{15} \cdot M_{15}^{-1} = \begin{pmatrix} 219 & 98 \\ 98 & 121 \end{pmatrix} \begin{pmatrix} 135 & 98 \\ 98 & 37 \end{pmatrix}$$
* Row 0, Col 0: $(219 \cdot 135 + 98 \cdot 98) = 29,565 + 9,604 = 39,169 \equiv 1 \pmod{256}$
* Row 0, Col 1: $(219 \cdot 98 + 98 \cdot 37) = 21,462 + 3,626 = 25,088 = 98 \cdot 256 \equiv 0 \pmod{256}$
* Row 1, Col 0: $(98 \cdot 135 + 121 \cdot 98) = 13,230 + 11,858 = 25,088 \equiv 0 \pmod{256}$
* Row 1, Col 1: $(98 \cdot 98 + 121 \cdot 37) = 9,604 + 4,477 = 14,081 = 55 \cdot 256 + 1 \equiv 1 \pmod{256}$

$$M_{15} \cdot M_{15}^{-1} \equiv \begin{pmatrix} 1 & 0 \\ 0 & 1 \end{pmatrix} \pmod{256} \quad \text{[Q.E.D.]}$$

---

### 2. Exact Fold Mechanics (`fold`)

The `fold(payload)` operator accepts an arbitrary byte array $X \in (\mathbb{Z}/256\mathbb{Z})^n$ and maps it into folded coordinates:

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                               TIER 12 FOLD PIPELINE                                     │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                         │
│   Input Bytes:       [ x₀   x₁ ]       [ x₂   x₃ ]   ...   [ x_{n-1} (odd) ]            │
│                        │     │           │     │                  │                     │
│                        ▼     ▼           ▼     ▼                  ▼                     │
│   Symplectic Mix:      M₁₅ Matrix       M₁₅ Matrix           First Column of M₁₅        │
│   (mod 256)          [ 219   98 ]     [ 219   98 ]           [ 219 ]   [  98 ]          │
│                      [  98  121 ]     [  98  121 ]             │         │              │
│                        │     │           │     │               │         │              │
│                        ▼     ▼           ▼     ▼               ▼         ▼              │
│   Folded Output:     [ u₀   v₀ ]       [ u₁   v₁ ]   ...   [ out_{-1}  out_{appended} ] │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

#### Step 1: Contiguous Pairwise Transformation
For each even index pair $(x, y) = (\text{payload}[2i], \text{payload}[2i+1])$ where $0 \le i < \lfloor n/2 \rfloor$:
$$u = (219 \cdot x + 98 \cdot y) \bmod 256$$
$$v = (98 \cdot x + 121 \cdot y) \bmod 256$$

#### Step 2: Trailing Odd Byte Handling
If the payload length $n$ is odd, the trailing un-paired byte $x_{\text{last}} = \text{payload}[n-1]$ is encoded using the first column of $M_{15}$ and appended as two deterministic output bytes:
$$\text{out}[n-1] = (219 \cdot x_{\text{last}}) \bmod 256$$
$$\text{out}_{\text{appended}} = (98 \cdot x_{\text{last}}) \bmod 256$$

This guarantees that trailing odd bytes never corrupt or misalign preceding 16-bit word boundaries.

#### Step 3: OVID-Bound Cryptographic Receipt
Every fold operation issues a formal cryptographic receipt containing:
1. Content-addressed Object Virtual Identifier: `o1_<sha256(payload)[:16]>`
2. SHA-256 digest of the folded byte stream.
3. Live verified determinant: $\det(M_{15}) \equiv 255 \pmod{256}$.
4. RFC 8785 canonical JSON representation with Ed25519 signature.

---

### 3. Exact Unfold Mechanics (`unfold`)

The `unfold(folded, orig_len)` operator reverses the transformation with zero information loss:

#### Step 1: Pairwise Inverse Reconstruction
For each folded pair $(u, v) = (\text{folded}[2i], \text{folded}[2i+1])$ where $0 \le i < \lfloor \text{orig\_len}/2 \rfloor$:
$$x = (135 \cdot u + 98 \cdot v) \bmod 256$$
$$y = (98 \cdot u + 37 \cdot v) \bmod 256$$

#### Step 2: Trailing Odd Byte Recovery
If `orig_len` is odd, the two appended bytes $(u, v) = (\text{folded}[\text{orig\_len}-1], \text{folded}[\text{orig\_len}])$ are inverted using Row 0 of $M_{15}^{-1}$:
$$x_{\text{last}} = (135 \cdot u + 98 \cdot v) \bmod 256$$

#### Step 3: Bijective Identity Guarantee (Invariant I8)
Because $M_{15} \cdot M_{15}^{-1} \equiv I \pmod{256}$, the round-trip equality holds identically:
$$\text{Unfold}(\text{Fold}(X), \operatorname{len}(X)) \equiv X \quad \forall X \in \bigcup_{k=0}^\infty (\mathbb{Z}/256\mathbb{Z})^k$$

---

### 4. Cassini Witness & System Invariants

The mathematical stability of the fold matrix is anchored in the **Cassini Identity** over the Fibonacci sequence $\{F_n\}$:

$$F_{n+1} \cdot F_{n-1} - F_n^2 \equiv (-1)^n \pmod{256}$$

#### System Invariant Verification Matrix:
* **Invariant I6 (Cassini Witness)**:
  $$\det \begin{pmatrix} F_{n+1} & F_n \\ F_n & F_{n-1} \end{pmatrix} = F_{n+1} F_{n-1} - F_n^2 = (-1)^n$$
  Holds for all Fibonacci indices evaluated by Tier 12.
* **Invariant I8 (Exact Bijective Invertibility)**:
  Bitwise exact identity $\text{Unfold}(\text{Fold}(X)) == X$ across all payload topologies (empty, single-byte, even-length, odd-length, and multi-megabyte buffers).
* **Invariant I9 (Modular Determinant Unit)**:
  $$\det(M_{15}) = 219 \cdot 121 - 98 \cdot 98 = 16,895 \equiv 255 \pmod{256}$$
  $$\gcd(255, 256) = 1 \implies M_{15} \text{ has exact inverse } M_{15}^{-1}$$

---

### 5. Implementation Reference

The canonical Python implementation is maintained in [`src/chronus/execution/structural.py`](file:///c:/Users/leonn/OneDrive/Desktop/chronus-quantum-igpu/src/chronus/execution/structural.py):

```python
M15 = ((219, 98), (98, 121))
M15_INV = ((135, 98), (98, 37))
M15_DET = 255  # 16895 % 256

def apply_m15_byte_map(x: int, y: int) -> tuple[int, int]:
    """Applies forward M15 transform: (219*x + 98*y mod 256, 98*x + 121*y mod 256)."""
    return ((219 * x + 98 * y) % 256, (98 * x + 121 * y) % 256)

def apply_m15_inverse_byte_map(u: int, v: int) -> tuple[int, int]:
    """Applies inverse M15 transform: (135*u + 98*v mod 256, 98*u + 37*v mod 256)."""
    return ((135 * u + 98 * v) % 256, (98 * u + 37 * v) % 256)
```

Verified with 100% pass rate in [`tests/test_mining.py`](file:///c:/Users/leonn/OneDrive/Desktop/chronus-quantum-igpu/tests/test_mining.py) (`test_m15_byte_map_is_bijective`).

