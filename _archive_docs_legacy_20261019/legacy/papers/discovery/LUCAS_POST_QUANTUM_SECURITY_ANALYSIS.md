# LUCAS POWER SCALING — POST-QUANTUM SECURITY ANALYSIS

**Status:** Formal assessment, honest classification
**Scope:** Every quantum algorithm wired to the `lucas/` pool
**Conclusion up front:** Lucas scaling is an arithmetic/resource transformation
on quantum algorithm *simulations*. It is not a cryptographic primitive, and it
neither strengthens nor weakens any cryptosystem. Nothing in this repository
should be relied upon for cryptographic assurance.

---

## 1. What "post-quantum safe" actually means

A system is post-quantum secure if it resists attack by adversaries equipped
with fault-tolerant quantum computers — specifically, if no known quantum
algorithm (Shor, Grover, or variants) reduces its security below an accepted
classical-equivalent work factor.

A bare boolean `post_quantum_safe: true` on an algorithm *benchmark* is
category error: the algorithms tested here are **primitives**, not
**cryptosystems**. QFT, Grover, QPE, quantum walks and VQE have no keys, no
messages, and no adversary. Asking whether they are "post-quantum safe" is
like asking whether a Fourier transform is secure against chosen-plaintext
attack — the predicate does not apply.

The previous `post_quantum_safe: True` fields in the verification report have
been replaced by a structured `security` assessment
(`_security_assessment()` in `experiments/toe_enterprise_collapse.py`).

---

## 2. Per-algorithm cryptanalytic relevance

| Algorithm | Cryptanalytic relevance | Direction |
|---|---|---|
| QFT | Core subroutine of Shor's algorithm | **Offensive** — enables breaking RSA, DH, ECC on fault-tolerant hardware |
| QPE | The phase-estimation engine inside Shor; also used in quantum chemistry | **Offensive** (as part of Shor) |
| Grover | Generic √N search speedup against symmetric ciphers and hash preimages | **Offensive** — halves effective key/security bits; mitigated by doubling key length |
| Quantum Walk | Search primitives; some walk-based attacks on structured problems exist in the literature | Mostly **neutral** at this scale |
| VQE | No known cryptanalytic application | **Neutral** |
| Quantum kernels / fidelity | No known cryptanalytic application | **Neutral** |

None of these algorithms, scaled or unscaled, *defend* anything. Two of them
(QFT/QPE inside Shor; Grover generically) are the standard reasons the field
migrates to post-quantum cryptography in the first place.

---

## 3. What Lucas scaling does and does not change

Lucas Power Scaling replaces a resource budget or precision parameter with an
exact Lucas number `L_n` (or a φ-algebraic factor) drawn from the shared pool:

- **It changes:** iteration schedules, precision-register sizing, step counts,
  sample budgets — the *cost accounting* of the simulation.
- **It does not change:** the algorithm's mathematical output class, its
  asymptotic complexity class, or its cryptanalytic power. A Lucas-scaled
  QFT is still a QFT; a Lucas-scaled Grover still searches in O(√N).
- **It provides no defence:** there is no mechanism by which choosing
  `L_15 = 1364` iterations instead of 1364 arbitrary steps creates, removes,
  or modifies any security property.

Equally important — **it provides no new attack surface:** the scaling is
deterministic exact arithmetic over `Z[φ]`; it introduces no randomness, no
side-channel-relevant data flow, and no secret-dependent behaviour.

---

## 4. Threat model

| Layer | Assets | Adversary | Applicability |
|---|---|---|---|
| This simulation stack | None (no keys, no secrets, no signatures) | N/A | Security predicates are **not applicable** |
| A real deployment embedding these algorithms | Keys, plaintexts, proofs | Quantum-capable adversary | Use NIST-standardized PQC — see §5 |

If this repository's *algorithms* are ever embedded in a system handling real
secrets, the security of that system is determined entirely by the surrounding
cryptographic construction — never by the algorithm primitives themselves.

---

## 5. Recommendations

For any deployment requiring actual post-quantum confidentiality or
authenticity, use the NIST-standardized constructions:

- **Key establishment:** ML-KEM (FIPS 203, CRYSTALS-Kyber) — ML-KEM-1024 for
  long-term security
- **Signatures:** ML-DSA (FIPS 204, CRYSTALS-Dilithium) or SLH-DSA (FIPS 205,
  SPHINCS+) for hash-based assurance
- **Symmetric/hash:** AES-256 and SHA-384+ already provide ≥128-bit
  post-quantum security against Grover (Grover halves the effective exponent)

Do not treat any flag, bound, or `is_lucas_bounded` result in this repository
as evidence of cryptographic security.

---

## 6. Honesty ledger

| Claim | Status |
|---|---|
| QFT unitary after scaling | **Verified** (error < 2e-15) |
| Grover correct after scaling | **Verified** (peak 0.9453 preserved) |
| Resource bounds ≤ L_n at ladder indices | **Verified** (per `lucas_bound` calls) |
| Algorithms are post-quantum cryptosystems | **Not applicable** — they are primitives |
| Lucas scaling provides cryptographic security | **False** — no mechanism exists |
| Lucas scaling weakens cryptographic security | **False** — it touches no cryptographic object |
| `theorem_proven` | **False everywhere**, pinned |

---

**Document control:** this analysis accompanies
`LUCAS_POWER_SCALING_RIGOROUS_FOUNDATIONS.md` and the empirical results in
`experiments/lucas_scaling_results.json`. It should be updated whenever the
algorithm inventory or the threat model changes.
