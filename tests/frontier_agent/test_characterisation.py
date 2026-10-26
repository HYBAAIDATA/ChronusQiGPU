from fractions import Fraction as F
import pytest
from chronus.agent._contracts import ContractError
from chronus.agent.characterisation import (
    MetaObservation,
    meta_calibration_review,
    characterise,
    predict_success,
)
from tests.frontier_agent.conftest import H


def test_m1_uncalibrated_fields_not_used_at_face_value(task):
    report = meta_calibration_review((), max_ece=F(1, 10), minimum_samples=2)
    profile = characterise(
        task.key,
        (F(0),),
        ((F(0),),),
        (("a", "same"), ("b", "same")),
        (True,),
        (True, True),
        100,
        report,
        minimum_interpretations=2,
    )
    assert profile.novelty == profile.ambiguity == 1
    assert profile.reversibility == "IRREVERSIBLE" and profile.verifiability == "EXTERNAL_ONLY"
    assert profile.remaining_budget == 0 and profile.estimates_confidence == 0


def test_calibrated_fields_use_measured_distances_and_diverse_interpretations(task):
    history = tuple(
        MetaObservation(f, F(1), True, H)
        for f in ("novelty", "ambiguity", "reversibility", "verifiability", "budget")
        for _ in range(2)
    )
    report = meta_calibration_review(history, max_ece=F(1, 10), minimum_samples=2)
    p = characterise(
        task.key,
        (F(1), F(0)),
        ((F(0), F(0)),),
        (("a", "same"), ("b", "different")),
        (True, False),
        (False, True),
        100,
        report,
        minimum_interpretations=2,
    )
    assert p.novelty == F(1, 2) and p.ambiguity == F(1, 2)
    assert p.reversibility == "IRREVERSIBLE" and p.verifiability == "TOOL"
    with pytest.raises(ContractError):
        characterise(
            task.key,
            (F(0),),
            (),
            (("a", "same"), ("a", "same")),
            (True,),
            (True, True),
            100,
            report,
            minimum_interpretations=2,
        )


def test_transfer_estimates_shrink_and_do_not_grant_authority():
    args = dict(
        prior=F(0),
        observed_rate=F(1),
        observed_lower_bound=F(3, 4),
        sample_size=10,
        similarity=F(0),
        shrinkage_strength=10,
        recency=F(1),
    )
    zero = predict_success(**args)
    assert zero.mean == zero.lower_confidence_bound == 0
    low = predict_success(**{**args, "similarity": F(1, 2)})
    high = predict_success(**{**args, "similarity": F(1)})
    more = predict_success(**{**args, "similarity": F(1), "sample_size": 100})
    assert low.lower_confidence_bound < high.lower_confidence_bound < more.lower_confidence_bound
    assert high.lower_confidence_bound <= high.mean
    assert not hasattr(high, "authority")
