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

## JSON inputs

Pass `problem` as a JSON object containing TOE `Problem.content()` fields and an
optional `domain` label (default: `cogito`). Nested structures, operators,
objectives and constraints use the canonical TOE content format. Capability
parameters go in `args`, such as `{"action": {"x": 1}}` for `intervene`.

A minimal call is `{"name": "represent", "arguments": {"problem": {}}}`.
For `revise`, pass `problem: {"episode_sha256": "<digest from run>"}` and
`args: {"observed": ...}`; learning remains bound to an episode previously
solved by this server's tenant.

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
