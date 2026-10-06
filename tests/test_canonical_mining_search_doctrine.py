from __future__ import annotations

import json
from pathlib import Path

import yaml

from scripts.check_canonical_mining_search import validate

ROOT = Path(__file__).resolve().parents[1]


def test_canonical_structured_search_doctrine_is_intact():
    validate(ROOT)


def test_resonance_figures_are_not_swapped():
    policy = yaml.safe_load(
        (ROOT / "governance" / "canonical_mining_search.yaml").read_text(encoding="utf-8")
    )
    evidence = json.loads(
        (
            ROOT
            / "artifacts"
            / "pythia_training"
            / "real_nonce_analysis_200_fresh.json"
        ).read_text(encoding="utf-8")
    )

    assert evidence["scoring"]["winner_hits"] == "122/200"
    assert evidence["scoring"]["winner_rate"] == 0.61
    assert evidence["baseline"]["rate"] == 0.61805
    assert policy["resonance"]["real_corpus"]["rate"] == 0.61
    assert policy["resonance"]["uniform_control"]["rate"] == 0.61805


def test_flat_search_cannot_be_promoted_over_hendrix_by_policy():
    policy = yaml.safe_load(
        (ROOT / "governance" / "canonical_mining_search.yaml").read_text(encoding="utf-8")
    )
    search = policy["search"]

    assert search["classification"] == "STRUCTURED_SEARCH"
    assert search["default_algorithm"] == "Hendrix"
    assert search["coverage"] == "FULL_NONCE_ESTATE"
    assert search["flat_search_may_replace_canonical_default"] is False
