"""Use the official SDK's in-memory MCP client instead of hand-written RPC."""

import pytest
from mcp.client import Client


@pytest.fixture
def mcp_client_factory():
    def create(server):
        # Force framed JSON-RPC: SDK 2's auto in-process mode bypasses framing.
        return Client(server, mode="legacy", cache=None)

    return create
