# PYTHIA Consumer Positioning — Apple-First

**Status:** working draft. Product strategy for the consumer offering built
on the φ-substrate. One page; owner review required before external use.

## Positioning statement

> **PYTHIA — computation you can check.**
> Exact mathematics running locally on your Apple device, where every result
> carries a receipt you can verify yourself. No cloud, no trust-me, no black box.

## The wedge

Differentiation is **verifiability**, not speed and not "quantum."
Zeckendorf certificates, Cassini ledgers, and exact Z[φ] arithmetic mean a
customer can prove a result is right *without trusting us*. No consumer
product offers this. Apple's customer base is pre-trained to pay for trust
and privacy — the claim lands.

## What we lead with / never lead with

| Lead | Never lead |
|---|---|
| Verifiable receipts, checked on-device | "Quantum computer" (reads as scam to press/reviewers) |
| Local-first, private, offline-capable | Mining (App Store 3.1.5(b) forbids on-device mining; trust liability) |
| Exact math, measured performance | Hashrate/speedup claims we can't bind to evidence |

Honesty is a marketing asset, not a constraint: *"we measure, we don't claim."*

## Surfaces

| Device | Product | Role | State |
|---|---|---|---|
| iPhone | Companion PWA at `/companion` (`pythia console --lan`) | Receipt wallet (localStorage), on-device JS verification at parity with the Python contract, node monitor | **built** |
| MacBook / iMac | PYTHIA Node — bundled wheel (iGPU + OVID + THESEUS) + `PYTHIA.app` | Full consumer node; MLX/Metal where available, honest CPU fallback | **built** (unsigned; signing/notarisation owner-gated) |
| Mac Studio / high-RAM Macs | PYTHIA Node (large-memory tier) | Unified memory ≥96 GiB → `pythia-node-large-memory` in census — exact-state widths discrete GPUs can't hold | **detected in census**; tier-specific productisation still open |

## Tiers

- **PYTHIA (free)** — `pythia` CLI + local console: node census, receipt
  verification, intelligence-surface status. This package.
- **PYTHIA Node** — self-contained bundle: iGPU fabric + OVID data
  organisation + THESEUS custody, one install, no cloud dependency.
- **PYTHIA Studio** — intelligence workloads (TOE/EUCLID surface) for
  researchers; server-side or on-device where it fits.

## Risks

1. **Crypto adjacency** — keep mining in the provenance story, never the headline.
2. **Quantum language** — say "exact mathematical computation" and
   "quantum-class algorithms verified on classical hardware."
3. **Performance honesty** — a Mac is a verification/intelligence node, not
   a mining rig. Say it before reviewers do.

## Evidence anchors (internal)

- Verification math: `verify.py` (Zeckendorf, Cassini, `ZECK-` certificates)
- Census honesty contract: `census.py` (detected facts only, never stubbed)
- Bundle sources: `aethel` (THESEUS), `hyba_db` (OVID), `chronos_one_igpu` (iGPU)
