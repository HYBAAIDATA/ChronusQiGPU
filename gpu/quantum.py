"""Fail-closed access to the Turing virtual quantum computer."""

from __future__ import annotations

from importlib import import_module
from typing import Any


class VirtualQuantumComputerUnavailable(RuntimeError):
    """The separately packaged VQC cannot be imported."""


def load_virtual_quantum_computer() -> Any:
    """Load the canonical exact-math VQC package.

    The import is explicit and lazy.  A missing installation is a deployment
    error rather than permission to substitute a dense or floating-point mock.
    """
    try:
        return import_module("turing_universal_quantum_computer")
    except ImportError as exc:
        raise VirtualQuantumComputerUnavailable(
            "install the in-tree turing_universal_quantum_computer package"
        ) from exc


def create_universal_system(*args: Any, **kwargs: Any) -> Any:
    """Construct the VQC's canonical universal system."""
    module = load_virtual_quantum_computer()
    return module.TenThousandQubitSystem(*args, **kwargs)


__all__ = [
    "VirtualQuantumComputerUnavailable",
    "create_universal_system",
    "load_virtual_quantum_computer",
]