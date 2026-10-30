# Turing Workflow 01 — VQC Capability & Algorithm Admission

<aside>

Required before a new Turing capability, algorithm family, circuit class, or execution mode is called production-supported.

</aside>

## Entry criteria

Named capability; formal input/output semantics; supported circuit/state domain; exactness/tolerance contract; independently checkable reference; declared representation/backend set; reproducible manifest.

## Promotion ladder

1. FORMALLY_SPECIFIED
2. REFERENCE_VERIFIED
3. PROPERTY_VERIFIED
4. DIFFERENTIAL_VERIFIED
5. REPRESENTATION_CONFORMANT
6. BACKEND_CONFORMANT
7. FAILURE_DOMAIN_VERIFIED
8. REPLAY_VERIFIED
9. OWNER_APPROVED where material
10. PRODUCTION_ADMITTED

## Required evidence

Known-answer tests; invariants; independent differential reference; unsupported-domain fail-closed tests; measurement/result verification; replay; resource bounds; negative tests; benchmark evidence where a performance claim exists.

## Rule

An imported class, passing unit test, or successful dispatch does not make a VQC capability production-supported.