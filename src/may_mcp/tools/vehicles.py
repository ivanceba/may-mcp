"""Explicit read and optionally enabled write tools for May vehicles."""

from typing import Annotated, Any

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from may_mcp.client import MayClient
from may_mcp.config import Settings
from may_mcp.errors import MayError
from may_mcp.models.vehicles import VehicleCreate, VehicleUpdate


def register_vehicle_tools(server: MCPServer[None], client: MayClient, settings: Settings) -> None:
    annotations = ToolAnnotations(
        read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=True
    )

    async def request(
        method: str, path: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        try:
            return await client.request(method, path, json=payload)
        except MayError as error:
            raise ToolError(f"{error.code}: {error}") from None

    @server.tool(annotations=annotations)
    async def may_list_vehicles() -> dict[str, Any]:
        """List vehicles accessible to the configured May account."""
        return await request("GET", "/api/v1/vehicles")

    @server.tool(annotations=annotations)
    async def may_get_vehicle(
        vehicle_id: Annotated[int, Field(gt=0, strict=True)],
    ) -> dict[str, Any]:
        """Get one accessible vehicle by a positive integer ID."""
        return await request("GET", f"/api/v1/vehicles/{vehicle_id}")

    if not settings.allow_writes:
        return

    @server.tool(
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=False,
            open_world_hint=True,
        )
    )
    async def may_create_vehicle(vehicle: VehicleCreate) -> dict[str, Any]:
        """Create an owned vehicle. Omitted optional fields use May defaults. No automatic retry."""
        return await request("POST", "/api/v1/vehicles", vehicle.model_dump(exclude_unset=True))

    @server.tool(
        annotations=ToolAnnotations(
            read_only_hint=False, destructive_hint=True, idempotent_hint=True, open_world_hint=True
        )
    )
    async def may_update_vehicle(
        vehicle_id: Annotated[int, Field(gt=0, strict=True)], changes: VehicleUpdate
    ) -> dict[str, Any]:
        """Update only supplied fields of an owned vehicle. Preserve null, zero, and false.

        Name, vehicle_type, and is_active cannot be null. Shared access alone cannot update.
        No automatic retry; verify state after an uncertain outcome.
        """
        return await request(
            "PATCH", f"/api/v1/vehicles/{vehicle_id}", changes.model_dump(exclude_unset=True)
        )

    @server.tool(
        annotations=ToolAnnotations(
            read_only_hint=False, destructive_hint=True, idempotent_hint=True, open_world_hint=True
        )
    )
    async def may_delete_vehicle(
        vehicle_id: Annotated[int, Field(gt=0, strict=True)],
    ) -> dict[str, Any]:
        """Permanently delete an owned vehicle. May cascades deletion to associated records,
        including fuel logs, expenses, attachments, specifications, trips, charging and parts.
        Shared access alone cannot delete.
        No automatic retry; verify state after an uncertain outcome.
        """
        return await request("DELETE", f"/api/v1/vehicles/{vehicle_id}")
