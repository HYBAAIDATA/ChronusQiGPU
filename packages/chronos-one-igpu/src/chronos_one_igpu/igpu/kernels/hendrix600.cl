/* Exact lowering of PYTHIA's supplied Hendrix/Cassini shard tables.
 * Six u64 columns: vertex, coarse face, start, width, stride, origin.
 * No strategy selection and no floating point mining decisions.
 */
__kernel void chronos_hendrix600(
    __global const ulong *rows, __global const uint *wide,
    ulong window, ulong stride, ulong position, uint active,
    ulong shortest, uint count, __global uint *out,
    __global uint2 *binding)
{
    uint gid = get_global_id(0);
    if (gid >= count) return;
    ulong j = ((position + (ulong)gid) * stride) % window;
    ulong head = shortest * (ulong)active;
    uint idx; ulong local_position;
    if (j < head) {
        idx = (uint)(j % active); local_position = j / active;
    } else {
        idx = wide[(uint)(j - head)]; local_position = shortest;
    }
    ulong start = rows[idx*6+2]; ulong width = rows[idx*6+3];
    out[gid] = (uint)(start + (rows[idx*6+5] + local_position*rows[idx*6+4]) % width);
    binding[gid] = (uint2)((uint)rows[idx*6], (uint)rows[idx*6+1]);
}
