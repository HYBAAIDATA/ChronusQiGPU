// Inputs are backend-produced witnesses. Domain is bounded so products fit ulong.
__kernel void chronus_cassini(__global const uint*n,__global const ulong*p,__global const ulong*f,__global const ulong*q,__global uchar*out){uint i=get_global_id(0);long d=(long)(p[i]*q[i]-f[i]*f[i]);out[i]=(uchar)(d==((n[i]&1)?-1:1));}
