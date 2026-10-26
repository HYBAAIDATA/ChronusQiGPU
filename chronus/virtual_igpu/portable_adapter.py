"""Execute the same exact integer IR on independent native C or host OpenCL."""

import ctypes
import hashlib
import shutil
import struct
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from chronus.compiler.exact_kernel import ExactKernelIR
from .abi import AdapterKind, CapabilityManifest, WorkloadKind
from .adapters import Adapter, AdapterUnavailable

_C_CACHE = {}
_C_LOCK = threading.Lock()


def _native(ir):
    source = ir.lower("c")
    key = hashlib.sha256(source.encode()).hexdigest()
    with _C_LOCK:
        if key not in _C_CACHE:
            if len(_C_CACHE) >= 32:
                raise AdapterUnavailable("native kernel cache admission limit reached")
            compiler = shutil.which("cc")
            if compiler is None:
                raise AdapterUnavailable("native exact compiler unavailable")
            with tempfile.TemporaryDirectory(prefix="chronus-kernel-") as directory:
                path = Path(directory)
                (path / "kernel.c").write_text(source)
                subprocess.run(
                    [
                        compiler,
                        "-O3",
                        "-fopenmp-simd",
                        "-shared",
                        "-fPIC",
                        str(path / "kernel.c"),
                        "-o",
                        str(path / "kernel.so"),
                    ],
                    check=True,
                    timeout=30,
                    capture_output=True,
                )
                library = ctypes.CDLL(str(path / "kernel.so"))
                fn = library.chronus_kernel
                u32 = ctypes.c_uint32
                fn.argtypes = [ctypes.POINTER(u32), u32, u32, ctypes.POINTER(u32)]
                fn.restype = None
                _C_CACHE[key] = (library, fn)
        return _C_CACHE[key][1]


class PortableExactAdapter(Adapter):
    priority = 110

    def __init__(self, target="c"):
        if target not in ("c", "opencl", "opencl_cpu"):
            raise ValueError("executable target must be c or opencl")
        self.target = target
        self.id = {
            "c": "chronus-exact-native",
            "opencl": "chronus-exact-opencl",
            "opencl_cpu": "chronus-exact-opencl-cpu",
        }[target]
        self.kind = AdapterKind.OPENCL if target == "opencl" else AdapterKind.SOFTWARE
        self.available, self.reason = False, "not probed"
        self._programs = {}
        self._lock = threading.Lock()

    def probe(self):
        with self._lock:
            return self._probe()

    def _probe(self):
        self._programs.clear()
        detail = {"target": self.target}
        try:
            if self.target == "c":
                _native(ExactKernelIR())
            else:
                import pyopencl as cl

                devices = [
                    d
                    for p in cl.get_platforms()
                    for d in p.get_devices(
                        device_type=(
                            cl.device_type.GPU if self.target == "opencl" else cl.device_type.CPU
                        )
                    )
                ]
                if not devices:
                    raise AdapterUnavailable("no OpenCL device of requested type")
                self._cl = cl
                self._context = cl.Context([devices[0]])
                self._queue = cl.CommandQueue(self._context)
                program = cl.Program(self._context, ExactKernelIR().lower("opencl")).build()
                self._programs[ExactKernelIR()] = cl.Kernel(program, "chronus_kernel")
                detail.update(device=devices[0].name, vendor=devices[0].vendor)
            self.available, self.reason = True, ""
        except Exception as exc:
            self.available, self.reason = False, f"{type(exc).__name__}: {exc}"
        return self._attestation(self.available, {**detail, "reason": self.reason})

    def supports(self, kind):
        return kind == WorkloadKind.EXACT_KERNEL and self.available

    def capabilities(self):
        return CapabilityManifest(
            self.id,
            self.kind.value,
            operations=("exact_kernel",) if self.available else (),
            dtypes=("uint32",),
            max_shape=(65536,),
            max_bytes=2**24,
            arithmetic={"overflow": "modulo_2^32", "exact_integer_ops": ("exact_kernel",)},
            available=self.available,
            reason=self.reason,
            device_ids=(self.id,),
            software_impl=self.target != "opencl",
            build_status="built" if self.available else "unavailable",
        )

    def execute(self, workload):
        if not self.available:
            raise AdapterUnavailable(self.reason)
        if workload.kind == WorkloadKind.PROBE:
            return self._result(workload, {"probe": self.health()}, time.time_ns())
        if workload.kind != WorkloadKind.EXACT_KERNEL:
            raise ValueError("portable adapter executes exact_kernel only")
        value = workload.input
        if set(value) != {"ir", "indices", "seed"}:
            raise ValueError("invalid exact kernel input")
        ir = ExactKernelIR.from_dict(value["ir"])
        indices, seed = value["indices"], value["seed"]
        ir.admit(indices, seed)
        started = time.time_ns()
        width = len(ir.outputs)
        if self.target == "c":
            u32 = ctypes.c_uint32
            output = (u32 * (len(indices) * width))()
            _native(ir)((u32 * len(indices))(*indices), len(indices), seed, output)
            flat = list(output)
        else:
            import numpy as np

            cl = self._cl
            with self._lock:
                if ir not in self._programs:
                    if len(self._programs) >= 32:
                        raise AdapterUnavailable("OpenCL kernel cache admission limit reached")
                    program = cl.Program(self._context, ir.lower("opencl")).build()
                    self._programs[ir] = cl.Kernel(program, "chronus_kernel")
                source = np.asarray(indices, dtype=np.uint32)
                result = np.empty(len(indices) * width, dtype=np.uint32)
                input_buffer = cl.Buffer(
                    self._context,
                    cl.mem_flags.READ_ONLY | cl.mem_flags.COPY_HOST_PTR,
                    hostbuf=source,
                )
                output_buffer = cl.Buffer(self._context, cl.mem_flags.WRITE_ONLY, result.nbytes)
                event = self._programs[ir](
                    self._queue,
                    (len(indices),),
                    None,
                    input_buffer,
                    np.uint32(len(indices)),
                    np.uint32(seed),
                    output_buffer,
                )
                cl.enqueue_copy(self._queue, result, output_buffer, wait_for=[event]).wait()
                flat = result.tolist()
        rows = [flat[i : i + width] for i in range(0, len(flat), width)]
        digest = hashlib.sha256(b"".join(struct.pack("<I", v) for v in flat)).hexdigest()
        return self._result(
            workload,
            {
                "rows": rows,
                "digest": digest,
                "legality": ir.legality(),
                "arithmetic": "exact_uint32",
            },
            started,
        )
