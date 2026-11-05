"""Read-only spending summaries with explicit currency and coverage limitations."""

import re
from typing import Annotated, Any

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from may_mcp.client import MayClient
from may_mcp.errors import MayError
from may_mcp.summary import collect_all, summarize_spending, validate_date_range


def register_summary_tools(server: MCPServer[None], client: MayClient) -> None:
    @server.tool(
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=True
        )
    )
    async def may_spending_summary(
        vehicle_id: Annotated[int, Field(gt=0, strict=True)],
        start_date: Annotated[str, Field(strict=True)] | None = None,
        end_date: Annotated[str, Field(strict=True)] | None = None,
    ) -> dict[str, Any]:
        """Summarize recorded spending in an inclusive date range, without tax double counting.

        Currency comes from May's owner-only Home Assistant Bearer API, in the configured
        account's monetary context. Unavailable currency excludes records as unknown_currency.
        Bounded pagination reports incomplete coverage. No private notes or derived consumption.
        """
        try:
            validate_date_range(start_date, end_date)
            currency = None
            currency_source = None
            try:
                metadata = await client.request("GET", f"/api/ha/vehicles/{vehicle_id}")
            except MayError as error:
                if error.code != "not_found":
                    raise
            else:
                if type(metadata.get("id")) is not int or metadata["id"] != vehicle_id:
                    raise MayError("invalid_response", "May returned mismatched currency metadata.")
                value = metadata.get("currency")
                if isinstance(value, str) and re.fullmatch(r"[A-Z]{3}", value):
                    currency = value
                    currency_source = f"/api/ha/vehicles/{vehicle_id}"
            collections = {}
            for source, path in (
                ("fuel", "fuel"),
                ("expenses", "expenses"),
                ("charging", "charging"),
            ):
                collections[source] = await collect_all(
                    client, f"/api/v1/vehicles/{vehicle_id}/{path}"
                )
            # Use the supported account context, never undocumented per-record currency extras.
            normalized = {
                source: [row | {"currency": currency} for row in result.records]
                for source, result in collections.items()
            }
            summary = summarize_spending(
                normalized["fuel"],
                normalized["expenses"],
                normalized["charging"],
                start_date,
                end_date,
            )
            summary.update(
                {
                    "vehicle_id": vehicle_id,
                    "start_date": start_date,
                    "end_date": end_date,
                    "currency_status": "verified_account" if currency else "unknown",
                    "currency_source": currency_source,
                    "coverage": {
                        source: {
                            "total": result.total,
                            "count": len(result.records),
                            "pages": result.pages,
                            "complete": result.complete,
                            "reason": result.reason,
                        }
                        for source, result in collections.items()
                    },
                }
            )
            summary["complete"] = summary["complete"] and all(
                result.complete for result in collections.values()
            )
            return summary
        except MayError as error:
            raise ToolError(f"{error.code}: {error}") from None
        except ValueError as error:
            raise ToolError(f"validation_error: {error}") from None
