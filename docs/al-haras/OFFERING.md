# AL HARAS / L-HRAS — Offerable Capability Positioning

> Internal positioning note. Every claim below is bounded by
> [GAP_ANALYSIS.md](GAP_ANALYSIS.md) — sell the mechanism, not a
> certification. Where a number is measured on this repo's benchmark
> harness it is marked `[measured]`; everything else is a target.

## One sharply-defined commercial wedge

**Governed, independently verifiable AI decision workflows for regulated
financial institutions.**

The first closeable use case: a decision API where every allowed call
produces a cryptographically checkable evidence pack — subscription
entitlement → governed verdict → hash-chained receipt → aethel
certificate — that an auditor can replay without trusting the operator.
The demo is `scripts/lhras_vertical_slice.py` (one command, clean
checkout, five stages, JSON evidence pack).

Everything else — swarm federation, autonomous modes, quantum-assisted
gates — is roadmap or supporting infrastructure, not the lead
proposition.

## Product boundary (three layers)

1. **Open / inspectable mathematical core** — `l_hras/` operators,
   `al_haras/` boundary, the substrate consumes (`toe`, `aethel`,
   `kellogg`), the test matrix. Auditable, benchmarkable, red-teamable.
2. **Enterprise governance + evidence platform** — the subscription
   gate, durable audit chain, evidence packs, compliance enablement
   mappings (control enablement, never legal certification), SIEM/SOAR
   emitters.
3. **Research-gated capabilities** — quantum access, autonomous
   operations, privacy compute, speculative scaling — never in the
   production-critical path.

## Deployment tiers

| Tier | Contents | Fit |
|---|---|---|
| **Gate** | AL HARAS subscription boundary + durable audit + container runbook | Regulated tenants needing entitlement enforcement + evidence |
| **Guardian** | Gate + L-HRAS conjunction (attestation, detection, topologies, fold certificates) | High-assurance decision APIs |
| **Swarm** | Guardian + quorum + federation peers + SOAR hooks | Multi-node coordinated defense |

## What the mechanism costs (measured, this host)

From `scripts/lhras_benchmark.py` (Windows dev, in-memory audit):

- Subscription gate: ~0.055 ms/request vs ~0.0002 ms for a dict policy
  lookup — a ~273× tax that is still tens of microseconds.
- L-HRAS conjunction: ~2.5 s/request — a decision-time control plane,
  not an inline filter. Selling it as per-request middleware would be a
  dishonest claim.
- Cold start (`initialize`+`stand`): ~19 ms.

These are developer-run numbers; third-party reproduction on named
hardware with fixed datasets is the remaining evidence gate.

## Analyst interrogation — honest answers

| Question | Answer |
|---|---|
| "Reference customers / ARR / channel?" | None yet — pre-validation. The vertical slice + benchmark + evidence pack are the pitch to land 2–3 design partners, not claims of them. |
| "How does a Tier-1 SOC analyst use it at 2 AM?" | Today: the evidence pack JSON and the SIEM event feed are the operator surface. A human-readable translation layer (verdict → ticket) is a required roadmap item, not built. |
| "TCO / insurance-premium ROI?" | Measurable inputs exist (decision latency, evidence-reconstruction cost). A before/after baseline needs a design partner; no ROI claim is made without it. |
| "Does fail-closed brick the business?" | Every failure refuses, but the blast radius of a refusal storm in a revenue path is documented per-component only — production outage modelling is not established. |
| "Works on our messy hybrid stack?" | The boundary is an HTTP surface + config file; it overlays rather than replaces. Real Splunk/Okta/ServiceNow receipts are not demonstrated — the emitters exist, the integrations don't. |
| "Why not Merkle trees + a standard policy engine?" | The ablation study is not established — this is a fair open challenge, not an answered one. The honest positioning is that Cassini/Zeckendorf addressing gives *self-verifying* storage invariants; whether that beats a Merkle tree for a given workload is a measured question, pending. |
| "Is the math necessary?" | Partially: the hash chain, HMAC gates, and error taxonomy are security-critical and conventional; the Fibonacci/Cassini/Zeckendorf substrate is the differentiation claim — its necessity is asserted architecturally, not proven ablation-wise. |

## What a design partner signs up for

- One workflow with a data boundary, owner, and success criterion.
- Before/after operational baselines (decision latency, evidence
  reconstruction time, audit review cost).
- A scoped pilot on one integration surface (e.g. SIEM emission), not a
  rip-and-replace.
- Their name and a success/failure write-up — the first non-developer
  evidence point.

## Honest limits (state in every sales motion)

- Software attestation only — no TPM/SGX/FIPS claims.
- Local JSONL spool is evidence, not WORM; export for retention.
- Replay protection is per-process without a shared nonce store.
- ~2.5 s/decision on this host: decision-time control plane only.
- No reference customers, independent security review, or hardware
  validation yet — the honest verdict is "conditional interest pending
  design-partner evidence and a third-party reproduction."
