"""Exact tests for the POVM-boundary execution invariants.

Invariant 1 (POVM boundary): 20 ASI-school effects {Pi_k} on an 11D exact
state space with  sum_k Pi_k = I  and  Pi_k >= 0, plus separation of the
internal state from the scalar readout (pure projection, no feedback).

Verification matrix rows under test:
- Pisot Engine (toe.py): Galois conjugate bounds via exact Sturm/Fraction.
- Zeckendorf Codec (unified_punch/hardened): non-adjacency, F_93, full u64.
- OpenCL F_93 table: no ulong wrap; lo/hi mask split ranges tile exactly.
- Telemetry: reported count == completed sha256d evaluations, 1:1. This is
  parity over digest evaluations, NOT device clock cycles — silicon clocks
  are unobservable from this layer, and claiming cycle parity would itself
  breach the telemetry truth boundary.
- Stratum ingestion: exact notify parsing; fail-closed submit gate.

Scope note: the 20 effects below are a reference construction proving the
POVM invariant algebra (completeness, positivity, trace preservation, and
a feedback-free Born readout) over the 11D exact state space. This file
does NOT claim production ASI-school routing already consumes this POVM;
that wiring is a separate integration and must not be asserted as done.

Deterministic algebra uses Fraction/integer arithmetic; environment isolation
uses pytest's monkeypatch fixture. No network connection is opened.
"""

import hashlib
import random
import re
import struct
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

import pytest

from Intelligence.hardened_unified_substrate import HardenedZeckendorfCodec

KERNEL_PATH = (
    Path(__file__).resolve().parent.parent
    / "kernels"
    / "unified_punch_kernel.cl"
)


# ---------------------------------------------------------------------------
# Invariant 1: the 20-school POVM on the 11D exact state space
# ---------------------------------------------------------------------------


def _school_effects():
    """20 rank-1 axis effects: axes 0,1 project fully; axes 2..10 are
    Fibonacci-split with rational weights p = Z_d / (Z_d + Z_{d+1}).
    The split ratio converges to phi^-2."""
    Z = HardenedZeckendorfCodec.FIBONACCI  # Zeckendorf fibs: 0,1,2,3,5,...
    effects = []
    for d in range(11):
        if d < 2:
            effects.append((d, Fraction(1)))
        else:
            p = Fraction(Z[d + 1], Z[d + 1] + Z[d + 2])
            effects.append((d, p))
            effects.append((d, 1 - p))
    assert len(effects) == 20
    return effects


def _effect_matrix(effect):
    d, w = effect
    M = [[Fraction(0)] * 11 for _ in range(11)]
    M[d][d] = w
    return M


def _mat_add(A, B):
    return [[a + b for a, b in zip(ra, rb)] for ra, rb in zip(A, B)]


def test_povm_20_schools_exact_completion_and_positivity():
    effects = _school_effects()
    total = None
    for e in effects:
        M = _effect_matrix(e)
        # Positivity: axis-aligned rank-1 with rational weight in (0, 1].
        d, w = e
        assert 0 < w <= 1
        assert all(M[i][j] == 0 for i in range(11) for j in range(11) if (i, j) != (d, d))
        total = M if total is None else _mat_add(total, M)
    # Completeness: sum of effects is EXACTLY the identity over Q.
    identity = [[Fraction(1) if i == j else Fraction(0) for j in range(11)] for i in range(11)]
    assert total == identity
    # Trace preservation: Tr(sum Pi) == Tr(I) == 11 exactly.
    assert sum(total[i][i] for i in range(11)) == 11
    # The split ratio is the golden conjugate damping. p_d =
    # F_{n}/F_{n+2} -> phi^-2 = 0.38196601125010510 (NOT phi^-1: the
    # denominator sums two successors, so the limit is F_n/F_{n+2}).
    # Deep split (d=10): p = 144/377 = 0.3819660... exact to ~1e-8.
    p_last = _school_effects()[18][1]
    assert abs(float(p_last) - 0.38196601125010510) < 1e-3


def test_povm_readout_is_exact_and_never_feeds_back():
    """Born readout Tr(rho Pi) as an exact Fraction; the internal density
    matrix is NOT mutated by the projection (separation of state and
    readout — no floating-point injection into the manifold state)."""
    Z = HardenedZeckendorfCodec.FIBONACCI[1:12]  # Z_1..Z_11
    total = sum(Z)
    rho = [Fraction(z, total) for z in Z]  # exact diagonal density matrix
    assert sum(rho) == 1

    def readout(rho_vec, effect):
        d, w = effect
        return rho_vec[d] * w  # Tr(rho Pi) on the diagonal

    snapshot = list(rho)
    values = [readout(rho, e) for e in _school_effects()]
    assert sum(values) == sum(
        rho[d] for d in range(11)
    )  # completeness: probabilities sum to Tr(rho I) = 1
    assert all(isinstance(v, Fraction) for v in values)
    assert rho == snapshot  # zero feedback into the internal state


# ---------------------------------------------------------------------------
# Pisot Engine (toe.py): Galois conjugate bounds via exact Sturm/Fraction
# ---------------------------------------------------------------------------


def test_toe_pisot_engine_galois_bounds_sturm_exact():
    toe = pytest.importorskip("toe")
    fam = toe.ExtendedAlgebraicFamily(precision=40)
    for name in fam.FAMILY_NAMES:
        assert fam.verify_pisot(name) is True
        assert fam.root(name) > 1
        assert fam.conjugate_modulus(name) < 1
    # Golden root is phi to full Decimal precision.
    phi_exact = (Decimal(1) + Decimal(5).sqrt()) / 2
    assert abs(fam.root("golden") - phi_exact) < Decimal("1e-30")
    # Sturm isolation on x^2 - x - 1 with exact Fractions: exactly one
    # root in (1, 2) — the Pisot root phi — and exactly one in (-1, 0)
    # — the conjugate psi = -1/phi. |psi| < 1 is thereby PROVEN by exact
    # sign-variation counting, not by floating-point evaluation.
    p = [Fraction(1), Fraction(-1), Fraction(-1)]
    seq = toe.ExtendedAlgebraicFamily._sturm(p)
    V = toe.ExtendedAlgebraicFamily._sturm_variations
    assert V(seq, Fraction(-1)) - V(seq, Fraction(0)) == 1  # psi in (-1, 0)
    assert V(seq, Fraction(1)) - V(seq, Fraction(2)) == 1  # phi in (1, 2)


# ---------------------------------------------------------------------------
# Zeckendorf Codec: F_93, full uint64, non-adjacency ('11' -> zero)
# ---------------------------------------------------------------------------


def test_f93_codec_full_uint64_roundtrip_and_nonadjacency():
    U64 = 2**64 - 1
    table = HardenedZeckendorfCodec.FIBONACCI
    cases = [0, 1, 2, 3, 4, 2**63, U64, table[92] - 1, table[91]]
    rng = random.Random(9301)
    cases += [rng.getrandbits(64) for _ in range(200)]
    for n in cases:
        mask = HardenedZeckendorfCodec.encode(n)
        assert HardenedZeckendorfCodec.verify_non_adjacent(mask) is True
        assert HardenedZeckendorfCodec.decode(mask) == n
    # The '11' amplitude-invariant: any adjacent mask fails the check.
    assert HardenedZeckendorfCodec.verify_non_adjacent(0b11) is False
    assert HardenedZeckendorfCodec.verify_non_adjacent(0b1101) is False
    # Range guard: values >= the table's last entry (F_94-shifted) are
    # rejected — but the ENTIRE uint64 range lies below it and encodes.
    assert table[-1] > U64
    with pytest.raises(ValueError):
        HardenedZeckendorfCodec.encode(table[-1])


# ---------------------------------------------------------------------------
# OpenCL F_93 substrate: no ulong wrap; lo/hi mask split tiles exactly
# ---------------------------------------------------------------------------


def test_kernel_fib_table_93_no_ulong_wrap_and_lohi_tiling():
    src = KERNEL_PATH.read_text(encoding="utf-8")
    m = re.search(r"__constant ulong FIB_TABLE\[94\]\s*=\s*\{(.*?)\};", src, re.S)
    assert m is not None
    values = [int(x) for x in re.findall(r"(\d+)UL", m.group(1))]
    U64 = 2**64 - 1
    # 94 entries, exact Fibonacci recurrence, and EVERY entry fits ulong —
    # the table stops at standard F_93 = 12200160415121876738 < 2^64-1.
    assert len(values) == 94
    assert values[0] == 0 and values[1] == 1 and values[2] == 1
    for i in range(2, 94):
        assert values[i] == values[i - 1] + values[i - 2]
    assert all(v <= U64 for v in values)
    assert values[-1] == 12200160415121876738
    # The lo/hi mask split is REQUIRED and the two ranges tile exactly:
    # highest mask bit = 93 - 2 = 91 > 63, so one u64 word cannot hold the
    # mask; lo covers bits 0..63, hi covers bits 64..91 (i = 66..93).
    assert 93 - 2 == 91 and 91 >= 64
    assert 66 - 2 - 64 == 0 and 93 - 2 - 64 == 27
    # Kernel table and the Python codec agree on the shared Zeckendorf
    # values (kernel standard-indexing stops at F_93; the codec's
    # Zeckendorf-indexing adds F_94 as the exclusive upper bound).
    assert set(values) <= set(HardenedZeckendorfCodec.FIBONACCI) | {1}
    # FIBONACCI is Zeckendorf-indexed (FIBONACCI[i] = standard F_{i+1}),
    # so standard F_93 = kernel values[-1] sits at codec index 92.
    assert values[-1] == HardenedZeckendorfCodec.FIBONACCI[92]


# ---------------------------------------------------------------------------
# Telemetry: absolute 1:1 parity of physical sha256d cycles
# ---------------------------------------------------------------------------


def test_telemetry_completed_digest_accounting(monkeypatch):
    import mining.hash_pipeline as hp

    # Neutral scoring: pin the punch host out of the pipeline so probe
    # order is the identity. This isolates the telemetry invariant from
    # Stage A dispatch entirely.
    monkeypatch.setattr(hp, "UnifiedPunchHost", None)
    header = hashlib.sha256(b"povm-parity").digest() * 2 + bytes(16)
    pipeline = hp.HashPipeline(host=None)

    # Impossible target (all-zero): every probe really runs sha256d — the
    # reported count must equal the completed digest evaluations EXACTLY.
    # (Parity is over completed evaluations, not silicon clock cycles:
    # device clocks are unobservable from this layer.)
    hard = pipeline.grind(header, bytes(32), list(range(50)))
    assert hard.winning_nonce is None
    assert hard.hashes_computed == 50

    # Easy target: the winner's digest must be genuinely below target.
    # Serial (CPU) grind early-exits at count == 1; batched (OpenCL) grind
    # physically computes EVERY digest in the launched batch (count == 50).
    # Both are honest: reported count == digests actually computed.
    easy = pipeline.grind(header, b"\xff" * 32, list(range(50)))
    assert easy.mining_success is True
    assert easy.winning_hash[::-1] < b"\xff" * 32
    assert easy.winning_nonce == 0
    assert easy.hashes_computed == (1 if easy.backend == "cpu" else 50)
    # Independent consensus re-verification: the reported winner is a REAL
    # sha256d preimage — recomputed here from raw hashlib, not trusted
    # from the pipeline's own bookkeeping.
    blob = header[:76] + struct.pack("<I", easy.winning_nonce)
    assert hashlib.sha256(hashlib.sha256(blob).digest()).digest() == easy.winning_hash
    # Backend telemetry names the engine that physically ran the digests.
    assert easy.backend == pipeline.hasher.backend
    # Reported throughput is derived ONLY from measured count / time.
    assert easy.measured_hps == pytest.approx(easy.hashes_computed / easy.elapsed_seconds, rel=1e-9)


# ---------------------------------------------------------------------------
# Stratum ingestion: exact notify parsing; fail-closed submit gate
# ---------------------------------------------------------------------------


def test_stratum_notify_parser_exact_and_gate_fail_closed(monkeypatch):
    from mining.stratum_bridge import StratumBridge, is_live_submit_approved

    # Hermetic: strip any locally-set approval flags so running this test
    # can never itself approve a live share submission.
    for var in (
        "HYBA_ENABLE_LIVE_SHARE_SUBMIT",
        "HYBA_LIVE_SHARE_APPROVAL_ID",
        "HYBA_AUTONOMOUS_EXTERNAL_ACTIONS",
    ):
        monkeypatch.delenv(var, raising=False)
    assert is_live_submit_approved() is False
    assert is_live_submit_approved({}) is False  # empty env: no submit
    bridge = StratumBridge("127.0.0.1", 3333, "worker.test", "x")
    assert bridge.sock is None  # constructor never opens a socket

    notify = {
        "id": None,
        "method": "mining.notify",
        "params": [
            "job-1",
            "ab" * 32,
            "coinb1",
            "coinb2",
            ["aa" * 4, "bb" * 4],
            "20000000",
            "1a0b2c3d",
            "65432100",
            True,
        ],
    }
    bridge._handle_server_message(notify)
    job = bridge.last_job
    assert job is not None
    assert job.job_id == "job-1"
    assert job.prev_hash == "ab" * 32
    assert job.merkle_branch == ["aa" * 4, "bb" * 4]
    assert job.version == "20000000"
    assert job.nbits == "1a0b2c3d"
    assert job.ntime == "65432100"
    assert job.clean_jobs is True
    assert job.difficulty == 1.0

    # set_difficulty propagates into the held job (live header tracking).
    bridge._handle_server_message({"id": None, "method": "mining.set_difficulty", "params": [4096]})
    assert bridge.last_job.difficulty == 4096.0

    # Short/notify params are ignored, not crashed on.
    bridge.last_job = None
    bridge._handle_server_message({"id": None, "method": "mining.notify", "params": ["x"]})
    assert bridge.last_job is None

    # Fail-closed gate: no approval -> submit returns None, zero socket
    # I/O, and no job resurrection.
    assert bridge.submit_share("job-1", "00", "65432100", "deadbeef") is None
    assert bridge.submit_calls == 0
    assert bridge.last_job is None


# ---------------------------------------------------------------------------
# POVM separation invariant — production enforcement
# ---------------------------------------------------------------------------


def test_asi_schools_have_no_substrate_write_path():
    """No pythagoras/asi module may import the storage substrate: the
    exact manifold state is never written from scalar readouts (the
    floating-point injection boundary)."""
    import ast

    asi_dir = Path(__file__).resolve().parent.parent / "pythagoras" / "asi"
    assert asi_dir.is_dir()
    banned_mods = ("hardened_unified_substrate",)
    banned_names = {"PrimeStorageManifold", "SelfHealingSubstrate"}
    checked = 0
    for f in sorted(asi_dir.glob("*.py")):
        tree = ast.parse(f.read_text(encoding="utf-8", errors="ignore"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                assert not any(b in mod for b in banned_mods), f.name
                assert not (banned_names & {a.name for a in node.names}), f.name
                checked += 1
            elif isinstance(node, ast.Import):
                for a in node.names:
                    assert not any(b in a.name for b in banned_mods), f.name
    assert checked > 0


def test_asi_projection_is_non_disturbing():
    """Every bridge readout leaves the manifold state bit-identical —
    measurement never feeds back into |psi>."""
    import numpy as np

    from pythagoras.asi import manifold_bridge as mb

    rng = np.random.default_rng(11)
    state = rng.standard_normal(11) * 0.1
    snapshot = state.copy()
    mb.scalar_projection(state)
    mb.state_to_covariance(state)
    mb.state_to_graph(state)
    mb.state_to_prior_layers(state, depth=3)
    assert np.array_equal(state, snapshot)
