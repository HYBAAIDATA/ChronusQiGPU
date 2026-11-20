"""Controlled analytic fixtures only, never live telemetry."""
import json
import math
import platform
import random
import statistics
import time

from golden_ontology.filter import PisotFilter,ZeckendorfMap
from golden_ontology.substrate import PV_REGISTRY,pisano_period_pow2
from golden_ontology.fold import fold_words,unfold_words

def rmse(a,b):
    if len(a)!=len(b) or not a:
        raise ValueError("equal nonempty inputs required")
    return math.sqrt(math.fsum((x-y)**2 for x,y in zip(a,b))/len(a))

def _kernel(sig,weights):
    r=len(weights)//2
    return [math.fsum(w*sig[min(max(i+j-r,0),len(sig)-1)]
                      for j,w in enumerate(weights)) for i in range(len(sig))]

def savgol_5(sig):
    return _kernel(sig,[x/35 for x in (-3,12,17,12,-3)])

def savgol_9(sig):
    return _kernel(sig,[x/231 for x in (-21,14,39,54,59,54,39,14,-21)])

def zero_phase_sma(sig,radius=4):
    return _kernel(sig,[1/(2*radius+1)]*(2*radius+1))

def causal_ema(sig,alpha=0.35):
    if not sig:
        return []
    out=[sig[0]]
    for x in sig[1:]:
        out.append(alpha*x+(1-alpha)*out[-1])
    return out

def impulse_asymmetry(fn,n=41):
    imp=[0.0]*n
    imp[n//2]=1.0
    r=fn(imp)
    return math.fsum(abs(r[n//2-i]-r[n//2+i]) for i in range(1,n//2+1))

def run_filter_benchmark():
    methods={f"pisot_{name}":PisotFilter(name,4).apply for name in PV_REGISTRY}
    methods.update(raw=list,savgol_5=savgol_5,savgol_9=savgol_9,
                   sma_5=lambda s:zero_phase_sma(s,2),sma_9=zero_phase_sma,
                   causal_ema_035=causal_ema)
    report=[]
    for seed in (20261119,20261120,20261121):
        rng=random.Random(seed)
        for fixture in ("sinusoid","constant","step","mixed_frequency"):
            n=400
            clean=[{
                "sinusoid":math.sin(2*math.pi*t/40),
                "constant":1.0,
                "step":float(t>=n//2),
                "mixed_frequency":math.sin(2*math.pi*t/40)+0.3*math.cos(2*math.pi*t/17),
            }[fixture] for t in range(n)]
            noisy=[x+rng.gauss(0,0.08) for x in clean]
            for name,fn in methods.items():
                t=time.perf_counter_ns()
                est=fn(noisy)
                report.append({"fixture":fixture,"seed":seed,"method":name,
                    "rmse":rmse(clean,est),"impulse_asymmetry":impulse_asymmetry(fn),
                    "elapsed_ns":time.perf_counter_ns()-t})
    return report

def run_warp_benchmark():
    rng=random.Random(20261119)
    base=[rng.uniform(-1.5,1.5) for _ in range(128)]
    def std(xs):
        mean,sd=statistics.mean(xs),statistics.pstdev(xs) or 1
        return [(x-mean)/sd for x in xs]
    def tanh(xs):
        rms=math.sqrt(math.fsum(x*x for x in xs)/len(xs)) or 1
        return [math.tanh(x/(100*rms)) for x in xs]
    z=ZeckendorfMap.encode_ranks(base)
    report={}
    for name,fn in {"unit_rescale":lambda x:3.7*x+12.4,"cubic_x3":lambda x:x**3,
                    "exp":math.exp,"arctan":math.atan}.items():
        y=[fn(x) for x in base]
        ZeckendorfMap.verify_monotone_warp(base,y)
        report[name]={"zeckendorf_rank_drift":sum(a!=b for a,b in zip(z,ZeckendorfMap.encode_ranks(y))),
                      "standard_scaler_rmse_drift":rmse(std(base),std(y)),
                      "tanh_rms_rmse_drift":rmse(tanh(base),tanh(y))}
    return report

def run_fold_benchmark():
    bits=4096
    steps=pisano_period_pow2(bits)-137
    w=[(1<<bits)-1,(1<<2048)+99]
    times=[]
    for _ in range(5):
        t=time.perf_counter_ns()
        y=fold_words(w,steps,bits)
        if unfold_words(y,steps,bits)!=w:
            raise ArithmeticError("roundtrip failed")
        times.append(time.perf_counter_ns()-t)
    return {"samples_ns":times,"median_ns":statistics.median(times),
            "all_under_supplied_one_second":all(t<10**9 for t in times)}

if __name__=="__main__":
    print(json.dumps({"classification":"controlled test fixtures; not real telemetry",
        "python":platform.python_version(),"platform":platform.platform(),
        "filter":run_filter_benchmark(),"warps":run_warp_benchmark(),
        "fold":run_fold_benchmark()},indent=2,allow_nan=False))
