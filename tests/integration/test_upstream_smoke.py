"""Authenticated smoke check against a provisioned, disposable real May."""

import httpx
import pytest

pytestmark = pytest.mark.integration


def test_upstream_smoke(may_test_instance):
    with httpx.Client(base_url=may_test_instance.base_url, trust_env=False) as client:
        assert client.get("/api/v1/vehicles").status_code == 401
        response = client.get(
            "/api/v1/vehicles",
            headers={"Authorization": f"Bearer {may_test_instance.api_key}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert [(v["name"], v["vehicle_type"]) for v in data["vehicles"]] == [
            ("MCP synthetic vehicle", "car")
        ]
