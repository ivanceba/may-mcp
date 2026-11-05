"""Fuel CRUD uses only the guarded HTTP client and explicit May REST fields."""

from typing import Annotated, Any, Literal

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from may_mcp.client import MayClient
from may_mcp.config import Settings
from may_mcp.errors import MayError
from may_mcp.models.fuel import FuelCreate, FuelUpdate
from may_mcp.pagination import add_page_metadata

PositiveId = Annotated[int, Field(gt=0, strict=True)]


def register_fuel_tools(server: MCPServer[None], client: MayClient, settings: Settings) -> None:
    reads = ToolAnnotations(
        read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=True
    )
    update = ToolAnnotations(
        read_only_hint=False, destructive_hint=True, idempotent_hint=True, open_world_hint=True
    )

    async def request(
        method: str, path: str, *, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        try:
            return await client.request(method, path, json=payload)
        except MayError as error:
            raise ToolError(f"{error.code}: {error}") from None

    @server.tool(annotations=reads)
    async def may_list_fuel_logs(
        vehicle_id: PositiveId,
        limit: Annotated[int, Field(ge=1, le=500, strict=True)] = 100,
        offset: Annotated[int, Field(ge=0, strict=True)] = 0,
        sort: Literal["asc", "desc"] = "desc",
    ) -> dict[str, Any]:
        """List fuel logs by date then odometer. Complete means the entire matching history.

        A final page with a nonzero offset is incomplete. No consumption is derived from this page.
        """
        try:
            page = await client.request(
                "GET",
                f"/api/v1/vehicles/{vehicle_id}/fuel",
                params={"limit": limit, "offset": offset, "sort": sort},
            )
            return add_page_metadata(page, "fuel_logs", limit=limit, offset=offset)
        except MayError as error:
            raise ToolError(f"{error.code}: {error}") from None

    @server.tool(annotations=reads)
    async def may_get_fuel_log(log_id: PositiveId) -> dict[str, Any]:
        """Get a fuel log, retaining May's odometer_confirmed and consumption fields."""
        return await request("GET", f"/api/v1/fuel/{log_id}")

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
    async def may_create_fuel_log(vehicle_id: PositiveId, fuel: FuelCreate) -> dict[str, Any]:
        """Create a fuel log. May POST requires odometer greater than zero.

        Omitted booleans use May defaults. May normalizes zero optional numeric values to null
        and may calculate total_cost when absent/zero. No automatic retry.
        """
        return await request(
            "POST",
            f"/api/v1/vehicles/{vehicle_id}/fuel",
            payload=fuel.model_dump(exclude_unset=True),
        )

    @server.tool(annotations=update)
    async def may_update_fuel_log(log_id: PositiveId, changes: FuelUpdate) -> dict[str, Any]:
        """Update only supplied fields. Null odometer marks unknown; zero is confirmed.

        May normalizes zero optional numeric values to null; returned fields show saved values.
        May allows updates to accessible shared vehicles. No automatic retry.
        """
        return await request(
            "PATCH", f"/api/v1/fuel/{log_id}", payload=changes.model_dump(exclude_unset=True)
        )

    @server.tool(annotations=update)
    async def may_delete_fuel_log(log_id: PositiveId) -> dict[str, Any]:
        """Permanently delete an accessible fuel log and its attachments. No automatic retry."""
        return await request("DELETE", f"/api/v1/fuel/{log_id}")
