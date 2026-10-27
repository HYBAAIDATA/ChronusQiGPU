# EUCLID Capability Qualification

`euclid.capability_qualification.CapabilityQualificationRegistry` qualifies a
claim for one exact source revision, domain, and task scope. It does not infer
general readiness from success in another domain, and qualification does not
itself authorize execution.

Each claim must include conclusions, evidence references, explicit authority
limits, and a rollback plan. Evidence records distinguish theorem proofs,
empirical observations, tests, benchmarks, and decision artifacts. A theorem
supports a conclusion only when formally verified; other evidence must record
an executed passing result. Reported results remain visible but cannot satisfy
independent acceptance. A conclusion with missing, reported-only, or otherwise
unsupported evidence is returned as unavailable.

Evidence metadata must be signed by a configured trusted verifier and match the
claim's exact revision, domain, and task scope. The verifier's signature binds
the artifact digest and its recorded result, failures, and limitations. The
registry does not fetch or independently inspect artifact bytes: the trusted
verifier must check and retain those artifacts before attesting. Any recorded
failure blocks promotion, including reported failures.

By default, the acceptance set must include an independently executed passing
domain test and passing safety checks named `proxy-reward-exploitation` and
`negative-transfer`. These controls must assess whether reward-proxy
exploitation or missed negative transfer occurred; absence of their evidence
leaves the claim unavailable. A failed result blocks promotion. Other
domain-specific acceptance checks may be added to the claim.

Promotion grants only the declared exact-scope authority strings. `authorize`
requires an exact claim ID, source revision, domain, task scope, and authority.
`revoke` removes that grant, records its reason and rollback plan in the local
event list, and prevents reactivation of the same qualification scope.

This registry is an in-process qualification gate, not a durable audit system,
test runner, benchmark runner, or production execution boundary. A host must
persist its event list and retained artifacts and enforce `authorize` at the
actual capability boundary before treating a qualification as operational.
