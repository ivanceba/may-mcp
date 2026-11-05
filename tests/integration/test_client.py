"""Exercise the guarded client against the pinned real May API."""

import pytest

from may_mcp.client import MayClient
from may_mcp.config import Settings
from may_mcp.errors import MayError

pytestmark = pytest.mark.integration


async def test_real_client_reads_and_blocks_writes(may_test_instance):
    client = MayClient(
        Settings(base_url=may_test_instance.base_url, api_key=may_test_instance.api_key)
    )
    try:
        data = await client.request("GET", "/api/v1/vehicles")
        assert data["count"] == 1
        assert data["vehicles"][0]["name"] == "MCP synthetic vehicle"
        with pytest.raises(MayError) as error:
            await client.request("POST", "/api/v1/vehicles", json={"name": "Must not be stored"})
        assert error.value.code == "read_only"
        assert (await client.request("GET", "/api/v1/vehicles"))["count"] == 1
    finally:
        await client.aclose()


async def test_real_client_maps_invalid_credentials(may_test_instance):
    client = MayClient(
        Settings(base_url=may_test_instance.base_url, api_key="synthetic-invalid-key")
    )
    try:
        with pytest.raises(MayError) as error:
            await client.request("GET", "/api/v1/vehicles")
        assert error.value.code == "authentication_error"
    finally:
        await client.aclose()
