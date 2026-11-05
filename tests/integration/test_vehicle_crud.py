"""Real persistence, ownership and cascade deletion using synthetic accounts only."""

import pytest
from mcp.client import Client

from may_mcp.client import MayClient
from may_mcp.config import Settings
from may_mcp.errors import MayError
from may_mcp.server import create_server

pytestmark = pytest.mark.integration


async def test_vehicle_crud_persists_partial_changes_and_cascades(may_test_instance):
    settings = Settings(may_test_instance.base_url, may_test_instance.api_key, allow_writes=True)
    upstream = MayClient(settings)
    vehicle_id = None
    try:
        async with Client(create_server(settings), mode="legacy", cache=None) as client:
            created = await client.call_tool(
                "may_create_vehicle",
                {
                    "vehicle": {
                        "name": "Disposable CRUD vehicle",
                        "vehicle_type": "car",
                        "make": "Synthetic",
                        "model": "Keep this model",
                        "tank_capacity": 42,
                    }
                },
            )
            assert created.is_error is not True
            vehicle_id = created.structured_content["id"]
            saved = await upstream.request("GET", f"/api/v1/vehicles/{vehicle_id}")
            assert saved["name"] == "Disposable CRUD vehicle"
            assert saved["fuel_type"] == "petrol"
            changed = await client.call_tool(
                "may_update_vehicle",
                {
                    "vehicle_id": vehicle_id,
                    "changes": {
                        "make": None,
                        "tank_capacity": 0,
                        "is_active": False,
                    },
                },
            )
            assert changed.is_error is not True
            saved = await upstream.request("GET", f"/api/v1/vehicles/{vehicle_id}")
            assert saved["make"] is None
            assert saved["tank_capacity"] == 0
            assert saved["is_active"] is False
            assert saved["model"] == "Keep this model"
            assert saved["name"] == "Disposable CRUD vehicle"
            fuel = await upstream.request(
                "POST",
                f"/api/v1/vehicles/{vehicle_id}/fuel",
                json={
                    "date": "2026-01-01",
                    "odometer": 123,
                    "volume": 10,
                    "total_cost": 15,
                },
            )
            assert (await upstream.request("GET", f"/api/v1/fuel/{fuel['id']}"))["id"] == fuel["id"]
            deleted = await client.call_tool("may_delete_vehicle", {"vehicle_id": vehicle_id})
            assert deleted.is_error is not True
            assert deleted.structured_content["success"] is True
            for path in (f"/api/v1/vehicles/{vehicle_id}", f"/api/v1/fuel/{fuel['id']}"):
                with pytest.raises(MayError) as error:
                    await upstream.request("GET", path)
                assert error.value.code == "not_found"
            vehicle_id = None
    finally:
        try:
            if vehicle_id is not None:
                await upstream.request("DELETE", f"/api/v1/vehicles/{vehicle_id}")
        finally:
            await upstream.aclose()


async def test_shared_read_access_does_not_grant_owner_mutations(may_test_instance):
    settings = Settings(
        may_test_instance.base_url, may_test_instance.other_api_key, allow_writes=True
    )
    owner = MayClient(Settings(may_test_instance.base_url, may_test_instance.api_key))
    try:
        async with Client(create_server(settings), mode="legacy", cache=None) as client:
            shared_id = may_test_instance.vehicle_id
            read = await client.call_tool("may_get_vehicle", {"vehicle_id": shared_id})
            assert read.is_error is not True
            assert read.structured_content["name"] == "MCP synthetic vehicle"
            for name, args in (
                ("may_update_vehicle", {"vehicle_id": shared_id, "changes": {"name": "Forbidden"}}),
                ("may_delete_vehicle", {"vehicle_id": shared_id}),
            ):
                result = await client.call_tool(name, args)
                assert result.is_error is True
                assert "permission_denied" in " ".join(block.text for block in result.content)
            saved = await owner.request("GET", f"/api/v1/vehicles/{shared_id}")
            assert saved["name"] == "MCP synthetic vehicle"
        with pytest.raises(MayError) as error:
            await owner.request("GET", f"/api/v1/vehicles/{may_test_instance.other_vehicle_id}")
        assert error.value.code == "not_found"
    finally:
        await owner.aclose()
