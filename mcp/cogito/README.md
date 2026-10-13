# Cogito MCP — Twelve Capabilities

MCP 2026-07-28 server exposing the EUCLID/TOE capability surface.

## Capabilities

represent · model · identify · intervene · counterfactual · evaluate_futures · uncertainty · plan · request_information · explain · revise · run

Every tool result is an envelope:

```json
{
  "capability": "...",
  "truth_class": "ACT" | "REFUSED" | "ACQUIRE_EVIDENCE",
  "result": { ... },
  "evidence": { "capability": "...", "problem_digest": "...", "result_digest": "..." },
  "theorem_proven": false
}
```

Agents inherit the honesty. Flattening is disallowed.

## Registration

```json
{
  "mcpServers": {
    "cogito": {
      "command": "python",
      "args": ["-m", "mcp.cogito.server"],
      "env": { "PYTHONPATH": "/path/to/EuclidPhiEnterprise" }
    }
  }
}
```

theorem_proven remains False.
