# Thermodynamic Boundary of Bitcoin Mining

## Scope

This document states exact logical obligations. It does not invent a numerical
energy floor, a measured device efficiency, or a physical implementation.

## Logical facts

1. SHA-256d maps a larger input domain to a 256-bit digest and is many-to-one
   at the published input/output boundary.
2. A classical circuit for SHA-256d can be embedded in a reversible circuit by
   retaining inputs and ancillary state, then uncomputing temporary state.
3. Reversibility of the inner circuit does not remove end-to-end state
   preparation, target comparison, I/O, and reset obligations.
4. Landauer's bound applies to logically erased information. It is not a fixed
   energy charge on every gate.
5. A physical energy statement requires a declared temperature, erased-bit
   count, device implementation, and measured operating evidence.

The exact symbolic lower-bound term is:

`E >= b * k_B * T * ln(2)`

where `b` is the number of bits that are actually erased. The implementation
keeps `b*T` rational and leaves `k_B*ln(2)` symbolic. No floating-point
approximation is admitted.

## Boundary

The PureQuantumMathASIC certifies algebra. It does not certify refrigeration,
switching energy, wall power, silicon efficiency, or executed hashes. A
reversible SHA-256d core is mathematically possible; a claim that an entire
mining system dissipates zero energy is not established by that fact.