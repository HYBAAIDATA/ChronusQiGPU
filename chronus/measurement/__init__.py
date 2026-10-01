"""Chronus tech-stack measurement — eleven layers, all measured or declared.

The iGPU measurement tree: system baseline, hardware topology, profiling,
roofline, workloads, efficiency, stability, attestation, store — ending in one
content-addressed, HMAC-attested, replayable :class:`MeasurementArtifact`.

Nothing here invents a number. Fields a backend cannot report stay ``None``
and land in ``unknown``/``available=False`` records; every measured number
carries its ``method``.
"""

from .attestation.artifact import MeasurementArtifact, build_artifact
from .attestation.hmac import attest_artifact, load_hmac_key
from .attestation.replay import replay_artifact
from .run import measure_chronus
from .store.evidence import EvidenceStore
from .system.baseline import SystemBaseline, capture_baseline
from .system.clinfo import OpenCLDevice, OpenCLPlatform, enumerate_devices
from .system.fingerprint import DeviceFingerprint, compute_fingerprint

__all__ = [
    "DeviceFingerprint",
    "EvidenceStore",
    "MeasurementArtifact",
    "OpenCLDevice",
    "OpenCLPlatform",
    "SystemBaseline",
    "attest_artifact",
    "build_artifact",
    "capture_baseline",
    "compute_fingerprint",
    "enumerate_devices",
    "load_hmac_key",
    "measure_chronus",
    "replay_artifact",
]
