"""Real stdio subprocess reads real synthetic May data through MCP."""

import asyncio
import os
import sys

import pytest
from mcp import StdioServerParameters
from mcp.client import Client

pytestmark = pytest.mark.integration


async def test_stdio_vehicle_reads_and_error_recovery(may_test_instance, capfd):
    process = StdioServerParameters(
        command=sys.executable,
        args=["-m", "may_mcp"],
        env={
            **os.environ,
            "MAY_BASE_URL": may_test_instance.base_url,
            "MAY_API_KEY": may_test_instance.api_key,
            "MAY_MCP_ALLOW_WRITES": "false",
        },
    )
    # Includes subprocess startup on slow shared Windows/WSL filesystems.
    async with asyncio.timeout(60), Client(process, cache=None) as client:
        tools = await client.list_tools()
        assert {tool.name for tool in tools.tools} == {
            "may_list_vehicles",
            "may_get_vehicle",
            "may_list_fuel_logs",
            "may_get_fuel_log",
            "may_list_expenses",
            "may_get_expense",
            "may_list_categories",
            "may_list_trips",
            "may_get_trip",
            "may_list_trip_purposes",
        }
        listed = await client.call_tool("may_list_vehicles", {})
        vehicle = listed.structured_content["vehicles"][0]
        detail = await client.call_tool("may_get_vehicle", {"vehicle_id": vehicle["id"]})
        assert detail.structured_content["name"] == "MCP synthetic vehicle"
        assert detail.structured_content["id"] == vehicle["id"]
        missing = await client.call_tool("may_get_vehicle", {"vehicle_id": 999999})
        assert missing.is_error is True
        assert "not_found" in " ".join(block.text for block in missing.content)
        again = await client.call_tool("may_list_vehicles", {})
        assert again.structured_content["count"] == 1
    captured = capfd.readouterr()
    assert may_test_instance.api_key not in captured.out + captured.err
