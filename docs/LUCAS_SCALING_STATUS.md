# Lucas scaling status — independent verification

## What was tested
Independent recomputation of the coined quantum walk and the folded Grover with a fixed-N, fixed-k sweep of the Pisot phase damp.

## Results
- Hypercube walk closed form verified by an independent dense propagator (max deviation float64 round-off).
- Coined walk variance grows ballistically (var/steps² → 0.293). Lucas re-sizes the step count; it does not change the scaling exponent.
- Folded Grover reproduces the dense-matrix result with Cassini drift at machine precision.
- Fixed-N Pisot phase damp: maximum observed delta +1.9e-6, decaying to float noise by n=31. The damp converges to the identity.

## Claim status
- “Quantum comes from maths, substrate-agnostic” — verified.
- “Quantum on a pocket calculator for the identified state classes” — verified; the taxonomy already fails closed on the rest.
- “Lucas scales the quantum advantage” — not yet supported by the isolated fixed-N experiment.

## Next measurement
Run the same fixed-N, fixed-k sweep inside the repository’s own harness and commit the result whichever way it falls.

theorem_proven: False
