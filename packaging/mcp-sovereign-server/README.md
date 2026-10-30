# hyba-mcp-sovereign-server

**HYBA Sovereign Model Context Protocol — exact-kernel MCP server, evidence-pack
client, and gateway boundary.**

## Scope

This distribution ships:

- **`hyba_mcp.server`** — Production MCP JSON-RPC 2.0 server exposing exact
  Lucas/Fibonacci/Cassini/Zeckendorf tools, ladder verification, SHA-256d
  evaluation, and intelligence scaling.
- **`hyba_mcp.client`** — Session-managed client with cryptographic evidence
  packaging: `Digest = SHA256(CanonicalJSON(EvidencePack))`.
- **Gateway boundary** — The `MCPGateway` in
  `euclid.enterprise.superintelligence_governance` manages agent registration,
  tool containment, situational AL HARAS leases, and automated kill-switch
  integration. The gateway is *not* vendored into this wheel; it remains a
  source-only integration surface.

## What this wheel does NOT contain

- `aethel`, `hyba_db`, `kellogg`, `toe`, `euclid`, `chronus`,
  `turing_universal_quantum_computer`, `salamander`, `al_haras`,
  `chronos_one_igpu`, `mla1517` — these remain separate products.
- No `hyba-*` runtime dependencies are declared. The MCP server imports
  `chronus.lucas` at runtime from the monorepo source tree; the published
  wheel is self-contained for its own package boundary.

## Evidence-pack digest

All evidence packs carry deterministic session digests:

    Digest = SHA256(CanonicalJSON(EvidencePack))

## Smoke reference values

| Tool call | Expected |
|---|---|
| `lucas n=15` | L₁₅ = 1364, Cassini = −4 |
| `lucas n=20` | L₂₀ = 15127, Cassini = +4 |

## Registry qualification

This scaffold enables local build, verification and smoke testing.
Registry qualification (TestPyPI → PyPI OIDC trusted publishing) and upload
remain a **future frozen-RC dispatch**. No upload, registry ownership or
production readiness is asserted by this scaffold.
