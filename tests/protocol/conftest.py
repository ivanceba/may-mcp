"""Use the official SDK's in-memory MCP client instead of hand-written RPC."""

import httpx
import pytest
from mcp.client import Client

from may_mcp.client import MayClient
from may_mcp.server import create_server


@pytest.fixture
async def server_factory(settings_factory):
    clients = []

    def create(handler, *, writes=False):
        settings = settings_factory(MAY_MCP_ALLOW_WRITES="true" if writes else "false")
        client = MayClient(settings, transport=httpx.MockTransport(handler))
        clients.append(client)
        return create_server(settings, client=client)

    yield create
    for client in clients:
        await client.aclose()


@pytest.fixture
def mcp_client_factory():
    def create(server):
        # Force framed JSON-RPC: SDK 2's auto in-process mode bypasses framing.
        return Client(server, mode="legacy", cache=None)

    return create
