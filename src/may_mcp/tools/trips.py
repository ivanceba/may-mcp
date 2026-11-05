"""Trip CRUD and live purpose discovery through the guarded HTTP boundary."""

from typing import Annotated, Any, Literal

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from may_mcp.client import MayClient
from may_mcp.config import Settings
from may_mcp.errors import MayError
from may_mcp.models.trips import TripCreate, TripUpdate
from may_mcp.pagination import add_page_metadata

PositiveId = Annotated[int, Field(gt=0, strict=True)]


def register_trip_tools(server: MCPServer[None], client: MayClient, settings: Settings) -> None:
    reads = ToolAnnotations(
        read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=True
    )
    writes = ToolAnnotations(
        read_only_hint=False, destructive_hint=True, idempotent_hint=True, open_world_hint=True
    )

    async def request(
        method: str, path: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        try:
            return await client.request(method, path, json=payload)
        except MayError as error:
            raise ToolError(f"{error.code}: {error}") from None

    @server.tool(annotations=reads)
    async def may_list_trips(
        vehicle_id: PositiveId,
        limit: Annotated[int, Field(ge=1, le=500, strict=True)] = 100,
        offset: Annotated[int, Field(ge=0, strict=True)] = 0,
        sort: Literal["asc", "desc"] = "desc",
    ) -> dict[str, Any]:
        """List trips by date then ID. Complete means the entire matching history is returned.

        A final page at a nonzero offset is incomplete. No totals are derived from this page.
        """
        try:
            page = await client.request(
                "GET",
                f"/api/v1/vehicles/{vehicle_id}/trips",
                params={"limit": limit, "offset": offset, "sort": sort},
            )
            return add_page_metadata(page, "trips", limit=limit, offset=offset)
        except MayError as error:
            raise ToolError(f"{error.code}: {error}") from None

    @server.tool(annotations=reads)
    async def may_get_trip(trip_id: PositiveId) -> dict[str, Any]:
        """Read an accessible trip. May's distance/fuel_used fields are preserved as returned."""
        return await request("GET", f"/api/v1/trips/{trip_id}")

    @server.tool(annotations=reads)
    async def may_list_trip_purposes() -> dict[str, Any]:
        """Discover allowed purpose IDs and display names from the configured May instance."""
        return await request("GET", "/api/v1/trip-purposes")

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
    async def may_create_trip(vehicle_id: PositiveId, trip: TripCreate) -> dict[str, Any]:
        """Create a trip with date, start_odometer (zero allowed) and a discovered purpose ID.

        Optional fuel levels are percentages 0-100 or null. No automatic retry.
        """
        return await request(
            "POST", f"/api/v1/vehicles/{vehicle_id}/trips", trip.model_dump(exclude_unset=True)
        )

    @server.tool(annotations=writes)
    async def may_update_trip(trip_id: PositiveId, changes: TripUpdate) -> dict[str, Any]:
        """Update supplied fields only. Null clears optional readings; zero is preserved.

        Date, purpose and start_odometer cannot be null. Shared access permits trip changes.
        No automatic retry; verify saved state after an uncertain outcome.
        """
        return await request(
            "PATCH", f"/api/v1/trips/{trip_id}", changes.model_dump(exclude_unset=True)
        )

    @server.tool(annotations=writes)
    async def may_delete_trip(trip_id: PositiveId) -> dict[str, Any]:
        """Permanently delete an accessible trip. No automatic retry."""
        return await request("DELETE", f"/api/v1/trips/{trip_id}")
