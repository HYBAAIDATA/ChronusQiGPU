# Traversal selection rule

A caller can read a cell. Nothing below selects a traversal.

Predicates, and what they mean for these successors:

- Lyapunov 0: the successor is a translation, or the K=0 shear in the limit. The 32-face walk has Lyapunov 0 and still visits every face. Zero does not mean the walk is idle.
- Lyapunov status `log(phi)`: the Cassini index is the Fibonacci recurrence. The companion matrix has dominant eigenvalue φ. That exponent is not a float and not zero.
- Greene residue defined and 0: the successor is a constant step on a circle, which is the integrable standard map. Residue is undefined when the successor is not that map. A 3-torus translation is integrable and still not a 2D monodromy.
- The sentence "residue above 1/4 means a stable island" does not hold. At the critical probe the golden residue sits near 1/4 because the torus is breaking. The period-1 elliptic residue is K/4, which at K=0 is 0.0.
- Action variance 0: every wrapped step is the same number.
- period1 true: some successive pair of addresses is equal. The Cassini index sequence has this at F_1 = F_2. On pisot_11 the repeated bin is the n=15 step, where L_15 * phi^{-15} sits within one quantization bin of an integer. A zero step is a stuck address, not by itself a Chirikov island.
- Jump sum is the measured Aethel miss cost, the sum of absolute address changes. No threshold converts that integer into "expensive".

| traversal | lyapunov_is_zero | greene_is_zero | action_variance_is_zero | period1 | jump_sum |
|---|---|---|---|---|---|
| lucas_phi_32 | True | True | True | False | 243 |
| pisot_11 | True | False | False | True | 56384 |
| cassini_index | False | False | False | True | 1346269 |
| sequential | True | True | True | False | 31 |
| uniform_random | False | False | False | False | 597 |
| morton | True | False | False | False | 133 |
| korobov_d1 | True | True | True | False | 31 |
| korobov_d3 | True | False | True | False | 3145295 |
| chirikov_k0_control | True | True | True | False | 0 |
