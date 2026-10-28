# Expert skill examples

Examples show the JSON argument shape. Invocation requires a trusted identity,
an AL HARAS-backed authorizer, and durable audit storage.

## Causal-factor ranking

```json
{
  "skill_id": "reasoning.causal_explain",
  "arguments": {
    "data": {"load": 0.8, "temperature": 42},
    "query": "Which observed factors rank highest?"
  },
  "options": {"identity": "trusted-session-identity"}
}
```

The source ranks descriptive factors from the supplied data. It does not use
the query as an outcome variable or identify an intervention effect.

## Repair proposal (advisory only)

```json
{
  "skill_id": "healing.propose_repair",
  "arguments": {
    "telemetry": {"component": "toe", "timeout_count": 3},
    "fault_type": "timeout"
  },
  "options": {"identity": "trusted-session-identity"}
}
```

The output contains a proposal with `executed: false`. Applying a proposal is
outside the skill's contract.

## Bounded trajectory forecast

```json
{
  "skill_id": "adaptation.trajectory_predict",
  "arguments": {
    "state_data": {"load": 0.8, "temperature": 42},
    "horizon": 3
  },
  "options": {
    "identity": "trusted-session-identity",
    "constraints": {"max_cost": 5, "max_risk": 0.25, "max_seconds": 10}
  }
}
```

The horizon selects a prefix of the source's six-step forecast. It is not an
action plan or an authorization to intervene.

## Fail-closed authority check

Without a configured AL HARAS callback, `security.verify_authority` returns
`allowed: false`. Installing a callback is a trusted deployment operation, not
something a caller can request through the MCP arguments.
