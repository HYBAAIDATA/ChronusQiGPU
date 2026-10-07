"""The canonical tensor specification as a machine-checked registry.

Every constituent of the canonical tensor specification, and every discovery
made while building Kellogg against it, is one :class:`SpecItem`. Nothing is
left out; each item says what Kellogg does with it:

    EXACT        implemented on the exact path (a declared exact field)
    FLOAT        implemented on the float64 plane, declared as such
    CORRECTED    the statement as written is false or ill-posed; the
                 corrected statement is implemented and the correction named
    REFUTED      false as stated, with the counter-argument recorded
    DELEGATED    owned by another product under the T6 boundary
    RESEARCH     no precise statement yet; isolated from the shipped surface
    NOT_STARTED  declared target with no evidence yet (never claimed)

``verify_registry()`` checks that every named symbol resolves, every
delegated item names a product, every correction carries its text, and every
benchmark id exists in :mod:`kellogg.benchmark`.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Dict, List, Tuple

STATUSES = ("EXACT", "FLOAT", "CORRECTED", "REFUTED", "DELEGATED", "RESEARCH", "NOT_STARTED")
PRODUCTS = (
    "kellogg",
    "aethel",
    "chronus",
    "mining",
    "theseus",
    "ovid",
    "salamander",
    "al_haras",
    "turing",
    "pythia",
    "euclid",
)


@dataclass(frozen=True)
class SpecItem:
    id: str
    part: str
    title: str
    statement: str
    status: str
    owner: str = "kellogg"
    symbols: Tuple[str, ...] = ()
    benchmarks: Tuple[str, ...] = ()
    note: str = ""
    field: str = ""


def _i(id, part, title, statement, status, **kw) -> SpecItem:
    kw = dict(kw)
    for key in ("symbols", "benchmarks"):
        if key in kw:
            kw[key] = tuple(kw[key])
    return SpecItem(id, part, title, statement, status, **kw)


REGISTRY: Tuple[SpecItem, ...] = (
    # Part I — axioms
    _i("T1", "I", "The substrate", "The tensor layer sits on (Z[phi], R), R: x -> phi x mod 1 on T^2.",
       "CORRECTED", field="Z[phi]",
       symbols=["kellogg.substrate.TRANSFER", "kellogg.substrate.cat_map", "kellogg.substrate.cat_map_period",
                "kellogg.substrate.lucas_wind"],
       benchmarks=["substrate_identities"],
       note="R is the golden transfer matrix [[1,1],[1,0]] acting on T^2 as the cat map (det -1, "
            "unimodular). x -> phi x mod 1 is not a map on R/Z: x and x+1 land phi apart."),
    _i("T2", "I", "The fields", "Every tensor declares an exact field; no float on the exact path.",
       "EXACT", symbols=["kellogg.certificate.FIELDS", "kellogg.exact_network.FIELD"],
       benchmarks=["determinism"]),
    _i("T3", "I", "The invariants", "Every tensor structure has invariants; every invariant is a theorem.",
       "EXACT", symbols=["kellogg.certificate.certify"], benchmarks=["mpo_preservation", "kraus_trace"],
       note="Invariants are decided exactly and bound into each certificate; theorem status is "
            "recorded per item (theorem_proven stays False without a formal proof)."),
    _i("T4", "I", "The certificates", "Every tensor operation emits a content-addressed certificate.",
       "EXACT", symbols=["kellogg.certificate.TensorCertificate", "kellogg.certificate.CertificateLedger"],
       benchmarks=["certificate_emission", "ten_thousand_qubit_voyage"]),
    _i("T5", "I", "The unifications", "The tensor layer is the substrate for VQC, fold, arithmetic, surface "
       "code, certificates and applications.", "CORRECTED",
       note="See VI.1-VI.10 for the per-unification status; two are corrected, one refuted, two research."),
    _i("T6", "I", "The boundary", "Kellogg owns tensor mathematics; Aethel fold custody; Chronus execution; "
       "Mining SHA-256d. The tensor layer does not cross.", "EXACT",
       symbols=["kellogg.custody.default_custody", "kellogg.phi_tensor_core.resolve_fold_custody"],
       benchmarks=["boundary_isolation"],
       note="Kellogg imports only stdlib and numpy at module load. Custody (Aethel) is bound by protocol, "
            "never imported by name at load; with no provider Kellogg uses its resident custody."),
    # Part II — fields
    _i("F.Q", "II", "Q", "Rationals.", "EXACT", field="Q", symbols=["fractions.Fraction"]),
    _i("F.Qi", "II", "Q(i)", "Gaussian rationals.", "EXACT", field="Q(i)",
       symbols=["kellogg.cyclotomic.Q8", "kellogg.cyclotomic.I8"], benchmarks=["exact_field_cost"]),
    _i("F.Qsqrt2", "II", "Q(sqrt 2)", "Quadratic extension; Born probabilities.", "EXACT", field="Q(sqrt2)",
       symbols=["kellogg.exact_tensor.Qsqrt2", "kellogg.cyclotomic.Q8.sign"], benchmarks=["exact_field_cost"]),
    _i("F.Qzeta8", "II", "Q(zeta_8)", "Q(i, sqrt 2): all Clifford gates + T.", "EXACT", field="Q(zeta8)",
       symbols=["kellogg.exact_tensor.F4", "kellogg.cyclotomic.Q8"], benchmarks=["exact_field_cost"],
       note="Q8 stores (a + b sqrt2 + i(c + d sqrt2))/den on integers; it equals F4 bit for bit and "
            "multiplies about 38x faster, so the tensor engine uses it."),
    _i("F.Zphi", "II", "Z[phi]", "Golden ring.", "EXACT", field="Z[phi]",
       symbols=["kellogg.scales.Zphi"], benchmarks=["exact_field_cost"]),
    _i("F.Qphi", "II", "Q(phi)", "Field of fractions of Z[phi] (added: the 11D weights and the "
       "beta-expansion need division).", "EXACT", field="Q(phi)",
       symbols=["kellogg.substrate.QPhi"], benchmarks=["exact_field_cost"]),
    _i("F.GF2", "II", "GF(2)", "Surface-code stabilizers.", "EXACT", field="GF(2)",
       symbols=["kellogg.surface_code.gf2_rank"], benchmarks=["surface_code_algebra"]),
    _i("F.digest", "II", "Digests are not field elements", "GF(2)^256 is a vector space; never treat a "
       "digest as an algebraic object.", "EXACT", symbols=["kellogg.certificate.cex_digest"],
       note="Digests are hex strings everywhere in Kellogg; no arithmetic is defined on them."),
    # Part III — substrate invariants
    _i("S.lucas", "III", "Lucas", "L_n = trace(R^n) = phi^n + psi^n.", "EXACT", field="Z",
       symbols=["kellogg.substrate.lucas_wind", "kellogg.scales.lucas"], benchmarks=["substrate_identities"]),
    _i("S.cassini", "III", "Cassini", "L_(n-1) L_(n+1) - L_n^2 = 5 (-1)^n.", "CORRECTED", field="Z",
       symbols=["kellogg.substrate.lucas_cassini", "kellogg.substrate.cassini_step"],
       benchmarks=["substrate_identities"],
       note="The sign is wrong as written: L_0 L_2 - L_1^2 = 2*3 - 1 = +5. The identity is "
            "5 (-1)^(n+1). The Fibonacci form F_(n-1) F_(n+1) - F_n^2 = (-1)^n = det(R^n) holds."),
    _i("S.pisot", "III", "Pisot", "|psi|^n -> 0, the conjugate cancels.", "EXACT", field="Z[phi]",
       symbols=["kellogg.substrate.pisot_residual", "kellogg.substrate.pisot_contracts"],
       benchmarks=["substrate_identities"]),
    _i("S.morton", "III", "Morton", "phi-expansion is the beta-expansion for beta = phi.", "CORRECTED",
       field="Q(phi)", symbols=["kellogg.substrate.phi_beta_expansion", "kellogg.substrate.parry_admissible"],
       benchmarks=["substrate_identities"],
       note="The beta-expansion is implemented exactly as phi_beta_expansion (greedy, Parry-admissible: "
            "no adjacent ones). 'Morton' in Kellogg names Z-order bit interleaving "
            "(first_principles.morton_encode), a different map, so the name is not reused."),
    _i("S.korobov", "III", "Korobov", "Fibonacci lattice discrepancy O(log n / n).", "EXACT", field="Q",
       symbols=["kellogg.substrate.korobov_point", "kellogg.substrate.star_discrepancy_2d"],
       benchmarks=["substrate_identities"],
       note="Star discrepancy is computed exactly; D* N / ln N is measured and stays bounded. The "
            "asymptotic itself is a published theorem (Zaremba/Niederreiter), cited, not re-proved."),
    _i("S.norm", "III", "Ring norm", "N(a + b phi) = a^2 + ab - b^2.", "EXACT", field="Z[phi]",
       symbols=["kellogg.substrate.ring_norm"], benchmarks=["substrate_identities"]),
    _i("S.sign", "III", "Sign", "(2a + b)^2 vs 5 b^2 decides sign exactly.", "EXACT", field="Z[phi]",
       symbols=["kellogg.substrate.ring_sign"], benchmarks=["substrate_identities"]),
    # Part IV — structures
    _i("IV.1", "IV", "MPS", "Field Q(zeta8); normalization, canonical form, entropy, exact contraction; "
       "entropy in Q(sqrt2).", "CORRECTED", field="Q(zeta8)",
       symbols=["kellogg.exact_network.ExactMPS", "kellogg.exact_network.ExactMPS.cut_purity",
                "kellogg.exact_network.ExactMPS.schmidt_rank", "kellogg.exact_network.ExactTensorTrain.compress"],
       benchmarks=["mps_gate_throughput", "mps_contraction_throughput", "ten_thousand_qubit_voyage"],
       note="Exact: gate application, amplitudes, expectations, norm, sampling, Schmidt rank, and the "
            "purity Tr(rho_A^2) in Q(sqrt2). The canonical form is the RREF gauge (unique, exact); the "
            "orthonormal canonical form needs square roots and is float. Von Neumann entropy is "
            "transcendental in general, so it is not in Q(sqrt2): it is a float boundary."),
    _i("IV.2", "IV", "TT", "Field Q(zeta8) or Q; ||T - TT||_F <= eps; SVD exactness.", "CORRECTED",
       field="Q(zeta8)",
       symbols=["kellogg.exact_network.ExactTensorTrain.from_dense", "kellogg.tensor_network.tt_svd"],
       benchmarks=["tt_svd_error_bound", "tt_svd_cost", "compression_fidelity"],
       note="SVD is not exact over these fields (singular values are square roots). Exact TT uses "
            "rank factorization: lossless, exact ranks. The eps bound is float tt_svd with the Oseledets "
            "budget. Discovery: TensorTrain(tolerance=t) thresholds against sigma_0 and reached 0.70 "
            "relative error at t = 0.1; it makes no Frobenius promise."),
    _i("IV.3", "IV", "MPO", "Application, composition, unitarity, trace.", "EXACT", field="Q(zeta8)",
       symbols=["kellogg.exact_network.ExactMPO.apply", "kellogg.exact_network.ExactMPO.compose",
                "kellogg.exact_network.ExactMPO.adjoint", "kellogg.exact_network.ExactMPO.is_unitary",
                "kellogg.exact_network.ExactMPO.trace"],
       benchmarks=["mpo_preservation"],
       note="Unitarity is decided as ||U^dagger U - I||_HS^2 == 0 from exact MPO traces."),
    _i("IV.4", "IV", "Hamiltonians", "Hermiticity, real spectrum, ground state, evolution (field Q(zeta8)).",
       "CORRECTED", field="Q(zeta8)",
       symbols=["kellogg.channels.PauliHamiltonian", "kellogg.exact_network.ising_mpo",
                "kellogg.exact_network.heisenberg_mpo", "kellogg.channels.pauli_rotation",
                "kellogg.dmrg.dmrg"],
       benchmarks=["hamiltonian_exact", "dmrg_vs_dense"],
       note="H = H^dagger is exact. A real spectrum follows from the spectral theorem; eigenvalues are "
            "float. exp(-i theta P) is exact only for theta in (pi/4)Z; other times raise NotInF4. "
            "Discovery: tensor_network.HeisenbergHamiltonianMPO encoded I + J S_(n-1).S_n instead of "
            "sum_i J S_i.S_(i+1) (identity at bond 0, not 4); fixed and checked against the explicit sum."),
    _i("IV.5", "IV", "Kraus maps", "sum K_i^dagger K_i = I within tolerance.", "EXACT", field="Q(zeta8)",
       symbols=["kellogg.channels.KrausChannel"], benchmarks=["kraus_trace"],
       note="Decided by exact equality, not a tolerance."),
    _i("IV.6", "IV", "Fisher metric", "F >= 0, Cramer-Rao, Heisenberg 1/N.", "EXACT", field="Q(sqrt2)",
       symbols=["kellogg.channels.fisher_matrix", "kellogg.channels.cramer_rao_holds",
                "kellogg.channels.heisenberg_bound_holds"],
       benchmarks=["fisher_exact"]),
    _i("IV.7", "IV", "Surface code", "d x d lattice; d=31: 984,064 pairs verified, 15 error correction.",
       "CORRECTED", field="GF(2)",
       symbols=["kellogg.surface_code.PlanarSurfaceCode", "kellogg.surface_code.edge_star_report"],
       benchmarks=["surface_code_algebra", "surface_code_correction"],
       note="984,064 = 32^2 x 31^2 counts a star on every vertex and a plaquette on every face; those "
            "checks commute but encode k = 0 logical qubits (n=1984, rank 1023 + 961), so distance and "
            "correction bound are undefined there. Kellogg's planar code (hypergraph product of "
            "repetition codes) at d=31: n=1861, k=1, 864,900 commuting pairs, exact distance 31, "
            "correction bound 15."),
    _i("IV.8", "IV", "11D vector", "Field Q(sqrt2) or Q(zeta8); phi-norm; Klein map; roundtrip to 1e-14.",
       "CORRECTED", field="Q(phi)",
       symbols=["kellogg.vector11.RootVector", "kellogg.vector11.fold", "kellogg.vector11.unfold"],
       benchmarks=["vector11_fold"],
       note="phi is not in Q(zeta8), so the field is Q(phi). Carrying vectors as c*sqrt(r) keeps the fold "
            "exact: the round trip is equality, not 1e-14."),
    _i("IV.9", "IV", "Zeckendorf certificate", "Unique representation; L15 = 1364; roundtrip n <= 1e6.",
       "EXACT", field="Z", symbols=["kellogg.scales.zeckendorf", "kellogg.scales.zeckendorf_is_legal"],
       benchmarks=["zeckendorf_roundtrip"]),
    # Part V — operations
    _i("V.fold", "V", "fold / unfold", "Vector -> Vector over Q, certified.", "DELEGATED", owner="aethel",
       symbols=["kellogg.custody.FoldStoreCustody"], benchmarks=["fold_roundtrip"],
       note="Aethel owns the fold. Kellogg uses it structurally: every core lives in custody as a "
            "phi-folded block. The fold is a lossless partition (placement), not compression."),
    _i("V.tt_svd", "V", "tt_svd", "Tensor -> TT.", "FLOAT", symbols=["kellogg.tensor_network.tt_svd"],
       benchmarks=["tt_svd_error_bound"]),
    _i("V.contract", "V", "mps_contract", "(MPS, MPS) -> scalar.", "EXACT", field="Q(zeta8)",
       symbols=["kellogg.exact_network.ExactTensorTrain.inner"], benchmarks=["mps_contraction_throughput"]),
    _i("V.mpo_apply", "V", "mpo_apply", "(MPO, MPS) -> MPS.", "EXACT", field="Q(zeta8)",
       symbols=["kellogg.exact_network.ExactMPO.apply"], benchmarks=["mpo_preservation"]),
    _i("V.evolve", "V", "hamiltonian_evolve", "(H, t) -> U in Q(zeta8).", "CORRECTED",
       symbols=["kellogg.channels.pauli_rotation"], benchmarks=["hamiltonian_exact"],
       note="Exact only on the pi/4 grid; elsewhere NotInF4."),
    _i("V.kraus", "V", "kraus_apply", "(Kraus, state) -> state.", "EXACT",
       symbols=["kellogg.channels.KrausChannel.apply"], benchmarks=["kraus_trace"]),
    _i("V.fisher", "V", "fisher_compute", "State -> matrix.", "EXACT",
       symbols=["kellogg.channels.fisher_matrix"], benchmarks=["fisher_exact"]),
    _i("V.syndrome", "V", "surface_syndrome / surface_decode", "Code -> bits -> correction.", "EXACT",
       symbols=["kellogg.surface_code.PlanarSurfaceCode.syndrome",
                "kellogg.surface_code.PlanarSurfaceCode.decode_exact",
                "kellogg.surface_code.PlanarSurfaceCode.decode_union_find"],
       benchmarks=["surface_code_correction"]),
    _i("V.zeckendorf", "V", "zeckendorf_encode / decode", "Z <-> mask.", "EXACT",
       symbols=["kellogg.scales.zeckendorf"], benchmarks=["zeckendorf_roundtrip"]),
    _i("V.compress", "V", "compress", "Tensor x eps -> tensor.", "EXACT",
       symbols=["kellogg.exact_network.ExactTensorTrain.compress", "kellogg.tensor_network.tt_svd"],
       benchmarks=["compression_fidelity"],
       note="Exact compression is lossless rank reduction; eps-compression is float tt_svd."),
    _i("V.every_op", "V", "Every operation emits a certificate", "No exceptions.", "CORRECTED",
       symbols=["kellogg.certificate.CertificateLedger", "kellogg.exact_network.ExactTensorTrain"],
       note="True for every operation of the exact tensor engine (exact_network): each records a "
            "certificate in custody. The older float substrates (quantum_tensor, golden modules) and "
            "tensor_ml use attest/commit records instead; they are not yet on TensorCertificate."),
    # Part VI — unifications
    _i("VI.1", "VI", "Tensor = VQC", "MPS with bond chi is exact for every state with entanglement "
       "entropy <= log chi at every cut.", "CORRECTED",
       symbols=["kellogg.exact_network.ExactMPS"], benchmarks=["ten_thousand_qubit_voyage"],
       note="Exact iff the Schmidt rank is <= chi at every cut. Entropy <= log chi is necessary, not "
            "sufficient (many tiny Schmidt values keep entropy low and rank high)."),
    _i("VI.2", "VI", "Fold = compression", "Fold is the invertible half, SVD the non-invertible half.",
       "CORRECTED", symbols=["kellogg.custody.FoldStoreCustody", "kellogg.tensor_network.tt_svd"],
       benchmarks=["fold_roundtrip", "compression_fidelity"],
       note="The phi-fold is a lossless partition that places bytes; it removes none. Lossless "
            "reduction is exact rank factorization; lossy reduction is eps-bounded tt_svd. Because the "
            "fold is exact, the pipeline error equals the truncation error."),
    _i("VI.3", "VI", "Arithmetic = contraction", "L_n = trace(R^n) is a contraction.", "EXACT",
       symbols=["kellogg.substrate.lucas_wind", "kellogg.substrate.cassini_step"],
       benchmarks=["substrate_identities"]),
    _i("VI.4", "VI", "Kraus = MPO", "Kraus rank is the MPO bond dimension.", "CORRECTED",
       symbols=["kellogg.channels.KrausChannel.stinespring", "kellogg.channels.KrausChannel.kraus_rank",
                "kellogg.channels.channel_mpo"],
       benchmarks=["kraus_trace"],
       note="Kraus rank is the purification (Stinespring ancilla) dimension = rank of the Choi matrix. "
            "A product of local channels is a bond-one MPO on doubled sites. Evidence: amplitude "
            "damping composed with dephasing has 4 Kraus operators but Kraus rank 3."),
    _i("VI.5", "VI", "Surface code = tensor network", "The decoder is tensor contraction.", "RESEARCH",
       note="The code space has a 2D tensor-network description; Kellogg verifies the code over GF(2) "
            "and decodes by matching / union-find, not by contraction."),
    _i("VI.6", "VI", "11D-32-face bridge", "32 = 2^5 factors through 11D via the Fibonacci ladder.",
       "RESEARCH", symbols=["kellogg.vector11.unit_lift", "kellogg.quantum_tensor.dual_frame_is_dual"],
       note="No precise statement. The frame lift and fold are implemented exactly. Discovery: "
            "turing_core's 'dual overlay' dodecahedron is the mirror orientation and is not at the "
            "icosahedron's face centres; Kellogg's frame is the dual (dual_frame_is_dual)."),
    _i("VI.7", "VI", "Fisher = natural gradient", "Exact F^-1 natural gradient for VQE/QAOA.", "CORRECTED",
       symbols=["kellogg.channels.natural_gradient_step"], benchmarks=["fisher_exact"],
       note="Exact for states and generators inside the field; general variational angles leave "
            "Q(zeta8) (only the pi/4 grid is exact)."),
    _i("VI.8", "VI", "Chemistry = DMRG", "H2, LiH, FeMoco executable on the tensor layer.", "CORRECTED",
       symbols=["kellogg.dmrg.dmrg"], benchmarks=["dmrg_vs_dense"],
       note="DMRG is implemented (float) and matches dense diagonalization to ~1e-14. Molecular "
            "Hamiltonians need an integral source and a Jordan-Wigner MPO, not shipped. FeMoco-size "
            "active spaces need chi ~ 1e3-1e4 and give variational upper bounds, not exact energies."),
    _i("VI.9", "VI", "ML = tensor network", "Layers and activations are MPOs; exponential compression.",
       "REFUTED", symbols=["kellogg.exact_network.ExactMPO.from_matrix"],
       note="Activations are nonlinear and an MPO is a linear operator, so activations are not MPOs. "
            "Linear layers can be MPOs (ExactMPO.from_matrix). Kellogg's exact_linear is a "
            "nearest-centroid classifier (docs/kellogg/exact_linear_algorithm_audit.md)."),
    _i("VI.10", "VI", "Certificate = tensor certificate", "Content-addressed, replayable.", "EXACT",
       symbols=["kellogg.certificate.certify", "kellogg.certificate.verify_certificate"],
       benchmarks=["determinism", "ten_thousand_qubit_voyage"]),
    # Part VII — certificate layer
    _i("VII.1", "VII", "Composition", "Compose iff boundaries, field and machine type match.", "EXACT",
       symbols=["kellogg.certificate.compose"], benchmarks=["determinism"]),
    _i("VII.2", "VII", "Aggregation", "Merkle membership plus independent verification.", "EXACT",
       symbols=["kellogg.certificate.aggregate", "kellogg.certificate.merkle_proof"]),
    _i("VII.3", "VII", "Lifecycle", "Signatures, delegation, validity, revocation, archival.", "DELEGATED",
       owner="al_haras", note="Signing and revocation are AL HARAS; archival is THESEUS/Aethel custody."),
    _i("VII.4", "VII", "Transparency", "RFC 6962-inspired log, inclusion and consistency proofs.",
       "DELEGATED", owner="al_haras", symbols=["kellogg.certificate.merkle_proof"],
       note="Kellogg provides RFC 6962-style leaf/node hashing and inclusion proofs; the log, "
            "consistency proofs and sequence numbers belong to AL HARAS."),
    _i("VII.5", "VII", "Policy and audit", "Declarative policy, fail-closed enforcement.", "DELEGATED",
       owner="al_haras"),
    _i("VII.6", "VII", "Exchange and storage", "CEX canonical JSON; Aethel/THESEUS storage.", "EXACT",
       symbols=["kellogg.certificate.cex", "kellogg.custody.FoldStoreCustody"]),
    _i("VII.7", "VII", "Research track", "Categorical, physical, arithmetic, ML research isolated.",
       "RESEARCH", note="Nothing from the research track ships; Kellogg contains no automated repair."),
    _i("XI.forgery", "XI", "Certificates are forgery-resistant", "Content-addressed and forgery-resistant.",
       "CORRECTED", owner="al_haras",
       note="Content addressing is tamper evidence. Forgery resistance needs keyed signatures, which "
            "belong to AL HARAS."),
    # Part VIII — execution layer
    _i("VIII.1", "VIII", "Backends", "CPU exact, CPU float, OpenCL, Chronus, remote.", "DELEGATED",
       owner="chronus", note="Kellogg ships the CPU exact and CPU float planes; devices are Chronus."),
    _i("VIII.2", "VIII", "Determinism H = M N f / I, floor 1e19 H/s", "Exact rational capacity.",
       "DELEGATED", owner="mining",
       note="Hashrate is outside the tensor layer: the tensor layer never reports H/s. A capacity "
            "floor is a design target, not an invariant."),
    _i("VIII.3", "VIII", "Cold-start correction", "1,000,001 chips cover pipeline fill.", "DELEGATED",
       owner="mining"),
    _i("VIII.4", "VIII", "Datapath, not ISA", "SHA-256d is 192 unrolled stages.", "DELEGATED", owner="mining"),
    _i("VIII.5", "VIII", "Six physical fixes", "Guarantee physical_H = design_H.", "DELEGATED",
       owner="chronus", note="Engineering mitigations, not a guarantee."),
    # Part IX — benchmarks
    _i("IX.1", "IX", "Correctness benchmarks", "fold, TT-SVD, MPO, Kraus, cross-version, determinism.",
       "EXACT", benchmarks=["fold_roundtrip", "tt_svd_error_bound", "mpo_preservation", "kraus_trace",
                            "cross_version_digest", "determinism"]),
    _i("IX.2", "IX", "Cost benchmarks", "gate, contraction, TT-SVD, fidelity, field, certificate, memory.",
       "EXACT", benchmarks=["mps_gate_throughput", "mps_contraction_throughput", "tt_svd_cost",
                            "compression_fidelity", "exact_field_cost", "certificate_emission",
                            "memory_footprint"]),
    _i("IX.3", "IX", "Meta-benchmark", "10,000-qubit voyage with certificate and replay.", "EXACT",
       benchmarks=["ten_thousand_qubit_voyage"]),
    _i("IX.5", "IX", "Cross-version digest", "Identical digests on CPython 3.11/3.12/3.13.", "EXACT",
       benchmarks=["cross_version_digest"],
       note="Measured identical on CPython 3.12.10 and 3.14.2 (KELLOGG_BENCH_PYTHONS). 3.11 and 3.13 "
            "are not installed on the reference host and are recorded NOT_RUN; a CI matrix closes them."),
    # Part X — formal proofs
    _i("X.T1", "X", "Lean: Binet & Cassini in Z[phi]", "No sorry.", "NOT_STARTED",
       note="No Lean toolchain on the reference host; no .lean file is claimed."),
    _i("X.T2", "X", "Lean: fold invertibility", "unfold(fold(x)) = x.", "NOT_STARTED"),
    _i("X.T3", "X", "Lean: 32-face coverage", "gcd(stride, 32) = 1 => full traversal.", "NOT_STARTED",
       symbols=["kellogg.traversal.TRAVERSAL_STRIDE"]),
    _i("X.T4", "X", "Lean: certificate soundness", "", "NOT_STARTED"),
    _i("X.T5", "X", "Lean: composition soundness", "", "NOT_STARTED"),
    _i("X.T6", "X", "Lean: replay determinism", "", "NOT_STARTED"),
    _i("X.2", "X", "Proofs separate from runtime tests", "Correspondence declared, not assumed.", "EXACT",
       note="theorem_proven stays False on every runtime record."),
    # Part XII — boundary (products)
    _i("XII.aethel", "XII", "Aethel", "Fold custody, NumericFoldState, integrity gate.", "DELEGATED",
       owner="aethel"),
    _i("XII.chronus", "XII", "Chronus", "Execution scheduling, OpenCL dispatch, virtual iGPU.", "DELEGATED",
       owner="chronus"),
    _i("XII.mining", "XII", "Mining", "SHA-256d, nonce search, block validation.", "DELEGATED", owner="mining",
       note="kellogg/public_headers.py (Bitcoin header survey) moved to mining/public_headers.py."),
    _i("XII.theseus", "XII", "THESEUS", "Durable custody, records, provenance.", "DELEGATED", owner="theseus"),
    _i("XII.ovid", "XII", "OVID", "Transformation, lineage.", "DELEGATED", owner="ovid"),
    _i("XII.salamander", "XII", "SALAMANDER", "Bounded self-healing.", "DELEGATED", owner="salamander"),
    _i("XII.al_haras", "XII", "AL HARAS", "Security, mediation, governance.", "DELEGATED", owner="al_haras"),
    _i("XII.turing", "XII", "TURING", "Virtual quantum computer.", "DELEGATED", owner="turing",
       note="Kellogg no longer imports turing_core (family companions and the dual frame are Kellogg's)."),
    _i("XII.pythia", "XII", "PYTHIA", "Predictive/causal intelligence, mining authority.", "DELEGATED",
       owner="pythia"),
    _i("XII.euclid", "XII", "EUCLID", "Intelligence orchestration.", "DELEGATED", owner="euclid"),
    # Discoveries recorded while building Kellogg against the specification
    _i("D.frame", "discovery", "Dual frame", "turing_core's dual-overlay frame is not dual.", "CORRECTED",
       owner="turing", symbols=["kellogg.quantum_tensor.dual_frame_is_dual"],
       note="Its 20 dodecahedron vertices are the mirror orientation; none sit at the icosahedron's face "
            "centres. Kellogg previously returned that frame whenever turing_core imported."),
    _i("D.reconstruct", "discovery", "Unguarded dense reconstruction", "TensorTrain.reconstruct had no "
       "size guard; a 10,000-site MPS would densify 2^10000.", "CORRECTED",
       symbols=["kellogg.tensor_network.TensorTrain.reconstruct"],
       note="reconstruct now refuses more than max_elements (default 2^27) values, matching the "
            "existing MatrixProductOperator.to_full_matrix guard."),
    _i("D.custody", "discovery", "Content-addressed custody deduplicates cores",
       "A 1,000-qubit GHZ state occupies 3 custody blocks.", "EXACT",
       symbols=["kellogg.exact_network.ExactTensorTrain.unique_blocks"], benchmarks=["memory_footprint"]),
)


def _resolve(dotted: str) -> object:
    parts = dotted.split(".")
    for cut in range(len(parts), 0, -1):
        try:
            obj = importlib.import_module(".".join(parts[:cut]))
        except ImportError:
            continue
        for attr in parts[cut:]:
            obj = getattr(obj, attr)
        return obj
    raise ImportError(dotted)


def verify_registry() -> Dict[str, object]:
    from .benchmark import BENCHMARKS

    problems: List[str] = []
    ids = [item.id for item in REGISTRY]
    if len(ids) != len(set(ids)):
        problems.append("duplicate ids")
    for item in REGISTRY:
        if item.status not in STATUSES:
            problems.append(f"{item.id}: bad status {item.status}")
        if item.owner not in PRODUCTS:
            problems.append(f"{item.id}: unknown owner {item.owner}")
        if item.status == "DELEGATED" and item.owner == "kellogg":
            problems.append(f"{item.id}: delegated to itself")
        if item.status in ("CORRECTED", "REFUTED", "RESEARCH") and not item.note:
            problems.append(f"{item.id}: {item.status} without a note")
        for sym in item.symbols:
            try:
                _resolve(sym)
            except (ImportError, AttributeError) as exc:
                problems.append(f"{item.id}: {sym} does not resolve ({exc})")
        for bench in item.benchmarks:
            if bench not in BENCHMARKS:
                problems.append(f"{item.id}: unknown benchmark {bench}")
    counts: Dict[str, int] = {}
    for item in REGISTRY:
        counts[item.status] = counts.get(item.status, 0) + 1
    return {"items": len(REGISTRY), "counts": counts, "problems": problems, "ok": not problems}


def by_status(status: str) -> Tuple[SpecItem, ...]:
    return tuple(item for item in REGISTRY if item.status == status)


__all__ = ["PRODUCTS", "REGISTRY", "STATUSES", "SpecItem", "by_status", "verify_registry"]
