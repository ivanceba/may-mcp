"""Real trip persistence, optional levels, pagination and cross-user access."""

import pytest
from mcp.client import Client

from may_mcp.client import MayClient
from may_mcp.config import Settings
from may_mcp.errors import MayError
from may_mcp.server import create_server

pytestmark = pytest.mark.integration


async def test_trip_crud_optional_readings_and_private_access(may_test_instance):
    settings = Settings(may_test_instance.base_url, may_test_instance.api_key, allow_writes=True)
    other_settings = Settings(
        may_test_instance.base_url, may_test_instance.other_api_key, allow_writes=True
    )
    upstream = MayClient(settings)
    vehicle_id = None
    try:
        vehicle = await upstream.request(
            "POST",
            "/api/v1/vehicles",
            json={"name": "Disposable trip vehicle", "vehicle_type": "car", "tank_capacity": 40},
        )
        vehicle_id = vehicle["id"]
        async with Client(create_server(settings), mode="legacy", cache=None) as client:
            purposes = await client.call_tool("may_list_trip_purposes", {})
            assert "personal" in {entry["id"] for entry in purposes.structured_content["purposes"]}
            ids = []
            for day in range(1, 4):
                created = await client.call_tool(
                    "may_create_trip",
                    {
                        "vehicle_id": vehicle_id,
                        "trip": {
                            "date": f"2026-01-0{day}",
                            "start_odometer": (day - 1) * 10,
                            "end_odometer": day * 10,
                            "purpose": "personal",
                            "start_fuel_level": 100,
                            "end_fuel_level": 50,
                            "description": "Synthetic trip",
                            "start_location": "Test start",
                            "end_location": "Test end",
                            "notes": "Keep these notes",
                        },
                    },
                )
                assert created.is_error is not True
                ids.append(created.structured_content["id"])
                assert created.structured_content["distance"] == 10
                assert created.structured_content["fuel_used"] == 20
            first = await client.call_tool("may_list_trips", {"vehicle_id": vehicle_id, "limit": 2})
            last = await client.call_tool(
                "may_list_trips", {"vehicle_id": vehicle_id, "limit": 2, "offset": 2}
            )
            assert first.structured_content["has_more"] is True
            assert first.structured_content["complete"] is False
            assert [row["id"] for row in first.structured_content["trips"]] == ids[:0:-1]
            assert last.structured_content["has_more"] is False
            assert last.structured_content["complete"] is False
            assert [row["id"] for row in last.structured_content["trips"]] == ids[:1]
            for end_reading, end_level in ((None, None), (0, 0)):
                updated = await client.call_tool(
                    "may_update_trip",
                    {
                        "trip_id": ids[0],
                        "changes": {
                            "end_odometer": end_reading,
                            "end_fuel_level": end_level,
                            "description": None,
                        },
                    },
                )
                assert updated.is_error is not True
                detail = await client.call_tool("may_get_trip", {"trip_id": ids[0]})
                saved = await upstream.request("GET", f"/api/v1/trips/{ids[0]}")
                assert detail.structured_content == saved
                assert saved["end_odometer"] == end_reading
                assert saved["end_fuel_level"] == end_level
                assert saved["start_odometer"] == 0
                assert saved["start_fuel_level"] == 100
                assert saved["description"] is None
                assert saved["notes"] == "Keep these notes"
                assert saved["fuel_used"] == (None if end_level is None else 40)
            invalid = await client.call_tool(
                "may_update_trip", {"trip_id": ids[0], "changes": {"purpose": "unsupported"}}
            )
            assert invalid.is_error is True
            assert "validation_error" in " ".join(block.text for block in invalid.content)
            async with Client(create_server(other_settings), mode="legacy", cache=None) as other:
                for name, args in (
                    ("may_get_trip", {"trip_id": ids[0]}),
                    ("may_update_trip", {"trip_id": ids[0], "changes": {"notes": "Forbidden"}}),
                    ("may_delete_trip", {"trip_id": ids[0]}),
                ):
                    denied = await other.call_tool(name, args)
                    text = " ".join(block.text for block in denied.content)
                    assert denied.is_error is True
                    assert "not_found" in text
                    assert "Keep these notes" not in text
            for trip_id in ids:
                deleted = await client.call_tool("may_delete_trip", {"trip_id": trip_id})
                assert deleted.structured_content["success"] is True
                with pytest.raises(MayError) as error:
                    await upstream.request("GET", f"/api/v1/trips/{trip_id}")
                assert error.value.code == "not_found"
    finally:
        try:
            if vehicle_id is not None:
                await upstream.request("DELETE", f"/api/v1/vehicles/{vehicle_id}")
        finally:
            await upstream.aclose()


async def test_shared_trip_mutations_are_allowed(may_test_instance):
    settings = Settings(
        may_test_instance.base_url, may_test_instance.other_api_key, allow_writes=True
    )
    owner = MayClient(
        Settings(may_test_instance.base_url, may_test_instance.api_key, allow_writes=True)
    )
    trip_id = None
    try:
        async with Client(create_server(settings), mode="legacy", cache=None) as client:
            created = await client.call_tool(
                "may_create_trip",
                {
                    "vehicle_id": may_test_instance.vehicle_id,
                    "trip": {"date": "2026-01-01", "start_odometer": 0, "purpose": "personal"},
                },
            )
            assert created.is_error is not True
            trip_id = created.structured_content["id"]
            assert (await owner.request("GET", f"/api/v1/trips/{trip_id}"))["end_odometer"] is None
            updated = await client.call_tool(
                "may_update_trip", {"trip_id": trip_id, "changes": {"end_odometer": 10}}
            )
            assert updated.structured_content["distance"] == 10
            deleted = await client.call_tool("may_delete_trip", {"trip_id": trip_id})
            assert deleted.structured_content["success"] is True
            trip_id = None
    finally:
        try:
            if trip_id is not None:
                await owner.request("DELETE", f"/api/v1/trips/{trip_id}")
        finally:
            await owner.aclose()
