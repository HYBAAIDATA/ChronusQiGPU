"""Domain-agnostic resonance intelligence and empirical A/B validation."""
from __future__ import annotations

import math
import time
import warnings
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Generator, Iterator

import numpy as np

from core.constants import DELTA, PHI, PHI_I

try:  # optional only
    from scipy.stats import ks_2samp
except ImportError:  # pragma: no cover
    ks_2samp=None


@dataclass
class CausalTrace:
    trace_vector:list[float]=field(default_factory=list)
    block_height_at_last_update:int=0
    total_blocks_experienced:int=0
    causal_depth:float=0.0
    continuity_score:float=0.0
    last_hashrate:float=1.0

    def update(self,current_resonance:float,block_height:int=0,max_trace_length:int=1000,
               network_hashrate:float=1.0)->None:
        if max_trace_length<=0: raise ValueError("max_trace_length must be positive")
        current=float(np.clip(current_resonance,0,1)); self.last_hashrate=max(0,float(network_hashrate))
        self.trace_vector=[PHI_I*value for value in self.trace_vector]
        self.trace_vector.append((1-PHI_I)*current)
        self.trace_vector=self.trace_vector[-max_trace_length:]
        if block_height>self.block_height_at_last_update:
            self.total_blocks_experienced+=block_height-self.block_height_at_last_update
            self.block_height_at_last_update=block_height
        total=sum(abs(v) for v in self.trace_vector)
        self.causal_depth=-math.log(min(abs(self.trace_vector[-1])/total,1)+1e-12) if total else 0
        recent=self.trace_vector[-20:]
        if len(recent)>=2:
            self.continuity_score=max(0.0,1-sum(abs(b-a) for a,b in zip(recent,recent[1:]))/(len(recent)-1)*10)

    def get_temporal_phi(self)->float:
        if not self.trace_vector:return 0.0
        values=np.abs(np.asarray(self.trace_vector,float)); total=float(values.sum())
        if total<1e-12:return 0.0
        probabilities=values/total; n=len(values)
        divergence=float(np.sum(probabilities*np.log((probabilities+1e-15)*n)))
        return float(np.clip(divergence/(math.log(n) if n>1 else 1),0,1))


@dataclass
class ResonanceProfile:
    resonance_score:float
    phi_drivers:list[dict[str,Any]]
    coherence_trajectory:list[float]
    steering_signals:list[str]
    confidence:float
    spectral_coherence:float
    tunneling_probability:float
    domain_entropy:float
    curvature_volatility:float
    causal_trace:CausalTrace=field(default_factory=CausalTrace)
    model_version:str="6.1.0"
    timestamp:float=field(default_factory=time.time)


@dataclass(frozen=True)
class ABTestResult:
    n_samples:int
    intelligence_resonance_mean:float
    random_resonance_mean:float
    lift:float
    ks_statistic:float
    p_value:float
    spectral_peak_to_mean_ratio:float
    intelligence_domain_entropy:float
    random_domain_entropy:float
    significant:bool
    summary:str


def _safe_mean(values:list[float])->float:return float(np.mean(values)) if values else 0.0
def _safe_std(values:list[float])->float:return float(np.std(values)) if len(values)>1 else 0.0

def _entropy(values:list[float])->float:
    arr=np.asarray(values,float); arr=arr[arr>0]
    if not len(arr):return 0.0
    arr/=arr.sum(); return float(-np.sum(arr*np.log(arr)))

def _ewma(values:list[float],alpha:float=.3)->list[float]:
    if not values:return []
    result=[float(values[0])]
    for value in values[1:]:result.append(alpha*float(value)+(1-alpha)*result[-1])
    return result

def _spectral_peak_to_mean(signal:list[float])->float:
    if len(signal)<4:return 1.0
    arr=np.asarray(signal,float); magnitude=np.abs(np.fft.rfft(arr-arr.mean()))
    return float(magnitude.max()/magnitude.mean()) if magnitude.mean()>0 else 1.0

def _chunked(values:list[Any],size:int)->Iterator[list[Any]]:
    if size<=0:raise ValueError("chunk size must be positive")
    for index in range(0,len(values),size):yield values[index:index+size]


class ResonanceIntelligence:
    def __init__(self,config:dict[str,Any]|None=None):
        self.config=dict(config or {})
        self._chunk_size=int(self.config.get("chunk_size",50_000))
        self._ewma_alpha=float(self.config.get("ewma_alpha",.3))
        self._threshold=float(self.config.get("resonance_threshold",PHI_I))
        if self._chunk_size<=0 or not 0<self._ewma_alpha<=1 or not 0<=self._threshold<=1:
            raise ValueError("invalid chunk, EWMA, or threshold configuration")
        self._resonance_history:list[float]=[]; self._coherence_history:list[float]=[]
        self._telemetry_buffer:list[dict[str,Any]]=[]; self._profile_calls=0; self._profile_total_ms=0.0
        self._causal_trace=CausalTrace()

    def generate_resonance_profile(self,telemetry_data:dict[str,Any])->ResonanceProfile:
        started=time.perf_counter(); self._profile_calls+=1
        with _suppress_harmless_warnings():
            try:
                features=self._extract_features(telemetry_data)
                score=self._compute_resonance_score(features,record=True)
                drivers=self._compute_feature_importance(features)
                trajectory=self._forecast_trajectory(score)
                signals=self._generate_steering_signals(score,features,drivers)
                self._causal_trace.update(score,int(telemetry_data.get("block_height",0)),
                                          network_hashrate=float(telemetry_data.get("network_hashrate",1)))
                profile=ResonanceProfile(score,drivers,trajectory,signals,features["confidence"],
                    features["spectral_coherence"],features["tunneling_probability"],
                    features["domain_entropy"],features["curvature_volatility"],self._causal_trace)
            except Exception:
                profile=self._neutral_profile()
        self._profile_total_ms+=(time.perf_counter()-started)*1000
        return profile

    def process_large_dataset(self,telemetry_rows:list[dict[str,Any]],chunk_size:int|None=None)->list[ResonanceProfile]:
        size=self._chunk_size if chunk_size is None else int(chunk_size)
        return [self.generate_resonance_profile(row) for chunk in _chunked(telemetry_rows,size) for row in chunk]

    def run_ab_test(self,intelligence_telemetry:list[dict[str,Any]],random_telemetry:list[dict[str,Any]])->ABTestResult:
        if not intelligence_telemetry or not random_telemetry:raise ValueError("both A/B groups must be non-empty")
        # Isolated engines prevent one group history from contaminating the other.
        intel_engine=ResonanceIntelligence(self.config); random_engine=ResonanceIntelligence(self.config)
        intel=[intel_engine.generate_resonance_profile(row) for row in intelligence_telemetry]
        random=[random_engine.generate_resonance_profile(row) for row in random_telemetry]
        im,rm=_safe_mean([p.resonance_score for p in intel]),_safe_mean([p.resonance_score for p in random])
        lift=(im-rm)/(rm+1e-12)*100
        a=[float(v) for row in intelligence_telemetry for v in row.get("curvature_values",[0])]
        b=[float(v) for row in random_telemetry for v in row.get("curvature_values",[0])]
        stat,p=self._ks_test(a,b); significant=bool(p<.05 and lift>0)
        summary=f"phi-guided lift: {lift:+.1f}% KS={stat:.4f} p={p:.4f} {'SIGNIFICANT' if significant else 'not significant'}"
        return ABTestResult(min(len(intel),len(random)),im,rm,lift,stat,p,
            _safe_mean([x.spectral_coherence for x in intel]),_safe_mean([x.domain_entropy for x in intel]),
            _safe_mean([x.domain_entropy for x in random]),significant,summary)

    def _extract_features(self,data:dict[str,Any])->dict[str,float]:
        res=[float(x) for x in data.get("resonance_values",[])]; curv=[float(x) for x in data.get("curvature_values",[])]
        domains=[float(x) for x in data.get("domain_counts",[])]; spectral=[float(x) for x in data.get("spectral_data",[])]
        tunnel=[int(x) for x in data.get("tunneling_events",[])]
        if any(not math.isfinite(x) for group in (res,curv,domains,spectral) for x in group):raise ValueError("non-finite telemetry")
        if any(x<0 for x in domains):raise ValueError("domain counts must be nonnegative")
        domain_entropy=_entropy(domains) if domains else math.log(32)
        concentration=.5
        if sum(domains)>0:
            probs=np.asarray(domains)/sum(domains); concentration=float(1-min(1,np.var(probs)*len(probs)))
        n=max(len(res),len(curv),1)
        return {"resonance_mean":_safe_mean(res),"resonance_std":_safe_std(res),"resonance_trend":self._linear_trend(res),
            "spectral_coherence":_spectral_peak_to_mean(spectral or res),
            "tunneling_probability":sum(tunnel)/len(tunnel) if tunnel else 0.0,
            "domain_entropy":domain_entropy,"curvature_volatility":float(np.var(curv)) if curv else 0.0,
            "delta_normalized_curv":_safe_mean(curv)/(DELTA+1e-12),
            "phi_beatty_alignment":sum(x>=PHI_I for x in res)/len(res) if res else 0.0,
            "concentration":concentration,"confidence":min(.95,.5+.45*(1-math.exp(-n/1000)))}

    def _compute_resonance_score(self,f:dict[str,float],record:bool=False)->float:
        weights=(PHI**-1,PHI**-2,PHI**-3,PHI**-1,PHI**-2,.1)
        raw=(weights[0]*f["resonance_mean"]+weights[1]*min(f["spectral_coherence"]/10,1)+
             weights[2]*f["tunneling_probability"]+weights[3]*f["phi_beatty_alignment"]+
             weights[4]*f["concentration"]+weights[5]*np.clip(f["resonance_trend"]*10,-1,1))/sum(weights)
        score=float(np.clip(raw,0,1))
        if record:
            self._resonance_history.append(score); self._resonance_history=self._resonance_history[-10_000:]
        return score

    def _compute_feature_importance(self,features:dict[str,float])->list[dict[str,Any]]:
        result=[]; sigma=.05
        for name,value in features.items():
            if name=="confidence":continue
            plus=dict(features);minus=dict(features);plus[name]=value+sigma;minus[name]=value-sigma
            gradient=(self._compute_resonance_score(plus)-self._compute_resonance_score(minus))/(2*sigma)
            result.append({"feature":name,"value":value,"importance":round(abs(gradient),4),
                           "direction":"positive" if gradient>0 else "negative" if gradient<0 else "neutral"})
        return sorted(result,key=lambda x:x["importance"],reverse=True)[:6]

    def _forecast_trajectory(self,current:float,n_steps:int=5)->list[float]:
        smooth=_ewma(self._resonance_history[-20:] or [current],self._ewma_alpha); trend=self._linear_trend(smooth[-10:])
        return smooth[-10:]+[float(np.clip(smooth[-1]+trend*i,0,1)) for i in range(1,n_steps+1)]

    @staticmethod
    def _linear_trend(values:list[float])->float:
        if len(values)<2:return 0.0
        x=np.arange(len(values),dtype=float); y=np.asarray(values,float); denominator=float(np.sum((x-x.mean())**2))
        return float(np.sum((x-x.mean())*(y-y.mean()))/denominator) if denominator else 0.0

    def _generate_steering_signals(self,score:float,f:dict[str,float],drivers:list[dict[str,Any]])->list[str]:
        signals=["increase_exploration: resonance critically low" if score<.4 else
                 "widen_domain_bias: resonance below phi inverse threshold" if score<self._threshold else
                 "maintain_exploitation: phi-resonant state confirmed"]
        if f["spectral_coherence"]>5:signals.append("spectral_coherence_high: tighten quality threshold")
        elif f["spectral_coherence"]<1.5:signals.append("spectral_coherence_low: increase tunneling rate")
        if f["domain_entropy"]>math.log(24):signals.append("high_entropy: redistribute domain bias")
        elif f["domain_entropy"]<math.log(8):signals.append("low_entropy: broaden search")
        if f["curvature_volatility"]>.5:signals.append("high_curvature_volatility: reduce retraction step")
        if f["tunneling_probability"]<.05:signals.append("low_tunneling: consider Delta-15 gap level")
        if drivers and drivers[0]["importance"]>.1:signals.append(f"key_driver={drivers[0]['feature']}")
        return signals

    @staticmethod
    def manifold_tsp_seed(domain_resonance:list[float],n_cities:int|None=None)->list[int]:
        if not domain_resonance:return []
        values=np.asarray(domain_resonance,float); limit=len(values) if n_cities is None else max(0,min(int(n_cities),len(values)))
        if limit==0:return []
        available=set(range(len(values))); current=int(np.argmax(values)); tour=[current];available.remove(current)
        while available and len(tour)<limit:
            current=max(available,key=lambda j:values[j]/PHI**(abs(j-tour[-1])/len(values)))
            tour.append(current);available.remove(current)
        return tour

    @staticmethod
    def hash_collision_density(hash_values:list[int],n_buckets:int=256)->dict[str,float|int]:
        if n_buckets<=0:raise ValueError("n_buckets must be positive")
        if not hash_values:return {"collision_rate":0.0,"max_bucket_density":0.0,"phi_resonant_buckets":0,"entropy":0.0}
        counts=[0]*n_buckets
        for value in hash_values:counts[int(value)%n_buckets]+=1
        densities=[count/len(hash_values) for count in counts]
        return {"collision_rate":sum(count>1 for count in counts)/n_buckets,"max_bucket_density":max(densities),
                "phi_resonant_buckets":sum(value>=PHI_I/n_buckets for value in densities),"entropy":_entropy(densities)}

    @staticmethod
    def _ks_test(a:list[float],b:list[float])->tuple[float,float]:
        if not a or not b:return 0.0,1.0
        if ks_2samp is not None:
            result=ks_2samp(a,b);return float(result.statistic),float(result.pvalue)
        aa=np.sort(a);bb=np.sort(b);combined=np.sort(np.concatenate([aa,bb]))
        statistic=float(np.max(abs(np.searchsorted(aa,combined,side="right")/len(aa)-np.searchsorted(bb,combined,side="right")/len(bb))))
        effective=len(aa)*len(bb)/(len(aa)+len(bb));return statistic,min(1.0,2*math.exp(-2*effective*statistic**2))

    def get_profiling_stats(self)->dict[str,float|int]:
        return {"total_calls":self._profile_calls,"total_ms":self._profile_total_ms,
                "avg_ms_per_call":self._profile_total_ms/max(1,self._profile_calls)}
    def reset_history(self)->None:self._resonance_history.clear();self._coherence_history.clear();self._telemetry_buffer.clear()
    @staticmethod
    def _neutral_profile()->ResonanceProfile:
        return ResonanceProfile(.5,[],[.5],["fallback: neutral profile returned due to error"],0,1,0,math.log(32),0)


@contextmanager
def _suppress_harmless_warnings()->Generator[None,None,None]:
    with warnings.catch_warnings():warnings.simplefilter("ignore",RuntimeWarning);yield

def generate_resonance_profile(telemetry_data:dict[str,Any],config:dict[str,Any]|None=None)->ResonanceProfile:
    return ResonanceIntelligence(config).generate_resonance_profile(telemetry_data)


__all__=["CausalTrace","ResonanceProfile","ABTestResult","ResonanceIntelligence","generate_resonance_profile"]
