"""Bounded multi-timescale coordination with explicit conflict policy."""
from __future__ import annotations
import hashlib,json,time
from dataclasses import dataclass
from enum import Enum
class Timescale(str,Enum):FAST="fast";MEDIUM="medium";LONG="long"
def _key(state):return hashlib.sha256(json.dumps(state,sort_keys=True,default=str).encode()).hexdigest()
@dataclass
class TimedLayer:
 function:object;max_latency_ms:float;ttl_seconds:float=0.;cache:dict=None
 def __post_init__(self):
  if not callable(self.function) or self.max_latency_ms<=0:raise ValueError("valid layer required")
  self.cache={}
 def run(self,state):
  key=_key(state);now=time.monotonic()
  if key in self.cache and now-self.cache[key][0]<=self.ttl_seconds:return self.cache[key][1],0.,True
  start=time.perf_counter();value=self.function(state);elapsed=(time.perf_counter()-start)*1000
  if self.ttl_seconds:self.cache[key]=(now,value)
  return value,elapsed,False
class TimescaleCoordinator:
 def __init__(self,fast_layer=None,medium_layer=None,long_layer=None,max_history=1000):self.layers={Timescale.FAST:fast_layer,Timescale.MEDIUM:medium_layer,Timescale.LONG:long_layer};self.conflict_history=[];self.max_history=max_history
 def coordinate_decision(self,state,context=Timescale.MEDIUM,emergency=False):
  results={}
  for scale,layer in self.layers.items():
   if layer:
    value,elapsed,cached=layer.run(state);results[scale.value]={"value":value,"latency_ms":elapsed,"within_budget":elapsed<=layer.max_latency_ms,"cached":cached}
  values=[v["value"] for v in results.values()]
  if not values:return {"resolved":None,"reason":"no_layers"}
  conflict=any(v!=values[0] for v in values[1:]);chosen=Timescale.FAST if emergency else Timescale(context)
  if chosen.value not in results:chosen=next(scale for scale in self.layers if scale.value in results)
  if conflict:
   self.conflict_history.append({"timestamp":time.time(),"selected":chosen.value,"emergency":emergency});self.conflict_history=self.conflict_history[-self.max_history:]
  results["resolved"]={"decision":results[chosen.value]["value"],"timescale":chosen.value,"conflict":conflict};return results
