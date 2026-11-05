"""Pinned mutation responses retain safe errors and never trigger retries."""

import httpx
import pytest

from may_mcp.client import MayClient
from may_mcp.errors import MayError


@pytest.mark.parametrize(
    "method,path,payload",
    [
        ("POST", "/api/v1/vehicles", {"name": "Synthetic", "vehicle_type": "car"}),
        ("PATCH", "/api/v1/vehicles/1", {"make": None, "is_active": False}),
        ("DELETE", "/api/v1/vehicles/1", None),
    ],
)
@pytest.mark.parametrize(
    "status,code,unknown",
    [
        (400, "validation_error", False),
        (403, "permission_denied", False),
        (404, "not_found", False),
        (500, "upstream_error", True),
    ],
)
async def test_vehicle_mutation_errors_are_safe_and_not_retried(
    settings_factory, method, path, payload, status, code, unknown
):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, text="private-record synthetic-test-key")

    client = MayClient(
        settings_factory(MAY_MCP_ALLOW_WRITES="true"), transport=httpx.MockTransport(handler)
    )
    try:
        with pytest.raises(MayError) as error:
            await client.request(method, path, json=payload)
        assert error.value.code == code
        assert error.value.outcome_unknown is unknown
        assert "private-record" not in str(error.value)
        assert "synthetic-test-key" not in str(error.value)
        assert len(calls) == 1
    finally:
        await client.aclose()
