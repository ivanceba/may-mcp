"""Fuel persistence and full-history page coverage against disposable May."""

import pytest
from mcp.client import Client

from may_mcp.client import MayClient
from may_mcp.config import Settings
from may_mcp.errors import MayError
from may_mcp.server import create_server

pytestmark = pytest.mark.integration


async def test_real_fuel_crud_pages_and_reading_states(may_test_instance):
    settings = Settings(may_test_instance.base_url, may_test_instance.api_key, allow_writes=True)
    upstream = MayClient(settings)
    vehicle_id = None
    try:
        vehicle = await upstream.request(
            "POST",
            "/api/v1/vehicles",
            json={"name": "Disposable fuel vehicle", "vehicle_type": "car"},
        )
        vehicle_id = vehicle["id"]
        async with Client(create_server(settings), mode="legacy", cache=None) as client:
            ids = []
            for day in range(1, 4):
                result = await client.call_tool(
                    "may_create_fuel_log",
                    {
                        "vehicle_id": vehicle_id,
                        "fuel": {
                            "date": f"2026-01-0{day}",
                            "odometer": day * 100,
                            "volume": 10,
                            "price_per_unit": 1.5,
                            "total_cost": 15,
                            "sales_tax": 2.5,
                            "fuel_type": "petrol",
                            "fuel_distance": 100,
                            "is_full_tank": True,
                            "is_missed": False,
                            "station": "Synthetic station",
                            "notes": "Keep these notes",
                        },
                    },
                )
                assert result.is_error is not True
                ids.append(result.structured_content["id"])
            first = await client.call_tool(
                "may_list_fuel_logs", {"vehicle_id": vehicle_id, "limit": 2}
            )
            last = await client.call_tool(
                "may_list_fuel_logs", {"vehicle_id": vehicle_id, "limit": 2, "offset": 2}
            )
            assert first.structured_content["total"] == 3
            assert first.structured_content["count"] == 2
            assert first.structured_content["has_more"] is True
            assert first.structured_content["complete"] is False
            assert [row["id"] for row in first.structured_content["fuel_logs"]] == ids[:0:-1]
            assert last.structured_content["has_more"] is False
            assert last.structured_content["complete"] is False
            assert [row["id"] for row in last.structured_content["fuel_logs"]] == ids[:1]
            all_rows = await client.call_tool(
                "may_list_fuel_logs", {"vehicle_id": vehicle_id, "limit": 500, "sort": "asc"}
            )
            assert all_rows.structured_content["complete"] is True
            assert [row["id"] for row in all_rows.structured_content["fuel_logs"]] == ids
            for reading, confirmed in ((None, False), (0, True)):
                updated = await client.call_tool(
                    "may_update_fuel_log",
                    {
                        "log_id": ids[0],
                        "changes": {
                            "odometer": reading,
                            "is_full_tank": False,
                            "station": None,
                            "volume": 0,
                        },
                    },
                )
                assert updated.is_error is not True
                detail = await client.call_tool("may_get_fuel_log", {"log_id": ids[0]})
                saved = await upstream.request("GET", f"/api/v1/fuel/{ids[0]}")
                assert detail.structured_content == saved
                assert saved["odometer"] == 0
                assert saved["odometer_confirmed"] is confirmed
                assert saved["consumption"] is None
                assert saved["is_full_tank"] is False
                assert saved["station"] is None
                assert saved["volume"] is None  # Pinned May normalizes optional numeric zero.
                assert saved["sales_tax"] == 2.5
                assert saved["total_cost"] == 15
                assert saved["notes"] == "Keep these notes"
            for log_id in ids:
                deleted = await client.call_tool("may_delete_fuel_log", {"log_id": log_id})
                assert deleted.structured_content["success"] is True
                with pytest.raises(MayError) as error:
                    await upstream.request("GET", f"/api/v1/fuel/{log_id}")
                assert error.value.code == "not_found"
            empty = await client.call_tool("may_list_fuel_logs", {"vehicle_id": vehicle_id})
            assert empty.structured_content["total"] == 0
            assert empty.structured_content["complete"] is True
    finally:
        try:
            if vehicle_id is not None:
                await upstream.request("DELETE", f"/api/v1/vehicles/{vehicle_id}")
        finally:
            await upstream.aclose()
