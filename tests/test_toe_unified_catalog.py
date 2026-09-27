"""Catalog contract: count, classes, and well-formed rows."""

from toe.unified.catalog import CATALOG, DISPLACED_CLASSES


def test_catalog_count_and_classes():
    ids = [spec.id for spec in CATALOG]
    assert len(ids) == 1063
    assert len(ids) == len(set(ids))
    assert set(DISPLACED_CLASSES) <= {spec.category for spec in CATALOG}
    for spec in CATALOG:
        assert spec.protocol
        assert spec.auth
        assert spec.entities
        assert spec.vendor
        assert spec.product
