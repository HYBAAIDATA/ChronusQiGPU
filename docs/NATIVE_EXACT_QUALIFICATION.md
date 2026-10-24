# Native exact execution: qualification and corrected claims

## Verified in this change

Pinned baseline: `c760cdfc6b5a7c8c9c97dec2493a9a75a1997dbc`.
The recorded run uses Python 3.13, NumPy 2.5.4, SymPy 1.14.0 and pytest 9.1.1.

- **Chronus independent execution is operational without an attached GPU.** Twelve real jobs across seeds 1337, 42 and 2026 execute exact Lucas/Pisot integer transforms, SHA256d scans and numerical matrix products through `ChronusSoftwareFabricAdapter`. Each result passes the independent runtime verifier; evidence bytes hash to their recorded address. The SHA256d tests also reproduce the published Bitcoin genesis header digest. A known historical nonce is a correctness vector, not a newly mined share.
- **The canonical TURING Hilbert operator module performs exact quantum mathematics on the tested software substrate.** Tests execute exact Born distributions, Bell/GHZ entanglement, QFT/inverse, reduced density matrices, entropy, gate-domain refusal and exact Grover recurrence/register agreement. The 10,000-qubit GHZ tests use two occupied amplitudes; the phase/reversal test allows four slots of workspace. Eight exact T gates and inverse entanglement return the state exactly to the computational basis. This is not materialization of all `2**10000` amplitudes or a generic 10,000-qubit dense computation claim.
- **Authority and identity survive replay.** Revocation is checked before returning cached results, idempotency keys are tenant-scoped, mutable requests are revalidated against their canonical hash, and cached results are detached from caller mutation.
- **Exact integer lanes reject lossy coercion.** Boolean, floating-point, decimal-like string and null indices are refused. A verifier cannot accept a fractional/string result by truncating it with `int()`.
- **Enterprise transport respects native mode.** Server-owned `execution.mode=independent` or `auto` does not impose a host-GPU gate on configure/start. Pool allowlists, secrets, caps, guardian admission, independent second approval and the canonical start path remain intact. `scale_stack` retains the device prerequisite; this change does not by itself certify that a detected accelerator can execute a kernel.

## Corrected status semantics

Physical GPU presence, mathematical execution and mining outcome are separate facts.

- `execution_status=VERIFIED` can coexist with `igpu_present=false`, `emulated=false` and a `WITHHELD` mining certificate.
- The absence of a GPU never manufactures `emulated=true`.
- The coordinator's real nested `execution_backend`, `last_execution`, `hashing` and `observed_at` fields are consumed instead of expecting an invented top-level `PASS` flag. Native qualification requires this measured nested form, a live publisher, fresh observation and positive completed work.
- Mining `ACTIVE` additionally requires live/ready workers, armed submission, canonical readiness, a connected/authorized pool, an accepted response less than five minutes old, and positive accepted shares. Native mathematical execution does not require a physical QPU/GPU; a named accelerator claim still requires that device's evidence.
- A running, measured native executor without pool acceptance is reported as execution verified with mining certification withheld, not as a daemon that is offline.

## Reproduction

From the repository root in an environment with the versions above:

```bash
python -m pytest --noconftest -q \
  tests/test_chronus_native_status_qualification.py \
  tests/test_chronus_native_enterprise_journey.py \
  tests/test_chronus_native_exactness_regressions.py \
  tests/test_chronus_vigpu_sha256d_contract.py \
  tests/test_chronus_vigpu_verification.py \
  tests/test_turing_hilbert_source_qualification.py
python tools/qualify_native_backend.py native-execution.json
```

Recorded result: **113 passed**, plus **12 native jobs** with independently checked results and content-addressed evidence. Separate `python -O` checks confirm normalization/unitarity refusal remains enabled.

Evidence is under `evidence/2026-10-23/native-exact-qualification/`; `DIGESTS.json` binds the recorded files, and `source-digests.json` binds tested source/test bytes. `adversarial-before.log` records 17 reproduced failures before the runtime/exactness fixes; `status-before.log` records three false-hardware/emulation failures. These are failure histories, not the final result.

## Scope and role integrity

This was a pinned **partial-source local qualification**, using real Chronus package initializers and real runtime/adapter/verifier modules. It is not a full-repository CI or deployed-service result. The standalone TURING tests load the canonical `hilbert.py` directly; they do not qualify every product facade or backend. Enterprise journey tests use an explicitly labelled backend fixture to test transport/authorization behavior; their accepted-share observations are fixtures, not external pool evidence.

TURING retains quantum operator authority. CHRONUS executes. TOE retains its full inference/certification scope; it is not redefined as only an invariant checker. TENSOR owns tensor execution and verification. OVID owns representation/addressability and THESEUS durable custody. None of those ownership boundaries is transferred by this transport correction.

The whole TOE inference stack, OVID bridge, THESEUS 10-of-12 custody/drill, external PostgreSQL, every TENSOR backend and the complete cross-owner production pipeline were **not requalified by this run**. The focused fold test may use the adapter's explicit identity frame when Aethel is unavailable; it is not evidence of OVID compression. No new proof of physical-QPU execution, hardware-rooted attestation, mining yield, universal exponential advantage or device speedup is claimed.

AI Studio was not modified or deployed.
