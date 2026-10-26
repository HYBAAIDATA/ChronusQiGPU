# Aethel traversal cost

Large jump: absolute address step > 8.

| traversal | jump_count | jump_sum | large_jumps | cassini_consulted | digest |
|---|---|---|---|---|---|
| lucas_phi_32 | 31 | 243 | 4 | true | 84e283f173e444f62209aee31a3d427ffb093b2c5b555c259ebc295b7560b267 |
| pisot_11 | 31 | 56384 | 27 | false | 2805072b7a93a010277e50e842a0a15761f80e4381d022090e3f1d6e062be272 |
| cassini_index | 31 | 1346269 | 23 | true | df5645536a31fdf0ec3d3aab152463d295ada8d885dbab317dc8a78156acdf80 |
| sequential | 31 | 31 | 0 | false | 23b22df6bf551a4e788327db3b3d3d96e1eca49078d2c6bd0049da2d390eca8b |
| uniform_random | 31 | 597 | 23 | false | 25dba80219c07effe34855950abe291a0101f49e913cd7d426fe85648ace9aba |
| morton | 31 | 133 | 1 | false | 57d5124ac68d025dde7ed3288adf617ec6e7443c21fbb24ae775476c5e0f8fc9 |
| korobov_d1 | 31 | 31 | 0 | false | 23b22df6bf551a4e788327db3b3d3d96e1eca49078d2c6bd0049da2d390eca8b |
| korobov_d3 | 31 | 3145295 | 31 | false | a8b194b7ff01913f23e9f7b368dda49c9ab4c5e2cf5b55f88716cf79b071d853 |
| chirikov_k0_control | 0 | 0 | 0 | false | 4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945 |
