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
- `theorem_proven` is a reserved proof-boundary field, always `False` in this
  suite. A successful identity check or signed pack is not a theorem, consensus
  approval, or permission to execute a privileged action.

---

## Architectural Components

1. **`hyba_mcp` (Production Package)**:
   - `hyba_mcp.server`: Model Context Protocol server exposing exact-math,
     scaling, repository-context, and governed skill tools:
     - `lucas`: Exact fast-doubling Lucas numbers ($L_n$) with Cassini witness.
     - `fibonacci`: Exact fast-doubling Fibonacci numbers ($F_n$).
     - `cassini`: Exact $L_n^2 - 5 F_n^2 = 4(-1)^n$ certificate.
     - `zeckendorf`: Canonical non-adjacent Zeckendorf representation.
     - `ladder_verify`: Complete Lucas ladder stops.
     - `ladder_capacity`: Exact envelope and capacity snapping.
     - `largest_feasible_tile`: Power-of-two work tiling under alignment.
     - `sha256d_verify`: Independent double-SHA256 evaluation against uint256 targets.
     - `discover_skills`: list governed expert capabilities.
     - `get_skill`: retrieve a skill contract, examples, and limitations.
     - `validate_inputs`: preflight a skill's argument schema.
     - `invoke_skill`: invoke through permission, budget, audit, and sandbox gates.
     - `evaluate_skill_outcome`: submit an authorized outcome for evaluation tracking.
     - `scale_intelligence`: Stateless Lucas scale selection and modeled metrics,
       requiring `Intelligence.lucas_scaler` and its dependencies.
      - `hyba_context`: find deterministic repository context for a query.
      - `hyba_verify`: verify exact phrases in repository files.
   - `hyba_mcp.client`: Session-managed client providing SHA-256 digests and
    HMAC-SHA256 authenticated evidence packs.
2. **`mcp/` & `.mcp.json`**:
   - Standard top-level server registration for local agent hosts and client interfaces.
3. **`euclid.enterprise.superintelligence_governance.MCPGateway`**:
   - Institutional gatekeeper managing agent registration, tool containment, situational access leases, and automated kill-switch integration.

---

## Running the Sovereign MCP Server

To start the production stdio server:

```bash
cd /absolute/path/to/HYBAEnterprise
python -m hyba_mcp.server
```

Install the repository and its declared dependencies first (see
[deployment checklist](docs/MCP_DEPLOYMENT.md)). The eight exact-kernel tools
remain available if the optional scaler import fails. Module loading emits a
warning on stderr and `tools/list` exposes `scale_intelligence` availability in
`_meta["hyba/status"]`; invoking it while unavailable returns an explicit error.
Install/repair dependencies and restart to restore it; there is no silent fallback.

The manifest marks `hyba-mcp` as the primary production server, `exact-kernel` as
an optional stable standalone server, and `cogito` as experimental/internal-only.
These are deployment classifications, not executed readiness certifications or
access controls. Register only the primary server in production unless separately
qualified. Manifest metadata does not automatically disable optional servers.

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

### Input contracts

`lucas`, `fibonacci`, `cassini`, and `zeckendorf` require integer `n` in
**0–10000 inclusive** (for Zeckendorf this is the integer being represented,
not an index). Strings, fractions, booleans, nulls and out-of-range values are
rejected before computation. Other tools enforce their advertised schema types,
minimums and enums too. Tool parameter errors return JSON-RPC `-32602` with the
request ID; unavailable scaler calls return `-32000`.

### `scale_intelligence` parameters and behavior

All parameters are optional; every invocation creates a **new scaler**, not
persistent session state. It does not configure a running EUCLID process.

| Parameter | Contract |
|---|---|
| `target_rung` | Integer in `10, 12, 15, 18, 20, 31`; starting rung, default `31` |
| `step_direction` | `up`, `down`, or `hold`; one ladder step, clamped at endpoints |
| `complexity` | Finite number in `[0, 1]`; values outside this interval fail closed |
| `task_type` | Free-form string, case-insensitive substring matching against the keywords below |

`up`/`down` take precedence over task adaptation; `hold` returns the starting
rung unchanged. Without a step, complexity/task matching selects the final rung
and can override `target_rung`. Complexity intervals are `[0,.15)` → 10,
`[.15,.35)` → 12, `[.35,.55)` → 15, `[.55,.75)` → 18, `[.75,.90)` → 20,
`[.90,1]` → 31. The highest keyword match wins; with both inputs, the higher
complexity/keyword rung wins. An unmatched label alone selects 31.

| Rung | Task keywords |
|---|---|
| 10 | triage, chat, ping, lookup, fast, simple, shallow |
| 12 | syntax, structure, format, schema, parse, grammar |
| 15 | coherence, semantic, alignment, integration, pullback, functor |
| 18 | abstraction, counterfactual, planning, simulation, pearl_level_3 |
| 20 | metacognition, reasoning, reflection, audit, self_healing, reconciliation |
| 31 | mining, cryptography, enterprise, proof, sovereign, maximal, blockchain, m_theory, coprime |

The response contains the selected `current_scale`, exact `lucas_number`,
`fibonacci_number` and `cassini` witness. `manifold_dimension` is the configured
representation dimension; `context_limit` and `reflection_depth` are configured
task envelope limits; `curvature_tolerance` is the envelope's modeled tolerance.
These are not measured allocations or throughput.

`pci_after`, `emergence_after`, and `consciousness_after` are modeled transforms
from fixed `0.5` baselines: respectively `1 − 0.5φ⁻ⁿ`, `1 − 0.5φ⁻²ⁿ`,
and `1 − 0.5φ⁻³ⁿ`. They are floating-point model values, not measurements of
intelligence, consciousness, accuracy, proof completion, or production readiness.
For example, `{"complexity": 0.55}` selects 18, while
`{"target_rung": 15, "step_direction": "up"}` also selects 18.

---

## Anti-Hallucination & Provenance Invariants

- Mathematical truth is verified through integer arithmetic; no floating-point approximations in the exact core (Rule 7).
- Cryptographic proof boundaries remain inviolable (SHA-256d + target).
- Evidence packs include handshake, tool arguments and outputs, plus session
  metadata, a SHA-256 digest and an HMAC-SHA256 authentication tag. Canonicalization
  and trusted-key verification are specified in [MCP security](docs/MCP_SECURITY.md).
  Packs vary with session identity and timestamp; hashing a fixed payload is deterministic.
- Session IDs use 128 bits of cryptographic randomness. Each session has a
  private 256-bit ephemeral signing key unless the operator supplies a managed key.
  Keys are never exported in packs; session close drops the client's key reference.
- The standalone stdio server and in-process client do **not** themselves enforce
  AL HARAS leases or tenant authorization. Production hosts must invoke them behind
  the governed gateway; local possession of a process or HMAC key is not authority.
- Authority remains exclusively with the HYBA / EUCLID CNS.
