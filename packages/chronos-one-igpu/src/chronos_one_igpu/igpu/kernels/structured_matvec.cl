#pragma OPENCL EXTENSION cl_khr_fp64 : enable
/* Two-pass matrix-free real operator. Local reduction then pointwise application.
   Full eigensolve is not claimed by these two kernels. */
__kernel void chronos_rank2_partials(__global const double *r,__global const double *im,__global const double *x,__global double *parts,uint n,__local double *lr,__local double *li){
 uint g=get_global_id(0),l=get_local_id(0),width=get_local_size(0);lr[l]=g<n?r[g]*x[g]:0;li[l]=g<n?im[g]*x[g]:0;barrier(CLK_LOCAL_MEM_FENCE);
 for(uint s=width/2;s;s/=2){if(l<s){lr[l]+=lr[l+s];li[l]+=li[l+s];}barrier(CLK_LOCAL_MEM_FENCE);}
 if(l==0){parts[2*get_group_id(0)]=lr[0];parts[2*get_group_id(0)+1]=li[0];}
}
__kernel void chronos_structured_apply(__global const double *d,__global const double *r,__global const double *im,__global const double *x,__global double *y,uint n,double off,double dr,double di){
 uint g=get_global_id(0);if(g>=n)return;double v=d[g]*x[g]-r[g]*dr-im[g]*di;if(g)v+=off*x[g-1];if(g+1<n)v+=off*x[g+1];y[g]=v;
}
