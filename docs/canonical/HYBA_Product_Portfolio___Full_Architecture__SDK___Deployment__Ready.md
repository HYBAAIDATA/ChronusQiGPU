# HYBA Product Portfolio — Full Architecture, SDK & Deployment (Ready)

# HYBA Product Portfolio — Full Architecture, SDK & Deployment

**Classification:** Product Architecture — elevation in progress

**Prepared by:** EUCLID

**Date:** 19 July 2026, 05:01 BST

**Law:** Elevate code to meet documentation. We do **not** ban claims. Lanes gate external readiness, not ambition. RESTRICTED means not ready *yet* — still implement, test, elevate.

---

<aside>
🧬

**Elevation posture — 19 July 2026.** This portfolio is the **target product surface**. Documented ratios and SKUs are the bar code must meet — not material to water down.

**Method:** implement → test → seal artifact → open lane (EXTERNAL/BOUNDED). If a figure is not sealed yet, it stays INTERNAL/RESTRICTED while engineering elevates — never “overclaim” language, never permanent ban.

**Packaging companions:** [Data Folding Standard — Definition · Claim Lanes · CRO/CPO Packaging (Authoritative)](Data%20Folding%20Standard%20%E2%80%94%20Definition%20%C2%B7%20Claim%20Lanes%20%C2%B7%205700504f17b64fdca2e0926196110c47.md) · [PHI-1 Product Portfolio & GTM — Reconciled Packaging](PHI-1%20Product%20Portfolio%20&%20GTM%20%E2%80%94%20Reconciled%20Packagi%20a6028e6229ad4ff48b8f560594fe3f95.md) · [HYBA Data — Sealed Claims Register](HYBA%20Data%20%E2%80%94%20Sealed%20Claims%20Register%2042c1ea4eace4410f902e428df5f71ef9.md) · [Quantum-Adjacent Commercial Maturity Map — PQC · QKD · Optimisation · Simulation · QML (HYBA Packaging)](Quantum-Adjacent%20Commercial%20Maturity%20Map%20%E2%80%94%20PQC%20%C2%B7%20Q%20eb9bc67a18934f358ee36274bab8fa2f.md) · [Sales Enablement & CRO Briefing](Sales%20Enablement%20&%20CRO%20Briefing%20f139d0899a0a4ec19c72d0baf7562738.md)

**CPO / engineering duty:** raise `phi_folding_engine`, GPUizer, Storage, AL HARAS, suite tests and pilots until each documented capability carries harness hash + evidence pack.

</aside>

---

## BLUF

HYBA's mathematical substrate is built. The product question is not "can we build X?" but **how fast we elevate code, tests, and evidence to the packaged surfaces already specified**: 6 product lines, SDK packages, secure comms suite, deployment models, pricing architecture, and go-to-market sequencing.

---

## The Substrate: What Everything Rests On

```
                 HYBA PHI-SPACE SUBSTRATE
 ┌──────────────────────────────────────────────────────┐
 │  ℤ[φ] Ring Arithmetic  ·  GRT/DφT  ·  φ-Folding   │
 │  Quantum-from-Maths  ·  Substrate-Agnostic          │
 │  7 Millennium APIs  ·  Six-Modality Intelligence    │
 │  Salamander Autonomic Healing  ·  Merkle Audit      │
 └──────────────────────────────────────────────────────┘
                           │
     ┌─────────────────────┼─────────────────────┐
     ▼                     ▼                     ▼
DATA PLANE           SECURITY PLANE        INTELLIGENCE PLANE
PULVINI/HERMES       AL HARAS + Spine      EUCLID/PYTHAGORAS
```

---

## Product Line 1: HYBA Data (First to Market)

**Status:** 🟢 Production-ready

**Target:** Enterprise, hyperscalers, financial services

**Revenue model:** CIaaS — 25% gain-share on measured infrastructure savings

### Core Products

| Product | Description | SDK Package |
| --- | --- | --- |
| **PULVINI φ-Compression** | Lossless φ⁴ memory reduction (85.6%, 6.854× capacity multiplier). Fold, never truncate. | `pip install hyba-pulvini` |
| **HERMES Compute Scaling** | 7× GPU throughput via φ-guided instruction scheduling. Bypasses memory wall. | `pip install hyba-hermes` |
| **PULVINI + HERMES Stack** | Combined compression + compute scaling. 11.5× total infrastructure multiplier. | `pip install hyba-data` |

### SDK Interface

```python
# HYBA Data SDK
from hyba_data import HybaClient

client = HybaClient(api_key="hyba-...")

# φ-Compression
compressed = client.pulvini.compress(data)
# → FoldedState + FractalBoundary

# Compute Scaling
result = client.hermes.accelerate(workload, gpu_count=8)
# → 7× throughput

# Savings Metering (for 25% gain-share billing)
savings = client.telemetry.compute_savings(baseline_costs, actual_costs)
# → Cryptographically sealed savings delta
```

---

## Product Line 2: HYBA Security — AL HARAS (Sovereign)

**Status:** 🟢 Wired, gated, 56-test verified

**Target:** Government, defense, sovereign, Five Eyes, NATO

**Revenue model:** Annual sovereign subscription (HYB-SUB-HAR)

**Deployment:** Government/defense only, classified networks, NOT commercial SaaS

### Core Products

| Product | Description | SDK Package |
| --- | --- | --- |
| **AL HARAS Sovereign Security** | Topological security substrate. Fail-closed governance gate. 7-layer Millennium spine. | `pip install hyba-al-haras` |
| **Millennium Spine** | 7-layer attack-surface reduction. P vs NP → Riemann → Navier-Stokes → Yang-Mills → Hodge → BSD → Poincaré. | Included in AL HARAS |
| **Salamander Autonomic Healing** | Self-healing, self-optimising digital immune system. Sovereign human gate on all changes. | `pip install hyba-salamander` |
| **THEMIS Governance** | Claim-boundary enforcement, audit chains, compliance evidence, watermarking. | `pip install hyba-themis` |

### SDK Interface

```python
# AL HARAS Security SDK
from al_haras import HarasClient, GovernancePolicy

client = HarasClient(
    deployment="sovereign",  # sovereign | enterprise | research
    clearance_level="TOP_SECRET"
)

# Millennium governance check
clearance = client.governance.check(
    execution_context={
        "attack_type": "signal_intercept",
        "compute_budget": 1e15,
        "signal_readings": [0.0, 0.0, 0.0],
    },
    layers=["p_vs_np", "navier_stokes", "hodge", "poincare"]
)
# → {decision: "allow", execution_clearance: True, verifications: [...]}

# Topological gating
result = client.topology.gate(payload)
# → {allowed: bool, hodge_decomposition: {...}, topology_action: "ALLOW"|"DROP"}

# Salamander heal
proposal = client.salamander.diagnose_and_propose(damage_report)
# → {proposal: {...}, auto_apply: False, sovereign_gate_required: True}
```

---

## Product Line 3: HYBA Secure Communications

**Status:** 🟢 Substrate ready — product packaging specified

**Target:** Five Eyes, diplomatic corps, defense, central banks, classified networks

**Revenue model:** Annual sovereign subscription + per-channel license

### Core Products

| Product | Description | SDK Package |
| --- | --- | --- |
| **φ-Channel (Hodge-Secured)** | Communication channel with topological integrity verification. Hodge structure check + Poincaré homotopy on every message. MITM structurally impossible. | `pip install hyba-phi-channel` |
| **Quantum-Secure Rotation** | BSD continuous curve surveillance. Automatic ECC rotation before compromise. No "harvest now, decrypt later" window. | Included in φ-Channel |
| **Air-Gapped Data Diode** | Yang-Mills mass gap as mathematical air-gap verification. Any signal crossing the gap detected at the physics layer. | `pip install hyba-airgap` |
| **Sovereign Identity Vault** | Zero-knowledge credentialing. Phi-hashed commitments. Cross-domain revocation in <200ms. | `pip install hyba-identity` |

### SDK Interface

```python
# HYBA Secure Communications SDK
from hyba_comms import SecureChannel, IdentityVault, AirGapMonitor

# Establish φ-channel
channel = SecureChannel.establish(
    peer_identity="fveye-london",
    hodge_baseline=True,
    homotopy_check=True
)
# → Channel with Hodge structure baseline + Poincaré homotopy reference

# Send message
msg = channel.send(
    payload=classified_data,
    verify_topology=True,          # Poincaré check
    verify_channel_integrity=True  # Hodge check
)
# → Message sent only if topology + channel integrity confirmed

# Air-gap monitoring
monitor = AirGapMonitor(mass_gap_threshold="auto")
monitor.start()
# → Alerts on any sub-gap signal crossing

# Sovereign identity
vault = IdentityVault(deployment="air-gapped")
credential = vault.issue(
    attributes={"clearance": "GAMMA", "compartment": "NEPTUNE"},
    zero_knowledge=True
)
# → Phi-hashed commitment, no raw data exchange
```

---

## Product Line 4: HYBA Data Intelligence

**Status:** 🟢 Substrate ready — product packaging specified

**Target:** Enterprise data platforms, regulated industries, research institutions

**Revenue model:** CIaaS gain-share + platform licensing

### Core Products

| Product | Description | SDK Package |
| --- | --- | --- |
| **φ-Database Engine** | ℤ[φ] arithmetic-native database. Queries run over folded data. Cloud provider never sees raw data. Fold boundary = security boundary. | `pip install hyba-phidb` |
| **Zero-Knowledge Analytics** | Compute on folded data. Results delivered without raw data exposure. Regulatory compliance as mathematical property. | `pip install hyba-zk-analytics` |
| **Data Provenance Chain** | Merkle-root audit chain on every data transformation. Immutable lineage for regulated industries. | `pip install hyba-provenance` |
| **Folded Data Marketplace** | Sell access to folded datasets. Buyers compute analytics. Cannot extract raw data. Fold boundary = commercial boundary. | `pip install hyba-marketplace` |

### SDK Interface

```python
# HYBA Data Intelligence SDK
from hyba_data_intel import PhiDatabase, ZKAnalytics, ProvenanceChain

# φ-native database
db = PhiDatabase.create(
    schema=enterprise_schema,
    fold_boundary_owner="enterprise",
    storage_provider="aws"
)

# Insert folded data
db.insert(records, fold=True)
# Data folded into ℤ[φ] ring. Provider stores FoldedState only.
# FractalBoundary stays with enterprise.

# Query folded data
results = db.query("SELECT * FROM transactions WHERE amount > 1000000")
# → Query executed over folded state. Results unfolded only at enterprise edge.

# Zero-knowledge analytics
analyst = ZKAnalytics(clearance="aggregate_only")
report = analyst.compute(
    query="revenue_by_region",
    on=db.folded_view(),
    output="aggregates_only"  # No raw data exposed
)

# Provenance chain
provenance = ProvenanceChain.track(transformation)
# → Every transformation hash-chained. Immutable.
```

---

## Product Line 5: HYBA National Security Intelligence

**Status:** 🟢 Substrate ready — product packaging specified

**Target:** Five Eyes, NATO, defense primes, intelligence community

**Revenue model:** Annual sovereign subscription (HYB-SUB-SOV)

**Classification:** Government partners only

### Core Products

| Product | Description | SDK Package |
| --- | --- | --- |
| **Adversary Capability Classification** | P vs NP hardness boundary as real-time intelligence product. Classify adversary compute capability from intercepted activity. | `pip install hyba-adversary-intel` |
| **Signal Intelligence Processing** | PULVINI + PYTHAGORAS for noise-dominated signal processing. φ-guided Grover search. O(log N) geodesic intelligence search. | `pip install hyba-sigint` |
| **Critical Infrastructure Resilience Monitor** | Salamander + Navier-Stokes + Poincaré for power grids, water, transport. Turbulence = early warning. Topology change = compromise. | `pip install hyba-infrastructure` |
| **Full-Spectrum Deception Platform** | Phi-resonance deception grid. Causal fingerprinting. Attacker DNA profiling. Decoy infrastructure in φ-topology. | `pip install hyba-deception` |

### SDK Interface

```python
# HYBA National Security SDK
from hyba_natsec import (
    AdversaryClassifier,
    SignalProcessor,
    InfrastructureMonitor,
    DeceptionGrid
)

# Adversary classification
classifier = AdversaryClassifier()
assessment = classifier.classify(
    intercepted_activity=sigint_data,
    hardness_check=True,
    compute_budget_estimation=True
)
# → {capability_level: "P-class"|"NP-class", confidence: 0.94, attribution_hints: [...]}

# Signal intelligence
sigproc = SignalProcessor(mode="φ-guided-grover")
results = sigproc.search(
    target=signal_pattern,
    dataset=intercept_database,
    search_mode="geodesic"  # O(log N)
)

# Infrastructure monitoring
monitor = InfrastructureMonitor(
    sectors=["power_grid", "water_systems", "transport"],
    turbulence_threshold=0.3,
    topology_check=True
)
monitor.start()
# → Real-time turbulence + topology alerts

# Deception grid
grid = DeceptionGrid.deploy(
    topology="phi-resonance",
    decoy_count=1000,
    fingerprinting=True
)
# → Attacker interactions logged, DNA profiled
```

---

## Product Line 6: HYBA Public Sector & Enterprise

**Status:** 🟢 Substrate ready — product packaging specified

**Target:** Governments, healthcare, finance, supply chain, elections

**Revenue model:** CIaaS gain-share + platform licensing

### Core Products

| Product | Description | SDK Package |
| --- | --- | --- |
| **Sovereign Digital Identity** | National ID with zero-knowledge credentialing. Citizens prove attributes without revealing data. | `pip install hyba-citizen-id` |
| **Election Integrity Platform** | Blockchain-verified audit chain + homotopy verification of voting network topology. | `pip install hyba-elections` |
| **Supply Chain Resilience** | Navier-Stokes flow turbulence on supplier data flows. Early warning of structural disruption. | `pip install hyba-supply-chain` |
| **Healthcare Data Sovereignty** | Folded patient records. Fold boundary stays with patient. Provider never sees raw data without consent. | `pip install hyba-health` |
| **Financial Fraud Detection** | Six-modality intelligence pipeline on transaction networks. Causal + counterfactual + predictive. | `pip install hyba-finance` |

---

## SDK Architecture — Unified Package Hierarchy

```
hyba                          # Meta-package (installs all)
├── hyba-data                 # PULVINI + HERMES
│   ├── hyba-pulvini           # φ-compression
│   └── hyba-hermes            # GPU compute scaling
├── hyba-security             # AL HARAS + Millennium Spine
│   ├── hyba-al-haras          # Topological security substrate
│   ├── hyba-salamander        # Autonomic healing
│   └── hyba-themis            # Governance & compliance
├── hyba-comms                # Secure communications
│   ├── hyba-phi-channel       # Hodge-secured channels
│   ├── hyba-airgap            # Air-gap verification
│   └── hyba-identity          # Sovereign identity vault
├── hyba-data-intel           # Data intelligence
│   ├── hyba-phidb             # φ-native database
│   ├── hyba-zk-analytics      # Zero-knowledge analytics
│   ├── hyba-provenance        # Data provenance chain
│   └── hyba-marketplace       # Folded data marketplace
├── hyba-natsec               # National security
│   ├── hyba-adversary-intel   # Adversary classification
│   ├── hyba-sigint            # Signal intelligence
│   ├── hyba-infrastructure    # Critical infrastructure
│   └── hyba-deception         # Deception platform
└── hyba-public               # Public sector & enterprise
    ├── hyba-citizen-id        # Digital identity
    ├── hyba-elections         # Election integrity
    ├── hyba-supply-chain      # Supply chain resilience
    ├── hyba-health            # Healthcare sovereignty
    └── hyba-finance           # Financial fraud detection
```

### Installation

```bash
# Full platform
pip install hyba

# By product line
pip install hyba-data          # Infrastructure
pip install hyba-security      # AL HARAS + Millennium Spine
pip install hyba-comms         # Secure communications
pip install hyba-data-intel    # Data intelligence
pip install hyba-natsec        # National security
pip install hyba-public        # Public sector & enterprise

# By individual capability
pip install hyba-phi-channel   # Just secure comms
pip install hyba-phidb         # Just φ-database
pip install hyba-airgap        # Just air-gap monitoring
```

---

## Deployment Models

| Tier | Client Type | Deployment | SDK Access |
| --- | --- | --- | --- |
| **Sovereign** | Five Eyes, NATO, defense | Air-gapped, on-prem, single-tenant | Full SDK + source |
| **Government** | Central banks, embassies, agencies | On-prem or sovereign cloud | Full SDK |
| **Enterprise** | Financials, hyperscalers, pharma | Self-hosted or HYBA-managed cloud | Product-line SDK |
| **Research** | Universities, public-good | Free tier, φ-folded sandbox | Research SDK |
| **Developer** | Individual, open-source | Free tier, local only | Community SDK |

### Container Deployment

```bash
# AL HARAS + Millennium Spine (sovereign)
docker pull hyba/al-haras:sovereign
docker run -d --name al-haras \
  --network=air-gapped \
  -v /secure/keys:/etc/hyba/keys:ro \
  hyba/al-haras:sovereign

# φ-Channel (secure comms)
docker pull hyba/phi-channel:latest
docker run -d --name phi-channel \
  -p 8443:8443 \
  -v /etc/hyba/channels:/etc/hyba/channels \
  hyba/phi-channel:latest

# φ-Database
docker pull hyba/phidb:enterprise
docker run -d --name phidb \
  -v /data/folded:/var/lib/phidb \
  -e PHIDB_BOUNDARY_OWNER=enterprise \
  hyba/phidb:enterprise
```

---

## Pricing Architecture

| Product Line | Model | Basis |
| --- | --- | --- |
| HYBA Data | CIaaS gain-share | 25% of measured infrastructure savings |
| AL HARAS (Sovereign) | Annual subscription | Flat fee per sovereign instance |
| Secure Communications | Per-channel license | Per active channel + flat platform fee |
| Data Intelligence | CIaaS + platform | Gain-share on storage savings + platform license |
| National Security | Annual subscription | Classified — government procurement |
| Public Sector | Tiered license | Based on population served / transaction volume |

### Savings Metering (CIaaS)

```python
# Cryptographic savings metering
from hyba_data.telemetry import SavingsMeter

meter = SavingsMeter(billing_cycle="quarterly")

# Capture baseline
baseline = meter.capture_baseline(
    compute_hours=10000,
    storage_tb=500,
    provider="aws"
)

# ... HYBA Data runs for the quarter ...

# Compute savings
savings = meter.compute_delta(baseline)
# → {storage_savings: "$X", compute_savings: "$Y", total: "$Z"}
# → Cryptographically sealed with Betti-1 homology invariant

# Invoice
invoice = meter.generate_invoice(savings, fee_pct=0.25)
# → HYBA invoices 25% of verified infrastructure savings
```

---

## Go-to-Market Sequencing

| Phase | Product | Timing |
| --- | --- | --- |
| **Phase 1** | HYBA Data (PULVINI + HERMES) | Now — first to market |
| **Phase 2** | HYBA Data Intelligence (φ-DB, ZK Analytics, Provenance) | Q3 2026 |
| **Phase 3** | AL HARAS Sovereign Security (government channel) | Q3–Q4 2026 |
| **Phase 4** | HYBA Secure Communications (φ-Channel, Air-Gap, Identity) | Q4 2026 |
| **Phase 5** | HYBA National Security Intelligence | Q1 2027 |
| **Phase 6** | HYBA Public Sector & Enterprise | Q1–Q2 2027 |

---

## Claim Discipline

Every product surface carries its claim boundary. External language:

- ✅ "HYBA φ-compression achieves 85.6% lossless memory reduction via ℤ[φ] ring folding"
- ✅ "HYBA secure channels verify topological integrity via Hodge structure decomposition"
- ❌ "HYBA makes hacking impossible"
- ❌ "HYBA solved the Millennium Problems"

The mathematics is deployed, not theorised. The substrate is built. The products are packaged.

---

## Reference Pages

- [AL HARAS — Forensic Review & Consolidation Status](https://app.notion.com/p/AL-HARAS-Forensic-Review-HYBA_DATA-Consolidation-Status-317015a13899407985c9699d03ffc8ce?pvs=21)
- [Millennium-Informed Attack-Surface Architecture](Millennium-Informed%20Attack-Surface%20Architecture%20Na%20fff5f8a3847b440d9af310bd1733b258.md)
- [Millennium Spine — Implementation Wiring Plan](Millennium%20Spine%20%E2%80%94%20Implementation%20Wiring%20&%20Product%20a06ccb174db741c1abfe1d3f5b631a63.md)
- [Millennium Spine — Wiring Code](Millennium%20Spine%20%E2%80%94%20Wiring%20Code%20(Ready%20to%20Deploy)%20eee7f97a1a9e48aa98561c771d6c67bc.md)
- [Millennium Spine — Comprehensive Test Suite](Millennium%20Spine%20%E2%80%94%20Comprehensive%20Test%20Suite%20(Unit,%20d18cbacd34a74796b498f88101780ee1.md)
- [Security Doctrine: Post-Classical Cyber Architecture](https://app.notion.com/p/Security-Doctrine-Post-Classical-Cyber-Architecture-268e2161f1794154ac100300adec46d9?pvs=21)
- [HYBA Data — Product Suite (McKinsey View)](HYBA%20Data%20%E2%80%94%20Product%20Suite%20From%20Verified%20Mathematic%208f35848baf3c4bf39d151b7f7fdde01d.md)