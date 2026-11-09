"""Charging CRUD and charger types through the guarded May client."""

from typing import Annotated, Any, Literal

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from may_mcp.client import MayClient
from may_mcp.config import Settings
from may_mcp.errors import MayError
from may_mcp.models.charging import ChargingCreate, ChargingUpdate
from may_mcp.pagination import add_page_metadata

PositiveId = Annotated[int, Field(gt=0, strict=True)]


def register_charging_tools(server: MCPServer[None], client: MayClient, settings: Settings) -> None:
    async def request(
        method: str, path: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        try:
            return await client.request(method, path, json=payload)
        except MayError as error:
            raise ToolError(f"{error.code}: {error}") from None

    @server.tool(
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=True
        )
    )
    async def may_list_charging_sessions(
        vehicle_id: PositiveId,
        limit: Annotated[int, Field(ge=1, le=500, strict=True)] = 100,
        offset: Annotated[int, Field(ge=0, strict=True)] = 0,
        sort: Literal["asc", "desc"] = "desc",
    ) -> dict[str, Any]:
        """List charging by date then ID. Energy is kWh; SoC is percent.

        Complete means the full matching history; a final nonzero-offset page is incomplete.
        """
        try:
            page = await client.request(
                "GET",
                f"/api/v1/vehicles/{vehicle_id}/charging",
                params={"limit": limit, "offset": offset, "sort": sort},
            )
            return add_page_metadata(page, "charging_sessions", limit=limit, offset=offset)
        except MayError as error:
            raise ToolError(f"{error.code}: {error}") from None

    @server.tool(
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=True
        )
    )
    async def may_get_charging_session(session_id: PositiveId) -> dict[str, Any]:
        """Get one accessible charging record. Energy is kWh; SoC is percent."""
        return await request("GET", f"/api/v1/charging/{session_id}")

    @server.tool(
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=True
        )
    )
    async def may_list_charger_types() -> dict[str, Any]:
        """Discover charger-type IDs and display names from the configured May instance."""
        return await request("GET", "/api/v1/charger-types")

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
    async def may_create_charging_session(
        vehicle_id: PositiveId, session: ChargingCreate
    ) -> dict[str, Any]:
        """Create charging with a date. kwh_added is kWh; SoC is integer percent 0-100.

        May validates charger types and may calculate total_cost if absent/zero. No automatic retry.
        """
        return await request(
            "POST",
            f"/api/v1/vehicles/{vehicle_id}/charging",
            session.model_dump(exclude_unset=True),
        )

    @server.tool(
        annotations=ToolAnnotations(
            read_only_hint=False, destructive_hint=True, idempotent_hint=True, open_world_hint=True
        )
    )
    async def may_update_charging_session(
        session_id: PositiveId, changes: ChargingUpdate
    ) -> dict[str, Any]:
        """Update only supplied fields. Null clears optional fields; zero is retained.

        Energy is kWh; SoC is integer percent. Shared access permits mutation. No automatic retry.
        """
        return await request(
            "PATCH", f"/api/v1/charging/{session_id}", changes.model_dump(exclude_unset=True)
        )

    @server.tool(
        annotations=ToolAnnotations(
            read_only_hint=False, destructive_hint=True, idempotent_hint=True, open_world_hint=True
        )
    )
    async def may_delete_charging_session(session_id: PositiveId) -> dict[str, Any]:
        """Permanently delete an accessible charging session. No automatic retry."""
        return await request("DELETE", f"/api/v1/charging/{session_id}")
