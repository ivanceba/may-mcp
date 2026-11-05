"""Exact recorded totals, currency separation and bounded page traversal."""

import httpx
import pytest

from may_mcp.client import MayClient
from may_mcp.errors import MayError
from may_mcp.summary import collect_all, summarize_spending


def record(record_id, amount, currency="EUR", day="2026-01-01"):
    return {"id": record_id, "date": day, "total_cost": amount, "currency": currency}


def test_decimal_totals_and_included_tax_are_not_double_counted():
    fuel = [record(1, "0.10"), record(2, "0.20") | {"sales_tax": 0.05}]
    result = summarize_spending(
        fuel, [{"id": 3, "date": "2026-01-01", "cost": "1.005", "currency": "USD"}], []
    )
    assert result["complete"] is True
    assert result["totals"] == [
        {
            "currency": "EUR",
            "fuel": "0.30",
            "expenses": "0.00",
            "charging": "0.00",
            "total": "0.30",
        },
        {
            "currency": "USD",
            "fuel": "0.00",
            "expenses": "1.005",
            "charging": "0.00",
            "total": "1.005",
        },
    ]


def test_inclusive_dates_and_safe_exclusions():
    fuel = [
        record(1, 1, day="2026-01-01"),
        record(2, 2, day="2026-01-02"),
        record(3, 9, day="2026-01-03"),
    ]
    result = summarize_spending(
        fuel,
        [],
        [record(4, None), record(5, 5, None) | {"notes": "private"}],
        "2026-01-01",
        "2026-01-02",
    )
    assert result["totals"][0]["total"] == "3.00"
    assert result["counts"] == {"fuel": 2, "expenses": 0, "charging": 0}
    assert result["complete"] is False
    assert result["excluded"] == [
        {"source": "charging", "id": 4, "reasons": ["missing_total"]},
        {"source": "charging", "id": 5, "reasons": ["unknown_currency"]},
    ]
    assert "private" not in str(result)


def test_widely_different_decimal_scales_remain_exact():
    result = summarize_spending([record(1, "1e308"), record(2, "0.10")], [], [])
    assert result["totals"][0]["total"] == "1" + "0" * 308 + ".10"


@pytest.mark.parametrize("amount", [True, float("nan"), float("inf"), "1e999999", "private text"])
def test_invalid_amount_is_excluded(amount):
    result = summarize_spending([record(1, amount)], [], [])
    assert result["complete"] is False
    assert result["excluded"][0]["reasons"] == ["invalid_total"]


@pytest.mark.parametrize(
    "start,end", [("2026-02-30", None), ("20260101", None), ("2026-02-01", "2026-01-01")]
)
def test_invalid_date_range_fails(start, end):
    with pytest.raises(ValueError):
        summarize_spending([], [], [], start, end)


async def test_collects_multiple_pages_with_no_notes_in_metadata(settings_factory):
    calls = []

    def handler(request):
        offset = int(request.url.params["offset"])
        calls.append(offset)
        rows = [record(i, 1) for i in range(offset + 1, min(offset + 3, 4))]
        return httpx.Response(
            200,
            json={"fuel_logs": rows, "total": 3, "count": len(rows), "limit": 2, "offset": offset},
        )

    client = MayClient(settings_factory(), transport=httpx.MockTransport(handler))
    try:
        result = await collect_all(client, "/api/v1/vehicles/1/fuel", limit=2)
        assert [row["id"] for row in result.records] == [1, 2, 3]
        assert result.complete is True
        assert result.pages == 2
        assert calls == [0, 2]
    finally:
        await client.aclose()


@pytest.mark.parametrize("fault", ["repeat", "missing", "changed_total"])
async def test_corrupt_or_changing_page_is_rejected(settings_factory, fault):
    def handler(request):
        offset = int(request.url.params["offset"])
        rows = (
            [record(1, 1), record(2, 1)]
            if offset == 0
            else [record(1 if fault == "repeat" else 3, 1)]
        )
        if offset and fault == "missing":
            rows = []
        return httpx.Response(
            200,
            json={
                "fuel_logs": rows,
                "total": 2 if offset and fault == "changed_total" else 3,
                "count": len(rows),
                "limit": 2,
                "offset": offset,
            },
        )

    client = MayClient(settings_factory(), transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(MayError) as error:
            await collect_all(client, "/api/v1/vehicles/1/fuel", limit=2)
        assert error.value.code == "invalid_response"
    finally:
        await client.aclose()


async def test_page_budget_reports_incomplete(settings_factory):
    def handler(request):
        return httpx.Response(
            200,
            json={
                "fuel_logs": [record(1, 1), record(2, 1)],
                "total": 3,
                "count": 2,
                "limit": 2,
                "offset": 0,
            },
        )

    client = MayClient(settings_factory(), transport=httpx.MockTransport(handler))
    try:
        result = await collect_all(client, "/api/v1/vehicles/1/fuel", limit=2, max_pages=1)
        assert result.complete is False
        assert result.reason == "page_limit"
        assert len(result.records) == 2
    finally:
        await client.aclose()
