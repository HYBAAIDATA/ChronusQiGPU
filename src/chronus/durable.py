"""Append only after synchronous fsync; resume only after signed replay."""
from __future__ import annotations
import json
import threading
from dataclasses import dataclass,field
from typing import Any
from chronus.canon import canonical_bytes
from chronus.chain import Chain,GENESIS,receipt_hash,verify_chain
from chronus.journal import Journal

@dataclass
class DurableChain:
    journal:Journal
    chain:Chain
    _seq:int=0
    _prev:str=GENESIS
    _lock:Any=field(default_factory=threading.Lock)

    def resume(self,inner_pk:bytes,outer_pk:bytes)->None:
        with self._lock:
            receipts=[json.loads(raw) for raw in self.journal.records]
            if receipts:
                verify_chain(receipts,inner_pk,outer_pk)
            self._seq=len(receipts)
            self._prev=receipt_hash(receipts[-1]) if receipts else GENESIS

    def append(self,payload:dict[str,Any])->dict[str,Any]:
        with self._lock:
            receipt=self.chain.seal(self._seq,self._prev,payload)
            self.journal.append(canonical_bytes(receipt))
            self._seq+=1
            self._prev=receipt_hash(receipt)
            return receipt
