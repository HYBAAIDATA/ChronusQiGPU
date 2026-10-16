"""Prime-gap address metadata over finite, durable PRIME-DB."""
import hashlib
from .constants import GoldenConstants
from .data_folding import DataFoldingEngine
class TransfiniteMemoryMapper:
    MAX_INDEX = 10000
    def address(self, index):
        if type(index) is not int or not 0 <= index < self.MAX_INDEX: raise ValueError("index exceeds finite prime table policy")
        left = GoldenConstants.prime(index + 1); right = GoldenConstants.prime(index + 2)
        return {"index": index, "left_prime": left, "right_prime": right, "gap": right-left, "physical_storage": True}
    def checkpoint(self, db, data, index=0):
        addr = self.address(index)
        compressed = DataFoldingEngine().fold(data)
        return db.put({"schema": "golden_checkpoint_v1", "address": addr, "compressed_hex": compressed.hex(),
                       "sha256": hashlib.sha256(data).hexdigest(), "raw_bytes": len(data), "stored_bytes": len(compressed)},
                       index+1, family="golden_checkpoint")
    def restore(self, db, object_id):
        payload = db.get(object_id).payload
        if payload.get("schema") != "golden_checkpoint_v1": raise ValueError("wrong checkpoint schema")
        out = DataFoldingEngine().unfold(bytes.fromhex(payload["compressed_hex"]))
        if len(out) != payload["raw_bytes"] or hashlib.sha256(out).hexdigest() != payload["sha256"]: raise ValueError("checkpoint integrity failure")
        return out

    def logical_address(self,index):
        if type(index)is not int or index<0:raise ValueError('nonnegative logical index required')
        if index<self.MAX_INDEX:return self.address(index)
        return {'index':str(index),'left_prime_expression':f'prime({index+1})','right_prime_expression':f'prime({index+2})',
                'encoding':'symbolic_prime_gap','physical_storage_allocated':False,'resolved':False}
