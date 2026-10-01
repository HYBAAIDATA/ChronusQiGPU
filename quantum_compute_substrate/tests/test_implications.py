"""Tests for the implications manifest."""

from quantum_compute_substrate.implications import (
    IMPLICATIONS,
    all_implications,
    category_names,
    implication_count,
    PARADIGM_ANALOGS,
    PARADIGM_SHIFT_STATEMENT,
)


class TestImplicationsManifest:
    def test_four_top_level_categories(self):
        assert len(IMPLICATIONS) == 4
        keys = [c.key for c in IMPLICATIONS]
        assert keys == ["computational", "societal", "enterprise", "strategic"]

    def test_category_titles(self):
        titles = category_names()
        assert "Computational Implications" in titles
        assert "Societal Implications" in titles
        assert "Enterprise Implications" in titles
        assert "Strategic Implications" in titles

    def test_expected_subcategory_counts(self):
        counts = implication_count()
        assert counts == {
            "computational": 3,
            "societal": 4,
            "enterprise": 4,
            "strategic": 3,
        }

    def test_all_implications_total_14(self):
        assert len(all_implications()) == 14

    def test_every_implication_has_four_bullets(self):
        for imp in all_implications():
            assert len(imp.bullets) == 4, f"{imp.key} has {len(imp.bullets)} bullets"

    def test_key_headline_topics_present(self):
        keys = {imp.key for imp in all_implications()}
        for required in (
            "quantum_democratization",
            "memory_revolution",
            "algorithm_renaissance",
            "scientific_acceleration",
            "education_workforce",
            "geopolitical_equity",
            "ethical_considerations",
            "immediate_roi",
            "competitive_advantages",
            "new_business_models",
            "industry_transformation",
            "redefinition_of_quantum",
            "new_research_directions",
            "investment_and_funding",
        ):
            assert required in keys, f"missing implication key: {required}"

    def test_paradigm_analogs(self):
        keys = [a[0] for a in PARADIGM_ANALOGS]
        assert keys == ["AI", "Graphics", "Cryptography"]

    def test_paradigm_shift_statement_non_empty(self):
        assert "mathematical operations" in PARADIGM_SHIFT_STATEMENT
        assert "phi-fold" in PARADIGM_SHIFT_STATEMENT

    def test_immutability(self):
        # frozen dataclasses -> attribute assignment raises
        import dataclasses

        imp = all_implications()[0]
        try:
            imp.title = "x"  # type: ignore[misc]
            assert False, "Implication should be frozen"
        except dataclasses.FrozenInstanceError:
            pass
