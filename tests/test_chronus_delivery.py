from __future__ import annotations

from dataclasses import dataclass

from chronus.delivery import (
    DeliveryMode,
    probe_cloud_instance,
    probe_delivery,
    probe_embedded,
)
from chronus.mla1517.remote_gpu import PROTOCOL_VERSION
from chronus.virtual_igpu import ProductMode


@dataclass
class _EmbeddedProbe:
    available: bool = True
    device_id: str = "opencl:Intel:Chronus-iGPU"
    device_name: str = "Chronus-iGPU"
    platform_name: str = "Intel OpenCL"
    reason: str = ""
    operations: tuple[str, ...] = ("matmul", "add", "scale", "kron", "hadamard")
    dtypes: tuple[str, ...] = ("float32",)

    def as_dict(self):
        return self.__dict__.copy()


class _RemoteDevice:
    def as_dict(self):
        return {
            "name": "Chronus Cloud iGPU",
            "vendor": "Intel",
            "type": "chronus",
            "platform": "Cloud OpenCL",
            "endpoint": "https://chronus.example",
            "capabilities": {
                "sha256d_kernel": True,
                "lucas_ladder_kernel": True,
                "fp64": False,
            },
            "backend": "opencl_remote",
        }


class _RemoteClient:
    endpoint = "https://chronus.example"

    def health(self):
        return {
            "status": "ok",
            "protocol": PROTOCOL_VERSION,
            "endpoints": ["ladder", "sha256d"],
        }


def test_embedded_delivery_is_explicit_and_in_process():
    out = probe_embedded(tensor_probe=lambda: _EmbeddedProbe())
    assert out.mode is DeliveryMode.EMBEDDED
    assert out.available is True
    assert out.software_mode_available is True
    assert out.accelerator_mode_available is True
    assert ProductMode.NATIVE_CHRONUS_GPU.value in out.product_modes
    assert ProductMode.HOST_GPU_AUGMENTATION.value in out.product_modes
    assert "standalone_software" in out.execution_modes
    assert "preferred_accelerator" in out.execution_modes
    assert out.execution_location == "customer_container"
    assert out.transport == "in_process"
    assert out.endpoint == ""
    assert "tensor:matmul" in out.capabilities
    assert "dtype:float32" in out.capabilities
    assert out.devices[0]["device_id"] == "opencl:Intel:Chronus-iGPU"


def test_embedded_delivery_accepts_native_cuda_without_opencl():
    cuda_probe = _EmbeddedProbe(
        device_id="cuda:0:Chronus-NVIDIA",
        device_name="Chronus-NVIDIA",
        platform_name="CUDA",
    )
    unavailable_opencl = _EmbeddedProbe(
        available=False,
        reason="no OpenCL GPU",
    )
    out = probe_embedded(
        native_probes=(
            ("chronus-opencl", lambda: unavailable_opencl, "test.opencl"),
            ("chronus-cuda", lambda: cuda_probe, "test.cuda"),
        )
    )
    assert out.available is True
    assert out.software_mode_available is True
    assert out.accelerator_mode_available is True
    assert len(out.devices) == 1
    assert out.devices[0]["backend"] == "chronus-cuda"
    assert "backend:chronus-cuda" in out.capabilities
    assert out.reason == ""


def test_cloud_delivery_uses_measured_remote_inventory():
    seen = {}

    def remote_probe(endpoints):
        seen["endpoints"] = endpoints
        return _RemoteClient(), [_RemoteDevice()], "remote device bound"

    out = probe_cloud_instance(
        endpoints=["https://chronus.example"],
        remote_probe=remote_probe,
    )
    assert seen["endpoints"] == ["https://chronus.example"]
    assert out.mode is DeliveryMode.REMOTE_SERVICE
    assert out.available is True
    assert out.execution_location == "hyba_instance_in_customer_cloud"
    assert out.transport == PROTOCOL_VERSION
    assert out.endpoint == "https://chronus.example"
    assert out.product_modes == (ProductMode.HOST_GPU_AUGMENTATION.value,)
    assert "sha256d_kernel" in out.capabilities
    assert "lucas_ladder_kernel" in out.capabilities
    assert "remote:ladder" in out.capabilities
    assert "remote:sha256d" in out.capabilities
    assert "fp64" not in out.capabilities


def test_cloud_unavailable_does_not_fall_back_to_embedded():
    embedded_called = False

    def embedded_probe():
        nonlocal embedded_called
        embedded_called = True
        return _EmbeddedProbe()

    def remote_probe(endpoints):
        del endpoints
        return None, [], "cloud endpoint unreachable"

    out = probe_delivery(
        DeliveryMode.REMOTE_SERVICE,
        endpoints=["https://missing.example"],
        tensor_probe=embedded_probe,
        remote_probe=remote_probe,
    )
    assert out.available is False
    assert out.mode is DeliveryMode.REMOTE_SERVICE
    assert "unreachable" in out.reason
    assert embedded_called is False


def test_embedded_without_accelerator_remains_available_in_software_mode():
    remote_called = False

    def remote_probe(endpoints):
        nonlocal remote_called
        remote_called = True
        return _RemoteClient(), [_RemoteDevice()], "remote device bound"

    out = probe_delivery(
        "embedded",
        tensor_probe=lambda: _EmbeddedProbe(available=False, reason="no local device"),
        remote_probe=remote_probe,
    )
    assert out.available is True
    assert out.mode is DeliveryMode.EMBEDDED
    assert out.software_mode_available is True
    assert out.accelerator_mode_available is False
    assert out.devices == ()
    assert out.product_modes == (ProductMode.NATIVE_CHRONUS_GPU.value,)
    assert out.execution_modes == ("standalone_software",)
    assert "no local device" in out.accelerator_reason
    assert remote_called is False


def test_delivery_contract_is_serializable_without_performance_invention():
    out = probe_embedded(tensor_probe=lambda: _EmbeddedProbe())
    payload = out.as_dict()
    assert payload["product"] == "Chronus"
    assert payload["delivery_mode"] == "embedded"
    assert payload["software_mode_available"] is True
    assert ProductMode.NATIVE_CHRONUS_GPU.value in payload["product_modes"]
    assert "standalone_software" in payload["execution_modes"]
    assert "tflops" not in payload
    assert "gflops" not in payload
