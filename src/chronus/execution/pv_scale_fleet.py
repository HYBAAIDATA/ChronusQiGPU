"""Fleet kernel for structural PV scaling, shared by HYBA workload consumers.

Registered by default on the coordinator and every worker. Residue pairs
use little-endian uint16 wire storage. The original index remains a decimal
string in work parameters and receipts; only the field factor is reduced.
"""
import re
import struct

from chronus.backends.pv_field import scale_pairs
from chronus.core.scaling import PVScale
from chronus.fleet.errors import KernelError
from chronus.fleet.kernels import Kernel, KnownAnswer, Prepared, MAX_WORK_UNIT_BYTES


class PVFieldScaleKernel(Kernel):
    name = 'pv_field_scale'
    description = 'Exact structural phi**scale_index multiplication in F_257[phi].'

    def prepare(self, params, payload):
        if set(params) != {'scale_index'}:
            raise KernelError('pv_field_scale requires only scale_index')
        index = params['scale_index']
        if not isinstance(index, str) or len(index) > 4096 or not re.fullmatch(r'0|[1-9][0-9]*', index):
            raise KernelError('scale_index must be a canonical nonnegative decimal string (max4096 digits)')
        if not isinstance(payload, (bytes, bytearray)) or not payload or len(payload) % 4 or len(payload) > MAX_WORK_UNIT_BYTES:
            raise KernelError('payload must contain nonempty little-endian uint16 residue pairs')
        if any(a > 256 or b > 256 for a, b in struct.iter_unpack('<HH', payload)):
            raise KernelError('residues must be in [0,256]')
        return Prepared({'scale_index': index}, bytes(payload), len(payload)//4)

    def tile_input(self, prepared, start, stop):
        return prepared.payload[4*start:4*stop]

    def run_reference(self, ctx, params, tile, start, stop):
        pairs = scale_pairs(list(struct.iter_unpack('<HH', tile)), int(params['scale_index']))
        return b''.join(struct.pack('<HH', *pair) for pair in pairs)

    def run_simd(self, ctx, params, tile, start, stop):
        import numpy as np
        pairs = np.frombuffer(tile, dtype='<u2').reshape(-1,2).astype(np.uint32)
        c,d = PVScale(int(params['scale_index'])).field_factor()
        a,b = pairs[:,0], pairs[:,1]
        out = np.stack(((a*c+b*d)%257, (a*d+b*c+b*d)%257), axis=1)
        return out.astype('<u2').tobytes()

    def run_opencl(self, ctx, params, tile, start, stop):
        return ctx.pv_field_scale(tile, int(params['scale_index']))

    def run_metal(self, ctx, params, tile, start, stop):
        return ctx.pv_field_scale(tile, int(params['scale_index']))

    def accepts(self, route, ctx, params, tile, start, stop):
        if route in ('opencl','metal') and 'pv_field_scale' not in getattr(ctx, 'ops', ()):
            return f'{route} engine has no pv_field_scale operation'
        return super().accepts(route, ctx, params, tile, start, stop)

    def known_answers(self):
        payload = struct.pack('<8H', 1,0, 256,256, 0,1, 128,256)
        return tuple(KnownAnswer('scale-'+index, {'scale_index':index}, payload, digest)
                     for index,digest in _KNOWN_ANSWERS)


_KNOWN_ANSWERS = (('10000', 'b48ac868eb05ebfdfcd24038c699b0908f50f8ca17ffce132cd0de16d0db66a2'), ('100000', '753797b1aa6e148f0cb2d34ded3d5e880cd04abeaf2f0680f48a9141954574f3'), ('1000000000000', '28a83ed75c2840df14e781b0945122e6a798dc383e61cce2de88b2a7d7f40af7'), ('1000000000000000', 'd8874bbb5481705d10318483b0988758fe6f515f7d4b6933fdf265fc6f314deb'), ('1000000000000000000', 'b23dfd2aa2892d1e440593d719fe665bbd80a668b50c178af0e1e5fc23445ad9'), ('100000000000000000000', '8ff60f0f192bbaf9506e76d5599b372201ee85182e112198853e1af08845c31a'))
