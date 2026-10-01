"""Canonical PYTHIA hardware miner entrypoint.

The intelligent runtime owns the real MMIO -> vault -> Stratum path. This
module is only the executable name used by deployment; it contains no
simulation or alternate mining implementation.
"""

from mining_runtime import main


if __name__ == "__main__":
    main()
