"""Trip tool discovery, REST payloads and validation over framed MCP."""

import json

import httpx
import pytest


@pytest.mark.parametrize("writes", [False, True])
async def test_trip_catalogue_and_write_guard(server_factory, mcp_client_factory, writes):
    calls = []
    async with mcp_client_factory(
        server_factory(lambda request: calls.append(request), writes=writes)
    ) as client:
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}
        for name in ("may_list_trips", "may_get_trip", "may_list_trip_purposes"):
            assert tools[name].annotations.read_only_hint is True
        mutations = {"may_create_trip", "may_update_trip", "may_delete_trip"}
        assert mutations & tools.keys() == (mutations if writes else set())
        if writes:
            assert tools["may_create_trip"].annotations.idempotent_hint is False
            for name in mutations - {"may_create_trip"}:
                assert tools[name].annotations.destructive_hint is True
                assert tools[name].annotations.idempotent_hint is True
        else:
            for name, args in (
                (
                    "may_create_trip",
                    {
                        "vehicle_id": 1,
                        "trip": {"date": "2026-01-01", "start_odometer": 0, "purpose": "personal"},
                    },
                ),
                ("may_update_trip", {"trip_id": 1, "changes": {"end_fuel_level": 0}}),
                ("may_delete_trip", {"trip_id": 1}),
            ):
                assert (await client.call_tool(name, args)).is_error is True
    assert calls == []


async def test_trip_payloads_and_purpose_lookup(server_factory, mcp_client_factory):
    calls = []

    def handler(request):
        calls.append((request.method, request.url.path, json.loads(request.content or b"{}")))
        return httpx.Response(200, json={"id": 7, "end_odometer": None, "distance": 0})

    async with mcp_client_factory(server_factory(handler, writes=True)) as client:
        results = [
            await client.call_tool("may_list_trip_purposes", {}),
            await client.call_tool(
                "may_create_trip",
                {
                    "vehicle_id": 1,
                    "trip": {"date": "2026-01-01", "start_odometer": 0, "purpose": "personal"},
                },
            ),
            await client.call_tool(
                "may_update_trip",
                {
                    "trip_id": 7,
                    "changes": {
                        "end_odometer": None,
                        "start_fuel_level": None,
                        "end_fuel_level": 0,
                    },
                },
            ),
            await client.call_tool("may_get_trip", {"trip_id": 7}),
            await client.call_tool("may_delete_trip", {"trip_id": 7}),
        ]
    assert all(result.is_error is not True for result in results)
    assert calls == [
        ("GET", "/api/v1/trip-purposes", {}),
        (
            "POST",
            "/api/v1/vehicles/1/trips",
            {"date": "2026-01-01", "start_odometer": 0, "purpose": "personal"},
        ),
        (
            "PATCH",
            "/api/v1/trips/7",
            {"end_odometer": None, "start_fuel_level": None, "end_fuel_level": 0},
        ),
        ("GET", "/api/v1/trips/7", {}),
        ("DELETE", "/api/v1/trips/7", {}),
    ]


async def test_trip_final_page_coverage(server_factory, mcp_client_factory):
    def handler(request):
        assert dict(request.url.params) == {"limit": "2", "offset": "2", "sort": "asc"}
        return httpx.Response(
            200, json={"trips": [{"id": 3}], "count": 1, "total": 3, "limit": 2, "offset": 2}
        )

    async with mcp_client_factory(server_factory(handler)) as client:
        result = await client.call_tool(
            "may_list_trips", {"vehicle_id": 1, "limit": 2, "offset": 2, "sort": "asc"}
        )
    assert result.is_error is not True
    assert result.structured_content["complete"] is False
    assert result.structured_content["has_more"] is False


@pytest.mark.parametrize(
    "name,args,field",
    [
        ("may_get_trip", {"trip_id": 0}, "trip_id"),
        ("may_delete_trip", {"trip_id": True}, "trip_id"),
        ("may_list_trips", {"vehicle_id": 1, "limit": 501}, "limit"),
        ("may_list_trips", {"vehicle_id": 1, "offset": -1}, "offset"),
        (
            "may_create_trip",
            {
                "vehicle_id": 1,
                "trip": {"date": "2026-02-30", "start_odometer": 0, "purpose": "personal"},
            },
            "date",
        ),
        ("may_update_trip", {"trip_id": 1, "changes": {"start_odometer": None}}, "start_odometer"),
        ("may_update_trip", {"trip_id": 1, "changes": {"end_fuel_level": 101}}, "end_fuel_level"),
        (
            "may_update_trip",
            {"trip_id": 1, "changes": {"start_fuel_level": -1}},
            "start_fuel_level",
        ),
        ("may_update_trip", {"trip_id": 1, "changes": {"purpose": None}}, "purpose"),
        ("may_update_trip", {"trip_id": 1, "changes": {"user_id": 2}}, "user_id"),
        ("may_update_trip", {"trip_id": 1, "changes": {}}, "changes"),
    ],
)
async def test_invalid_trip_inputs_never_reach_http(
    server_factory, mcp_client_factory, name, args, field
):
    calls = []
    async with mcp_client_factory(
        server_factory(lambda request: calls.append(request), writes=True)
    ) as client:
        result = await client.call_tool(name, args)
    assert result.is_error is True
    message = " ".join(block.text for block in result.content)
    assert "Unknown tool" not in message
    assert field in message
    assert calls == []
