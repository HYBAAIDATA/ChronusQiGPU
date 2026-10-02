/* Chronus OpenCL tensor kernels.
 * Float32 output ownership is deterministic. Matmul traverses K in a fixed
 * tile order and uses local memory suitable for unified-memory iGPUs.
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
__kernel void tensor_matmul_tiled_f32(
    __global const float *a, __global const float *b, __global float *out,
    const uint m, const uint k, const uint n,
    __local float *tile_a, __local float *tile_b) {
  const uint col=get_global_id(0), row=get_global_id(1);
  const uint lx=get_local_id(0), ly=get_local_id(1);
  const uint tile=get_local_size(0);
  float acc=0.0f;
  for(uint base=0;base<k;base+=tile) {
    const uint ap=base+lx, bp=base+ly;
    tile_a[ly*tile+lx]=(row<m && ap<k) ? a[row*k+ap] : 0.0f;
    tile_b[ly*tile+lx]=(bp<k && col<n) ? b[bp*n+col] : 0.0f;
    barrier(CLK_LOCAL_MEM_FENCE);
    for(uint p=0;p<tile;++p)
      acc=acc+tile_a[ly*tile+p]*tile_b[p*tile+lx];
    barrier(CLK_LOCAL_MEM_FENCE);
  }
  if(row<m && col<n) out[row*n+col]=acc;
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