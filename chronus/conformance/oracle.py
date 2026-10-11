"""Independent NumPy float32 semantic oracle; never an execution backend."""
import numpy as np
ORACLE='numpy-float32-v1';POLICY={'vector_add':'exact','reduce_sum_local':'ordered-exact','matmul_tiled':'max_abs_error<=1e-5'}
def vector_add(a,b):return np.add(np.asarray(a,dtype=np.float32),np.asarray(b,dtype=np.float32),dtype=np.float32)
def reduce_sum_local(a):
 acc=np.float32(0);one=np.float32(1)
 for x in np.asarray(a,dtype=np.float32):acc=np.float32(np.float32(x)*one+acc)
 return np.asarray([acc],dtype=np.float32)
def matmul_tiled(a,b):return np.asarray(a,dtype=np.float32)@np.asarray(b,dtype=np.float32)
