import numpy as np
import pytest

from quantum import (State, apply_diffusion, apply_phase, brute_force_optimum,
                     decode_allocation, dense_diffusion, dense_phase, encode,
                     evolve, problem_diagonal)
from team.agents import Specialist, breed
from team.contracts import ContractRegistry, canonical_json
from team.fitness import FitnessEvaluator
from team.fold import M15, M15_INV, fold, from_wire, to_wire, unfold
from team.tool import QuantumTool
from team.wire import (FitnessReportMessage, MessageKind, PatchMessage,
                       TaskMessage, decode_frame, encode_frame)


# ---- fold: the bijectivity proof ------------------------------------------

def test_fold_inverse_is_derived():
    assert M15_INV == ((135, 98), (98, 37))
    ident = [[sum(M15[i][k] * M15_INV[k][j] for k in range(2)) % 256
              for j in range(2)] for i in range(2)]
    assert ident == [[1, 0], [0, 1]]


def test_fold_determinant_is_minus_one():
    assert (M15[0][0] * M15[1][1] - M15[0][1] * M15[1][0]) % 256 == 255


def test_fold_matches_chronus_canonical_m15():
    """Provenance: byte-identical to Chronus's canonical M15 fold over all
    65,536 pairs and the odd-length pad path."""
    golden = pytest.importorskip("chronus.math.golden_core")
    assert golden.M15 == M15 and golden.M15_INV == M15_INV
    for x in range(256):
        for y in range(256):
            pair = bytes((x, y))
            assert fold(pair).data == golden.t_phi_fold(pair)
    assert fold(b"\x07").data == golden.t_phi_fold(b"\x07")


def test_fold_every_pair_roundtrips():
    for x in range(256):
        for y in range(256):
            assert unfold(fold(bytes((x, y)))) == bytes((x, y))


@pytest.mark.parametrize("n", [0, 1, 2, 7, 33, 255])
def test_fold_roundtrip_lengths(n):
    raw = bytes((i * 37 + 11) & 0xFF for i in range(n))
    assert unfold(fold(raw)) == raw
    assert len(fold(raw).data) == n + (n & 1)
    assert unfold(from_wire(to_wire(fold(raw)))) == raw


# ---- wire codec ------------------------------------------------------------

def _task_msg(i=0, desc="implement module_0"):
    return TaskMessage(task_id=i, generation=0, specialty="api",
                       module="module_0", description=desc,
                       required_digests=("a" * 64,), parent_patches=())


def _reg_two_contracts():
    reg = ContractRegistry()
    reg.freeze("core_api", {"type": "object"})
    reg.freeze("wire_format", {"type": "object"})
    return reg


def test_frame_roundtrip_all_kinds():
    reg = _reg_two_contracts()
    frames = [
        encode_frame(TaskMessage(0, 0, "api", "m", "d", ("a" * 64,))),
        encode_frame(PatchMessage(task_id=0, agent_id="a", parent_ids=(),
                                  files={"m.py": "x"},
                                  declares=reg.live_digests(),
                                  tests_passed=8, tests_total=10)),
        encode_frame(FitnessReportMessage("b" * 64, 0, True, (), (), 0.8,
                                          0.0, 0.8, 0.8 * 3.141592653589793)),
    ]
    for f in frames:
        kind, msg = decode_frame(f)
        assert decode_frame(encode_frame(msg)) == (kind, msg)


def test_frame_rejects_non_hex_digests():
    """The schema's hex pattern is enforced on decode, not just documented."""
    with pytest.raises(ValueError, match="pattern"):
        decode_frame(encode_frame(TaskMessage(0, 0, "api", "m", "d",
                                              ("x" * 64,))))


def test_frame_odd_length_payload_roundtrips():
    """Force an odd canonical payload through the fold padding path."""
    desc = "x"
    while len(canonical_json(_task_msg(desc=desc).to_dict())) % 2 == 0:
        desc += "x"
    frame = encode_frame(_task_msg(desc=desc))
    kind, msg = decode_frame(frame)
    assert msg.description == desc


def test_frame_rejects_corruption():
    frame = bytearray(encode_frame(_task_msg()))
    frame[-1] ^= 0xFF
    with pytest.raises(ValueError, match="SHA-256 prefix mismatch"):
        decode_frame(bytes(frame))

    frame = bytearray(encode_frame(_task_msg()))
    frame[0:2] = b"XX"
    with pytest.raises(ValueError, match="magic"):
        decode_frame(bytes(frame))

    frame = bytearray(encode_frame(_task_msg()))
    frame[2] = 0x09
    with pytest.raises(ValueError, match="version"):
        decode_frame(bytes(frame))

    frame = bytearray(encode_frame(_task_msg()))
    frame[4] ^= 0x01
    with pytest.raises(ValueError, match="length mismatch"):
        decode_frame(bytes(frame))

    with pytest.raises(ValueError, match="Truncated"):
        decode_frame(encode_frame(_task_msg())[:10])


def test_patch_id_is_content_addressed():
    reg = _reg_two_contracts()
    p = PatchMessage(task_id=0, agent_id="a", parent_ids=(),
                     files={"m.py": "x"}, declares=reg.live_digests(),
                     tests_passed=5, tests_total=10)
    q = PatchMessage(task_id=0, agent_id="a", parent_ids=(),
                     files={"m.py": "y"}, declares=reg.live_digests(),
                     tests_passed=5, tests_total=10)
    assert p.patch_id != q.patch_id
    with pytest.raises(ValueError, match="patch_id mismatch"):
        PatchMessage(task_id=0, agent_id="a", parent_ids=(),
                     files={"m.py": "x"}, declares=reg.live_digests(),
                     tests_passed=5, tests_total=10, patch_id="f" * 64)


def test_schema_validation_rejects():
    frame = bytearray(encode_frame(_task_msg()))
    frame += b" "
    with pytest.raises(ValueError):
        decode_frame(bytes(frame))
    bad = TaskMessage(0, 0, "sales", "m", "d", ())   # specialty not in enum
    with pytest.raises(ValueError):
        decode_frame(encode_frame(bad))


# ---- quantum layer ----------------------------------------------------------

def test_phase_and_diffusion_are_unitary():
    U = dense_phase(np.linspace(0, 1, 16))
    D = dense_diffusion(16)
    assert np.allclose(U.conj().T @ U, np.eye(16))
    assert np.allclose(D.conj().T @ D, np.eye(16))


def test_matrixfree_matches_dense():
    s = State.uniform(16)
    out_free = apply_diffusion(apply_phase(s, np.linspace(0, 1, 16)))
    out_dense = State(dense_diffusion(16)
                      @ (dense_phase(np.linspace(0, 1, 16)) @ s.amps))
    assert np.allclose(out_free.amps, out_dense.amps)


def test_phase_preserves_magnitudes_exactly():
    s = State.uniform(16)
    out = apply_phase(s, np.linspace(0, 1, 16))
    assert np.allclose(np.abs(out.amps), np.abs(s.amps))


def test_grover_recovers_marked_set():
    """Theorem check: N=16, M=2, r=2 -> sin^2(5·theta) > 0.94."""
    f = np.zeros(16)
    f[[5, 11]] = 1.0
    s = State.uniform(16)
    for _ in range(2):
        s = apply_phase(s, f)
        s = apply_diffusion(s)
    assert s.probs()[[5, 11]].sum() > 0.9


def test_load_penalty_sums_over_agents():
    """E = load_pen * sum_a max(0, n_a - limit)^2, hand-computed.
    T=3, A=2, limit=1: all on agent 0 -> over=(2,0) -> 6*4=24;
    (0,0,1) -> over=(1,0) -> 6; (0,1,1) -> over=(0,1) -> 6."""
    diag = problem_diagonal(3, 2, np.zeros((3, 2)), [], load_limit=1,
                            load_pen=6.0)
    assert diag.shape == (8,)
    assert diag[encode({0: 0, 1: 0, 2: 0}, 3, 2)] == 24.0
    assert diag[encode({0: 0, 1: 0, 2: 1}, 3, 2)] == 6.0
    assert diag[encode({0: 0, 1: 1, 2: 1}, 3, 2)] == 6.0


def test_adiabatic_matches_brute_force():
    """Certification: measured allocation's energy == min of the SAME
    diagonal the Hamiltonian encodes."""
    rng = np.random.default_rng(3)
    T, A = 4, 3
    cost = rng.uniform(0.5, 2.0, size=(T, A))
    diag = problem_diagonal(T, A, cost, [(0, 1), (2, 3)], 2)
    psi = evolve(diag, T, A, total_time=40.0, steps=2000)
    got = decode_allocation(np.abs(psi) ** 2, T, A)
    assert np.isclose(diag[encode(got, T, A)], diag.min())


def test_solve_allocation_default_schedule_matches_brute_force():
    """Exercises the default total_time/steps path (np.ptp) end to end."""
    rng = np.random.default_rng(5)
    cost = rng.uniform(0.5, 2.0, size=(4, 3))
    out = QuantumTool().solve_allocation(cost=cost, coupled=[(0, 1)],
                                         load_limit=2)
    diag = problem_diagonal(4, 3, cost, [(0, 1)], 2)
    assert np.isclose(diag[encode(out["assignments"], 4, 3)],
                      out["optimal_cost"])


def test_selection_schedule_is_closed_form():
    f = [0.1, 0.2, 0.15, 0.95, 0.9, 0.12, 0.3, 0.25]
    out = QuantumTool().select_generation(f, k=2, rng=np.random.default_rng(1))
    fn = np.asarray(f) / max(f)
    expected = max(1, int(np.floor(
        (np.pi / 4) * np.sqrt(len(f) / np.sum(fn ** 2)))))
    assert out["rounds"] == expected
    assert set(out["parent_indices"]) & set(np.argsort(f)[-2:])


def test_conformance_gate_with_live_digests():
    reg = _reg_two_contracts()
    evalr = FitnessEvaluator(reg)
    good = PatchMessage(0, "a", (), {}, declares=reg.live_digests(),
                        tests_passed=10, tests_total=10)
    stale = PatchMessage(0, "a", (), {}, declares=frozenset(),
                         tests_passed=10, tests_total=10)
    assert evalr.score(good) > 0.0
    assert evalr.score(stale) == 0.0


def test_end_to_end_loop_runs():
    from loop import run
    assert len(run(generations=2, T=6, seed=11)) == 2
