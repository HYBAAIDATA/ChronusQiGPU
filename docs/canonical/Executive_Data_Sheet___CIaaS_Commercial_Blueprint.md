# Executive Data Sheet — CIaaS Commercial Blueprint

# CIaaS Commercial Blueprint

## BLUF

**Computational Intelligence as a Service (CIaaS)** replaces the friction of traditional enterprise SaaS integration with an immediate, self-verifying, value-shared utility model. The customer deploys the SDK or sidecar, experiences immediate computational acceleration, and is billed exclusively based on cryptographically verified capacity savings. 

## The Commercial Mechanics

### 1. Zero-Knowledge Hermitian Telemetry

Sovereign entities and enterprise clients (such as defense agencies or tier-1 banks) cannot permit telemetry agents to transmit raw usage statistics off-premise. 

- **The Solution:** The local HYBA controller signs hardware allocation metrics ($M_{raw}$ vs $M_{active}$) with the topological invariant ($\beta_1$). Only the signed proof of the capacity differential ($\Delta C$) and the compute time differential ($\Delta T$) are securely transmitted.
- **Result:** A mathematically sound, Zero-Knowledge audit log that verifies savings without exposing the underlying data payload.

### 2. The 25% Value-Share Billing Equation

HYBA does not charge arbitrary subscription seats. We price based on the physics we solve, scaled by the capital we generate.

The monthly invoice consists of:

1. **The Base Access Fee:** A tiered flat rate gating access to the infrastructure (ranging from Pay-As-You-Go for SMBs to $10M+ for Hyperscaler core integration).
2. **The Physics Royalty (25% of Savings):** Calculated from the verified reduction in memory footprint (PULVINI) and compute time (HERMES) against standard market rates.

$\text{Total Invoice} = \text{Base Access Fee} + 0.25 \times (\text{Memory Savings} + \text{Compute Savings})$

## Frictionless Onboarding Tiers

1. **Client SDK (Edge Devices / Researchers):** A direct `pip install` wrapper for PyTorch/JAX datasets utilizing Apple Metal and ARM NEON registers. Time to value: **5 minutes**.
2. **Enterprise API & Sidecars (Hyperscalers):** A Kubernetes sidecar or bare-metal Linux kernel driver (`/dev/al_haras`) intercepting traffic with zero database schema changes. Time to value: **1 hour**.
3. **Sovereign Substrate (Governments):** Air-gapped delivery verified via local JasperGold SVA execution, bound to Hardware Security Modules (HSMs).
4. **Model Context Protocol (AI Agents):** Secured LLM query routing using the `al-haras-mcp-server` to provide topological context retrieval without prompt injection risk.