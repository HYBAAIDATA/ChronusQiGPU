# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""Exact PV scaling through fleet tiles, signed receipts and device routes."""
import hashlib
import struct

import pytest
from chronus.execution.pv_scale_fleet import PVFieldScaleKernel
from chronus.fleet.errors import KernelError
from chronus.fleet import FleetExecutor, WorkUnit


def recurrence(payload, index):
    pairs = list(struct.iter_unpack('<HH', payload))
    for _ in range(index % 516):
        pairs = [(b, (a+b)%257) for a,b in pairs]
    return b''.join(struct.pack('<HH', *pair) for pair in pairs)


@pytest.mark.parametrize('index', [10**4,10**5,10**12,10**15,10**18,10**20])
def test_pinned_answers_and_all_igpu_tiles(index):
    kernel = PVFieldScaleKernel()
    answer = next(a for a in kernel.known_answers() if a.params['scale_index'] == str(index))
    expected = recurrence(answer.payload, index)
    assert hashlib.sha256(expected).hexdigest() == answer.output_sha256
    prepared = kernel.prepare(answer.params, answer.payload)
    assert prepared.params['scale_index'] == str(index)
    for route in ('reference','simd','igpu'):
        outputs = [kernel.implementation(route)(None,prepared.params,kernel.tile_input(prepared,i,i+1),i,i+1)
                   for i in range(prepared.items)]
        assert kernel.merge(prepared.params, outputs) == expected


@pytest.mark.parametrize('params,payload', [
    ({'scale_index':10**20},struct.pack('<HH',1,0)),
    ({'scale_index':'01'},struct.pack('<HH',1,0)),
    ({'scale_index':'-1'},struct.pack('<HH',1,0)),
    ({'scale_index':'1.5'},struct.pack('<HH',1,0)),
    ({'scale_index':'0'},struct.pack('<HH',257,0)),
    ({'scale_index':'0'},b'\x00\x00'),
])
def test_invalid_wire_format_fails_closed(params,payload):
    with pytest.raises(KernelError):
        PVFieldScaleKernel().prepare(params,payload)


def test_embedded_fleet_dispatch_and_signed_receipt_keep_full_scale(tmp_path):
    index = 10**20
    payload = struct.pack('<8H',256,256,1,0,0,1,128,256)
    with FleetExecutor.embedded(tmp_path/'fleet', local_workers=1,
                                worker_routes=['simd','reference'],measure=False) as fleet:
        unit = WorkUnit(kernel='pv_field_scale',params={'scale_index':str(index)},payload=payload,route='simd')
        result = fleet.submit(unit, timeout=30)
        assert result.output == recurrence(payload,index)
        assert result.verified
        # The receipt binds the complete WorkUnit, including unreduced index.
        assert str(index) in str(result.receipt)
