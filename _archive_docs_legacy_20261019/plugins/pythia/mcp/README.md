# Pythia Cognitive OS — MCP package

MCP is the transport interface. It is not the intelligence.

## Contract

- Session start records mandatory skills and a context snapshot.
- Evidence verification requires a digest. Boolean-only evidence is rejected.
- Completion is refused unless context is loaded, evidence is retrieved, verification is executed, and tests pass.
- Owner approval overrides interpretation and is required for canonical writes.
- Unknown equals unavailable.
- No secret leakage. Tokens live in the environment only.

## Skills

The master-coder skill is mandatory:
- Context grounding
- Plan before patch
- Smallest credible change
- TDD
- Verification before claim
- Boundary awareness
- Provenance and auditability
- Anti-hallucination

## Architecture

Pythia is the reasoning and evidence layer.  
A bespoke Notion agent is the memory and canonical knowledge layer.  
MCP is the transport only.  
Intelligence remains inside the repository.
