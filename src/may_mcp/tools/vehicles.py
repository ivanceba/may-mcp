"""Read-only tools for the May vehicle API."""

from typing import Annotated, Any

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from may_mcp.client import MayClient
from may_mcp.config import Settings
from may_mcp.errors import MayError


def register_vehicle_tools(server: MCPServer[None], client: MayClient, settings: Settings) -> None:
    annotations = ToolAnnotations(
        read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=True
    )

    async def read(path: str) -> dict[str, Any]:
        try:
            return await client.request("GET", path)
        except MayError as error:
            raise ToolError(f"{error.code}: {error}") from None

    @server.tool(annotations=annotations)
    async def may_list_vehicles() -> dict[str, Any]:
        """List vehicles accessible to the configured May account."""
        return await read("/api/v1/vehicles")

    @server.tool(annotations=annotations)
    async def may_get_vehicle(
        vehicle_id: Annotated[int, Field(gt=0, strict=True)],
    ) -> dict[str, Any]:
        """Get one accessible vehicle by a positive integer ID."""
        return await read(f"/api/v1/vehicles/{vehicle_id}")
