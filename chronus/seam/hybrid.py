"""Hybrid bridge — partition is a function of (KernelClass, DeviceClass)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence

from igpu.seam.probe import Capability
from igpu.seam.types import KERNEL_CLASS, DeviceClass, KernelClass, KernelName


@dataclass(frozen=True)
class Window:
    start: int
    end: int
    kernel: KernelName

    def as_dict(self) -> Dict[str, int]:
        return {"start": self.start, "end": self.end, "kernel": self.kernel.value}


def kernel_class(kernel: KernelName) -> KernelClass:
    return KERNEL_CLASS.get(kernel, KernelClass.coordination)


def supports_class(device: Capability, klass: KernelClass) -> bool:
    dc = device.device_class
    if klass is KernelClass.compute_heavy:
        return dc in {
            DeviceClass.gpu_integrated,
            DeviceClass.gpu_discrete,
            DeviceClass.gpu_datacenter,
            DeviceClass.gpu_cloud_instance,
            DeviceClass.tpu,
            DeviceClass.fpga,
            DeviceClass.cpu_reference,
        }
    if klass is KernelClass.hash_heavy:
        return dc in {
            DeviceClass.asic,
            DeviceClass.fpga,
            DeviceClass.gpu_discrete,
            DeviceClass.gpu_datacenter,
            DeviceClass.gpu_integrated,
            DeviceClass.cpu_reference,
        }
    if klass is KernelClass.traversal:
        return dc in {
            DeviceClass.gpu_integrated,
            DeviceClass.gpu_discrete,
            DeviceClass.gpu_datacenter,
            DeviceClass.gpu_cloud_instance,
            DeviceClass.fpga,
            DeviceClass.cpu_reference,
        }
    return True


def fallback_candidates(fleet: Sequence[Capability], klass: KernelClass) -> List[Capability]:
    if klass is KernelClass.hash_heavy:
        return [
            d
            for d in fleet
            if d.device_class
            in {
                DeviceClass.gpu_integrated,
                DeviceClass.gpu_discrete,
                DeviceClass.gpu_datacenter,
                DeviceClass.cpu_reference,
            }
        ]
    if klass is KernelClass.compute_heavy:
        return [d for d in fleet if d.device_class is DeviceClass.cpu_reference]
    return []


def partition(job_kernels: Sequence[KernelName], span: int = 1 << 20) -> Dict[KernelClass, List[Window]]:
    out: Dict[KernelClass, List[Window]] = {}
    cursor = 0
    width = max(1, int(span) // max(1, len(job_kernels)))
    for kernel in job_kernels:
        klass = kernel_class(kernel)
        window = Window(start=cursor, end=cursor + width, kernel=kernel)
        out.setdefault(klass, []).append(window)
        cursor += width
    return out
