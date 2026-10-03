from __future__ import annotations
import numpy as np
DISTRIBUTIONS=('zeros','signed_zero','small','large','mixed','repeated','cancellation','alternating','random')
def values(seed,n):
 r=np.random.default_rng(seed);kind=DISTRIBUTIONS[seed%len(DISTRIBUTIONS)]
 if kind=='zeros':x=np.zeros(n,np.float32)
 elif kind=='signed_zero':x=np.where(np.arange(n)%2,np.float32(-0.0),np.float32(0.0)).astype(np.float32)
 elif kind=='small':x=r.uniform(-1e-6,1e-6,n).astype(np.float32)
 elif kind=='large':x=r.uniform(-1e10,1e10,n).astype(np.float32)
 elif kind=='mixed':x=r.uniform(-100,100,n).astype(np.float32)
 elif kind=='repeated':x=np.full(n,np.float32((seed%17)-8),np.float32)
 elif kind=='cancellation':x=np.resize(np.array([1e5,1,-1e5,-1],np.float32),n)
 elif kind=='alternating':x=np.where(np.arange(n)%2,-1,1).astype(np.float32)
 else:x=r.normal(size=n).astype(np.float32)
 return x
