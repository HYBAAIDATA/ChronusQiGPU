"""Exact reversible pair tree with independent selective unfolding.

A node stores (combined=left+right, left). Its right child is combined-left.
This explicit standalone encoding does not assert byte compression.
"""
from dataclasses import dataclass
from fractions import Fraction
import hashlib,json
@dataclass(frozen=True)
class ExactFoldState:
    count:int
    levels:tuple
    digest:str
    @classmethod
    def fold(cls, values):
        values=list(values)
        if not values or len(values)>65536 or any(not isinstance(v,(int,Fraction)) or isinstance(v,bool) for v in values):
            raise ValueError('bounded exact integers/rationals required')
        work=[Fraction(v) for v in values]; levels=[]
        while len(work)>1:
            if len(work)%2: work.append(Fraction(0))
            pairs=tuple((work[i]+work[i+1],work[i]) for i in range(0,len(work),2))
            levels.append(pairs); work=[p[0] for p in pairs]
        if not levels: levels=[((work[0],work[0]),)]
        body=cls._body(len(values),tuple(levels)); digest=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        return cls(len(values),tuple(levels),digest)
    @staticmethod
    def _body(count,levels): return {'count':count,'levels':[[[[a.numerator,a.denominator],[b.numerator,b.denominator]] for a,b in level] for level in levels]}
    def to_dict(self): return {**self._body(self.count,self.levels),'digest':self.digest,'encoding':'exact_sum_left_v1','compression_claimed':False}
    @classmethod
    def from_dict(cls,data):
        if data.get('encoding')!='exact_sum_left_v1': raise ValueError('unknown fold encoding')
        state=cls(data['count'],tuple(tuple((Fraction(*a),Fraction(*b))for a,b in level)for level in data['levels']),data['digest'])
        state.verify();return state
    def verify(self):
        if not 0<self.count<=65536 or not self.levels: raise ValueError('invalid fold shape')
        body=self._body(self.count,self.levels)
        if hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':')).encode()).hexdigest()!=self.digest: raise ValueError('fold digest mismatch')
        for lower,upper in zip(self.levels,self.levels[1:]):
            values=[p[0]for p in lower]
            if len(values)%2:values.append(Fraction(0))
            if tuple((values[i]+values[i+1],values[i])for i in range(0,len(values),2))!=upper:raise ValueError('fold parent invariant failure')
        if len(self.levels[0]) != (self.count+1)//2 or len(self.levels[-1])!=1: raise ValueError('leaf/root shape mismatch')
        expected=(self.count+1)//2
        for level in self.levels:
            if len(level)!=expected:raise ValueError('fold level shape mismatch')
            expected=(expected+1)//2
        if self.count%2 and self.levels[0][-1][0]!=self.levels[0][-1][1]:raise ValueError('nonzero padded fold leaf')
        return True
    def unfold_partial(self,indices):
        # Select only requested leaf pairs. Full reconstruction is never called.
        out=[]
        for index in indices:
            if type(index)is not int or not 0<=index<self.count:raise ValueError('fold index outside state')
            combined,left=self.levels[0][index//2];out.append(left if index%2==0 else combined-left)
        return tuple(out)
    def unfold(self):return self.unfold_partial(range(self.count))
    def scale(self,factor):
        if not isinstance(factor,(int,Fraction))or isinstance(factor,bool):raise ValueError('exact scaling factor required')
        # Operates on folded pairs directly, preserving all tree relations.
        levels=tuple(tuple((a*factor,b*factor)for a,b in level)for level in self.levels)
        body=self._body(self.count,levels);digest=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        return ExactFoldState(self.count,levels,digest)
