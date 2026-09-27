"""Substrate freeze — write, verify, and sign off ``turing_core.py``.

``freeze_substrate()`` proves, on the real module:
  * ``M15 == ((219, 98), (98, 121))`` in GL(2, Z/256Z)
  * ``M15 * M15_INV ≡ I (mod 256)`` — exact integer inverse
  * ``det(M15) ≡ -1 (mod 256)`` — the Cassini protection
  * ``t_phi_unfold(t_phi_fold(b), len(b)) == b`` bit-exact for a
    deterministic sweep of every length 0..511

The signoff file records *which checks ran* per role — attestations of
executed evidence, not human signatures.
"""

from __future__ import annotations

import hashlib
import json
import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, Optional

from hyba.operating_model.roles import repo_root

FREEZE_PATH = "docs/substrate_freeze.json"
FREEZE_MAX_LEN = 512
FREEZE_VECTORS_PER_LEN = 16  # deterministic sweep density per length


def _load_turing_core(root: Path) -> ModuleType:
    path = root / "turing_core.py"
    spec = importlib.util.spec_from_file_location("turing_core_frozen", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _matmul_mod(
    a: tuple[tuple[int, int], tuple[int, int]],
    b: tuple[tuple[int, int], tuple[int, int]],
    m: int,
) -> tuple[tuple[int, int], tuple[int, int]]:
    return (
        ((a[0][0] * b[0][0] + a[0][1] * b[1][0]) % m,
         (a[0][0] * b[0][1] + a[0][1] * b[1][1]) % m),
        ((a[1][0] * b[0][0] + a[1][1] * b[1][0]) % m,
         (a[1][0] * b[0][1] + a[1][1] * b[1][1]) % m),
    )


def _det_mod(m15: tuple[tuple[int, int], tuple[int, int]], m: int) -> int:
    return (m15[0][0] * m15[1][1] - m15[0][1] * m15[1][0]) % m


def _deterministic_bytes(length: int, seed: int) -> bytes:
    """Deterministic test vector — index/mixing function of (length, seed);
    no RNG, no per-instance hardcoding."""
    return bytes(((i * 37 + length * 11 + seed * 101) ^ (i >> 1)) & 0xFF
                 for i in range(length))


def freeze_substrate(root: Optional[Path] = None, *, write: bool = True) -> Dict[str, Any]:
    """Verify the substrate and record the freeze. Raises on any failure —
    a substrate that cannot prove its invariants must not be built on."""
    root = repo_root() if root is None else Path(root)
    core_path = root / "turing_core.py"
    blob = core_path.read_bytes()
    core = _load_turing_core(root)

    checks: Dict[str, str] = {}

    # 1. Matrix and ring.
    assert core.M15 == ((219, 98), (98, 121)), "M15 diverged from the declared matrix"
    checks["mathematician"] = "exact inverse verified"

    # 2. Exact integer inverse mod 256.
    ident = _matmul_mod(core.M15, core.M15_INV, 256)
    assert ident == ((1, 0), (0, 1)), f"M15*M15_INV mod 256 = {ident}, not I"
    assert _matmul_mod(core.M15_INV, core.M15, 256) == ident
    checks["cryptographer"] = "mod-256 arithmetic verified"

    # 3. Cassini protection: det = -1 mod 256.
    assert _det_mod(core.M15, 256) == 255
    checks["number_theorist"] = "Cassini verified"

    # 4. Round-trip bit-exact, deterministic sweep, odd + even lengths.
    for length in range(FREEZE_MAX_LEN):
        for seed in range(FREEZE_VECTORS_PER_LEN):
            raw = _deterministic_bytes(length, seed)
            folded = core.t_phi_fold(raw)
            back = core.t_phi_unfold(folded, length)
            assert back == raw, f"round-trip broke at L={length} seed={seed}"
            # Folded form must answer queries without materialising raw:
            assert bytes(core.iter_original_u8(folded, length)) == raw
    checks["systems"] = "runs in target runtime"

    # 5. No float leak on the exact fold surface.
    import inspect
    src = inspect.getsource(core.t_phi_fold) + inspect.getsource(core.t_phi_unfold)
    assert "float(" not in src and "math." not in src, \
        "float leak on the exact fold surface"
    checks["numerical"] = "no float leak on exact surfaces"

    # 6. The lemma freezes with the substrate — verify + executed signoff.
    from hyba.operating_model.lemma import (
        LEMMA, LEMMA_PATH, collect_signoff, verify_lemma)
    lemma_v = verify_lemma(LEMMA, LEMMA["verified_range"])
    assert lemma_v[0]["verdict"] == "HOLDS"
    lemma_signoff = collect_signoff(LEMMA, LEMMA["verified_range"])
    lemma_doc = root / LEMMA_PATH
    lemma_sha = hashlib.sha256(
        lemma_doc.read_bytes()).hexdigest() if lemma_doc.is_file() else None

    record = {
        "frozen_sha": hashlib.sha256(blob).hexdigest(),
        "file": "turing_core.py",
        "sweep": {"max_len": FREEZE_MAX_LEN - 1,
                  "vectors_per_len": FREEZE_VECTORS_PER_LEN,
                  "vectors_total": FREEZE_MAX_LEN * FREEZE_VECTORS_PER_LEN},
        "lemma_sha": lemma_sha,
        "lemma_verify": lemma_v,
        "signatures": checks,
        "lemma_signoff": lemma_signoff["attestations"],
        "theorem_proven": False,
    }
    if write:
        out = root / FREEZE_PATH
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    return record


def substrate_frozen(root: Optional[Path] = None) -> bool:
    """True iff a freeze record exists AND the recorded sha matches the
    current turing_core.py bytes — a silent substrate drift re-opens the
    gate."""
    root = repo_root() if root is None else Path(root)
    rec = root / FREEZE_PATH
    core = root / "turing_core.py"
    if not rec.is_file() or not core.is_file():
        return False
    try:
        stored = json.loads(rec.read_text(encoding="utf-8"))
    except Exception:
        return False
    if stored.get("theorem_proven") is not False:
        return False
    if stored.get("frozen_sha") != hashlib.sha256(core.read_bytes()).hexdigest():
        return False
    # Lemma drift also re-opens the freeze — they freeze together.
    lemma_doc = root / "docs" / "lemma_lucas_polynomial.md"
    stored_lemma_sha = stored.get("lemma_sha")
    if stored_lemma_sha is not None:
        if not lemma_doc.is_file():
            return False
        return stored_lemma_sha == hashlib.sha256(
            lemma_doc.read_bytes()).hexdigest()
    return True
