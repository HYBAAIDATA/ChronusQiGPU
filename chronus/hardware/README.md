# Bounded exact Chronus RTL

`hyba.vhd` at repository root implements one registered Z[phi] multiplication
and GF(2^8) multiplication per valid input cycle. Phi coefficients are signed
16-bit inputs with full 34-bit signed outputs, preserving all products and
sums. GF(256) uses polynomial x^8+x^4+x^3+x+1. Reset clears validity and outputs.
An invalid cycle clears validity and holds arithmetic outputs.

`golden_stride.vhd` generates uint32 candidates modulo 2^32 with stride
0x9E3779B9. Its FIFO depth is computed as Fibonacci(6)=8. Start atomically
reseeds and discards the prior queued sequence. Backpressure preserves the
head and prevents overwrite; simultaneous push/pop preserves ordering.
This defines ordering, not fewer SHA256d evaluations.

Run from the repository root with the declared Python environment and GHDL:

```bash
python -m scripts.verify_chronus_rtl
```

The runner uses a temporary directory, compiles both designs, and runs GHDL
synthesis elaboration before the testbenches. It checks 817 coefficient vectors
(including every combination of signed-16 extrema, zero and units, plus seeds
1337/42/2026) against Kellogg's exact integer algebra, all 65,536 GF products
against a separate polynomial-reduction oracle, and FIFO reset/reseed, stalls
and uint32 wrap. GHDL is an OS development dependency (`apt-get install ghdl`
on Ubuntu); no provider credentials or hardware device is required for these
source conformance checks.

This is bounded arithmetic RTL, not a completed systolic array, an RDMA device
or a tape-out. A registered combinational datapath is not a measured clock-rate
claim. Target FPGA/ASIC mapping, physical timing closure, power/resource measurements,
ISA/runtime integration and dot-product accumulation remain explicit delivery
gates in `docs/CHRONUS_GPIU_EXECUTION.md`.
