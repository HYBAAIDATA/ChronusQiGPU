import copy
from dataclasses import replace
import hashlib
import json
import subprocess
import sys

import pytest
import sympy as sp
from chronos_one_igpu import OneIGPU
from chronos_one_igpu.adapters.base import BackendAbsent
from chronos_one_igpu.m5_ultra import m5_ultra_fabric, elevate_pads
from chronos_one_igpu.igpu.m5_quantum import execute_quantum, verify_quantum, digest
from chronos_one_igpu.igpu.exact_quantum import decode_expression


@pytest.mark.parametrize('topology', ['chain', 'ring', 'full_mesh'])
@pytest.mark.parametrize('algorithm', ['exact_m5_ghz', 'exact_m5_cluster'])
def test_canonical_pad_quantum_algebra(topology, algorithm):
    model = m5_ultra_fabric(topology)
    with OneIGPU(working_width=32, prime_rom_limit=1000) as gpu:
        session = gpu.m5_resident(model=model)
        result = session.execute_quantum(algorithm)
        assert session.verify_quantum(result, algorithm)
        assert result['requested_algorithm'] == result['planned_algorithm'] == result['executed_algorithm'] == algorithm
        assert result['physical_quantum_execution'] is False
        assert result['sha256d_evaluations'] == 0
        assert result['request']['full_model_register_executed'] is False
        assert result['substrate']['kind'] == 'cpu'
        assert sum(decode_expression(p) for p in result['probabilities']) == 1
        assert all(not decode_expression(a).has(sp.Float) for a in result['amplitudes'])


def test_cluster_edges_act_as_actual_cz_gates():
    model = m5_ultra_fabric('chain')
    result = execute_quantum(model, 'exact_m5_cluster')
    # Pads 0 and 1 both set: edge(0,1) flips the exact plus-state sign.
    assert decode_expression(result['amplitudes'][3]) == -sp.Rational(1, 4)
    assert decode_expression(result['amplitudes'][1]) == sp.Rational(1, 4)
    assert result['gates'][-3:] == [['CZ', 0, 1], ['CZ', 1, 2], ['CZ', 2, 3]]


def test_ten_pad_ghz_is_not_full_model_hilbert_execution():
    model = elevate_pads(10)
    result = execute_quantum(model, 'exact_m5_ghz')
    assert len(result['amplitudes']) == 1024
    assert model.hilbert_log2_dim > 10
    assert result['iterations_work_performed']['state_dimension'] == 1024
    assert verify_quantum(result, model, 'exact_m5_ghz')


@pytest.mark.parametrize('field', ['implementation_digest', 'execution_mode', 'executed_algorithm', 'physical_quantum_execution', 'sha256d_evaluations'])
def test_resealed_identity_lies_fail(field):
    model = m5_ultra_fabric()
    result = execute_quantum(model, 'exact_m5_ghz')
    result[field] = True if field == 'physical_quantum_execution' else 1 if field == 'sha256d_evaluations' else 'substituted'
    body = dict(result); body.pop('receipt_digest'); result['receipt_digest'] = digest(body)
    with pytest.raises(ValueError):
        verify_quantum(result, model, 'exact_m5_ghz')


def test_resealed_amplitude_and_normalisation_corruption_fails():
    model = m5_ultra_fabric()
    result = execute_quantum(model, 'exact_m5_ghz')
    result['amplitudes'][0] = {'rational': [1, 1]}
    result['probabilities'][0] = {'rational': [1, 1]}
    body = dict(result); body.pop('receipt_digest'); result['receipt_digest'] = digest(body)
    with pytest.raises(ValueError, match='Born verification'):
        verify_quantum(result, model, 'exact_m5_ghz')


def test_model_or_algorithm_substitution_fails():
    model = m5_ultra_fabric('chain')
    result = execute_quantum(model, 'exact_m5_cluster')
    with pytest.raises(ValueError):
        verify_quantum(result, m5_ultra_fabric('full_mesh'), 'exact_m5_cluster')
    with pytest.raises(ValueError):
        verify_quantum(result, model, 'exact_m5_ghz')


def test_duplicate_edges_and_invalid_pad_ids_fail():
    model = m5_ultra_fabric()
    with pytest.raises(ValueError, match='duplicate'):
        execute_quantum(replace(model, links=model.links + (model.links[0],)), 'exact_m5_cluster')
    pad = replace(model.pads[1], index=True)
    with pytest.raises(ValueError):
        execute_quantum(replace(model, pads=(model.pads[0], pad, *model.pads[2:])), 'exact_m5_ghz')


def test_no_unavailable_physical_quantum_fallback():
    with OneIGPU(working_width=32, prime_rom_limit=1000) as gpu:
        with pytest.raises(BackendAbsent):
            gpu.m5_resident().execute_quantum('exact_m5_ghz', require_host_gpu=True)


def test_quantum_receipt_fresh_process_replay(tmp_path):
    result = execute_quantum(m5_ultra_fabric(), 'exact_m5_cluster')
    path = tmp_path/'quantum.json'; path.write_text(json.dumps(result))
    code = '''import json,sys
from chronos_one_igpu.m5_ultra import m5_ultra_fabric
from chronos_one_igpu.igpu.m5_quantum import verify_quantum
assert verify_quantum(json.load(open(sys.argv[1])),m5_ultra_fabric(),'exact_m5_cluster')
print('EXACT_REPLAY_VERIFIED')'''
    assert 'EXACT_REPLAY_VERIFIED' in subprocess.check_output([sys.executable, '-I', '-c', code, str(path)], text=True)


def test_cli_emits_actual_exact_execution_receipt():
    result = json.loads(subprocess.check_output([sys.executable, '-I', '-m', 'chronos_one_igpu.release_cli', 'm5-quantum', '--state', 'ghz'], text=True))
    assert verify_quantum(result, m5_ultra_fabric(), 'exact_m5_ghz')
