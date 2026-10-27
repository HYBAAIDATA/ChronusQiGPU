# HYBA Sovereign Model Context Protocol (MCP) Suite

The MCP exposes two distinct capability tiers:

1. **Exact-math tools** — deterministic Lucas/Fibonacci, Cassini, Zeckendorf,
   SHA256d, and scale operations.
2. **Expert skills** — governed, advisory EUCLID/TOE/SALAMANDER capabilities
   with explicit contracts, permission checks, audit, and bounded execution.
   Skill output does not grant proof, consensus, or execution authority.

See [the skill reference](docs/SKILLS_REFERENCE.md), [architecture](docs/SKILLS_ARCHITECTURE.md),
[deployment guide](docs/SKILLS_DEPLOYMENT.md), and [examples](docs/SKILLS_EXAMPLES.md).

## Sovereignty & Crediting Doctrine (Mandatory)

HYBA MCP is a sovereign tool and exact-mathematical-kernel interface.
**We do NOT serve or augment narrow AI.**
- Narrow AI models obtain **zero credit, zero authority, and zero decision rights**.
- HYBA / EUCLID adapts tools, training environments, and curricula into its own deterministic cognitive and mathematical substrate.
- All actions are subject to **AL HARAS zero-trust containment**, situational access leases, and cryptographic evidence logging.
- `theorem_proven` remains `False` until verified against consensus gates.

---

## Architectural Components

1. **`hyba_mcp` (Production Package)**:
   - `hyba_mcp.server`: High-throughput Model Context Protocol server exposing verified tools:
     - `lucas`: Exact fast-doubling Lucas numbers ($L_n$) with Cassini witness.
     - `fibonacci`: Exact fast-doubling Fibonacci numbers ($F_n$).
     - `cassini`: Exact $L_n^2 - 5 F_n^2 = 4(-1)^n$ certificate.
     - `zeckendorf`: Canonical non-adjacent Zeckendorf representation.
     - `ladder_verify`: Complete Lucas ladder stops.
     - `ladder_capacity`: Exact envelope and capacity snapping.
     - `largest_feasible_tile`: Power-of-two work tiling under alignment.
     - `sha256d_verify`: Independent double-SHA256 evaluation against uint256 targets.
     - `discover_skills`, `get_skill`, `validate_inputs`, `invoke_skill`,
       `evaluate_skill_outcome`: separate governed expert-capability layer.
   - `hyba_mcp.client`: Session-managed client providing cryptographic evidence packaging and digest signing.
2. **`mcp/` & `.mcp.json`**:
   - Standard top-level server registration for local agent hosts and client interfaces.
3. **`euclid.enterprise.superintelligence_governance.MCPGateway`**:
   - Institutional gatekeeper managing agent registration, tool containment, situational access leases, and automated kill-switch integration.

---

## Running the Sovereign MCP Server

To start the production stdio server:

```bash
python -m hyba_mcp.server
```

### JSON-RPC Verification Example

```json
{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
{"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
{"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "lucas", "arguments": {"n": 15}}}
{"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "lucas", "arguments": {"n": 20}}}
```

Responses are returned with bit-exact Cassini invariants:
- $L_{15} = 1364$ (Cassini: $-4$)
- $L_{20} = 15127$ (Cassini: $+4$)

---

## Anti-Hallucination & Provenance Invariants

- Mathematical truth is verified through integer arithmetic; no floating-point approximations in the exact core (Rule 7).
- Cryptographic proof boundaries remain inviolable (SHA-256d + target).
- Evidence packs carry deterministic session digests:
  $$\text{Digest} = \text{SHA256}(\text{CanonicalJSON}(\text{EvidencePack}))$$
- Authority remains exclusively with the HYBA / EUCLID CNS.
