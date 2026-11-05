"""The HTTP fixture must support async calls without allowing real sockets."""

import httpx
import pytest


async def test_unexpected_mock_request_fails(mock_may_http):
    async with httpx.AsyncClient(transport=mock_may_http()) as client:
        with pytest.raises(AssertionError, match="Unexpected request"):
            await client.get("https://may.invalid/api/v1/vehicles")
