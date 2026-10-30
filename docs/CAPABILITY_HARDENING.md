# Capability contract and error hardening

Embed CapabilityMCPServer with the existing trusted host constructor arguments.
The implementation now composes the base server without modifying its global
tool registry. The existing CLI and manifest remain unchanged.

New tools: capability_contract(skill_id), and capability_invoke(skill_id,
arguments, options?). Invocation forwards to the existing invoke_skill path,
retaining trusted identity, authorization, durable audit and sandbox gates.
Strict guards validate inputs and successful outputs. Error responses contain
stable codes, safe fixed messages, retryable=false and random correlation IDs;
raw source exceptions are not returned through the new tools. No automatic
retry is performed. Legacy tools retain their existing behavior. Correlation
IDs are response incident identifiers; a persistent incident lookup is not
implemented by this increment.

Validation supports an explicit restricted schema subset: primitive/object/array
types, properties, required keys, boolean additionalProperties, items, enums,
numeric bounds and length/item bounds. Unsupported keywords fail closed. Enum
equality uses canonical JSON representation, intentionally stricter than full
JSON Schema numeric equivalence. Inputs and results are bounded to 256 KiB,
depth 20 and 20000 JSON values. Definitions include contract/error versions,
source reference, schemas, limitations, authority boundaries, static estimated
cost units and a digest. Digests do not attest executable source or binaries.

Run python -m pytest tests/test_production_contracts.py -q. Thirteen isolated
validation tests passed during authoring. Full repository, protocol, real-skill
and deployment qualification remain required; this is not production certification.
This increment does not push or recreate the earlier execution-runtime bundle,
provide a durable job scheduler, or claim automatic semantic goal planning.
