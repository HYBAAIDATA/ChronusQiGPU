# Real MPS norm transfer and evidence constraints

Replaced hard-coded contraction path costs with concrete MPS site-dimension cost estimates for two real transfer orders. The executor now requires the actual network and computes the squared state norm using CPU NumPy transfer contractions. The adaptive entry point calls that executor. All unimplemented GPU plans and non-norm objectives fail closed. Path arithmetic estimates are not measured FLOPs. Search is correctly labelled NumPy cosine similarity, not tensor network search. Policy checks use exceptions instead of optimization-removable assertions.

Tests compare computed norm against independently assembled complex statevectors and reject plan-only or GPU pseudo-execution. No acceleration, physical device, quantum advantage, exact arithmetic or production qualification claim follows from these source changes.
