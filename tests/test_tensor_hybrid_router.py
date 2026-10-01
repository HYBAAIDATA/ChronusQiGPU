import numpy as np
from tensor.backends import BackendRegistry
from tensor.backends.numpy_backend import NumpyBackend
from tensor.contracts import ExactnessMode, Precision, TensorOperationSpec, TensorRequest, TensorShape
from tensor.hybrid import ProfiledHybridRouter


class FakeHardwareBackend:
    name="chronus-opencl"; backend_class="hardware"; device_id="fake-gpu"
    def is_available(self): return True
    def capabilities(self): return {"operations":("matmul",)}
    def supports(self,operation): return operation.name=="matmul" and operation.dtype is Precision.FLOAT32
    def execute(self,operation,inputs,*,deterministic):
        del operation,deterministic
        return np.asarray(inputs[0],dtype=np.float32)@np.asarray(inputs[1],dtype=np.float32)


def _request():
    spec=TensorOperationSpec(name="matmul",input_shapes=(TensorShape((32,32)),TensorShape((32,32))),
        output_shape=TensorShape((32,32)),dtype=Precision.FLOAT32,exactness_mode=ExactnessMode.EXACT,op_count=2*32**3)
    return TensorRequest(operation=spec)

def _registry():
    r=BackendRegistry(); r.register("chronus-opencl",FakeHardwareBackend,priority=10); r.register("numpy-cpu",NumpyBackend,priority=20); return r


def test_hybrid_routes_large_structured_to_available_hardware():
    router=ProfiledHybridRouter(min_elements_for_hardware=1,min_operations_for_hardware=1)
    a=np.ones((32,32),dtype=np.float32); b=np.eye(32,dtype=np.float32); execution=router.execute(_request(),(a,b),registry=_registry())
    assert execution.decision.backend=="chronus-opencl" and execution.decision.hardware_available is True
    assert execution.result.provenance.backend.backend_class=="hardware"; np.testing.assert_array_equal(execution.result.data,a)


def test_hybrid_keeps_irregular_work_on_reference():
    router=ProfiledHybridRouter(min_elements_for_hardware=1,min_operations_for_hardware=1)
    a=np.ones((32,32),dtype=np.float32); b=np.eye(32,dtype=np.float32)
    execution=router.execute(_request(),(a,b),registry=_registry(),structured_hint=False)
    assert execution.decision.backend=="numpy-cpu" and "irregular" in execution.decision.reason
    assert execution.result.provenance.backend.backend_class=="reference"
