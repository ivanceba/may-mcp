"""Bounded history collection and exact aggregation of verified recorded totals."""

import datetime as dt
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation, localcontext
from typing import Any

from may_mcp.client import MayClient
from may_mcp.errors import MayError
from may_mcp.pagination import add_page_metadata


@dataclass(frozen=True)
class CollectionResult:
    records: list[dict[str, Any]] = field(repr=False)
    total: int
    pages: int
    complete: bool
    reason: str | None = None


async def collect_all(
    client: MayClient, path: str, *, limit: int = 100, max_pages: int = 100
) -> CollectionResult:
    if (
        type(limit) is not int
        or not 1 <= limit <= 500
        or type(max_pages) is not int
        or not 1 <= max_pages <= 100
    ):
        raise ValueError("Invalid collection bounds.")
    key = {"fuel": "fuel_logs", "expenses": "expenses", "charging": "charging_sessions"}.get(
        path.rsplit("/", 1)[-1]
    )
    if key is None:
        raise ValueError("Unsupported spending collection.")
    records: list[dict[str, Any]] = []
    seen: set[int] = set()
    total: int | None = None
    for page_number in range(1, max_pages + 1):
        offset = len(records)
        page = await client.request(
            "GET", path, params={"limit": limit, "offset": offset, "sort": "asc"}
        )
        page = add_page_metadata(page, key, limit=limit, offset=offset)
        if total is not None and total != page["total"]:
            raise MayError("invalid_response", "May history changed during pagination.")
        total = page["total"]
        for row in page[key]:
            record_id = row.get("id")
            if type(record_id) is not int or record_id <= 0 or record_id in seen:
                raise MayError("invalid_response", "May returned missing or repeated record IDs.")
            seen.add(record_id)
            records.append(row)
        if not page["has_more"]:
            return CollectionResult(records, total, page_number, True)
    assert total is not None
    return CollectionResult(records, total, max_pages, False, "page_limit")


def validate_date_range(start_date: str | None, end_date: str | None) -> None:
    for value in (start_date, end_date):
        if value is not None:
            if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                raise ValueError("Dates must use YYYY-MM-DD.")
            try:
                dt.date.fromisoformat(value)
            except ValueError:
                raise ValueError("Dates must be valid calendar dates.") from None
    if start_date and end_date and start_date > end_date:
        raise ValueError("The start date must not follow the end date.")


def _amount(value: Any) -> Decimal:
    if (
        isinstance(value, bool)
        or not isinstance(value, (str, int, float, Decimal))
        or len(str(value)) > 128
    ):
        raise ValueError("Invalid recorded total.")
    try:
        amount = Decimal(str(value))
    except InvalidOperation:
        raise ValueError("Invalid recorded total.") from None
    if not amount.is_finite():
        raise ValueError("Invalid recorded total.")
    if amount == 0:
        return Decimal(0)
    if not -324 <= amount.adjusted() <= 308:
        raise ValueError("Recorded total exceeds the supported numeric range.")
    return amount


def _format(amount: Decimal) -> str:
    text = format(amount, "f")
    if "." not in text:
        return text + ".00"
    return text + "0" * max(0, 2 - len(text.rsplit(".", 1)[1]))


def summarize_spending(
    fuel: list[dict[str, Any]],
    expenses: list[dict[str, Any]],
    charging: list[dict[str, Any]],
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """Caller must supply verified currency per record; absent currency is excluded."""
    validate_date_range(start_date, end_date)
    groups: dict[str, dict[str, Decimal]] = {}
    counts = {"fuel": 0, "expenses": 0, "charging": 0}
    excluded: list[dict[str, Any]] = []
    # Bounded decimal text (128 chars), IEEE float exponents and at most 50k rows
    # per source fit exactly in this precision, including widely different scales.
    with localcontext() as context:
        context.prec = 1024
        for source, records, amount_key in (
            ("fuel", fuel, "total_cost"),
            ("expenses", expenses, "cost"),
            ("charging", charging, "total_cost"),
        ):
            for row in records:
                record_id = row.get("id")
                safe_id = record_id if type(record_id) is int and record_id > 0 else None
                day = row.get("date")
                try:
                    if day is None:
                        raise ValueError("Missing date.")
                    validate_date_range(day, day)
                except ValueError:
                    excluded.append({"source": source, "id": safe_id, "reasons": ["invalid_date"]})
                    continue
                if (start_date and day < start_date) or (end_date and day > end_date):
                    continue
                reasons = []
                if safe_id is None:
                    reasons.append("invalid_id")
                currency = row.get("currency")
                if not isinstance(currency, str) or not re.fullmatch(r"[A-Z]{3}", currency):
                    reasons.append("unknown_currency")
                amount = Decimal(0)
                if row.get(amount_key) is None:
                    reasons.append("missing_total")
                else:
                    try:
                        amount = _amount(row[amount_key])
                    except ValueError:
                        reasons.append("invalid_total")
                if reasons:
                    excluded.append({"source": source, "id": safe_id, "reasons": reasons})
                    continue
                assert isinstance(currency, str)
                group = groups.setdefault(currency, {key: Decimal(0) for key in counts})
                group[source] += amount
                counts[source] += 1
        totals = [
            {
                "currency": currency,
                **{source: _format(value) for source, value in group.items()},
                "total": _format(sum(group.values(), Decimal(0))),
            }
            for currency, group in sorted(groups.items())
        ]
    return {"totals": totals, "counts": counts, "excluded": excluded, "complete": not excluded}
