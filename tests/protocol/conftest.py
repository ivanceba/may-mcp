"""Use the official SDK's in-memory MCP client instead of hand-written RPC."""

import pytest
from mcp.client import Client


@pytest.fixture
def mcp_client_factory():
    return Client
