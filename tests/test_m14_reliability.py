"""M14 local status must not probe the remote provider without explicit opt-in."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from bvmt.api import create_app
from bvmt.gateway import MarketDataGateway

pytest_plugins = ["test_api"]


@pytest.mark.parametrize("query,expected", [("", False), ("?check_remote=true", True)])
def test_market_status_remote_probe_is_explicit(service, query, expected):
    original = MarketDataGateway.get_status
    observed = []

    def local_status(gateway, *args, **kwargs):
        observed.append(kwargs.get("probe_remote"))
        # Keep the test offline even when verifying propagation of explicit opt-in.
        return original(gateway, probe_remote=False)

    before = service.resolve_context().ledger_path.read_bytes()
    with patch.object(MarketDataGateway, "get_status", local_status):
        with TestClient(create_app(service)) as client:
            response = client.get("/api/market-data/status" + query)
    assert response.status_code == 200
    assert observed == [expected]
    assert service.resolve_context().ledger_path.read_bytes() == before
