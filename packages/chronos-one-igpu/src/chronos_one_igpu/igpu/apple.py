"""Public Apple-framework bindings; standalone exact authority remains unchanged.

MLX tensor execution uses explicit GPU streams and materialisation before timing.
Core ML inference permits OS compute-unit selection; no per-layer ANE claim is made.
"""
import hashlib,json,platform,time
from pathlib import Path
import numpy as np
from ..adapters.base import BackendAbsent,DispatchError
from .tensor_runtime import tensor_operation

def _features(value):
    a=np.asarray(value,dtype=np.float32)
    if a.ndim!=2 or a.size>1000000 or not np.isfinite(a).all():raise ValueError('bounded finite feature matrix required')
    return a

class MLXOverlay:
    def __init__(self):
        if platform.system()!='Darwin'or platform.machine().lower()not in('arm64','aarch64'):raise BackendAbsent('MLX GPU binding requires Apple silicon macOS')
        try:
            import mlx.core as mx
            if not mx.metal.is_available():raise BackendAbsent('MLX Metal device unavailable')
            self.mx=mx;self.last_receipt=None
        except BackendAbsent:raise
        except Exception as exc:raise BackendAbsent(f'MLX unavailable: {type(exc).__name__}')from exc
    def capability(self):
        return {'device_id':'apple_mlx_gpu','backend':'mlx_metal','physical':True,'operations':['tensor'],'host_unified_memory':True,'precision':'float32','lazy_materialisation_required':True}
    def execute_tensor(self,operation,left,right=None):
        reference=tensor_operation(operation,left,right)
        if np.iscomplexobj(reference):raise ValueError('MLX adapter accepts real tensors; use exact core/CPU for other types')
        # Float32 is an explicit numeric execution contract, never integer authority.
        if any(np.asarray(x).dtype.kind not in('f',)for x in(left,[]if right is None else right)):raise ValueError('MLX float32 contract requires floating inputs')
        mx=self.mx;started=time.perf_counter()
        with mx.stream(mx.gpu):
            a=mx.array(np.asarray(left,dtype=np.float32));b=mx.array(np.asarray(right,dtype=np.float32))if right is not None else None
            if operation=='matmul':out=mx.matmul(a,b)
            elif operation=='add':out=a+b
            elif operation in('hadamard','scale'):out=a*b
            elif operation=='kron':out=mx.kron(a,b)
            else:raise ValueError('unsupported MLX tensor operation')
            mx.eval(out)
        result=np.asarray(out)
        if result.shape!=reference.shape or not np.isfinite(result).all()or not np.allclose(result,reference,atol=1e-5,rtol=1e-4):raise DispatchError('MLX tensor failed host numeric validation')
        self.last_receipt={**self.capability(),'operation':operation,'items_executed':int(result.size),'wall_seconds':time.perf_counter()-started,'host_numeric_verified':True,'atol':1e-5,'rtol':1e-4,'materialised_before_receipt':True}
        return result

class LinearNeuralRanker:
    """Deterministic bounded dense/ReLU inference with supplied model weights.

Ranking is an exact permutation of candidates, not authority to discard a lease.
"""
    def __init__(self,weights,bias):
        self.weights=_features(weights);self.bias=np.asarray(bias,dtype=np.float32)
        if self.bias.ndim!=1 or self.bias.shape[0]!=self.weights.shape[1]or not np.isfinite(self.bias).all():raise ValueError('network bias/weight shape mismatch')
        self.digest=hashlib.sha256(self.weights.tobytes()+self.bias.tobytes()).hexdigest();self.last_receipt=None
    def score(self,features):
        x=_features(features)
        if x.shape[1]!=self.weights.shape[0]:raise ValueError('network feature shape mismatch')
        started=time.perf_counter();hidden=np.maximum(x@self.weights+self.bias,0);scores=hidden.sum(axis=1)
        if not np.isfinite(scores).all():raise ValueError('network overflow')
        self.last_receipt={'backend':'cpu_reference','operation':'neural_rank','model_digest':self.digest,'items_executed':len(x),'wall_seconds':time.perf_counter()-started,'trained_on_bitcoin_claimed':False}
        return scores
    def rank(self,candidates,features):
        values=tuple(candidates);scores=np.asarray(self.score(features))
        if scores.shape!=(len(values),)or len(set(values))!=len(values):raise ValueError('ranking must preserve unique candidate domain')
        return tuple(values[i]for i in np.argsort(-scores,kind='stable'))

class CoreMLRanker:
    def __init__(self,model_path,input_name,output_name,compute_units='ALL',expected_sha256=None,max_model_bytes=512*1024*1024):
        if platform.system()!='Darwin':raise BackendAbsent('Core ML execution requires macOS')
        path=Path(model_path)
        if not path.is_file()or not 0<path.stat().st_size<=max_model_bytes:raise ValueError('bounded .mlmodel file required')
        self.model_digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if expected_sha256 is not None and expected_sha256!=self.model_digest:raise ValueError('Core ML model custody mismatch')
        if compute_units not in('ALL','CPU_ONLY','CPU_AND_GPU','CPU_AND_NE'):raise ValueError('unsupported Core ML compute-unit policy')
        try:
            import coremltools as ct
            self.model=ct.models.MLModel(str(path),compute_units=getattr(ct.ComputeUnit,compute_units))
        except Exception as exc:raise BackendAbsent(f'Core ML binding unavailable: {type(exc).__name__}')from exc
        self.input_name=input_name;self.output_name=output_name;self.compute_units=compute_units;self.last_receipt=None
    def score(self,features):
        x=_features(features);started=time.perf_counter();output=self.model.predict({self.input_name:x})
        scores=np.asarray(output[self.output_name],dtype=np.float32).reshape(-1)
        if scores.shape!=(len(x),)or not np.isfinite(scores).all():raise DispatchError('Core ML score shape/finiteness violation')
        self.last_receipt={'backend':'coreml_os_selected','operation':'neural_rank','compute_units_allowed':self.compute_units,'actual_neural_engine_dispatch':None,'model_digest':self.model_digest,'items_executed':len(x),'wall_seconds':time.perf_counter()-started}
        return scores
    rank=LinearNeuralRanker.rank
