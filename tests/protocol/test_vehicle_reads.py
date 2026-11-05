"""Vehicle reads through a real framed MCP client/server conversation."""

import httpx
import pytest

from may_mcp.client import MayClient
from may_mcp.errors import MayError
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


@pytest.mark.parametrize("writes", [False, True])
async def test_catalogue_and_typed_read_only_annotations(
    server_factory, mcp_client_factory, writes
):
    server = server_factory(lambda request: httpx.Response(200, json={}), writes=writes)
    async with mcp_client_factory(server) as client:
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}
    assert set(tools) == {"may_list_vehicles", "may_get_vehicle"}
    for tool in tools.values():
        assert tool.annotations.read_only_hint is True
        assert tool.annotations.destructive_hint is False
        assert tool.annotations.idempotent_hint is True
        assert tool.annotations.open_world_hint is True
    schema = tools["may_get_vehicle"].input_schema
    assert schema["properties"]["vehicle_id"]["type"] == "integer"
    assert schema["properties"]["vehicle_id"]["exclusiveMinimum"] == 0
    assert schema["required"] == ["vehicle_id"]


async def test_vehicle_list_and_detail_over_mcp(
    server_factory, mcp_client_factory, synthetic_vehicle
):
    paths = []

    def handler(request):
        paths.append(request.url.path)
        if request.url.path == "/api/v1/vehicles":
            return httpx.Response(200, json={"vehicles": [synthetic_vehicle], "count": 1})
        assert request.url.path == "/api/v1/vehicles/1"
        return httpx.Response(200, json=synthetic_vehicle)

    async with mcp_client_factory(server_factory(handler)) as client:
        listed = await client.call_tool("may_list_vehicles", {})
        detail = await client.call_tool("may_get_vehicle", {"vehicle_id": 1})
    assert listed.is_error is not True
    assert listed.structured_content["count"] == 1
    assert detail.structured_content["name"] == "MCP synthetic vehicle"
    assert paths == ["/api/v1/vehicles", "/api/v1/vehicles/1"]


@pytest.mark.parametrize("vehicle_id", [0, -1, True, "1"])
async def test_invalid_id_does_not_reach_may(server_factory, mcp_client_factory, vehicle_id):
    calls = []
    server = server_factory(lambda request: calls.append(request))
    async with mcp_client_factory(server) as client:
        result = await client.call_tool("may_get_vehicle", {"vehicle_id": vehicle_id})
    assert result.is_error is True
    assert "vehicle_id" in " ".join(block.text for block in result.content)
    assert calls == []


async def test_upstream_error_is_safe_and_connection_survives(server_factory, mcp_client_factory):
    def handler(request):
        if request.url.path.endswith("/99"):
            return httpx.Response(404, text="private-record synthetic-test-key")
        return httpx.Response(200, json={"vehicles": [], "count": 0})

    async with mcp_client_factory(server_factory(handler)) as client:
        result = await client.call_tool("may_get_vehicle", {"vehicle_id": 99})
        listed = await client.call_tool("may_list_vehicles", {})
    text = " ".join(block.text for block in result.content)
    assert result.is_error is True
    assert "not_found" in text
    assert "private-record" not in text
    assert "synthetic-test-key" not in text
    assert listed.structured_content["count"] == 0


async def test_shutdown_closes_injected_client(settings_factory, mcp_client_factory):
    may = MayClient(
        settings_factory(),
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={})),
    )
    try:
        async with mcp_client_factory(create_server(settings_factory(), client=may)) as client:
            await client.list_tools()
        with pytest.raises(MayError) as error:
            await may.request("GET", "/api/v1/vehicles")
        assert error.value.code == "client_closed"
    finally:
        await may.aclose()
