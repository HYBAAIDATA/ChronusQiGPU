"""Matrix-free real-symmetric tridiagonal minus rank-two advisory operator.

Re(a a*) = real(a) real(a)^T + imag(a) imag(a)^T. A complex
amplitude vector therefore needs two real update columns, not generally one.
"""
from dataclasses import dataclass
import numpy as np
try:
 from . import _structured_native
except ImportError:
 _structured_native=None
MAX_STRUCTURED_DIMENSION=8192
@dataclass(frozen=True)
class GroundState:
 vector:np.ndarray
 evidence:dict
class StructuredHamiltonian:
 def __init__(self,amplitudes,phi):
  a=np.asarray(amplitudes,dtype=np.complex128)
  if a.ndim!=1 or not 1<=len(a)<=MAX_STRUCTURED_DIMENSION or not np.isfinite(a).all() or not 1<=phi<=4 or not np.isfinite(phi):raise ValueError('finite bounded state and phi in [1,4] required')
  norm=float(np.vdot(a,a).real)
  if not 0<norm<=16:raise ValueError('bounded nonzero state norm required')
  self.n=len(a);self.phi=float(phi);self.off=-1/self.phi
  self.real=np.frombuffer(np.ascontiguousarray(a.real).tobytes(),dtype=np.float64)
  self.imag=np.frombuffer(np.ascontiguousarray(a.imag).tobytes(),dtype=np.float64)
  self.diagonal=np.frombuffer(np.linspace(0,1,self.n).tobytes(),dtype=np.float64)
 @property
 def storage_bytes(self):return self.real.nbytes+self.imag.nbytes+self.diagonal.nbytes
 def matvec(self,vector):
  v=np.asarray(vector)
  if v.shape!=(self.n,) or not np.isfinite(v).all():raise ValueError('finite dimension-matched vector required')
  out=self.diagonal*v-self.real*np.dot(self.real,v)-self.imag*np.dot(self.imag,v)
  out[1:]+=self.off*v[:-1];out[:-1]+=self.off*v[1:];return out
 def dense(self):
  if self.n>512:raise ValueError('dense materialization quota exceeded')
  a=self.real+1j*self.imag;h=np.diag(self.diagonal)-np.real(np.outer(a,a.conj()))
  if self.n>1:h+=np.diag(np.full(self.n-1,self.off),1)+np.diag(np.full(self.n-1,self.off),-1)
  return h
 def _block(self,x,positive=True):
  p=np.empty(self.n);yr=self.real.copy();yi=self.imag.copy();p[0]=self.diagonal[0]-x
  if abs(p[0])<1e-14 or(positive and p[0]<0):raise ArithmeticError('tridiagonal positive pivot required')
  for k in range(1,self.n):
   l=self.off/p[k-1];p[k]=self.diagonal[k]-x-l*self.off
   if abs(p[k])<1e-14 or(positive and p[k]<0):raise ArithmeticError('tridiagonal positive pivot required')
   yr[k]-=l*yr[k-1];yi[k]-=l*yi[k-1]
  yr[-1]/=p[-1];yi[-1]/=p[-1]
  for k in range(self.n-2,-1,-1):yr[k]=(yr[k]-self.off*yr[k+1])/p[k];yi[k]=(yi[k]-self.off*yi[k+1])/p[k]
  b00=float(self.real@yr);b01=float(self.real@yi);b11=float(self.imag@yi);delta=np.hypot(b00-b11,2*b01);angle=0.5*np.arctan2(2*b01,b00-b11)
  return (b00+b11+delta)/2,(b00+b11-delta)/2,yr*np.cos(angle)+yi*np.sin(angle)
 def _sturm(self,x):
  q=self.diagonal[0]-x;count=int(q<0)
  for d in self.diagonal[1:]:
   if abs(q)<1e-300:q=-1e-300
   q=d-x-self.off*self.off/q;count+=int(q<0)
  return count
 def _python_ground(self):
  tl=-2*abs(self.off)-1e-12;th=1+2*abs(self.off)+1e-12
  for _ in range(100):
   if th-tl<=2e-15*max(1,abs(tl)):break
   m=(tl+th)/2
   if self._sturm(m):th=m
   else:tl=m
  norm=float(self.real@self.real+self.imag@self.imag);lo=tl-norm-1;hi=tl-1e-11
  if self._block(lo)[0]>=1 or self._block(hi)[0]<=1:raise ArithmeticError('structured ground-state bracket unresolved')
  steps=0
  for _ in range(100):
   if hi-lo<=2e-15*max(1,abs(lo)):break
   m=(lo+hi)/2
   if self._block(m)[0]>=1:hi=m
   else:lo=m
   steps+=1
  value=(lo+hi)/2;point=value+(2+2*abs(self.off)+norm)/self.n;gap=0
  for _ in range(80):
   try:big,small,_=self._block(point,positive=False)
   except ArithmeticError:point=(point+value)/2;continue
   if abs(big-1)>1e-8 and abs(small-1)>1e-8 and self._sturm(point)+int(big>1)+int(small>1)==1:gap=point-value;break
   point=(point+value)/2
  if gap<=1e-12:raise ArithmeticError('ground-state separation unresolved')
  _,_,v=self._block(value);v/=np.linalg.norm(v)
  if v[int(np.argmax(np.abs(v)))]<0:v=-v
  return {'vector_bytes':v.tobytes(),'ground_lower':lo,'ground_upper':hi,'gap_lower':gap,'iterations':steps,'working_bytes':self.n*7*8}
 def ground(self,backend='auto'):
  if backend not in ('auto','native','python','dense'):raise ValueError('unknown structured backend')
  if backend=='dense':
   from ..engine import ChronosEngine
   v=ChronosEngine().evolve(self.dense());meta={'backend':'original_dense_reference','matrix_materialized':True,'working_bytes':self.n*self.n*8,'gap_lower':None}
  else:
   if backend=='native'and _structured_native is None:raise RuntimeError('native structured solver unavailable')
   native=backend!='python'and _structured_native is not None
   meta=_structured_native.ground(self.real.tobytes(),self.imag.tobytes(),self.phi)if native else self._python_ground()
   v=np.frombuffer(meta.pop('vector_bytes'),dtype=np.float64).copy();meta.update(backend='native_structured_cpu'if native else'python_structured_cpu',matrix_materialized=False)
  hv=self.matvec(v);value=float(np.vdot(v,hv).real);residual=float(np.linalg.norm(hv-value*v));norm=float(np.linalg.norm(v))
  if abs(norm-1)>1e-10 or not np.isfinite(v).all() or residual>1e-10:raise ValueError('structured eigenpair failed host validation')
  meta.update(dimension=self.n,eigenvalue=value,residual=residual,vector_norm=norm,operator_storage_bytes=self.storage_bytes,rank_update_columns=2,ground_check='numerical_lowest_root_bracket'if backend!='dense'else'original_dense_lowest_eigenvalue')
  v=np.frombuffer(np.asarray(v,dtype=np.complex128).tobytes(),dtype=np.complex128)
  return GroundState(v,meta)
