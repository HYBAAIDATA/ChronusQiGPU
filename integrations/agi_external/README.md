# External AGI Surface

## What is offered externally

Contract-bound capabilities available to commercial clients through the LLM gateway:

- `llm_gateway` — full commercial pipeline (AL HARAS → PYTHIA → EUCLID + SALAMANDER)
- `reasoning` — client-context reasoning, results sanitized
- `retrieval` — PYTHIA-backed retrieval under security gate
- `structured_output` — schema-validated extraction

Every call is ledgered. Every response is gated. No self-modification path is exposed.

## What is withheld (internal ASI)

The following remain internal and are never imported by this package:

- `Intelligence/asi/` — full ASI substrate
- Regenerative runtime self-modification and polarity-unrestricted cycles
- Direct access to the entanglement store write path from external callers
- Autonomous learning loops that alter core invariants

## Boundary rule

External AGI may call the commercial gateway. It may not import from `Intelligence/asi` or invoke any self-modifying cycle. The import graph enforces the split.

## Usage

```python
from integrations.agi_external import ExternalAGI

agi = ExternalAGI()
result = agi.reason("Summarise the quarterly risk report.", client_id="client-42")
print(result["status"], result["security"])
```
