"""OVID: content-addressed objects, zero-copy pointers and receipts.

First-class import path for the OVID primitives implemented in
chronus.security.ovid; the objects below are the same objects. State is
process-local: OVID is not a durable or distributed store.
"""

from chronus.security.ovid import (
    POINTER_PREFIX,
    OVIDReceipt,
    OVIDStorage,
    OVIDZeroCopyPointer,
    VerifyEndpoint,
)

__all__ = [
    "POINTER_PREFIX",
    "OVIDReceipt",
    "OVIDStorage",
    "OVIDZeroCopyPointer",
    "VerifyEndpoint",
]
