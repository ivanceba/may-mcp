"""Validate May pages before adding full-history coverage hints."""

from typing import Any

from may_mcp.errors import MayError


def add_page_metadata(
    page: dict[str, Any], collection: str, *, limit: int, offset: int
) -> dict[str, Any]:
    rows = page.get(collection)
    total, count = page.get("total"), page.get("count")
    if (
        type(total) is not int
        or type(count) is not int
        or type(page.get("limit")) is not int
        or type(page.get("offset")) is not int
        or type(limit) is not int
        or type(offset) is not int
        or not 1 <= limit <= 500
        or offset < 0
        or page["limit"] != limit
        or page["offset"] != offset
        or total < 0
        or not isinstance(rows, list)
        or any(not isinstance(row, dict) for row in rows)
        or count != len(rows)
        or count != min(limit, max(total - offset, 0))
    ):
        raise MayError("invalid_response", "May returned inconsistent pagination metadata.")
    return page | {"has_more": offset + count < total, "complete": offset == 0 and count == total}
