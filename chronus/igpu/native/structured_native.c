#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <math.h>
#include <string.h>
/* Linear-storage tridiagonal + rank-two ground-state bracketing.
   CPU numerical execution, not a physical accelerator or a formal proof. */
typedef struct {Py_ssize_t n;double off,*d,*r,*im,*p,*yr,*yi,norm2;} Op;
static int sturm(Op *o,double x){double q=o->d[0]-x;int count=q<0;for(Py_ssize_t i=1;i<o->n;i++){if(fabs(q)<1e-300)q=-1e-300;q=o->d[i]-x-o->off*o->off/q;count+=q<0;}return count;}
static int block(Op *o,double x,double *largest,double *smallest,double *z0,double *z1,int positive){
 o->p[0]=o->d[0]-x;if(fabs(o->p[0])<1e-14||(positive&&o->p[0]<0))return 0;o->yr[0]=o->r[0];o->yi[0]=o->im[0];
 for(Py_ssize_t i=1;i<o->n;i++){double l=o->off/o->p[i-1];o->p[i]=o->d[i]-x-l*o->off;if(fabs(o->p[i])<1e-14||(positive&&o->p[i]<0)||!isfinite(o->p[i]))return 0;o->yr[i]=o->r[i]-l*o->yr[i-1];o->yi[i]=o->im[i]-l*o->yi[i-1];}
 o->yr[o->n-1]/=o->p[o->n-1];o->yi[o->n-1]/=o->p[o->n-1];
 for(Py_ssize_t j=o->n-1;j>0;j--){Py_ssize_t i=j-1;o->yr[i]=(o->yr[i]-o->off*o->yr[j])/o->p[i];o->yi[i]=(o->yi[i]-o->off*o->yi[j])/o->p[i];}
 double b00=0,b01=0,b11=0;for(Py_ssize_t i=0;i<o->n;i++){b00+=o->r[i]*o->yr[i];b01+=o->r[i]*o->yi[i];b11+=o->im[i]*o->yi[i];}
 double delta=hypot(b00-b11,2*b01);*largest=(b00+b11+delta)/2;*smallest=(b00+b11-delta)/2;double angle=0.5*atan2(2*b01,b00-b11);*z0=cos(angle);*z1=sin(angle);return isfinite(*largest)&&isfinite(*smallest);
}
static PyObject *ground(PyObject *self,PyObject *args){
 PyObject *real,*imag;double phi;if(!PyArg_ParseTuple(args,"OOd",&real,&imag,&phi))return NULL;
 if(!PyBytes_Check(real)||!PyBytes_Check(imag)||PyBytes_GET_SIZE(real)!=PyBytes_GET_SIZE(imag)||PyBytes_GET_SIZE(real)%sizeof(double)||PyBytes_GET_SIZE(real)<8||PyBytes_GET_SIZE(real)>8192*8||!isfinite(phi)||phi<1||phi>4){PyErr_SetString(PyExc_ValueError,"bounded double state and phi in [1,4] required");return NULL;}
 Py_ssize_t n=PyBytes_GET_SIZE(real)/8;double *mem=PyMem_Malloc((size_t)n*7*sizeof(double));if(!mem)return PyErr_NoMemory();Op o={n,-1/phi,mem,mem+n,mem+2*n,mem+3*n,mem+4*n,mem+5*n,0};double *v=mem+6*n;
 memcpy(o.r,PyBytes_AS_STRING(real),(size_t)n*8);memcpy(o.im,PyBytes_AS_STRING(imag),(size_t)n*8);
 double step=n>1?1.0/(n-1):0;for(Py_ssize_t i=0;i<n;i++){o.d[i]=i*step;if(i==n-1&&n>1)o.d[i]=1;if(!isfinite(o.r[i])||!isfinite(o.im[i])){PyMem_Free(mem);PyErr_SetString(PyExc_ValueError,"finite state required");return NULL;}o.norm2+=o.r[i]*o.r[i]+o.im[i]*o.im[i];}
 if(!isfinite(o.norm2)||o.norm2<=0||o.norm2>16){PyMem_Free(mem);PyErr_SetString(PyExc_ValueError,"bounded nonzero state norm required");return NULL;}
 int ok=1,iterations=0;double lo=0,hi=0,lambda=0,residual=0,value=0,gap=0,z0=0,z1=0,big=0,small=0;
 Py_BEGIN_ALLOW_THREADS
 double tl=-2*fabs(o.off)-1e-12,th=1+2*fabs(o.off)+1e-12;
 for(int k=0;k<100&&th-tl>2e-15*fmax(1,fabs(tl));k++){double mid=(tl+th)/2;if(sturm(&o,mid)>=1)th=mid;else tl=mid;}
 hi=tl-1e-11;lo=tl-o.norm2-1;
 if(!block(&o,lo,&big,&small,&z0,&z1,1)||big>=1||!block(&o,hi,&big,&small,&z0,&z1,1)||big<=1)ok=0;
 if(ok){
  for(int k=0;k<100&&hi-lo>2e-15*fmax(1,fabs(lo));k++){double mid=(lo+hi)/2;if(!block(&o,mid,&big,&small,&z0,&z1,1)){ok=0;break;}if(big>=1)hi=mid;else lo=mid;iterations++;}
  lambda=(lo+hi)/2;
  double point=lambda+(2+2*fabs(o.off)+o.norm2)/n;
  for(int k=0;k<80;k++){if(block(&o,point,&big,&small,&z0,&z1,0)&&fabs(big-1)>1e-8&&fabs(small-1)>1e-8&&sturm(&o,point)+(big>1)+(small>1)==1){gap=point-lambda;break;}point=(point+lambda)/2;}
  if(!block(&o,lambda,&big,&small,&z0,&z1,1)||gap<=1e-12)ok=0;
  if(ok){double norm=0;for(Py_ssize_t i=0;i<n;i++){v[i]=o.yr[i]*z0+o.yi[i]*z1;norm+=v[i]*v[i];}norm=sqrt(norm);if(!isfinite(norm)||norm<=0)ok=0;
   if(ok){double dr=0,di=0;Py_ssize_t peak=0;for(Py_ssize_t i=0;i<n;i++){v[i]/=norm;dr+=o.r[i]*v[i];di+=o.im[i]*v[i];if(fabs(v[i])>fabs(v[peak]))peak=i;}if(v[peak]<0){for(Py_ssize_t i=0;i<n;i++)v[i]=-v[i];dr=-dr;di=-di;}
    for(Py_ssize_t i=0;i<n;i++){double h=o.d[i]*v[i]-o.r[i]*dr-o.im[i]*di;if(i)h+=o.off*v[i-1];if(i+1<n)h+=o.off*v[i+1];o.p[i]=h;value+=v[i]*h;}
    for(Py_ssize_t i=0;i<n;i++){double e=o.p[i]-value*v[i];residual+=e*e;}residual=sqrt(residual);if(!isfinite(residual)||residual>1e-10)ok=0;
   }
  }
 }
 Py_END_ALLOW_THREADS
 if(!ok){PyMem_Free(mem);PyErr_SetString(PyExc_RuntimeError,"structured ground-state bracket unresolved; use dense reference");return NULL;}
 PyObject *out=Py_BuildValue("{s:y#,s:d,s:d,s:d,s:d,s:d,s:i,s:n}","vector_bytes",v,n*8,"eigenvalue",value,"residual",residual,"ground_lower",lo,"ground_upper",hi,"gap_lower",gap,"iterations",iterations,"working_bytes",n*7*8);PyMem_Free(mem);return out;
}
static PyMethodDef methods[]={{"ground",ground,METH_VARARGS,"Compute tridiagonal-minus-rank-two ground state in linear storage."},{NULL,NULL,0,NULL}};
static struct PyModuleDef module={PyModuleDef_HEAD_INIT,"_structured_native","CPU structured numerical solver.",-1,methods};
PyMODINIT_FUNC PyInit__structured_native(void){return PyModule_Create(&module);}
