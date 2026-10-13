#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#ifdef CHRONOS_OPENSSL
#define OPENSSL_SUPPRESS_DEPRECATED
#include <openssl/sha.h>
#include <openssl/opensslv.h>
#endif
typedef uint32_t uint;
/* Bitcoin SHA256d, unchanged digest predicate. One owned nonce per work item. */
static const uint K256[64]={0x428a2f98U,0x71374491U,0xb5c0fbcfU,0xe9b5dba5U,0x3956c25bU,0x59f111f1U,0x923f82a4U,0xab1c5ed5U,0xd807aa98U,0x12835b01U,0x243185beU,0x550c7dc3U,0x72be5d74U,0x80deb1feU,0x9bdc06a7U,0xc19bf174U,0xe49b69c1U,0xefbe4786U,0x0fc19dc6U,0x240ca1ccU,0x2de92c6fU,0x4a7484aaU,0x5cb0a9dcU,0x76f988daU,0x983e5152U,0xa831c66dU,0xb00327c8U,0xbf597fc7U,0xc6e00bf3U,0xd5a79147U,0x06ca6351U,0x14292967U,0x27b70a85U,0x2e1b2138U,0x4d2c6dfcU,0x53380d13U,0x650a7354U,0x766a0abbU,0x81c2c92eU,0x92722c85U,0xa2bfe8a1U,0xa81a664bU,0xc24b8b70U,0xc76c51a3U,0xd192e819U,0xd6990624U,0xf40e3585U,0x106aa070U,0x19a4c116U,0x1e376c08U,0x2748774cU,0x34b0bcb5U,0x391c0cb3U,0x4ed8aa4aU,0x5b9cca4fU,0x682e6ff3U,0x748f82eeU,0x78a5636fU,0x84c87814U,0x8cc70208U,0x90befffaU,0xa4506cebU,0xbef9a3f7U,0xc67178f2U};
static inline uint ror256(uint x,uint n){return(x>>n)|(x<<(32-n));}
static inline void init256(uint*h){h[0]=0x6a09e667U;h[1]=0xbb67ae85U;h[2]=0x3c6ef372U;h[3]=0xa54ff53aU;h[4]=0x510e527fU;h[5]=0x9b05688cU;h[6]=0x1f83d9abU;h[7]=0x5be0cd19U;}
static inline void compress256(uint*h,uint*w){for(int i=16;i<64;i++){uint s0=ror256(w[i-15],7)^ror256(w[i-15],18)^(w[i-15]>>3);uint s1=ror256(w[i-2],17)^ror256(w[i-2],19)^(w[i-2]>>10);w[i]=w[i-16]+s0+w[i-7]+s1;}uint a=h[0],b=h[1],c=h[2],d=h[3],e=h[4],f=h[5],g=h[6],z=h[7];for(int i=0;i<64;i++){uint s1=ror256(e,6)^ror256(e,11)^ror256(e,25);uint ch=(e&f)^((~e)&g);uint t1=z+s1+ch+K256[i]+w[i];uint s0=ror256(a,2)^ror256(a,13)^ror256(a,22);uint maj=(a&b)^(a&c)^(b&c);uint t2=s0+maj;z=g;g=f;f=e;e=d+t1;d=c;c=b;b=a;a=t1+t2;}h[0]+=a;h[1]+=b;h[2]+=c;h[3]+=d;h[4]+=e;h[5]+=f;h[6]+=g;h[7]+=z;}

typedef struct {uint h[8];uint tail[3];unsigned char block0[64];
#ifdef CHRONOS_OPENSSL
SHA256_CTX openssl_state;
#endif
} Prepared;
static uint be32(const unsigned char *p){return ((uint)p[0]<<24)|((uint)p[1]<<16)|((uint)p[2]<<8)|p[3];}
static inline uint swap32(uint x){return (x>>24)|((x>>8)&0xff00U)|((x<<8)&0xff0000U)|(x<<24);}
static void destroy_context(PyObject *capsule){Prepared *p=PyCapsule_GetPointer(capsule,"chronos.midstate.v1");if(p)PyMem_Free(p);else PyErr_Clear();}
static PyObject *prepare(PyObject *self,PyObject *arg){
    if(!PyBytes_Check(arg)||PyBytes_GET_SIZE(arg)!=76){PyErr_SetString(PyExc_ValueError,"76-byte immutable prefix required");return NULL;}
    const unsigned char *prefix=(const unsigned char*)PyBytes_AS_STRING(arg);
    Prepared *p=PyMem_Malloc(sizeof(Prepared));if(!p)return PyErr_NoMemory();
    #ifdef CHRONOS_OPENSSL
    SHA256_Init(&p->openssl_state);SHA256_Update(&p->openssl_state,prefix,64);
    for(int i=0;i<8;i++){p->h[i]=p->openssl_state.h[i];}
#else
    uint w[64];init256(p->h);for(int i=0;i<16;i++){w[i]=be32(prefix+4*i);}compress256(p->h,w);
#endif
    memcpy(p->block0,prefix,64);for(int i=0;i<3;i++)p->tail[i]=be32(prefix+64+4*i);
    PyObject *result=PyCapsule_New(p,"chronos.midstate.v1",destroy_context);if(!result)PyMem_Free(p);return result;
}
static PyObject *rebind(PyObject *self,PyObject *args){
    PyObject *capsule,*prefix;
    if(!PyArg_ParseTuple(args,"OO",&capsule,&prefix))return NULL;
    Prepared *old=PyCapsule_GetPointer(capsule,"chronos.midstate.v1");if(!old)return NULL;
    if(!PyBytes_Check(prefix)||PyBytes_GET_SIZE(prefix)!=76){PyErr_SetString(PyExc_ValueError,"76-byte prefix required");return NULL;}
    const unsigned char *raw=(const unsigned char*)PyBytes_AS_STRING(prefix);
    if(memcmp(old->block0,raw,64)){PyErr_SetString(PyExc_ValueError,"midstate cannot bind a different first block");return NULL;}
    Prepared *p=PyMem_Malloc(sizeof(Prepared));if(!p)return PyErr_NoMemory();memcpy(p,old,sizeof(Prepared));
    for(int i=0;i<3;i++)p->tail[i]=be32(raw+64+4*i);
    PyObject *result=PyCapsule_New(p,"chronos.midstate.v1",destroy_context);if(!result)PyMem_Free(p);return result;
}
static void hash_nonce(const Prepared *p,uint nonce,unsigned char *output){
    #ifdef CHRONOS_OPENSSL
    unsigned char tail[16],first[32];SHA256_CTX a=p->openssl_state,b;
    for(int i=0;i<3;i++){uint w=p->tail[i];tail[4*i]=(unsigned char)(w>>24);tail[4*i+1]=(unsigned char)(w>>16);tail[4*i+2]=(unsigned char)(w>>8);tail[4*i+3]=(unsigned char)w;}
    for(int i=0;i<4;i++){tail[12+i]=(unsigned char)(nonce>>(8*i));}
    SHA256_Update(&a,tail,16);SHA256_Final(first,&a);SHA256_Init(&b);SHA256_Update(&b,first,32);SHA256_Final(output,&b);
#else
    uint h[8],w[64];memcpy(h,p->h,sizeof(h));
    w[0]=p->tail[0];w[1]=p->tail[1];w[2]=p->tail[2];w[3]=swap32(nonce);w[4]=0x80000000U;
    for(int i=5;i<15;i++){w[i]=0;}
    w[15]=640;compress256(h,w);
    for(int i=0;i<8;i++){w[i]=h[i];}
    w[8]=0x80000000U;for(int i=9;i<15;i++){w[i]=0;}w[15]=256;
    init256(h);compress256(h,w);
    for(int i=0;i<8;i++){output[4*i]=(unsigned char)(h[i]>>24);output[4*i+1]=(unsigned char)(h[i]>>16);output[4*i+2]=(unsigned char)(h[i]>>8);output[4*i+3]=(unsigned char)h[i];}
#endif
}
static int target_ok(const unsigned char *digest,const unsigned char *target){
    for(int i=31;i>=0;i--){if(digest[i]<target[i])return 1;if(digest[i]>target[i])return 0;}return 1;
}
static PyObject *hash_batch(PyObject *self,PyObject *args){
    PyObject *capsule,*iterable;
    if(!PyArg_ParseTuple(args,"OO",&capsule,&iterable))return NULL;
    Prepared *p=PyCapsule_GetPointer(capsule,"chronos.midstate.v1");if(!p)return NULL;
    if((!PyList_Check(iterable)&&!PyTuple_Check(iterable))||PySequence_Size(iterable)>4096){PyErr_SetString(PyExc_ValueError,"bounded concrete nonce array required");return NULL;}
    PyObject *seq=PySequence_Fast(iterable,"bounded nonce sequence required");if(!seq)return NULL;
    Py_ssize_t n=PySequence_Fast_GET_SIZE(seq);
    if(n>4096){Py_DECREF(seq);PyErr_SetString(PyExc_ValueError,"native batch exceeds 4096");return NULL;}
    uint *values=PyMem_Malloc((n?n:1)*sizeof(uint));if(!values){Py_DECREF(seq);return PyErr_NoMemory();}
    for(Py_ssize_t i=0;i<n;i++){
        PyObject *value=PySequence_Fast_GET_ITEM(seq,i);
        if(!PyLong_CheckExact(value)){PyMem_Free(values);Py_DECREF(seq);PyErr_SetString(PyExc_ValueError,"uint32 integer nonce required");return NULL;}
        unsigned long long v=PyLong_AsUnsignedLongLong(value);
        if(PyErr_Occurred()||v>0xffffffffULL){PyMem_Free(values);Py_DECREF(seq);if(!PyErr_Occurred())PyErr_SetString(PyExc_ValueError,"nonce overflow");return NULL;}values[i]=(uint)v;
    }
    PyObject *output=PyBytes_FromStringAndSize(NULL,n*32);if(!output){PyMem_Free(values);Py_DECREF(seq);return NULL;}
    unsigned char *bytes=(unsigned char*)PyBytes_AS_STRING(output);
    Py_BEGIN_ALLOW_THREADS
    for(Py_ssize_t i=0;i<n;i++)hash_nonce(p,values[i],bytes+32*i);
    Py_END_ALLOW_THREADS
    PyMem_Free(values);Py_DECREF(seq);return output;
}
static PyObject *scan_range(PyObject *self,PyObject *args){
    PyObject *capsule,*target;unsigned long long start,count;
    if(!PyArg_ParseTuple(args,"OKKO",&capsule,&start,&count,&target))return NULL;
    Prepared *p=PyCapsule_GetPointer(capsule,"chronos.midstate.v1");if(!p)return NULL;
    if(start>0xffffffffULL||count>4096ULL||count>0x100000000ULL-start||!PyBytes_Check(target)||PyBytes_GET_SIZE(target)!=32){PyErr_SetString(PyExc_ValueError,"bounded uint32 range and 32-byte target required");return NULL;}
    unsigned char target_copy[32],digest[32]={0};memcpy(target_copy,PyBytes_AS_STRING(target),32);
    unsigned long long completed=0,winner=0;int found=0;
    Py_BEGIN_ALLOW_THREADS
    for(unsigned long long i=0;i<count;i++){hash_nonce(p,(uint)(start+i),digest);completed++;if(target_ok(digest,target_copy)){found=1;winner=start+i;break;}}
    Py_END_ALLOW_THREADS
    if(found)return Py_BuildValue("(KKy#)",completed,winner,digest,(Py_ssize_t)32);
    return Py_BuildValue("(KOO)",completed,Py_None,Py_None);
}
static PyObject *scan_batch(PyObject *self,PyObject *args){
    PyObject *capsule,*iterable,*target;
    if(!PyArg_ParseTuple(args,"OOO",&capsule,&iterable,&target))return NULL;
    Prepared *p=PyCapsule_GetPointer(capsule,"chronos.midstate.v1");if(!p)return NULL;
    if((!PyList_Check(iterable)&&!PyTuple_Check(iterable))||PySequence_Size(iterable)>4096||!PyBytes_Check(target)||PyBytes_GET_SIZE(target)!=32){PyErr_SetString(PyExc_ValueError,"bounded nonce array and 32-byte target required");return NULL;}
    PyObject *seq=PySequence_Fast(iterable,"nonce array required");if(!seq)return NULL;
    Py_ssize_t n=PySequence_Fast_GET_SIZE(seq);uint *values=PyMem_Malloc((n?n:1)*sizeof(uint));if(!values){Py_DECREF(seq);return PyErr_NoMemory();}
    for(Py_ssize_t i=0;i<n;i++){
        PyObject *v=PySequence_Fast_GET_ITEM(seq,i);
        if(!PyLong_CheckExact(v)){PyMem_Free(values);Py_DECREF(seq);PyErr_SetString(PyExc_ValueError,"uint32 integer nonce required");return NULL;}
        unsigned long long x=PyLong_AsUnsignedLongLong(v);
        if(PyErr_Occurred()||x>0xffffffffULL){PyMem_Free(values);Py_DECREF(seq);if(!PyErr_Occurred())PyErr_SetString(PyExc_ValueError,"nonce overflow");return NULL;}values[i]=(uint)x;
    }
    unsigned char target_copy[32],digest[32]={0};memcpy(target_copy,PyBytes_AS_STRING(target),32);
    unsigned long long completed=0,winner=0;int found=0;
    Py_BEGIN_ALLOW_THREADS
    for(Py_ssize_t i=0;i<n;i++){hash_nonce(p,values[i],digest);completed++;if(target_ok(digest,target_copy)){found=1;winner=values[i];break;}}
    Py_END_ALLOW_THREADS
    PyMem_Free(values);Py_DECREF(seq);
    if(found)return Py_BuildValue("(KKy#)",completed,winner,digest,(Py_ssize_t)32);
    return Py_BuildValue("(KOO)",completed,Py_None,Py_None);
}
static PyObject *midstate(PyObject *self,PyObject *capsule){
    Prepared *p=PyCapsule_GetPointer(capsule,"chronos.midstate.v1");if(!p)return NULL;unsigned char out[32];
    for(int i=0;i<8;i++){out[4*i]=(unsigned char)(p->h[i]>>24);out[4*i+1]=(unsigned char)(p->h[i]>>16);out[4*i+2]=(unsigned char)(p->h[i]>>8);out[4*i+3]=(unsigned char)p->h[i];}
    return PyBytes_FromStringAndSize((char*)out,32);
}
static PyObject *implementation(PyObject *self,PyObject *unused){
#ifdef CHRONOS_OPENSSL
    return Py_BuildValue("{s:s,s:s}","backend","native_openssl_midstate","library",OPENSSL_VERSION_TEXT);
#else
    return Py_BuildValue("{s:s,s:O}","backend","native_c_midstate","library",Py_None);
#endif
}
static PyMethodDef methods[]={{"implementation",implementation,METH_NOARGS,"Report compiled crypto execution identity."},{"prepare",prepare,METH_O,"Prepare first-block SHA256 midstate."},{"rebind",rebind,METH_VARARGS,"Rebind tail while preserving an identical first block."},{"hash_batch",hash_batch,METH_VARARGS,"Materialise bounded SHA256d outputs."},{"scan_batch",scan_batch,METH_VARARGS,"Fuse ordered nonce hashing and target comparison."},{"scan_range",scan_range,METH_VARARGS,"Execute compact candidate-only bounded range."},{"midstate",midstate,METH_O,"Return the raw first-block chaining state."},{NULL,NULL,0,NULL}};
static struct PyModuleDef module={PyModuleDef_HEAD_INIT,"_sha256d_native","Portable native ASIC-like midstate pipeline; CPU execution, not ASIC silicon.",-1,methods};
PyMODINIT_FUNC PyInit__sha256d_native(void){return PyModule_Create(&module);}
