"""Charging persistence using a synthetic EV, shared access and private denial."""

import pytest
from mcp.client import Client

from may_mcp.client import MayClient
from may_mcp.config import Settings
from may_mcp.errors import MayError
from may_mcp.server import create_server

pytestmark = pytest.mark.integration


async def test_charging_crud_energy_times_and_private_access(may_test_instance):
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
            json={
                "name": "Disposable synthetic EV",
                "vehicle_type": "car",
                "fuel_type": "electric",
            },
        )
        vehicle_id = vehicle["id"]
        async with Client(create_server(settings), mode="legacy", cache=None) as client:
            types = await client.call_tool("may_list_charger_types", {})
            assert "home" in {entry["id"] for entry in types.structured_content["charger_types"]}
            ids = []
            for day in range(1, 4):
                created = await client.call_tool(
                    "may_create_charging_session",
                    {
                        "vehicle_id": vehicle_id,
                        "session": {
                            "date": f"2026-01-0{day}",
                            "start_time": "00:00",
                            "end_time": "01:00:30",
                            "odometer": 0,
                            "kwh_added": 10.5,
                            "cost_per_kwh": 0.2,
                            "start_soc": 0,
                            "end_soc": 80,
                            "charger_type": "home",
                            "location": "Synthetic garage",
                            "network": "Synthetic network",
                            "notes": "Private synthetic notes",
                        },
                    },
                )
                assert created.is_error is not True
                ids.append(created.structured_content["id"])
                assert created.structured_content["kwh_added"] == 10.5
                assert created.structured_content["total_cost"] == 2.1
                assert created.structured_content["start_soc"] == 0
                assert created.structured_content["start_time"] == "00:00:00"
            first = await client.call_tool(
                "may_list_charging_sessions", {"vehicle_id": vehicle_id, "limit": 2}
            )
            last = await client.call_tool(
                "may_list_charging_sessions", {"vehicle_id": vehicle_id, "limit": 2, "offset": 2}
            )
            assert first.structured_content["has_more"] is True
            assert first.structured_content["complete"] is False
            assert [row["id"] for row in first.structured_content["charging_sessions"]] == ids[
                :0:-1
            ]
            assert last.structured_content["has_more"] is False
            assert last.structured_content["complete"] is False
            assert [row["id"] for row in last.structured_content["charging_sessions"]] == ids[:1]
            updated = await client.call_tool(
                "may_update_charging_session",
                {
                    "session_id": ids[0],
                    "changes": {
                        "start_time": "00:00:00",
                        "end_time": None,
                        "start_soc": 0,
                        "end_soc": None,
                        "kwh_added": None,
                        "total_cost": 0,
                        "location": None,
                    },
                },
            )
            assert updated.is_error is not True
            detail = await client.call_tool("may_get_charging_session", {"session_id": ids[0]})
            saved = await upstream.request("GET", f"/api/v1/charging/{ids[0]}")
            assert detail.structured_content == saved
            assert saved["start_time"] == "00:00:00"
            assert saved["end_time"] is None
            assert saved["start_soc"] == 0
            assert saved["end_soc"] is None
            assert saved["kwh_added"] is None
            assert saved["total_cost"] == 0
            assert saved["location"] is None
            assert saved["cost_per_kwh"] == 0.2
            assert saved["notes"] == "Private synthetic notes"
            invalid = await client.call_tool(
                "may_update_charging_session",
                {"session_id": ids[0], "changes": {"charger_type": "unsupported"}},
            )
            assert invalid.is_error is True
            assert "validation_error" in " ".join(block.text for block in invalid.content)
            async with Client(create_server(other_settings), mode="legacy", cache=None) as other:
                for name, args in (
                    ("may_get_charging_session", {"session_id": ids[0]}),
                    (
                        "may_update_charging_session",
                        {"session_id": ids[0], "changes": {"start_soc": 0}},
                    ),
                    ("may_delete_charging_session", {"session_id": ids[0]}),
                ):
                    denied = await other.call_tool(name, args)
                    text = " ".join(block.text for block in denied.content)
                    assert denied.is_error is True
                    assert "not_found" in text
                    assert "Private synthetic notes" not in text
            for session_id in ids:
                deleted = await client.call_tool(
                    "may_delete_charging_session", {"session_id": session_id}
                )
                assert deleted.structured_content["success"] is True
                with pytest.raises(MayError) as error:
                    await upstream.request("GET", f"/api/v1/charging/{session_id}")
                assert error.value.code == "not_found"
    finally:
        try:
            if vehicle_id is not None:
                await upstream.request("DELETE", f"/api/v1/vehicles/{vehicle_id}")
        finally:
            await upstream.aclose()


async def test_shared_charging_mutations_are_allowed(may_test_instance):
    settings = Settings(
        may_test_instance.base_url, may_test_instance.other_api_key, allow_writes=True
    )
    owner = MayClient(
        Settings(may_test_instance.base_url, may_test_instance.api_key, allow_writes=True)
    )
    session_id = None
    try:
        async with Client(create_server(settings), mode="legacy", cache=None) as client:
            created = await client.call_tool(
                "may_create_charging_session",
                {"vehicle_id": may_test_instance.vehicle_id, "session": {"date": "2026-01-01"}},
            )
            assert created.is_error is not True
            session_id = created.structured_content["id"]
            assert (await owner.request("GET", f"/api/v1/charging/{session_id}"))[
                "kwh_added"
            ] is None
            updated = await client.call_tool(
                "may_update_charging_session",
                {"session_id": session_id, "changes": {"kwh_added": 0}},
            )
            assert updated.structured_content["kwh_added"] == 0
            deleted = await client.call_tool(
                "may_delete_charging_session", {"session_id": session_id}
            )
            assert deleted.structured_content["success"] is True
            session_id = None
    finally:
        try:
            if session_id is not None:
                await owner.request("DELETE", f"/api/v1/charging/{session_id}")
        finally:
            await owner.aclose()
