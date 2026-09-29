"""Independent checkpoint witness with mandatory external anchoring."""
from __future__ import annotations
from dataclasses import asdict, dataclass, replace
import json, time
from typing import Callable, Iterable

class WitnessError(RuntimeError): pass
@dataclass(frozen=True)
class WitnessReceipt:
    subject_hash:str; chain_head:int; epoch:int; witness_identity:str; signed_at:int; signature:str=""; external_anchor:str|None=None
    def canonical(self)->bytes:
        v=asdict(self); v["signature"]=""; v["external_anchor"]=None
        return json.dumps(v,sort_keys=True,separators=(",",":")).encode()

def anchor_checkpoint(*,subject_hash:str,chain_head:int,epoch:int,witness_identity:str,signer:Callable[[bytes],str],anchors:Iterable[Callable[[WitnessReceipt],str|None]],now:int|None=None)->WitnessReceipt:
    receipt=WitnessReceipt(subject_hash,chain_head,epoch,witness_identity,int(time.time() if now is None else now))
    receipt=replace(receipt,signature=signer(receipt.canonical()))
    for anchor in anchors:
        reference=anchor(receipt)
        if reference: return replace(receipt,external_anchor=reference)
    raise WitnessError("no independent external anchor accepted checkpoint")

def verify_chain_against_witness(chain_hash_at:Callable[[int],str],receipts:Iterable[WitnessReceipt],verify_signature:Callable[[bytes,str,str],bool])->bool:
    for receipt in receipts:
        if not receipt.external_anchor or chain_hash_at(receipt.chain_head)!=receipt.subject_hash: return False
        if not verify_signature(receipt.canonical(),receipt.signature,receipt.witness_identity): return False
    return True
