"""HYBA PCI health shim — reports the real engine's liveness."""


def health() -> dict:
    from pci.engine import ExactQuantumComputer

    return {"ok": True, "service": "pci-exact", "provenance": ExactQuantumComputer.provenance()}
