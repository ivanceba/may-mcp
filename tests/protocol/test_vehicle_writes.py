"""Mutation discovery and validation through framed MCP messages."""

import json

import httpx
import pytest


@pytest.mark.parametrize(
    "name,args",
    [
        ("may_create_vehicle", {"vehicle": {"name": "Synthetic", "vehicle_type": "car"}}),
        ("may_update_vehicle", {"vehicle_id": 1, "changes": {"name": "Synthetic"}}),
        ("may_delete_vehicle", {"vehicle_id": 1}),
    ],
)
async def test_read_only_cannot_call_mutations(server_factory, mcp_client_factory, name, args):
    calls = []
    async with mcp_client_factory(server_factory(lambda request: calls.append(request))) as client:
        result = await client.call_tool(name, args)
    assert result.is_error is True
    assert calls == []


async def test_enabled_tools_and_partial_payload(server_factory, mcp_client_factory):
    calls = []

    def handler(request):
        calls.append((request.method, request.url.path, json.loads(request.content or b"{}")))
        return httpx.Response(200, json={"success": True})

    async with mcp_client_factory(server_factory(handler, writes=True)) as client:
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}
        for name in ("may_create_vehicle", "may_update_vehicle", "may_delete_vehicle"):
            assert tools[name].annotations.read_only_hint is False
            assert tools[name].annotations.open_world_hint is True
        assert tools["may_create_vehicle"].annotations.idempotent_hint is False
        assert tools["may_update_vehicle"].annotations.destructive_hint is True
        assert tools["may_update_vehicle"].annotations.idempotent_hint is True
        assert tools["may_delete_vehicle"].annotations.destructive_hint is True
        assert tools["may_delete_vehicle"].annotations.idempotent_hint is True
        results = [
            await client.call_tool(
                "may_create_vehicle", {"vehicle": {"name": "Synthetic", "vehicle_type": "car"}}
            ),
            await client.call_tool(
                "may_update_vehicle",
                {
                    "vehicle_id": 1,
                    "changes": {"make": None, "tank_capacity": 0, "is_active": False},
                },
            ),
            await client.call_tool("may_delete_vehicle", {"vehicle_id": 1}),
        ]
    assert all(result.is_error is not True for result in results)
    assert calls == [
        ("POST", "/api/v1/vehicles", {"name": "Synthetic", "vehicle_type": "car"}),
        ("PATCH", "/api/v1/vehicles/1", {"make": None, "tank_capacity": 0, "is_active": False}),
        ("DELETE", "/api/v1/vehicles/1", {}),
    ]


@pytest.mark.parametrize(
    "name,args,field",
    [
        (
            "may_create_vehicle",
            {"vehicle": {"name": "Synthetic", "vehicle_type": "boat"}},
            "vehicle_type",
        ),
        ("may_create_vehicle", {"vehicle": {"name": "", "vehicle_type": "car"}}, "name"),
        (
            "may_create_vehicle",
            {"vehicle": {"name": "Synthetic", "vehicle_type": "car", "owner_id": 2}},
            "owner_id",
        ),
        (
            "may_create_vehicle",
            {"vehicle": {"name": "Synthetic", "vehicle_type": "car", "year": True}},
            "year",
        ),
        ("may_update_vehicle", {"vehicle_id": 1, "changes": {"owner_id": 2}}, "owner_id"),
        ("may_update_vehicle", {"vehicle_id": 1, "changes": {}}, "changes"),
        ("may_update_vehicle", {"vehicle_id": 1, "changes": {"name": None}}, "name"),
        ("may_update_vehicle", {"vehicle_id": 1, "changes": {"is_active": None}}, "is_active"),
        (
            "may_update_vehicle",
            {"vehicle_id": 1, "changes": {"tank_capacity": True}},
            "tank_capacity",
        ),
        (
            "may_update_vehicle",
            {"vehicle_id": 1, "changes": {"tank_capacity": "3"}},
            "tank_capacity",
        ),
        *[
            (
                name,
                {
                    "vehicle_id": value,
                    **({"changes": {"name": "Synthetic"}} if name == "may_update_vehicle" else {}),
                },
                "vehicle_id",
            )
            for name in ("may_update_vehicle", "may_delete_vehicle")
            for value in (0, -1, True, "1")
        ],
    ],
)
async def test_invalid_writes_never_reach_may(
    server_factory, mcp_client_factory, name, args, field
):
    calls = []
    async with mcp_client_factory(
        server_factory(lambda request: calls.append(request), writes=True)
    ) as client:
        result = await client.call_tool(name, args)
    assert result.is_error is True
    assert field in " ".join(block.text for block in result.content)
    assert calls == []
