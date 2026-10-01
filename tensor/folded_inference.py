"""Measured linear-inference pilot over exact PULVINI-custodied weights.

Weights are preserved bit-for-bit by viewing IEEE-754 float32/float64 values as
unsigned integers before applying exact PULVINI. Only requested output-row
chunks are reconstructed by true partial unfold and dispatched through Tensor.
No storage-compression claim is made: physical_compression_ratio is unavailable
until physical evidence exists.
"""
from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any

import numpy as np

from .contracts import ExactnessMode, ModelIdentity, Precision, TensorOperationSpec, TensorRequest, TensorShape
from .engine import execute as execute_tensor
from .pulvini_bridge import load_geodesic_tensor_engine

_DTYPE_TO_PRECISION={np.dtype(np.float32):Precision.FLOAT32,np.dtype(np.float64):Precision.FLOAT64}
_DTYPE_TO_UINT={np.dtype(np.float32):np.dtype(np.uint32),np.dtype(np.float64):np.dtype(np.uint64)}


@dataclass(frozen=True)
class FoldedWeightState:
    state: Any
    dtype: str
    shape: tuple[int,int]
    itemsize: int

    @classmethod
    def from_array(cls, weights: np.ndarray, *, depth: int=8) -> "FoldedWeightState":
        array=np.asarray(weights)
        if array.ndim!=2: raise ValueError("folded linear weights must be rank 2")
        dtype=np.dtype(array.dtype)
        if dtype not in _DTYPE_TO_UINT: raise TypeError("folded inference supports float32 or float64 weights")
        contiguous=np.ascontiguousarray(array)
        raw=contiguous.view(_DTYPE_TO_UINT[dtype]).reshape(-1)
        engine=load_geodesic_tensor_engine()
        state=engine.fold_exact((int(v) for v in raw),depth=int(depth),shape=(raw.size,))
        return cls(state,dtype.str,tuple(int(v) for v in array.shape),dtype.itemsize)

    @property
    def numpy_dtype(self): return np.dtype(self.dtype)
    @property
    def uint_dtype(self): return _DTYPE_TO_UINT[self.numpy_dtype]

    def _decode(self, values):
        raw=np.asarray([int(v) for v in values],dtype=self.uint_dtype)
        return raw.view(self.numpy_dtype)

    def restore(self): return self._decode(self.state.unfold()).reshape(self.shape)

    def rows(self,start:int,stop:int):
        rows,cols=self.shape; start,stop=int(start),int(stop)
        if start<0 or stop<start or stop>rows: raise ValueError("row boundary outside folded weight matrix")
        engine=load_geodesic_tensor_engine(); boundary=engine.KernelBoundary(start*cols,stop*cols)
        values,stats=self.state.unfold_partial_with_stats(boundary)
        matrix=self._decode(values).reshape((stop-start,cols))
        return matrix,{"requested_values":stats.requested_values,"source_values_read":stats.source_values_read,
                       "depth":stats.depth,"full_length":stats.full_length,
                       "reconstructed_fraction":stats.reconstructed_fraction}

    def representation_report(self):
        return {"shape":self.shape,"dtype":self.numpy_dtype.name,"fold_depth":int(self.state.depth),
                "logical_values":int(self.state.original_length),"stored_exact_values":len(self.state.values),
                "representation_only":True,"physical_compression_ratio":None,
                "claim_boundary":"exact reversible custody; no byte/HBM compression claim"}


class FoldedLinearPilot:
    def __init__(self, folded_weights: FoldedWeightState): self.weights=folded_weights

    def run(self,activations:np.ndarray,*,chunk_rows:int=128,backend_required:str="numpy-cpu",
            registry=None,model_id:str="folded-linear-pilot"):
        if chunk_rows<1: raise ValueError("chunk_rows must be positive")
        dtype=self.weights.numpy_dtype; precision=_DTYPE_TO_PRECISION[dtype]
        x=np.asarray(activations,dtype=dtype); was_vector=x.ndim==1
        if was_vector: x=x.reshape(1,-1)
        if x.ndim!=2 or x.shape[1]!=self.weights.shape[1]:
            raise ValueError("activations must have shape (batch, in_features)")
        started=time.perf_counter_ns(); chunks=[]; partial_stats=[]; measurements=[]; total_ops=0
        out_features,in_features=self.weights.shape
        for start in range(0,out_features,int(chunk_rows)):
            stop=min(out_features,start+int(chunk_rows)); weight_rows,stats=self.weights.rows(start,stop)
            partial_stats.append(stats); rhs=np.ascontiguousarray(weight_rows.T)
            batch=x.shape[0]; width=stop-start; op_count=2*batch*in_features*width; total_ops+=op_count
            spec=TensorOperationSpec(name="matmul",input_shapes=(TensorShape((batch,in_features)),
                    TensorShape((in_features,width))),output_shape=TensorShape((batch,width)),
                    dtype=precision,exactness_mode=ExactnessMode.EXACT,op_count=op_count)
            request=TensorRequest(operation=spec,backend_required=backend_required,allow_fallback=False)
            result=execute_tensor(request,(x,rhs),registry=registry,model=ModelIdentity(model_id=model_id))
            chunks.append(np.asarray(result.data,dtype=dtype)); measurements.append(result.as_dict())
        output=np.concatenate(chunks,axis=1) if chunks else np.empty((x.shape[0],0),dtype=dtype)
        elapsed_ns=max(1,time.perf_counter_ns()-started); baseline=x@self.weights.restore().T
        diff=np.asarray(output,dtype=np.float64)-np.asarray(baseline,dtype=np.float64)
        error=float(np.max(np.abs(diff))) if diff.size else 0.0
        return {"output":output[0] if was_vector else output,"backend_required":backend_required,
                "end_to_end_elapsed_ns":elapsed_ns,"declared_operations":total_ops,
                "measured_end_to_end_tflops":total_ops*1_000_000_000.0/elapsed_ns/1e12,
                "max_abs_error_vs_dense_same_dtype":error,"partial_unfold":partial_stats,
                "chunk_measurements":measurements,"weights":self.weights.representation_report(),
                "truth_class":"measured","physical_compression_ratio":None,"representation_only":True}


__all__=["FoldedLinearPilot","FoldedWeightState"]
