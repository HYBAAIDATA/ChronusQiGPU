# Hybrid GPU/ASIC Unified-Theory Integration

## Status and evidence boundary

This document is the corrected executable architecture derived from the ASIC pseudocode review. It is a specification with open engineering questions, not a fabricated chip claim or a proof of physical advantage.

- **Executable now:** GPU/OpenCL or explicit CPU fallback, deterministic nonce partitioning, replayable ordering advice, host SHA-256d re-verification, and dispatch attestation.
- **Executable only when probed:** network/serial/PCIe ASIC channels supported by the solver contract.
- **Future physical work:** RTL, synthesis, place-and-route, timing closure, thermal validation, die attestation, and silicon measurements.
- **Never inferred:** PDK area, power, timing, hashrate, or energy efficiency.

## Unified theory role

`GoldenUnifiedTheory` is the shared representation and evidence-arbitration foundation for TOE, analytics, ML/BI, and the hybrid mining planner. It binds observations to a versioned theory digest and admits or rejects domain lenses explicitly.

In mining, the theory is deliberately weaker than consensus:

1. It may rank an existing set of certified, disjoint nonce windows.
2. It must return an exact permutation—no nonce may be added, removed, or mutated.
3. It cannot change the header, target, job identity, capability result, or validity predicate.
4. Every ordering decision has replay evidence containing the model, job, input order, and output order digests.
5. SHA-256d and the protocol target remain the only local validity authority; the pool remains the acceptance authority.

Enable the experimental ordering adapter with:

```bash
PYTHIA_UNIFIED_THEORY_HYBRID=1
```

It is disabled by default. Enabling it does not imply a performance advantage; that must be measured against identity, random, and established deterministic controls.

## Correct Bitcoin SHA-256d datapath

An 80-byte Bitcoin header requires three SHA-256 compression calls:

1. First SHA-256, block 1: fixed 64-byte header prefix, precomputed once per job.
2. First SHA-256, block 2: remaining header bytes including the nonce plus padding.
3. Second SHA-256, block 3: the first digest plus padding.

Therefore, after the job midstate is prepared, each nonce requires two variable compression calls. A hybrid ASIC profile that reports any other count is rejected.

The design exploration supports 2, 4, 8, 16, 32, or 64 rounds per stage. Four rounds per stage is the default exploration point. A fully unrolled 64-round pipeline is not declared canonical and must compete on measured area, frequency, power, and thermal behavior.

Message-schedule sharing is a required physical-design study: fixed job data should be computed once and broadcast where synthesis and timing evidence show a net benefit.

## Runtime pseudocode

```text
BIND():
    gpu  := probe_local_opencl_or_explicit_cpu()
    asic := probe_physical_asic_channels()
    remotes := probe_configured_remote_agents()

    devices := supported_unique(gpu, asic, remotes)
    attest_every_exclusion_and_reason()
    if devices is empty: fail_closed()

    ranker := disabled
    if PYTHIA_UNIFIED_THEORY_HYBRID is enabled:
        ranker := GoldenUnifiedWindowRanker(theory_digest)

    return HybridCoordinator(devices, ranker)

RUN(job, nonce_interval):
    require(len(job.header) == 80)
    require(len(job.target) == 32)
    prepare_job_midstate_on_each_device(job)

    windows, certificate := partition_disjoint_total_coverage(
        nonce_interval,
        devices,
        measured_device_throughput,
    )
    require(certificate.verify())

    if ranker is enabled:
        ranked, evidence := ranker.permute_only(job, windows)
        require(exact_permutation(ranked, windows))
        attest(evidence)
        windows := ranked

    dispatch_windows_concurrently(windows)
    while work_is_live:
        candidate := poll_devices()
        if candidate exists:
            require(host_sha256d(candidate.header, candidate.nonce) == candidate.digest)
            require(candidate.digest meets job.target)
            cancel_losers(reason="peer_won")
            return verified(candidate)

    require(all_executed_counts_are_measured())
    return exhausted_without_share
```

## GPU and ASIC separation

The GPU build and ASIC build remain separable:

- **GPU build:** reference executor, functional emulator, profiler, benchmark baseline, and operational fallback.
- **ASIC build:** fixed-function SHA-256d executor exposed only after a real capability probe. A configured endpoint is not evidence that hardware exists.
- **Hybrid build:** partitions disjoint work across the devices that actually joined. It does not relabel CPU or GPU execution as ASIC work.

Every candidate returned by any device is rehashed by the host. A channel error, timeout, unsupported feature, partial exhaustion, invalid attestation, or failed host verification is a failure—not completed coverage.

## Physical ASIC requirements

A future ASIC implementation must provide evidence for:

- a job-level block-1 midstate and schedule-sharing strategy;
- parameterized rounds-per-stage selected by synthesis and measurement;
- monotonic executed-hash counters and explicit partial-exhaustion reporting;
- junction-temperature, voltage, frequency, throttling, and fault telemetry;
- nonce-lease recovery when a device disappears mid-window;
- signed die identity with provision, rotation, revocation, and replay protection;
- host-side signature, work identity, nonce range, digest, and target checks;
- RTL simulation, formal properties, synthesis reports, timing closure, physical verification, and silicon characterization.

Attestation strengthens device provenance but never replaces consensus verification.

## Failure and recovery rules

- **Hard device failure:** cancel or orphan its lease, record uncovered work, and reissue only through a new certified partition.
- **Invalid shares:** quarantine the device; do not submit its candidate.
- **Thermal throttle:** reduce measured scheduling weight; never report nominal hashrate as executed work.
- **Attestation failure:** quarantine the identity and reject all associated candidates.
- **Coordinator restart:** restore only hash-bound checkpoints; reconstruct live work from the current Stratum job.
- **Stale job:** cancel all old-epoch handles and reject late candidates.

## Measurement gates

Promotion requires equal-budget A/B testing across at least:

1. identity window order;
2. unified-theory order;
3. random-order control;
4. the current deterministic production order.

Report executed hashes, wall time, accepted shares, reject/stale rate, energy where measured, temperature, device identity, software/RTL revision, and confidence intervals. A lower candidate index is an ordering result, not proof of reduced cryptographic complexity.

## Build gates

1. **Software correctness:** unit, property, replay, and consensus-vector tests pass.
2. **GPU reference:** OpenCL and CPU reference outputs agree on every test vector.
3. **RTL equivalence:** RTL matches the software model for fixed and randomized headers.
4. **Physical feasibility:** synthesis and place-and-route close against a named PDK and constraints.
5. **Thermal/reliability:** sustained operation remains within declared limits.
6. **Protocol integration:** local Stratum/regtest harness verifies notify, job change, submit, stale, reject, reconnect, and recovery behavior.
7. **Comparative advantage:** measured results beat controls under equal resources.

Until all gates pass, the honest status is **integrated experimental hybrid architecture**, not production-proven ASIC silicon.
