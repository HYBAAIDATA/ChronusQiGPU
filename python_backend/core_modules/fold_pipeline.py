"""Persistent exact folded-object execution and proof boundary."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from fractions import Fraction
import hashlib,hmac,json,sqlite3
from typing import Iterable
from .math_folding import PulviniFold,pulvini_fold

class UnsupportedPairing(ValueError): pass
@dataclass(frozen=True)
class OperatorContract:
    name:str; families:tuple[str,...]; mode:str; deterministic:bool=True
REGISTRY={
 "pulvini_roundtrip":OperatorContract("pulvini_roundtrip",("fibonacci","rational"),"PRESERVE"),
 "sum_exact":OperatorContract("sum_exact",("fibonacci","rational"),"REHYDRATE"),
}
def _frac(v:Fraction): return [v.numerator,v.denominator]
def _canonical(v): return json.dumps(v,sort_keys=True,separators=(",",":")).encode()
class FoldPipeline:
    def __init__(self,path:str,proof_key:bytes):
        if len(proof_key)<32: raise ValueError("proof key must be at least 32 bytes")
        self.key=proof_key; self.db=sqlite3.connect(path)
        self.db.execute("CREATE TABLE IF NOT EXISTS folded_objects(object_id TEXT PRIMARY KEY,family TEXT NOT NULL,exact_json TEXT NOT NULL,folded_json TEXT NOT NULL,residual_json TEXT NOT NULL,lineage_json TEXT NOT NULL)"); self.db.commit()
    def put_folded(self,values:Iterable[int|Fraction],*,family:str="rational",lineage:tuple[str,...]=()):
        exact=tuple(Fraction(v) for v in values); folded=pulvini_fold(exact)
        body={"family":family,"exact":[_frac(v) for v in exact],"folded":[[_frac(a),_frac(b)] for a,b in folded.pairs],"residual":[],"lineage":list(lineage)}
        oid=hashlib.sha256(_canonical(body)).hexdigest()
        with self.db:self.db.execute("INSERT OR IGNORE INTO folded_objects VALUES(?,?,?,?,?,?)",(oid,family,json.dumps(body["exact"]),json.dumps(body["folded"]),"[]",json.dumps(body["lineage"])))
        return oid
    def execute(self,object_id:str,operator:str):
        op=REGISTRY.get(operator)
        if not op: raise UnsupportedPairing("unknown operator")
        row=self.db.execute("SELECT family,exact_json,folded_json,lineage_json FROM folded_objects WHERE object_id=?",(object_id,)).fetchone()
        if not row: raise KeyError(object_id)
        family,exact_json,folded_json,lineage_json=row
        if family not in op.families: raise UnsupportedPairing(f"{operator} does not accept {family}")
        exact=tuple(Fraction(n,d) for n,d in json.loads(exact_json))
        pairs=tuple((Fraction(*a),Fraction(*b)) for a,b in json.loads(folded_json))
        reconstructed=PulviniFold(pairs,len(exact)).unfold()
        if reconstructed!=exact: raise ValueError("folded object failed exact reconstruction")
        output=reconstructed if op.mode=="PRESERVE" else sum(reconstructed,Fraction(0))
        proof_body={"object_id":object_id,"operator":operator,"input_hash":hashlib.sha256(exact_json.encode()).hexdigest(),"output":str(output),"deterministic":op.deterministic,"rehydrated":op.mode=="REHYDRATE"}
        proof={**proof_body,"signature":hmac.new(self.key,_canonical(proof_body),hashlib.sha256).hexdigest()}
        return {"output":output,"proof":proof,"lineage":tuple(json.loads(lineage_json))+(hashlib.sha256(_canonical(proof)).hexdigest(),)}
