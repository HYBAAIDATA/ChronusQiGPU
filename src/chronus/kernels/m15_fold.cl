/* Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
 * Chronus is a HYBA Data product.
 *
 * M15 byte-pair fold (or unfold) in GL(2, Z/256Z): one work item per pair.
 * The 2x2 matrix is passed row-major as four arguments, so the same kernel
 * computes M15 and its inverse. Integer-only and exact; output is compared
 * with the pure-Python reference by the fleet's known-answer self-test.
 */
__kernel void m15_pairs(__global const uchar *in_pairs,
                        __global uchar *out_pairs,
                        const uint m00,
                        const uint m01,
                        const uint m10,
                        const uint m11,
                        const uint pairs)
{
    const uint i = (uint)get_global_id(0);
    if (i >= pairs) {
        return;
    }
    const uint a = (uint)in_pairs[2u * i];
    const uint b = (uint)in_pairs[2u * i + 1u];
    out_pairs[2u * i] = (uchar)((m00 * a + m01 * b) & 0xFFu);
    out_pairs[2u * i + 1u] = (uchar)((m10 * a + m11 * b) & 0xFFu);
}
