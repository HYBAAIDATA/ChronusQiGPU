"""A connector without credentials writes nothing."""

import pytest

from toe.unified import UnifiedAnalyticsPlatform
from toe.unified.catalog import CATALOG
from toe.unified.connectors import ConnectorUnavailable


def test_missing_credentials_write_nothing():
    platform = UnifiedAnalyticsPlatform()
    for protocol in ("jdbc", "rest", "odata", "kafka", "sdk", "opcua"):
        spec = next(item for item in CATALOG if item.protocol == protocol)
        with pytest.raises(ConnectorUnavailable):
            platform.connect(spec.id, {})
    assert platform.export_records() == []
    assert platform.connections() == {}
