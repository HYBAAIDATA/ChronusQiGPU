# Chronus conformance authority v1

PR #104 defines two independent authorities. `conformance/generators/isa.py` describes raw Chronus-1 machine cases and never imports compiler lowering. `conformance/generators/semantic.py` describes IR cases that are compiled, assembled, packed as `.chronus` v1.1 and executed by the accepted emulator; NumPy float32 is only the independent oracle.

Cases and results use separate canonical JSON schemas. All binary artifacts are raw little-endian bytes under SHA-256 names; floats are IEEE-754 binary32. There are no pickles, absolute paths, network dependencies or emulator implementation objects. Trap comparison is by backend-neutral class, never exception text.

The v0.1 compiler surface is frozen to `vector_add(f32,1<=n<=4080)`, `reduce_sum_local(f32,1<=n<=256)`, and `matmul_tiled(f32,32x32x32)`. `n=4081` is `REJECTED_IR`. Float64/f64, NaN and infinity are outside the accepted corpus and are explicitly rejected/excluded; generated inputs are finite float32.

Run `python scripts/check_chronus104.py`. It invokes #100-#103 first, builds the corpus twice, compares byte-identical trees, verifies boundaries, breadth, schemas, taxonomy and deterministic replay, then writes content-addressed closure artifacts. This PR makes no physical-backend, #105, #106, intrinsic, FPGA, ASIC, CUDA, ROCm, Metal, Vulkan or production-mining claim.
