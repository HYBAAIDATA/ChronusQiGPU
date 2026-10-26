# Production execution wiring

## Canonical path

What the canonical miner (`chronus/mla1517/mining/coordinator.py`)
does for every window:

```text
Stratum TCP/TLS -> subscribe -> authorize -> mining.notify
  -> canonical work identity (generation, job fingerprint)
  -> operating policy: window size (Lucas ladder, within the responsiveness
     envelope and the thermal de-rate) and precompute depth (job churn)
  -> SearchPlan + nonce lease (no overlap, no resurrection of old work)
  -> policy governor: admit the window only within configured scheduling limits
     (operator target and network-relative policy derived from nbits; these
     limits are not executed-hash measurements)
  -> Execution Router: the bound route executes the leased interval, in the
     Hendrix structured-search order (PYTHIA_NONCE_ORDER, default hendrix):
     position p visits base + (p * stride) mod window, every nonce once
       cpu_reference   exact SHA256d on the CPU
       opencl_m32      the OpenCL kernels (bitcoin_sha256d_hendrix, or the
                       M32 lane order), after a start-up self-check
  -> independent SHA256d / target recheck of every candidate
  -> submission gate: --submit, or the operator's approval bound to this
     pool's endpoint and worker; otherwise shadow (recorded, not written)
  -> pool outcome correlated back to the plan, lease and execution
  -> learning: world model, loss ledger, forecasts scored (learning.*)
```

`PYTHIA_EXECUTION_BACKEND=auto` binds OpenCL when a device passes the
self-check and falls back to the CPU reference otherwise; the fallback reason
is reported in the evidence. `HYBA_REQUIRE_HYBA=1` refuses any device that is
not one of `HYBA_DEVICE_ALIAS`.

The virtual quantum computer (`turing_universal_quantum_computer/`) is part
of the miner: it supplies the Hendrix schedule and the exact register the
policy audit runs Grover minimum finding on. It is a declared dependency,
installed beside the miner (`pip install ./turing_universal_quantum_computer .`),
and every image and CI job installs it.

Nothing on this path changes Bitcoin's proof boundary:

- the intelligence decides how much work each window carries, and in what
  order;
- SHA256d decides validity;
- the pool decides acceptance.

The previous `PYTHIA_EXECUTION_PATH` settings (`aethel`, `aethel_hendrix`,
`direct`) and the triple `HYBA_*` live-share environment gate belonged to the
retired `mining/production_miner.py`, now in `legacy/`. The canonical miner
does not read them.

## Pool lifecycle evidence

The following are separate evidence gates:

1. `connected`: TCP/TLS session established.
2. `authorized`: `mining.subscribe` and `mining.authorize` succeeded.
3. `job_received`: a validated `mining.notify` arrived.
4. `candidate_found`: a candidate passed independent SHA256d and target
   verification (in shadow, this is where it stops).
5. `submitted`: `mining.submit` was written, only while submission is
   approved.
6. `accepted`: the correlated pool response was `result: true`.

A job receipt is not a share. A submitted share is not an accepted share. No
accepted-share claim is valid without the pool response.
