# Hybrid falsification report

No statistically significant difference was measured between Lucas-weighted traversal and sequential/even baselines on the positive-control target (all 95% CIs contain zero). On the measured corpus, the traversal ordering did not change nonces-to-first-share. That is the honest outcome.

- harness_trustworthy: True (negative-control CIs contain zero; the instrument is not measuring artifacts)
- negative control lucas − gpu_only CI: [0.0, 0.0]
- positive control lucas − gpu_only CI: [0.0, 0.0]
- corpus: negative=DETERMINISTIC SYNTHETIC (sha256-derived, fixed seed) positive=DETERMINISTIC SYNTHETIC (sha256-derived, fixed seed)

Method: paired per-header winner probe index (position in logical
traversal order), bootstrap 95% CI. Physical hashes executed are
reported separately in hybrid_benchmark.md.
Every dispatched window was attested; absent ASIC channels were
recorded as attestation gaps, not simulated.
