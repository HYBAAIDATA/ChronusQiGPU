"""Compile real QSDL scenes into the executable QX command contract.

This is the missing bridge between the mathematical Chronos v3.3 scene
pipeline and the QX command boundary captured in the original pseudocode.
It remains substrate-independent: hardware backends may execute the same
sealed command buffer later, but compilation itself requires no GPU.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any

import numpy as np

from .hamiltonian import HamiltonianLibrary
from .qsdl_compiler import ManifoldConfig, QSDLCompiler
from .qx import QXCommandBuffer, QXMemoryDomain, QXReferenceExecutor


@dataclass(frozen=True)
class QXSceneCompilation:
    source_sha256: str
    dimension: int
    object_count: int
    light_count: int
    command_digest: str
    buffer: QXCommandBuffer

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_sha256": self.source_sha256,
            "dimension": self.dimension,
            "object_count": self.object_count,
            "light_count": self.light_count,
            "command_digest": self.command_digest,
        }


def compile_qsdl_to_qx(
    source: str,
    *,
    n_faces: int = 32,
    dt: float = 0.05,
    weak_epsilon: float = 0.005,
) -> QXSceneCompilation:
    """Compile one QSDL scene to a sealed, deterministic QX command buffer."""
    if not isinstance(source, str) or not source.strip().startswith("scene"):
        raise ValueError("QX compilation requires explicit QSDL scene source")
    compiler = QSDLCompiler(ManifoldConfig(n_faces=int(n_faces)))
    scene = compiler.compile(source)
    library = HamiltonianLibrary(n_faces=scene.manifold.n_faces)
    terms = library.build(scene.objects, scene.lights)

    observable = np.diag(np.asarray(terms.resonance_weights, dtype=np.float64))
    source_sha = hashlib.sha256(source.encode("utf-8")).hexdigest()

    buffer = QXCommandBuffer()
    buffer.allocate_cavity_region(scene.manifold.n_faces, region_id="scene")
    buffer.bind_descriptor_set(
        "scene",
        {
            "source_sha256": source_sha,
            "manifold": scene.manifold.name,
            "dimension": scene.manifold.n_faces,
            "objects": len(scene.objects),
            "lights": len(scene.lights),
        },
    )
    buffer.set_hamiltonian(terms.total_hamiltonian)
    buffer.evolve(float(dt))
    buffer.memory_barrier(QXMemoryDomain.CAVITY)
    buffer.weak_measure(observable, epsilon=float(weak_epsilon), probe_id="scene-readout")
    buffer.read_expectation(observable, result_id="scene-expectation")
    buffer.synchronize("scene-complete")
    digest = buffer.seal()

    return QXSceneCompilation(
        source_sha256=source_sha,
        dimension=scene.manifold.n_faces,
        object_count=len(scene.objects),
        light_count=len(scene.lights),
        command_digest=digest,
        buffer=buffer,
    )


def execute_qsdl_qx_reference(source: str, *, n_faces: int = 32) -> dict[str, Any]:
    """Compile and execute the QSDL-to-QX path on the deterministic reference backend."""
    compiled = compile_qsdl_to_qx(source, n_faces=n_faces)
    report = QXReferenceExecutor().execute(compiled.buffer)
    return {
        "compilation": compiled.as_dict(),
        "execution": {
            "command_digest": report.command_digest,
            "backend": report.backend,
            "precision": report.precision,
            "dimension": report.dimension,
            "commands_executed": report.commands_executed,
            "barrier_epoch": report.barrier_epoch,
            "event_ids": list(report.event_ids),
            "expectations": dict(report.expectations),
            "weak_measurements": dict(report.weak_measurements),
            "final_state_sha256": report.final_state_sha256,
            "norm_error": report.norm_error,
        },
        "passed": (
            report.command_digest == compiled.command_digest
            and report.dimension == compiled.dimension
            and report.norm_error <= 1e-10
        ),
    }


__all__ = ["QXSceneCompilation", "compile_qsdl_to_qx", "execute_qsdl_qx_reference"]
