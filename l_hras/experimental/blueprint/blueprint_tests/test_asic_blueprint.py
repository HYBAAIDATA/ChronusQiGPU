from __future__ import annotations
import numpy as np
from l_hras.experimental.blueprint.asic.types import *
from l_hras.experimental.blueprint.asic.capability import ASICCapability
from l_hras.experimental.blueprint.asic.hash import Job, Share, asic_hash, sha256d
from l_hras.experimental.blueprint.asic.fold import Vector11D, asic_fold, fold_11d, unfold_11d
from l_hras.experimental.blueprint.asic.intelligences import IntelligenceType, run_all_intelligences
from l_hras.experimental.blueprint.asic.modes import run_all_modes, stand
from l_hras.experimental.blueprint.asic.attestation import AethelStore, asic_attest
from l_hras.experimental.blueprint.asic.boundary import asic_guard
from l_hras.experimental.blueprint.asic.workflow import asic_mine
from l_hras.experimental.blueprint.asic.probe import probe_asic


def capability(fold=True):
    d=Distribution(1.0,0.0,1,1.0,1.0,1.0)
    cap=ASICCapability('asic-1','vendor','model','firmware',Technology.CONVENTIONAL_CMOS,
        DeviceClass.ASIC_QUANTUM_ARMED if fold else DeviceClass.ASIC_CLASSIC,
        d,d,d,fold,100 if fold else 0,{KernelName.SHA256D_SCAN},DeviceState.PRESENT,[{'root':'x'}])
    cap.aethel_store=AethelStore(); cap.id=cap.device_id; cap.paths=['network','serial']
    return cap


class Circuit:
    def __init__(self, clifford=True):
        self.vector=Vector11D(np.linspace(-0.4,0.4,11)); self.clifford=clifford
    def is_permutation(self): return True
    def is_clifford(self): return self.clifford


def job(circuit=None,qubits=0):
    return Job('j',b'\0'*80,b'\xff'*32,[0,1,2],circuit,qubits)


def test_fold_roundtrip_and_limits():
    x=Vector11D(np.linspace(-0.4,0.4,11)); y=fold_11d(x); back=unfold_11d(y)
    assert isinstance(back,Ok) and np.allclose(back.value.components,x.components,atol=1e-14)
    assert isinstance(asic_fold(capability(),job(Circuit(),101)),Err)


def test_hash_is_double_sha_and_target_checked():
    j=job(); result=asic_hash(capability(False),j)
    assert isinstance(result,Ok)
    header=bytearray(j.header);header[76:80]=result.value.nonce.to_bytes(4,'little')
    assert result.value.hash==sha256d(bytes(header)) and result.value.hash[::-1] < j.target


def test_boundary_is_explicit():
    assert asic_guard(capability(False),job()).value.path=='classic'
    assert asic_guard(capability(),job(Circuit(),10)).value.path=='fold'
    assert isinstance(asic_guard(capability(),job(Circuit(),101)),Err)


def test_six_intelligences_and_measurement():
    ei=run_all_intelligences(capability(),job())
    assert len(ei.states)==6 and len(ei.entanglement)==15
    ei.measure(IntelligenceType.PREDICTIVE,1)
    assert all(np.allclose(s.amplitudes,[0,1]) for s in ei.states.values())


def test_five_modes_stand_and_execute():
    cap=capability(); assert all(vars(stand(cap)).values())
    modes=run_all_modes(cap,job())
    assert set(modes)=={'multiply','entangle','swarm','honey_pot','willow_expose'}
    assert modes['multiply'].cardinality==64


def test_attestation_and_coordinated_forgery_detection():
    cap=capability(); folded=asic_fold(cap,job(Circuit(),10)).value
    share=asic_hash(cap,job()).value
    result=asic_attest(cap,job(),share,folded.certificate)
    assert isinstance(result,Ok)
    key=result.value['aethel_key']; assert cap.aethel_store.verify_replay(key)
    cap.aethel_store.blocks[key].digest='forged'; cap.aethel_store.ledger[key]='forged'
    assert not cap.aethel_store.verify_replay(key)


def test_complete_workflow_classic_and_fold():
    assert isinstance(asic_mine(capability(False),job()),Ok)
    assert isinstance(asic_mine(capability(),job(Circuit(),10)),Ok)


def test_probe_measures_and_declares_fold():
    class Firmware:
        digest='fw'
        def supports_fold(self): return True
        def max_fold_qubits(self): return 20
    class Device:
        id='d';vendor='v';model='m';firmware=Firmware();technology=Technology.CONVENTIONAL_CMOS
        def run_hash_benchmark(self,duration): return 100
        def read_power(self): return 10.0
        def build_attestation_chain(self): return [{'firmware':'fw'}]
    result=probe_asic(Device())
    assert isinstance(result,Ok) and result.value.fold_capable
    assert result.value.hashrate.mean > 0 and result.value.attestation_chain
