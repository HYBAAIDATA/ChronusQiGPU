"""Five fail-closed diagnostic gates. CI attestation is separately mandatory."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable
from chronus.verdict import GateResult,Status
from chronus.crypto.signers import ml_dsa_available,SignerUnavailable
from chronus.chain import Chain,verify_chain,receipt_hash,GENESIS,ChainBroken
from chronus.canon import canonical_bytes

@dataclass(frozen=True)
class Fixture:
    chain:Chain|None
    receipts:list[dict]
    inner_pk:bytes
    outer_pk:bytes
    provider:object

def _result(gate:str,status:Status,detail:str="")->GateResult:
    return GateResult(gate,status,detail)

def dual_signature(fx:Fixture)->GateResult:
    name="CO-SIGN"
    if not ml_dsa_available():
        return _result(name,Status.UNQUALIFIED,"ML-DSA-65 provider unavailable")
    if not fx.receipts:
        return _result(name,Status.UNQUALIFIED,"no receipts")
    try:
        verify_chain(fx.receipts,fx.inner_pk,fx.outer_pk)
    except SignerUnavailable as exc:
        return _result(name,Status.UNQUALIFIED,str(exc))
    except ChainBroken as exc:
        return _result(name,Status.FAIL,str(exc))
    return _result(name,Status.PASS)

def receipt_integrity(fx:Fixture)->GateResult:
    name="RS-RECEIPT"
    if not fx.receipts:
        return _result(name,Status.UNQUALIFIED,"no receipt fixture")
    try:
        verify_chain(fx.receipts,fx.inner_pk,fx.outer_pk)
        changed=[dict(r) for r in fx.receipts]
        changed[0]={**changed[0],"payload":{"tampered":True}}
        try:
            verify_chain(changed,fx.inner_pk,fx.outer_pk)
        except ChainBroken:
            return _result(name,Status.PASS)
        return _result(name,Status.FAIL,"tamper accepted")
    except SignerUnavailable as exc:
        return _result(name,Status.UNQUALIFIED,str(exc))
    except ChainBroken as exc:
        return _result(name,Status.FAIL,str(exc))

def replay(fx:Fixture)->GateResult:
    name="RS-REPLAY"
    if len(fx.receipts)<3:
        return _result(name,Status.UNQUALIFIED,"need at least 3 receipts")
    try:
        verify_chain(fx.receipts,fx.inner_pk,fx.outer_pk)
        reordered=list(fx.receipts)
        reordered[1],reordered[2]=reordered[2],reordered[1]
        try:
            verify_chain(reordered,fx.inner_pk,fx.outer_pk)
        except ChainBroken:
            return _result(name,Status.PASS)
        return _result(name,Status.FAIL,"reordered chain accepted")
    except SignerUnavailable as exc:
        return _result(name,Status.UNQUALIFIED,str(exc))
    except ChainBroken as exc:
        return _result(name,Status.FAIL,str(exc))

def claims(fx:Fixture)->GateResult:
    return _result("FN-CLAIMS",Status.UNQUALIFIED,"independent attested claims audit not yet integrated")

def custody(fx:Fixture)->GateResult:
    return _result("FN-CUSTODY",Status.UNQUALIFIED,"Azure Managed HSM live sign and authorization evidence unavailable")

GATES:tuple[Callable[[Fixture],GateResult],...]=(dual_signature,receipt_integrity,replay,claims,custody)
