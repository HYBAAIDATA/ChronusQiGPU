"""Generic tensor execution on a physical Chronus OpenCL GPU.

Importing this module does not require OpenCL; probing/context creation are lazy.
A CPU OpenCL device is rejected: a result named ``chronus-opencl`` must have
executed on a GPU/accelerator. There is no internal CPU fallback.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Sequence

import numpy as np


class ChronusTensorUnavailable(RuntimeError):
    pass


class ChronusTensorValidationError(ValueError):
    pass


@dataclass(frozen=True)
class TensorDeviceProbe:
    available: bool
    device_id: str
    device_name: str
    platform_name: str
    reason: str
    operations: tuple[str, ...] = ("matmul", "add", "scale", "kron", "hadamard")
    dtypes: tuple[str, ...] = ("float32",)

    def as_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "device_id": self.device_id,
            "device_name": self.device_name,
            "platform_name": self.platform_name,
            "reason": self.reason,
            "operations": self.operations,
            "dtypes": self.dtypes,
        }


def _pick_gpu():
    try:
        import pyopencl as cl
    except Exception as exc:
        return None, None, f"pyopencl unavailable: {type(exc).__name__}: {exc}"
    try:
        candidates=[]
        for platform in cl.get_platforms():
            for device in platform.get_devices():
                dev_type=int(getattr(device,"type",0))
                mask=int(cl.device_type.GPU)|int(cl.device_type.ACCELERATOR)
                if dev_type & mask:
                    candidates.append((platform,device))
    except Exception as exc:
        return None, None, f"OpenCL enumeration failed: {type(exc).__name__}: {exc}"
    if not candidates:
        return None, None, "no OpenCL GPU/accelerator device found"
    selected=max(candidates,key=lambda item:(
        int(getattr(item[1],"max_compute_units",0) or 0),
        int(getattr(item[1],"global_mem_size",0) or 0)))
    return cl, selected, ""


def probe() -> TensorDeviceProbe:
    cl, selected, reason=_pick_gpu(); del cl
    if selected is None:
        return TensorDeviceProbe(False,"unavailable","","",reason)
    platform,device=selected
    name=str(getattr(device,"name","unknown")).strip()
    platform_name=str(getattr(platform,"name","unknown")).strip()
    return TensorDeviceProbe(True,f"opencl:{platform_name}:{name}",name,platform_name,"")


class ChronusTensorRuntime:
    def __init__(self) -> None:
        cl, selected, reason=_pick_gpu()
        if cl is None or selected is None:
            raise ChronusTensorUnavailable(reason)
        platform,device=selected
        source_path=Path(__file__).resolve().parent/"kernels"/"tensor_ops.cl"
        if not source_path.is_file():
            raise ChronusTensorUnavailable(f"tensor kernel source missing: {source_path}")
        try:
            context=cl.Context([device]); queue=cl.CommandQueue(context)
            program=cl.Program(context,source_path.read_text(encoding="utf-8")).build()
        except Exception as exc:
            raise ChronusTensorUnavailable(
                f"OpenCL tensor kernel build failed: {type(exc).__name__}: {exc}") from exc
        self.cl=cl; self.context=context; self.queue=queue; self.program=program; self.device=device
        self.device_id=(f"opencl:{str(getattr(platform,'name','unknown')).strip()}:"
                        f"{str(getattr(device,'name','unknown')).strip()}")

    @staticmethod
    def _float32_array(value: Any, shape: Sequence[int]) -> np.ndarray:
        array=np.asarray(value,dtype=np.float32,order="C")
        if tuple(array.shape)!=tuple(int(v) for v in shape):
            raise ChronusTensorValidationError(
                f"input shape {array.shape} does not match declared shape {tuple(shape)}")
        return np.ascontiguousarray(array)

    def _buffers(self, arrays: Sequence[np.ndarray], output_size: int):
        cl=self.cl; flags=cl.mem_flags
        inputs=[cl.Buffer(self.context,flags.READ_ONLY|flags.COPY_HOST_PTR,hostbuf=a) for a in arrays]
        output=np.empty(int(output_size),dtype=np.float32)
        output_buffer=cl.Buffer(self.context,flags.WRITE_ONLY,output.nbytes)
        return inputs,output,output_buffer

    def _finish(self, output, output_buffer, shape):
        self.cl.enqueue_copy(self.queue,output,output_buffer); self.queue.finish()
        return output.reshape(tuple(int(v) for v in shape))

    def execute(self, operation: str, inputs: Sequence[Any],
                input_shapes: Sequence[Sequence[int]], output_shape: Sequence[int]) -> np.ndarray:
        if len(inputs)!=len(input_shapes):
            raise ChronusTensorValidationError("input count does not match declared shapes")
        arrays=[self._float32_array(v,s) for v,s in zip(inputs,input_shapes)]
        out_size=int(np.prod(tuple(output_shape),dtype=np.int64))
        buffers,output,out_buffer=self._buffers(arrays,out_size); u32=np.uint32
        if operation in {"add","hadamard"}:
            if len(arrays)!=2 or arrays[0].shape!=arrays[1].shape:
                raise ChronusTensorValidationError(f"{operation} requires two equal shapes")
            getattr(self.program,f"tensor_{operation}_f32")(
                self.queue,(out_size,),None,buffers[0],buffers[1],out_buffer,u32(out_size))
        elif operation=="scale":
            if len(arrays)!=2 or arrays[1].size!=1:
                raise ChronusTensorValidationError("scale requires a tensor and one scalar")
            self.program.tensor_scale_f32(
                self.queue,(out_size,),None,buffers[0],buffers[1],out_buffer,u32(out_size))
        elif operation=="matmul":
            if len(arrays)!=2 or arrays[0].ndim!=2 or arrays[1].ndim!=2:
                raise ChronusTensorValidationError("matmul requires two rank-2 inputs")
            m,k=arrays[0].shape; k2,n=arrays[1].shape
            if k!=k2 or tuple(output_shape)!=(m,n):
                raise ChronusTensorValidationError("matmul dimensions/output shape disagree")
            self.program.tensor_matmul_f32(
                self.queue,(out_size,),None,buffers[0],buffers[1],out_buffer,u32(m),u32(k),u32(n))
        elif operation=="kron":
            if len(arrays)!=2 or arrays[0].ndim!=arrays[1].ndim:
                raise ChronusTensorValidationError("kron requires equal-rank inputs")
            if arrays[0].ndim==1:
                an,bn=arrays[0].size,arrays[1].size
                if tuple(output_shape)!=(an*bn,):
                    raise ChronusTensorValidationError("kron output shape disagrees")
                self.program.tensor_kron_1d_f32(
                    self.queue,(out_size,),None,buffers[0],buffers[1],out_buffer,u32(an),u32(bn))
            elif arrays[0].ndim==2:
                ar,ac=arrays[0].shape; br,bc=arrays[1].shape
                if tuple(output_shape)!=(ar*br,ac*bc):
                    raise ChronusTensorValidationError("kron output shape disagrees")
                self.program.tensor_kron_2d_f32(
                    self.queue,(out_size,),None,buffers[0],buffers[1],out_buffer,
                    u32(ar),u32(ac),u32(br),u32(bc))
            else:
                raise ChronusTensorValidationError("Chronus kron supports rank 1 or 2")
        else:
            raise ChronusTensorValidationError(f"unsupported operation {operation!r}")
        return self._finish(output,out_buffer,output_shape)


_RUNTIME: ChronusTensorRuntime | None=None
_RUNTIME_LOCK=Lock()


def get_runtime() -> ChronusTensorRuntime:
    global _RUNTIME
    if _RUNTIME is None:
        with _RUNTIME_LOCK:
            if _RUNTIME is None:
                _RUNTIME=ChronusTensorRuntime()
    return _RUNTIME


get_tensor_runtime=get_runtime
probe_tensor=probe

__all__=["ChronusTensorRuntime","ChronusTensorUnavailable","ChronusTensorValidationError",
         "TensorDeviceProbe","get_runtime","get_tensor_runtime","probe","probe_tensor"]
