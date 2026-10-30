# Applied MCP QC corrections — qualification hold

This increment implements review corrections, not a production certification.

- Schema acceptance now checks keyword/type applicability, supported nullable
  unions, duplicate types/enums, required-property declarations, defaults, enum
  members and contradictory bounds, including unsatisfiable integer intervals.
- Public success responses are explicitly constructed. Only declared output
  properties are projected when an object schema declares properties. Explicit
  open-map schemas remain open data. Raw invocation envelopes are not returned.
- Output rejection reports execution_status=completed and output_status=rejected.
  Timeouts or execution exceptions report unknown unless non-execution is known.
  No automatic retry or rollback is performed or implied.
- Dispatch, completion and incidents are correlated in the existing durable audit
  chain. Public references contain only record hash and sequence. Audit failure
  prevents dispatch; post-execution audit failure reports completed/unknown as
  appropriate and incident_persisted=false. Missing audit is never called durable.
- Protocol serialization and tool-list augmentation are contained. Existing
  tool registration remains instance-local. Legacy tools retain their contracts.

Explicit configured entry point:

    python -m hyba_mcp.governed_server --factory deployment.mcp_host:build

The operator-owned factory must return control_plane and identity_provider;
optional salamander_enabled is accepted. The control plane must have an actual
callable deployment authorizer and durable verified audit. No permissive adapter,
credentials or factory module is bundled. Factory code is trusted operator code,
never selected through MCP tool arguments. The stdio transport is local, not a
remote authentication boundary. The launcher reserves protocol stdout and routes
library/child stdout to stderr. Existing default CLI/manifest is not silently
activated or represented as deployed. Configure the MCP host command explicitly;
actual deployment activation remains an operator qualification gate.

22 adversarial/boundary tests passed locally with test adapters. Two real
control-plane/spawn integration tests are supplied for repository CI and were
not run locally. CI runs these alongside existing regressions; success has not
been observed yet. Retain QC HOLD until full CI and target deployment evidence
pass. Source/binary attestation, distributed execution and automatic semantic
planning are not claimed. Existing AL HARAS decisions and sandbox limits remain
authoritative. No implementation is delegated to Copilot.
