# HYBA deployment profiles and acceptance gates

Executable implementation: `hyba_profiles`.

Profiles are `developer`, `edge`, `enterprise`, `sovereign` (`government` alias), and `hyperscaler`. Each profile declares dominant tiers, required/optional/prohibited modules, identity/network controls, and external assessments. A profile name never elevates assurance: every required module needs source and executed-test evidence, and production authorization remains external.

Gate results are `ACCEPTED`, `CONDITIONALLY_ACCEPTED`, `REJECTED`, `NOT_EXECUTED`, or `EXTERNAL_ASSESSMENT_REQUIRED`. Current repository capability must be supplied as `ModuleEvidence`; the compiler never invents it.

The compiler emits a blueprint, HMAC-SHA256 assembly lock, threat list, compliance crosswalk, resource policy, gate report, blockers and external-assessment requirements. HMAC is the reference signing boundary; sovereign deployments must replace it with an approved asymmetric or hardware-backed signer.
