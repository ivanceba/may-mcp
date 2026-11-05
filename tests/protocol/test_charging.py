"""Charging fields and guards through framed MCP conversations."""

import json

import httpx
import pytest


@pytest.mark.parametrize("writes", [False, True])
async def test_charging_catalogue_and_guard(server_factory, mcp_client_factory, writes):
    calls = []
    async with mcp_client_factory(
        server_factory(lambda request: calls.append(request), writes=writes)
    ) as client:
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}
        for name in (
            "may_list_charging_sessions",
            "may_get_charging_session",
            "may_list_charger_types",
        ):
            assert tools[name].annotations.read_only_hint is True
        mutations = {
            "may_create_charging_session",
            "may_update_charging_session",
            "may_delete_charging_session",
        }
        assert mutations & tools.keys() == (mutations if writes else set())
        if writes:
            assert tools["may_create_charging_session"].annotations.idempotent_hint is False
            for name in mutations - {"may_create_charging_session"}:
                assert tools[name].annotations.destructive_hint is True
                assert tools[name].annotations.idempotent_hint is True
        else:
            for name, args in (
                (
                    "may_create_charging_session",
                    {"vehicle_id": 1, "session": {"date": "2026-01-01"}},
                ),
                ("may_update_charging_session", {"session_id": 1, "changes": {"start_soc": 0}}),
                ("may_delete_charging_session", {"session_id": 1}),
            ):
                assert (await client.call_tool(name, args)).is_error is True
    assert calls == []


async def test_charging_payloads_and_lookup(server_factory, mcp_client_factory):
    calls = []

    def handler(request):
        calls.append((request.method, request.url.path, json.loads(request.content or b"{}")))
        return httpx.Response(200, json={"id": 7})

    async with mcp_client_factory(server_factory(handler, writes=True)) as client:
        results = [
            await client.call_tool("may_list_charger_types", {}),
            await client.call_tool(
                "may_create_charging_session",
                {
                    "vehicle_id": 1,
                    "session": {
                        "date": "2026-01-01",
                        "kwh_added": 10.5,
                        "cost_per_kwh": 0.2,
                        "start_time": "00:00",
                    },
                },
            ),
            await client.call_tool(
                "may_update_charging_session",
                {
                    "session_id": 7,
                    "changes": {
                        "kwh_added": None,
                        "total_cost": 0,
                        "start_soc": 0,
                        "end_time": None,
                    },
                },
            ),
            await client.call_tool("may_get_charging_session", {"session_id": 7}),
            await client.call_tool("may_delete_charging_session", {"session_id": 7}),
        ]
    assert all(result.is_error is not True for result in results)
    assert calls == [
        ("GET", "/api/v1/charger-types", {}),
        (
            "POST",
            "/api/v1/vehicles/1/charging",
            {"date": "2026-01-01", "kwh_added": 10.5, "cost_per_kwh": 0.2, "start_time": "00:00"},
        ),
        (
            "PATCH",
            "/api/v1/charging/7",
            {"kwh_added": None, "total_cost": 0, "start_soc": 0, "end_time": None},
        ),
        ("GET", "/api/v1/charging/7", {}),
        ("DELETE", "/api/v1/charging/7", {}),
    ]


async def test_charging_final_page_is_incomplete(server_factory, mcp_client_factory):
    def handler(request):
        assert dict(request.url.params) == {"limit": "2", "offset": "2", "sort": "asc"}
        return httpx.Response(
            200,
            json={
                "charging_sessions": [{"id": 3}],
                "total": 3,
                "count": 1,
                "limit": 2,
                "offset": 2,
            },
        )

    async with mcp_client_factory(server_factory(handler)) as client:
        result = await client.call_tool(
            "may_list_charging_sessions", {"vehicle_id": 1, "limit": 2, "offset": 2, "sort": "asc"}
        )
    assert result.is_error is not True
    assert result.structured_content["has_more"] is False
    assert result.structured_content["complete"] is False


@pytest.mark.parametrize(
    "name,args,field",
    [
        ("may_get_charging_session", {"session_id": "1"}, "session_id"),
        ("may_delete_charging_session", {"session_id": 0}, "session_id"),
        ("may_list_charging_sessions", {"vehicle_id": True}, "vehicle_id"),
        ("may_list_charging_sessions", {"vehicle_id": 1, "limit": 501}, "limit"),
        ("may_list_charging_sessions", {"vehicle_id": 1, "offset": -1}, "offset"),
        (
            "may_create_charging_session",
            {"vehicle_id": 1, "session": {"date": "2026-02-30"}},
            "date",
        ),
        ("may_update_charging_session", {"session_id": 1, "changes": {"date": None}}, "date"),
        (
            "may_update_charging_session",
            {"session_id": 1, "changes": {"start_time": "24:00"}},
            "start_time",
        ),
        (
            "may_update_charging_session",
            {"session_id": 1, "changes": {"start_soc": 101}},
            "start_soc",
        ),
        ("may_update_charging_session", {"session_id": 1, "changes": {"end_soc": 1.5}}, "end_soc"),
        (
            "may_update_charging_session",
            {"session_id": 1, "changes": {"kwh_added": -1}},
            "kwh_added",
        ),
        (
            "may_update_charging_session",
            {"session_id": 1, "changes": {"tessie_charge_id": "external"}},
            "tessie_charge_id",
        ),
        ("may_update_charging_session", {"session_id": 1, "changes": {}}, "changes"),
    ],
)
async def test_invalid_charging_inputs_never_reach_http(
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
