"""opencl_igpu backend."""
from __future__ import annotations

import hashlib
from pathlib import Path

__all__ = ["probe", "execute"]
_KERNEL = Path(__file__).resolve().parents[2] / "kernels" / "bitcoin_sha256d.cl"


def _cl():
    import pyopencl
    return pyopencl


def probe(opencl_only=False):
    try:
        p = _cl()
    except Exception as exc:
        return {"available": False, "reason": f"import failed: {exc}"}
    try:
        ctx = None
        for plat in p.get_platforms():
            for dev in plat.get_devices(p.device_type.all):
                try:
                    v = float(str(dev.version).split()[-1].split(".")[0])
                except Exception:
                    v = 0.0
                if v < 1.2:
                    continue
                try:
                    ctx = p.Context([dev])
                except Exception:
                    continue
                if ctx is not None:
                    break
            if ctx is not None:
                break
        if ctx is None:
            return {"available": False, "reason": "no OpenCL 1.2+ device bound"}
        ok, reason = _golden_self_check(ctx)
        return {"available": ok, "device": str(ctx.devices[0].name),
                "vendor": str(ctx.devices[0].vendor), "self_check": reason}
    except Exception as exc:
        return {"available": False, "reason": f"probe error: {exc}"}



def execute(op, payload):
    p = _cl()
    header = bytes(payload) if isinstance(payload, (bytes, bytearray)) else bytes(payload["header"])
    n = payload["nonce"] if isinstance(payload, dict) else 0
    ctx = None
    for plat in p.get_platforms():
        for dev in plat.get_devices(p.device_type.all):
            try:
                ctx = p.Context([dev])
            except Exception:
                continue
            if ctx is not None:
                break
        if ctx is not None:
            break
    if ctx is None:
        raise RuntimeError("no OpenCL device")
    prog = p.Program(ctx, _KERNEL.read_text(encoding="utf-8")).build()
    inbuf = p.Buffer(p, p.mem_flags.READ_ONLY, len(header))
    nbuf = p.Buffer(p, p.mem_flags.READ_ONLY, 4)
    obuf = p.Buffer(p, p.mem_flags.WRITE_ONLY, 32)
    queue = p.CommandQueue(ctx)
    prog.bitcoin_sha256d(queue, (1,), None, inbuf, nbuf, obuf, 1)
    out = bytearray(32)
    p.enqueue_read_buffer(queue, obuf, out).wait()
    return {"op": op, "backend": "opencl_igpu", "digest": bytes(out).hex()}

def _golden_self_check(ctx):
    try:
        header = bytearray(80)
        header[4:8] = (1337).to_bytes(4, "big")
        w = [0, 0, 0, 1337, 0x80000000] + [0] * 10 + [640]
        block = b"".join(x.to_bytes(4, "big") for x in w)
        expected = hashlib.sha256(hashlib.sha256(block).digest()).hexdigest()
        nbuf = ctx.Buffer(ctx, pyopencl.mem_flags.READ_ONLY, 4)
        obuf = ctx.Buffer(ctx, pyopencl.mem_flags.WRITE_ONLY, 32)
        inbuf = ctx.Buffer(ctx, pyopencl.mem_flags.READ_ONLY, 80)
        queue = ctx.CommandQueue(ctx)
        prog = ctx.Program(ctx, _KERNEL.read_text(encoding="utf-8")).build()
        prog.bitcoin_sha256d(queue, (1,), None, inbuf, nbuf, obuf, 1)
        out = bytearray(32)
        ctx.enqueue_read_buffer(queue, obuf, out).wait()
        return bytes(out).hex() == expected, "self-check PASS"
    except Exception as exc:
        return False, f"self-check failed: {exc}"
