# Chronusv2 implementation note — not a scientific validation

This note describes a limited repository-level implementation scope. It does not claim a novel theorem, formal verification, cryptographic soundness, production performance, or scientific peer review.

The source includes selected exact arithmetic and Lucas/PV reference workload code, along with service and experimental execution components. The default execution path is CPU reference code. The source review did not run tests, formal proofs, benchmarks, or hardware experiments. In particular, the security modules do not substantiate conformant ML-DSA/FIPS 204 or sound STARK/FRI claims.

To turn an implementation observation into a scientific claim, publish precise definitions, assumptions, derivations or proof artifacts, reproducible code and experiments, and limitations, then obtain independent review. See the [claim audit](../claim-audit.md) and [current implementation assessment](../system-update/current-state-assessment.md).