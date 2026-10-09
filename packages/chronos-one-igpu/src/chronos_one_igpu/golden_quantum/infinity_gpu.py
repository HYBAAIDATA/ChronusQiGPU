"""Compatibility names compose the ONE standalone Chronos iGPU owner."""
class ClusterInventory:
    def __init__(self,fabric=None):self.fabric=fabric
    def snapshot(self):
        if self.fabric is None:
            from ..igpu.fabric import ComputeFabric
            self.fabric=ComputeFabric()
        return self.fabric.compose()
class SuperGPU:
    def __init__(self,gpu=None,**kwargs):
        if gpu is None:
            from ..igpu.facade import OneIGPU
            gpu=OneIGPU(**kwargs)
        self.gpu=gpu
    def compose(self):return self.gpu.compose()
    def route(self,operation,scale_index=15):return self.gpu.route(operation,scale_index)
    def select(self,operation,require_hardware=False):
        route=self.route(operation)
        if require_hardware and route.executor=='cpu_reference':raise RuntimeError('no physical executor for this operation')
        return {'backend':route.executor,'device_id':route.bound_device,'logical_device':route.logical_device,'capability':route.capability}
    def __getattr__(self,name):return getattr(self.gpu,name)
InfinityGPU=SuperGPU
