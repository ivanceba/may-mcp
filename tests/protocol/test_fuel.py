"""Fuel tools use framed MCP, strict inputs and truthful coverage metadata."""

import json

import httpx
import pytest


@pytest.mark.parametrize(
    "offset,rows,more,complete",
    [(0, [1, 2], True, False), (2, [3], False, False), (0, [], False, True)],
)
async def test_fuel_pages_and_query_contract(
    server_factory, mcp_client_factory, offset, rows, more, complete
):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            200,
            json={
                "fuel_logs": [{"id": row, "odometer_confirmed": True} for row in rows],
                "count": len(rows),
                "total": 3 if rows else 0,
                "offset": offset,
                "limit": 2,
            },
        )

    async with mcp_client_factory(server_factory(handler)) as client:
        result = await client.call_tool(
            "may_list_fuel_logs", {"vehicle_id": 1, "limit": 2, "offset": offset, "sort": "asc"}
        )
    assert result.is_error is not True
    assert result.structured_content["has_more"] is more
    assert result.structured_content["complete"] is complete
    assert calls[0].url.path == "/api/v1/vehicles/1/fuel"
    assert dict(calls[0].url.params) == {"limit": "2", "offset": str(offset), "sort": "asc"}


@pytest.mark.parametrize("writes", [False, True])
async def test_fuel_catalogue_and_write_guard(server_factory, mcp_client_factory, writes):
    calls = []
    async with mcp_client_factory(
        server_factory(lambda request: calls.append(request), writes=writes)
    ) as client:
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}
        for name in ("may_list_fuel_logs", "may_get_fuel_log"):
            assert tools[name].annotations.read_only_hint is True
        mutations = {"may_create_fuel_log", "may_update_fuel_log", "may_delete_fuel_log"}
        assert mutations & tools.keys() == (mutations if writes else set())
        if writes:
            assert tools["may_create_fuel_log"].annotations.idempotent_hint is False
            for name in mutations - {"may_create_fuel_log"}:
                assert tools[name].annotations.destructive_hint is True
                assert tools[name].annotations.idempotent_hint is True
        else:
            for name, args in (
                (
                    "may_create_fuel_log",
                    {"vehicle_id": 1, "fuel": {"date": "2026-01-01", "odometer": 10}},
                ),
                ("may_update_fuel_log", {"log_id": 1, "changes": {"is_full_tank": False}}),
                ("may_delete_fuel_log", {"log_id": 1}),
            ):
                assert (await client.call_tool(name, args)).is_error is True
    assert calls == []


async def test_fuel_crud_sends_only_supported_supplied_fields(server_factory, mcp_client_factory):
    calls = []

    def handler(request):
        calls.append((request.method, request.url.path, json.loads(request.content or b"{}")))
        return httpx.Response(
            200, json={"id": 7, "odometer": 0, "odometer_confirmed": False, "consumption": None}
        )

    async with mcp_client_factory(server_factory(handler, writes=True)) as client:
        results = [
            await client.call_tool(
                "may_create_fuel_log",
                {
                    "vehicle_id": 1,
                    "fuel": {
                        "date": "2026-01-01",
                        "odometer": 10,
                        "sales_tax": 2.5,
                        "is_missed": False,
                    },
                },
            ),
            await client.call_tool(
                "may_update_fuel_log",
                {
                    "log_id": 7,
                    "changes": {
                        "odometer": None,
                        "volume": 0,
                        "station": None,
                        "is_full_tank": False,
                    },
                },
            ),
            await client.call_tool("may_get_fuel_log", {"log_id": 7}),
            await client.call_tool("may_delete_fuel_log", {"log_id": 7}),
        ]
    assert all(result.is_error is not True for result in results)
    assert results[2].structured_content["odometer_confirmed"] is False
    assert results[2].structured_content["consumption"] is None
    assert calls == [
        (
            "POST",
            "/api/v1/vehicles/1/fuel",
            {"date": "2026-01-01", "odometer": 10, "sales_tax": 2.5, "is_missed": False},
        ),
        (
            "PATCH",
            "/api/v1/fuel/7",
            {"odometer": None, "volume": 0, "station": None, "is_full_tank": False},
        ),
        ("GET", "/api/v1/fuel/7", {}),
        ("DELETE", "/api/v1/fuel/7", {}),
    ]


async def test_inconsistent_page_is_safe_error_and_connection_survives(
    server_factory, mcp_client_factory
):
    def handler(request):
        if request.url.path.endswith("/fuel"):
            return httpx.Response(
                200,
                json={
                    "fuel_logs": [],
                    "count": 0,
                    "total": "private-record synthetic-test-key",
                    "limit": 100,
                    "offset": 0,
                },
            )
        return httpx.Response(200, json={"id": 1})

    async with mcp_client_factory(server_factory(handler)) as client:
        result = await client.call_tool("may_list_fuel_logs", {"vehicle_id": 1})
        again = await client.call_tool("may_get_fuel_log", {"log_id": 1})
    assert result.is_error is True
    text = " ".join(block.text for block in result.content)
    assert "invalid_response" in text
    assert "private-record" not in text
    assert "synthetic-test-key" not in text
    assert again.structured_content["id"] == 1


@pytest.mark.parametrize(
    "name,args,field",
    [
        ("may_list_fuel_logs", {"vehicle_id": 1, "limit": 501}, "limit"),
        ("may_list_fuel_logs", {"vehicle_id": 1, "limit": 0}, "limit"),
        ("may_list_fuel_logs", {"vehicle_id": 1, "offset": -1}, "offset"),
        ("may_list_fuel_logs", {"vehicle_id": 1, "sort": "random"}, "sort"),
        ("may_list_fuel_logs", {"vehicle_id": True}, "vehicle_id"),
        ("may_get_fuel_log", {"log_id": "1"}, "log_id"),
        ("may_delete_fuel_log", {"log_id": 0}, "log_id"),
        ("may_update_fuel_log", {"log_id": -1, "changes": {"notes": "Test"}}, "log_id"),
        (
            "may_create_fuel_log",
            {"vehicle_id": 1, "fuel": {"date": "2026-02-30", "odometer": 10}},
            "date",
        ),
        (
            "may_create_fuel_log",
            {"vehicle_id": 1, "fuel": {"date": "2026-01-01", "odometer": 0}},
            "odometer",
        ),
        (
            "may_create_fuel_log",
            {"vehicle_id": 1, "fuel": {"date": "2026-01-01", "odometer": 10, "user_id": 2}},
            "user_id",
        ),
        ("may_update_fuel_log", {"log_id": 1, "changes": {}}, "changes"),
        ("may_update_fuel_log", {"log_id": 1, "changes": {"date": None}}, "date"),
        ("may_update_fuel_log", {"log_id": 1, "changes": {"is_full_tank": None}}, "is_full_tank"),
        ("may_update_fuel_log", {"log_id": 1, "changes": {"odometer": 10000000}}, "odometer"),
        ("may_update_fuel_log", {"log_id": 1, "changes": {"volume": True}}, "volume"),
    ],
)
async def test_invalid_fuel_input_never_reaches_http(
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
