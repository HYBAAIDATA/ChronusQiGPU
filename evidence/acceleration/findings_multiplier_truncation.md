# Finding: multiplier coefficient truncation

Source `hw/cyclotomic_mul_128bit.sv`, Git blob `c0e85c983a0d4d1e4276d4a6d458588d7784c2e0`, inspected at `7be3e20d1dc34bcb7477d00346669ce98debaa7b`. Its output packs only bits `[31:0]` of each reduced coefficient; the 64-bit intermediate sums can also overflow for sufficiently large inputs. Fixed-width packing is not closed under unrestricted integer multiplication.

The previously committed failing case is `hw/tb_cyclotomic_overflow_finding.sv`: inputs `(65536,0,0,0)` and `(65536,0,0,0)` have exact first coefficient `4294967296`, while the observed packed first coefficient is `0`. The simulator output is [rtl-overflow-output.txt](../cyclotomic/rtl-overflow-output.txt), SHA-256 `264fb1581529bac535ba768476808e4756ab0a066ec09f025c4148a594aea68e`; testbench SHA-256 `5d7e91690378d9a4c6edf94d60fdd697d9bff74d45452d951a7900bf6d4b775f`. The failing test and output were committed in `16d4e441b4dd7e61abf4f08c2faf430fbef929be`.

```sh
iverilog -g2012 -s tb_cyclotomic_overflow_finding -o /tmp/cyclotomic-overflow hw/cyclotomic_mul_128bit.sv hw/tb_cyclotomic_overflow_finding.sv
vvp /tmp/cyclotomic-overflow
```

The recorded run exits nonzero. It demonstrates this case, not a general timing measurement. The previously committed [finding](../cyclotomic/rtl-overflow-finding.md) specifies the missing implementation target and timing constraints.
