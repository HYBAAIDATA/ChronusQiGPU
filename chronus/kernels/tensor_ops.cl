/* Chronus generic tensor kernels.
 * Deterministic float32 arithmetic. Each output is owned by one work item;
 * matmul uses a fixed accumulation order.
 */
__kernel void tensor_add_f32(__global const float *a, __global const float *b,
                             __global float *out, const uint n) {
  const uint gid=get_global_id(0); if(gid<n) out[gid]=a[gid]+b[gid];
}
__kernel void tensor_hadamard_f32(__global const float *a, __global const float *b,
                                  __global float *out, const uint n) {
  const uint gid=get_global_id(0); if(gid<n) out[gid]=a[gid]*b[gid];
}
__kernel void tensor_scale_f32(__global const float *a, __global const float *s,
                               __global float *out, const uint n) {
  const uint gid=get_global_id(0); if(gid<n) out[gid]=a[gid]*s[0];
}
__kernel void tensor_matmul_f32(__global const float *a, __global const float *b,
                                __global float *out, const uint m,
                                const uint k, const uint n) {
  const uint gid=get_global_id(0); if(gid>=m*n) return;
  const uint row=gid/n, col=gid-row*n; float acc=0.0f;
  for(uint p=0;p<k;++p) acc=acc+a[row*k+p]*b[p*n+col];
  out[gid]=acc;
}
__kernel void tensor_kron_1d_f32(__global const float *a, __global const float *b,
                                 __global float *out, const uint an, const uint bn) {
  const uint gid=get_global_id(0); if(gid<an*bn) out[gid]=a[gid/bn]*b[gid%bn];
}
__kernel void tensor_kron_2d_f32(__global const float *a, __global const float *b,
                                 __global float *out, const uint ar,
                                 const uint ac, const uint br, const uint bc) {
  const uint rows=ar*br, cols=ac*bc, gid=get_global_id(0); if(gid>=rows*cols) return;
  const uint row=gid/cols, col=gid-row*cols;
  out[gid]=a[(row/br)*ac+(col/bc)]*b[(row%br)*bc+(col%bc)];
}
