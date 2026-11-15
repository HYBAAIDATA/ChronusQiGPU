# RTL overflow counterexample — blocked exactness and timing

Source reference: `de838752204a59a9e38490c79505ff2e4313d8cc`, `hw/cyclotomic_mul_128bit.sv`, Git blob `c0e85c983a0d4d1e4276d4a6d458588d7784c2e0`. The source was read through GitHub MCP and streamed to the simulator, not a full checkout. Testbench and output are recorded alongside this finding.

Reproduce from a complete checkout using Icarus Verilog 11.0 and vvp:

```sh
iverilog -g2012 -s tb_cyclotomic_overflow_finding -o /tmp/cyclotomic-overflow hw/cyclotomic_mul_128bit.sv hw/tb_cyclotomic_overflow_finding.sv
vvp /tmp/cyclotomic-overflow
```

Observed: both inputs have coefficients `(65536,0,0,0)`; the exact result has coefficient 4294967296 but the output exposes a 32-bit zero. Simulation exits 1. This is a counterexample to unbounded integer-ring exactness, not a timing measurement. The present interface discards upper bits; a successful fix needs a specified policy (widened interface and/or explicit overflow with multiword continuation) and integration tests; output widening alone cannot make a fixed-width interface closed under unrestricted multiplication.

Timing remains BLOCKED: specify FPGA vendor, exact part and speed grade, implementation tool/version, clock period, input/output delays, clock uncertainty, operating corner and required slack; alternatively supply an ASIC library, process/voltage/temperature corner and equivalent constraints. No post-synthesis or physical timing measurement was run. Functional simulation's one-clock scheduling is not evidence of frequency or timing closure.

Testbench SHA-256 `5d7e91690378d9a4c6edf94d60fdd697d9bff74d45452d951a7900bf6d4b775f`; output SHA-256 `264fb1581529bac535ba768476808e4756ab0a066ec09f025c4148a594aea68e`. The test intentionally fails against this source and is not a passing release gate. Reproduction uses checkout source rather than an alternate module. It proves only this specific case.
