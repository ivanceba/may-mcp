"""Real history traversal and verified account-currency summaries with synthetic data."""

import pytest
from mcp.client import Client

from may_mcp.client import MayClient
from may_mcp.config import Settings
from may_mcp.server import create_server
from may_mcp.summary import collect_all

pytestmark = pytest.mark.integration


async def test_real_summary_verifies_account_currency_and_full_coverage(may_test_instance):
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
            assert summary["totals"] == [
                {
                    "currency": "EUR",
                    "fuel": "0.30",
                    "expenses": "1.25",
                    "charging": "2.50",
                    "total": "4.05",
                }
            ]
            assert summary["currency_status"] == "verified_account"
            assert summary["currency_source"] == f"/api/ha/vehicles/{vehicle_id}"
            assert summary["complete"] is True
            assert summary["excluded"] == []
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


async def test_shared_vehicle_without_owner_currency_stays_unknown(may_test_instance):
    owner = MayClient(
        Settings(may_test_instance.base_url, may_test_instance.api_key, allow_writes=True)
    )
    other = Settings(may_test_instance.base_url, may_test_instance.other_api_key)
    log_id = None
    try:
        created = await owner.request(
            "POST",
            f"/api/v1/vehicles/{may_test_instance.vehicle_id}/fuel",
            json={"date": "2026-01-01", "odometer": 123, "total_cost": 0.1},
        )
        log_id = created["id"]
        async with Client(create_server(other), mode="legacy", cache=None) as client:
            result = await client.call_tool(
                "may_spending_summary", {"vehicle_id": may_test_instance.vehicle_id}
            )
            assert result.is_error is not True
            summary = result.structured_content
            assert summary["currency_status"] == "unknown"
            assert summary["totals"] == []
            assert summary["complete"] is False
            assert summary["excluded"] == [
                {"source": "fuel", "id": log_id, "reasons": ["unknown_currency"]}
            ]
    finally:
        try:
            if log_id is not None:
                await owner.request("DELETE", f"/api/v1/fuel/{log_id}")
        finally:
            await owner.aclose()
