"""Single frozen public thesis for the Chronus / PYTHIA systems paradigm.

Medal-path discipline: one claim surface. Everything else is scaffolding,
hypothesis, or legacy. Overclaims are machine-rejected by
``assert_thesis_bounds`` and by ``al_haras.refuted_claims``.
"""
from __future__ import annotations

from typing import Any, Mapping

from al_haras.refuted_claims import assert_claims

THESIS_ID = "c-paradigm-thesis-v1"

THESIS: dict[str, Any] = {
    "id": THESIS_ID,
    "title": "Fail-Closed Virtual Accelerators",
    "sentence": (
        "Chronus provides a versioned, fail-closed virtual accelerator ABI "
        "whose receipts bind workload, backend, digest, and trust class; "
        "algebraic schedules may reorder classical work but never substitute "
        "for SHA256d or pool acknowledgement."
    ),
    "track": "systems",  # not Fields math, not quantum hardware, not EH/s
    "abi_version": "virtual_igpu_v1",
    "separations": (
        "schedule_is_not_accept_predicate",
        "delivery_mode_is_not_backend",
        "requested_policy_is_not_executed_route",
        "content_hash_is_not_hardware_root",
        "software_result_is_never_labelled_device",
        "pool_ack_is_ground_truth_for_shares",
    ),
    "authorized_claims": (
        "virtual_igpu_v1 ABI is versioned and fail-closed",
        "TrustClass lattice is explicit and non-inflating",
        "golden-stride walk is a bijection of Z/2^32Z (ordering only)",
        "evidence ledger is content-addressed and chain-linked",
        "missing adapter/device fails closed with typed reason",
        "schedule bakeoff reports measured times without inventing advantage",
    ),
    "forbidden_claims": (
        "quantum advantage for Bitcoin mining",
        "exponential speedup",
        "10 EH/s",
        "one device equals 20,000 NVIDIA GPUs",
        "simulator is physical quantum",
        "Lucas/Pisot quantum speedup",
        "Cassini seal is proof-of-work",
        "content hash proves hardware-rooted execution",
        "ordering predicts SHA256d output",
        "any Millennium problem",
    ),
    "triad": {
        "lemma": "golden_stride_bijection",
        "systems": "virtual_igpu_v1_conformance",
        "measurement": "schedule_bakeoff_honest",
    },
    "theorem_proven": False,  # systems thesis; math lemmas pin their own flags
    "status": "VERIFIED_SPINE",  # spine exists; external bakeoff still open
}


def thesis_text() -> str:
    """Canonical one-sentence thesis."""
    return str(THESIS["sentence"])


def assert_thesis_bounds(text: str | Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Reject refuted/prohibited phrasing in a document or the thesis itself.

    Returns a small report. Raises ``ClaimRefuted`` on banned phrases.
    """
    if text is None:
        blob = "\n".join(
            [
                thesis_text(),
                " ".join(THESIS["authorized_claims"]),
                " ".join(f"NOT: {c}" for c in THESIS["forbidden_claims"]),
            ]
        )
    elif isinstance(text, Mapping):
        blob = "\n".join(f"{k}: {v}" for k, v in text.items())
    else:
        blob = str(text)

    # Positive surface must not contain refuted marketing.
    # Forbidden list is quoted as negation — strip those lines first.
    lines = []
    for line in blob.splitlines():
        low = line.strip().casefold()
        if low.startswith("not:") or "forbidden" in low or "never" in low:
            continue
        if any(f.casefold() in low for f in THESIS["forbidden_claims"]):
            # Line states a forbidden claim affirmatively — reject via al_haras
            # only when it is not clearly a disclaimer.
            if not any(
                m in low
                for m in (
                    "not a",
                    "never",
                    "does not",
                    "must not",
                    "forbidden",
                    "refuted",
                    "prohibited",
                    "without inventing",
                )
            ):
                assert_claims(line)
        lines.append(line)
    cleaned = "\n".join(lines)
    assert_claims(cleaned)
    return {
        "ok": True,
        "thesis_id": THESIS_ID,
        "track": THESIS["track"],
        "sentence": thesis_text(),
    }


def as_claim_record() -> dict[str, Any]:
    """Shape suitable for claims.yaml / release notes."""
    return {
        "id": THESIS_ID,
        "text": thesis_text(),
        "status": "VERIFIED",
        "test_command": "python -m pytest tests/test_paradigm_spine.py -q",
        "artifact": "chronus/paradigm/thesis.py",
        "baseline": "single systems thesis; schedule≠accept; trust non-inflating",
    }
