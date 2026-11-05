"""Trip input boundaries and distinction between omitted, null and zero readings."""

import pytest
from pydantic import ValidationError

from may_mcp.models.trips import TripCreate, TripUpdate


@pytest.mark.parametrize(
    "changes",
    [
        {"date": None},
        {"date": "2026-02-29"},
        {"start_odometer": -1},
        {"end_odometer": float("nan")},
        {"end_odometer": "0"},
        {"start_fuel_level": True},
        {"end_fuel_level": float("inf")},
        {"distance": 10},
        {"fuel_used": 2},
        {"user_id": 2},
    ],
)
def test_invalid_or_read_only_fields_fail(changes):
    with pytest.raises(ValidationError):
        TripUpdate.model_validate(changes)


def test_zero_readings_and_absence_are_preserved():
    payload = {"date": "2026-01-01", "start_odometer": 0, "purpose": "personal"}
    assert TripCreate.model_validate(payload).model_dump(exclude_unset=True) == payload
    patch = {
        "end_odometer": None,
        "start_fuel_level": None,
        "end_fuel_level": 0,
        "description": None,
    }
    assert TripUpdate.model_validate(patch).model_dump(exclude_unset=True) == patch
