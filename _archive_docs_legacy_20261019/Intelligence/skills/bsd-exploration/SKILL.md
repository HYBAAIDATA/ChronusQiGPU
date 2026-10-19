---
name: bsd-exploration
description: End-to-end workflow skill for exploring, analyzing, ledgering, and verifying the Birch and Swinnerton-Dyer (BSD) Millennium Problem using the EUCLID-SALAMANDER-PYTHIA-AL_HARAS multi-agent swarm, with exact Weierstrass curve arithmetic, Frobenius point counting, Zeckendorf certificates, Hodges model theory, Tononi Phi integration, and CMI claim honesty boundary enforcement.
version: 1.0.0
---

# Birch & Swinnerton-Dyer (BSD) Multi-Agent Workflow Skill

> **Foundational Axiom Anchor:** Governed by [`OWNER_DECLARATIONS.md`](file:///c:/Users/leonn/OneDrive/Desktop/PhiEnterprise-main/OWNER_DECLARATIONS.md) (D5: Zeckendorf folds, Fibonacci/Cassini stores; D6: Quantum comes from maths, exact algebra; D8: Whole-system integration) and [`AGENTS.md`](file:///c:/Users/leonn/OneDrive/Desktop/PhiEnterprise-main/AGENTS.md).
>
> **CMI Honesty Invariant:** No component of this workflow claims to have proven the BSD conjecture. All outputs are structured conjectures, empirical invariants, and model-theoretic sentences. `proof_claim: False` is strictly enforced by AL HARAS.

---

## 1. Overview & Swarm Architecture

The Birch and Swinnerton-Dyer conjecture relates the arithmetic of rational points on an elliptic curve $E/\mathbb{Q}$ to the analytic behavior of its Hasse-Weil $L$-function $L(E, s)$ at the critical point $s = 1$:

$$\operatorname{ord}_{s=1} L(E, s) = \operatorname{rank} E(\mathbb{Q})$$

and conjectures the leading Taylor coefficient:

$$\frac{L^{(r)}(E, 1)}{r!} = \frac{\Omega_E \cdot R_E \cdot |\mathrm{Sha}(E)| \cdot \prod c_p}{|E(\mathbb{Q})_{\text{tors}}|^2}$$

This skill orchestrates a specialized 4-agent collaborative team to explore and verify BSD invariants:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           BSD MULTI-AGENT SWARM                             │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
     ┌─────────────────────────────────┼─────────────────────────────────┐
     ▼                                 ▼                                 ▼
┌──────────────┐              ┌─────────────────┐              ┌────────────────┐
│    EUCLID    │              │   SALAMANDER    │              │     PYTHIA     │
│  Conjectural │              │    Autonomic    │              │  Topological   │
│   Reasoner   │              │    Verifier     │              │     Ledger     │
└──────┬───────┘              └────────┬────────┘              └────────┬───────┘
       │                               │                                │
       │ [Weierstrass, a_p,            │ [Hasse Bounds,                 │ [Zeckendorf,   │
       │  Euler slope, Hodges]         │  Mazur Torsion, Integrality]   │  Poincaré, H^2]│
       │                               │                                │
       └───────────────────────────────┼────────────────────────────────┘
                                       │
                                       ▼
                       ┌───────────────────────────────┐
                       │           AL HARAS            │
                       │     CMI Claim Honesty Sentry  │
                       │   (proof_claim: False seal)   │
                       └───────────────┬───────────────┘
                                       │
                                       ▼
                       ┌───────────────────────────────┐
                       │       BSDTeamReport           │
                       │   (Phi >= 0.70, CMI Valid)    │
                       └───────────────────────────────┘
```

### Team Architecture & Algorithmic Scopes

The pipeline operates as an orchestrated 4-agent software workflow implementing techniques across 10 mathematical domains:

1. **EUCLID** (Lead Conjectural Reasoner):
   - Constructs Weierstrass curve $E: y^2 = x^3 + ax + b$ with exact rational arithmetic over $\mathbb{Q}$.
   - Computes Frobenius point counting $\#E(\mathbb{F}_p) = p + 1 + \sum_{x \in \mathbb{F}_p} \left(\frac{x^3 + ax + b}{p}\right)$ via $O(p \log p)$ character summation.
   - Evaluates Euler product partials $P(X) = \prod_{p \le X, p \nmid \Delta} \frac{N_p}{p}$ and computes empirical rank slope $\alpha \approx \frac{\log P(X)}{\log \log X}$ via linear regression.
   - *Limitation note:* For small bounds ($X \le 200$), character oscillations on high-conductor curves (e.g. $y^2 = x^3 - 432x$) can yield distorted or negative empirical slopes. True rank certification requires algebraic 2-descent or Selmer groups.
   - Formulates Wilfrid Hodges model-theoretic sentence schemas over $\operatorname{Structure}(\mathbb{Q}, E_{\text{arithmetic}})$.

2. **SALAMANDER** (Autonomic Invariant Verifier & Self-Healer):
   - Verifies Hasse's Theorem: $|a_p| \le 2\sqrt{p}$ strictly at primes of good reduction ($p \nmid \Delta$).
   - Verifies Mazur's Torsion Bound: $|E(\mathbb{Q})_{\text{tors}}| \in \{1..10, 12, 16\}$ within a bounded integer search box.
   - Verifies Nagell-Lutz integrality: $x, y \in \mathbb{Z}$ and $y^2 \mid \Delta$ for non-2-torsion integer points on integral models.
   - Monitors telemetry and enforces self-healing execution integrity.

3. **PYTHIA** (Topological Memory & Zeckendorf Certifier):
   - Encodes Frobenius traces $\{|a_p|\}$ into canonical Zeckendorf non-adjacent Fibonacci index representations ($\forall i, j \in I_p: |i - j| \ge 2$) in $\mathbb{Z}[\phi]$.
   - Verifies Cassini unimodular identity $F_{n-1}F_{n+1} - F_n^2 = (-1)^n$ identically in $\mathbb{Z}$.
   - Embeds Frobenius points into Poincaré hyperbolic disk coordinates $\mathbb{D} \subset \mathbb{C}$ ($u^2 + v^2 < 1$).
   - Computes Sato-Tate distribution angle entropy and SHA-256 state integrity signature.

4. **AL HARAS** (Clay Mathematics Institute Claim Honesty Sentry):
   - Strictly enforces the Clay Mathematics Institute boundary protocol.
   - Hard invariant: `proof_claim = False`, `claim_status = "CONJECTURE_EXPLORATION"`.
   - Scans output corpus to prohibit false claims of full proof.
   - Issues cryptographically sealed attestation certificate.

---

## 2. Command-Line Workflows

### 2.1 Run Multi-Agent Team on a Target Curve

To run the full 4-agent swarm on a specific elliptic curve $y^2 = x^3 + ax + b$:

```powershell
python scripts/bsd_cli.py team --a -36 --b 0 --max-prime 300
```

Add `--json` to output structured JSON for programmatic consumption:

```powershell
python scripts/bsd_cli.py team --a -1 --b 0 --max-prime 200 --json
```

### 2.2 Sweep Canonical Benchmark Curves Across Known Ranks

To sweep standard benchmark curves across ranks 0, 1, and 2:

```powershell
python scripts/bsd_cli.py sweep --max-prime 200
```

Curves swept:
- $y^2 = x^3 - x$ (Rank 0, conductor 32)
- $y^2 = x^3 + 1$ (Rank 0, conductor 36)
- $y^2 = x^3 - 36x$ (Rank 1, conductor 576)
- $y^2 = x^3 - 4$ (Rank 1)
- $y^2 = x^3 - 432x$ (Rank 2)

---

## 3. Python API Integration via Native Capability Fabric

```python
from Intelligence.salamander import SalamanderEngine

engine = SalamanderEngine()
report, receipt = engine.execute_capability("bsd-exploration", a=-36, b=0, max_prime=200)

assert report["proof_claim"] is False
assert report["cmi_protocol_compliant"] is True
assert receipt.status == "SUCCESS"
```
