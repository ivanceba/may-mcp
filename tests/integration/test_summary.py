"""Real history traversal and honest unknown-currency summaries with synthetic data."""

import pytest
from mcp.client import Client

from may_mcp.client import MayClient
from may_mcp.config import Settings
from may_mcp.server import create_server
from may_mcp.summary import collect_all

pytestmark = pytest.mark.integration


async def test_real_summary_reports_unknown_currency_and_full_coverage(may_test_instance):
    settings = Settings(may_test_instance.base_url, may_test_instance.api_key, allow_writes=True)
    upstream = MayClient(settings)
    vehicle_id = None
    try:
        vehicle = await upstream.request(
            "POST",
            "/api/v1/vehicles",
            json={
                "name": "Disposable summary vehicle",
                "vehicle_type": "car",
                "fuel_type": "electric",
            },
        )
        vehicle_id = vehicle["id"]
        for day in range(1, 4):
            await upstream.request(
                "POST",
                f"/api/v1/vehicles/{vehicle_id}/fuel",
                json={
                    "date": f"2026-01-0{day}",
                    "odometer": day * 100,
                    "volume": 10,
                    "total_cost": day / 10,
                    "sales_tax": 0.01,
                },
            )
        await upstream.request(
            "POST",
            f"/api/v1/vehicles/{vehicle_id}/expenses",
            json={
                "date": "2026-01-02",
                "category": "parking",
                "description": "Synthetic",
                "cost": 1.25,
                "notes": "Private instruction-like notes",
            },
        )
        await upstream.request(
            "POST",
            f"/api/v1/vehicles/{vehicle_id}/charging",
            json={"date": "2026-01-02", "kwh_added": 10, "total_cost": 2.5},
        )
        collected = await collect_all(upstream, f"/api/v1/vehicles/{vehicle_id}/fuel", limit=2)
        assert collected.complete is True
        assert collected.pages == 2
        assert [row["total_cost"] for row in collected.records] == [0.1, 0.2, 0.3]
        read_only = Settings(may_test_instance.base_url, may_test_instance.api_key)
        async with Client(create_server(read_only), mode="legacy", cache=None) as client:
            result = await client.call_tool(
                "may_spending_summary",
                {"vehicle_id": vehicle_id, "start_date": "2026-01-01", "end_date": "2026-01-02"},
            )
            assert result.is_error is not True
            summary = result.structured_content
            assert summary["totals"] == []
            assert summary["currency_status"] == "unknown"
            assert summary["complete"] is False
            assert len(summary["excluded"]) == 4
            assert all(row["reasons"] == ["unknown_currency"] for row in summary["excluded"])
            assert all(page["complete"] for page in summary["coverage"].values())
            assert summary["coverage"]["fuel"]["count"] == 3
            assert "Private instruction-like notes" not in str(summary)
            denied = await client.call_tool(
                "may_spending_summary", {"vehicle_id": may_test_instance.other_vehicle_id}
            )
            assert denied.is_error is True
            assert "not_found" in " ".join(block.text for block in denied.content)
    finally:
        try:
            if vehicle_id is not None:
                await upstream.request("DELETE", f"/api/v1/vehicles/{vehicle_id}")
        finally:
            await upstream.aclose()
