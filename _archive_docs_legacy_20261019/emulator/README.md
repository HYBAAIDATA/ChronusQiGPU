# Chronus-1 reference emulator

Build with CMake or run `python scripts/check_chronus_emulator.py`, which uses a strict C++17 compiler directly when CMake is unavailable.

```bash
chronus-emu --load kernel.chronus --global 2,2,1 --local 2,2,1 --memory 4096 --budget 100000 --dump 128:4
```

Exit `0` means completed execution, `2` means a Chronus architectural trap, and `1` means CLI/configuration failure. The emulator never falls back to a host implementation of the submitted kernel.
