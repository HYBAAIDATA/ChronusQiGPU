from __future__ import annotations
import itertools
VECTOR_BOUNDARIES=(0,1,31,32,33,255,256,257,1024,4063,4064,4065,4079,4080,4081)
REDUCE_BOUNDARIES=(0,1,31,32,33,255,256,257)
MATMUL_REJECT=((31,32,32),(33,32,32),(32,31,32),(32,33,32),(32,32,31),(32,32,33))
def ir(op,shape,dtype='f32',schema='chronus.ir.v0.1',name='case'):return {'schema':schema,'name':name,'op':op,'dtype':dtype,'shape':shape}
def named():
 out=[]
 for n in VECTOR_BOUNDARIES:out.append(('vector_add',104000+n,ir('vector_add',{'n':n}), 'PASS' if 1<=n<=4080 else 'REJECTED_IR'))
 for n in REDUCE_BOUNDARIES:out.append(('reduce_sum_local',105000+n,ir('reduce_sum_local',{'n':n}), 'PASS' if 1<=n<=256 else 'REJECTED_IR'))
 out.append(('matmul_tiled',106032,ir('matmul_tiled',{'m':32,'k':32,'n':32}),'PASS'))
 for i,(m,k,n) in enumerate(MATMUL_REJECT):out.append(('matmul_tiled',106100+i,ir('matmul_tiled',{'m':m,'k':k,'n':n}),'REJECTED_IR'))
 for op,shape in [('vector_add',{'n':4}),('reduce_sum_local',{'n':4}),('matmul_tiled',{'m':32,'k':32,'n':32})]:out.append((op,107000+len(out),ir(op,shape,'f64'),'REJECTED_IR'))
 return out
def generated():
 out=[]
 for i in range(256):out.append(('vector_add',104001+i,ir('vector_add',{'n':1+((i*257)%4080)},name=f'vector_{i}'),'PASS'))
 for i in range(64):out.append(('vector_add',104401+i,ir('vector_add',{'n':0 if i%2==0 else 4081+i},name=f'vector_reject_{i}'),'REJECTED_IR'))
 for i in range(256):out.append(('reduce_sum_local',105001+i,ir('reduce_sum_local',{'n':1+(i%256)},name=f'reduce_{i}'),'PASS'))
 for i in range(64):out.append(('reduce_sum_local',105401+i,ir('reduce_sum_local',{'n':0 if i%2==0 else 257+i},name=f'reduce_reject_{i}'),'REJECTED_IR'))
 for i in range(128):out.append(('matmul_tiled',106001+i,ir('matmul_tiled',{'m':32,'k':32,'n':32},name=f'matmul_{i}'),'PASS'))
 bad=list(MATMUL_REJECT)
 for i in range(64):
  m,k,n=bad[i%len(bad)];out.append(('matmul_tiled',106401+i,ir('matmul_tiled',{'m':m,'k':k,'n':n},name=f'matmul_reject_{i}'),'REJECTED_IR'))
 return out
