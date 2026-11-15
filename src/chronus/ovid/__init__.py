"""OVID representation transformation, materialisation and compatibility surfaces.

OVID does not own durable custody. Legacy content-addressed helpers remain
available for compatibility; production persistence belongs to THESEUS.
"""

from chronus.ovid.transform import (
    OvidRepresentation,
    OvidTransformService,
    TransformationContract,
)
from chronus.security.ovid import (
    POINTER_PREFIX,
    OVIDReceipt,
    OVIDStorage,
    OVIDZeroCopyPointer,
    VerifyEndpoint,
)

__all__ = [
    "OvidRepresentation",
    "OvidTransformService",
    "POINTER_PREFIX",
    "OVIDReceipt",
    "OVIDStorage",
    "OVIDZeroCopyPointer",
    "TransformationContract",
    "VerifyEndpoint",
]
