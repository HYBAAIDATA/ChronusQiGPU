# Exact Kernel MCP Server

Production-ready MCP server exposing the EuclidPhiEnterprise exact mathematical substrate.

**Protocol:** MCP specification `2026-07-28` (stateless).
- No `initialize` handshake.
- Every request carries protocol version, `clientInfo`, and `clientCapabilities` in `_meta`.
- Implements `server/discover`.
- Version mismatch returns `UnsupportedProtocolVersionError` (-32022).

## Tools

- `lucas(n)` — Exact L_n + Cassini witness. `theorem_proven: false`
- `fibonacci(n)` — Exact F_n
- `cassini(n)` — Full Cassini identity check
- `zeckendorf(n)` — Non-adjacent Fibonacci representation + non-adjacency certificate
- `ladder_verify()` — Lucas scale ladder verification
- `ladder_capacity(bound)` — Snap bound to ladder index
- `largest_feasible_tile(max_size, alignment=16)` — Power-of-two dispatch tile

All responses are exact integer results with machine-checkable witnesses. No floating-point, no approximations, no simulations.

## Registration (Claude Desktop / Notion agents)

Add to your MCP client configuration (`claude_desktop_config.json` or equivalent):

```json
{
  "mcpServers": {
    "exact-kernel": {
      "command": "python",
      "args": ["-m", "mcp.exact_kernel.server"],
      "env": {
        "PYTHONPATH": "/absolute/path/to/EuclidPhiEnterprise"
      }
    }
  }
}
```

The server uses stdio JSON-RPC. Ensure the repository root is on `PYTHONPATH` so `chronus.lucas` imports resolve.

Clients speaking 2026-07-28 must include `_meta` on every request. Older clients may still work via fallback, but the server targets the current specification.

## Owner discipline

`theorem_proven` remains `False` on every response. Owner approval (`@EuclidUltimaPhi`) is still required for canonical promotion. This server is the tool boundary; it does not self-certify theorems.

## Status

Aligned with MCP 2026-07-28 (ground zero for the product). Ready for Notion agents to consume the exact kernel, finish remaining codebase certification, and begin package construction.
