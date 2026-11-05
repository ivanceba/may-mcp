"""Completeness describes all matching rows, even on the final page."""

import pytest

from may_mcp.errors import MayError
from may_mcp.pagination import add_page_metadata


@pytest.mark.parametrize(
    "total,offset,limit,count,more,complete",
    [
        (3, 0, 2, 2, True, False),
        (3, 2, 2, 1, False, False),
        (3, 0, 500, 3, False, True),
        (0, 0, 100, 0, False, True),
        (0, 2, 100, 0, False, False),
        (3, 9, 100, 0, False, False),
    ],
)
def test_truthful_page_coverage(total, offset, limit, count, more, complete):
    page = {"items": [{}] * count, "count": count, "total": total, "offset": offset, "limit": limit}
    result = add_page_metadata(page, "items", limit=limit, offset=offset)
    assert result["has_more"] is more
    assert result["complete"] is complete
    assert "complete" not in page


@pytest.mark.parametrize(
    "changes",
    [
        {"total": -1},
        {"total": True},
        {"count": "1"},
        {"count": 0},
        {"limit": 501},
        {"limit": 0},
        {"offset": -1},
        {"offset": 2},
        {"items": {}},
        {"items": [1]},
        {"total": 0},
        {},
    ],
)
def test_invalid_upstream_metadata_is_not_reported_complete(changes):
    page = {"items": [{}], "count": 1, "total": 1, "limit": 100, "offset": 0}
    if not changes:
        page.pop("total")
    else:
        page.update(changes)
    with pytest.raises(MayError) as error:
        add_page_metadata(page, "items", limit=100, offset=0)
    assert error.value.code == "invalid_response"
