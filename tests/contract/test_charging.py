"""Charging input units, times and strict numeric boundaries."""

import pytest
from pydantic import ValidationError

from may_mcp.models.charging import ChargingCreate, ChargingUpdate


@pytest.mark.parametrize(
    "changes",
    [
        {"date": None},
        {"date": "2026-02-30"},
        {"start_time": "01:60"},
        {"end_time": "01:00:00Z"},
        {"start_soc": True},
        {"start_soc": "10"},
        {"end_soc": -1},
        {"odometer": -1},
        {"total_cost": float("nan")},
        {"cost_per_kwh": float("inf")},
        {"user_id": 2},
    ],
)
def test_invalid_charging_fields_fail(changes):
    with pytest.raises(ValidationError):
        ChargingUpdate.model_validate(changes)


def test_date_only_create_and_partial_zero_null():
    assert ChargingCreate(date="2026-01-01").model_dump(exclude_unset=True) == {
        "date": "2026-01-01"
    }
    changes = {
        "start_time": "00:00:00",
        "end_time": None,
        "start_soc": 0,
        "end_soc": None,
        "kwh_added": 0,
        "total_cost": 0,
    }
    assert ChargingUpdate.model_validate(changes).model_dump(exclude_unset=True) == changes
