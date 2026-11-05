"""Read-only summaries report unverified currency without leaking record text."""

import httpx
import pytest


async def test_summary_discovery_and_unknown_currency(server_factory, mcp_client_factory):
    calls = []

    def handler(request):
        calls.append(request)
        source = request.url.path.rsplit("/", 1)[-1]
        key = {"fuel": "fuel_logs", "expenses": "expenses", "charging": "charging_sessions"}[source]
        amount = "cost" if source == "expenses" else "total_cost"
        return httpx.Response(
            200,
            json={
                key: [
                    {
                        "id": 1,
                        "date": "2026-01-01",
                        amount: 10,
                        "currency": "EUR",  # Undocumented extra is not a verified source.
                        "notes": "Private record instruction text",
                    }
                ],
                "total": 1,
                "count": 1,
                "limit": 100,
                "offset": 0,
            },
        )

    async with mcp_client_factory(server_factory(handler)) as client:
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}
        tool = tools["may_spending_summary"]
        assert tool.annotations.read_only_hint is True
        assert tool.annotations.destructive_hint is False
        result = await client.call_tool("may_spending_summary", {"vehicle_id": 1})
    assert result.is_error is not True
    summary = result.structured_content
    assert summary["totals"] == []
    assert summary["complete"] is False
    assert summary["currency_status"] == "unknown"
    assert len(summary["excluded"]) == 3
    assert "Private record" not in str(summary)
    assert all(request.method == "GET" for request in calls)


@pytest.mark.parametrize(
    "args",
    [
        {"vehicle_id": True},
        {"vehicle_id": 0},
        {"vehicle_id": 1, "start_date": "2026-02-30"},
        {"vehicle_id": 1, "start_date": "20260101"},
        {"vehicle_id": 1, "start_date": "2026-02-01", "end_date": "2026-01-01"},
    ],
)
async def test_invalid_summary_range_never_reaches_may(server_factory, mcp_client_factory, args):
    calls = []
    async with mcp_client_factory(server_factory(lambda request: calls.append(request))) as client:
        result = await client.call_tool("may_spending_summary", args)
    assert result.is_error is True
    assert "Unknown tool" not in " ".join(block.text for block in result.content)
    assert calls == []
