"""REST-only fields and numeric/date validation at the fuel input boundary."""

import pytest
from pydantic import ValidationError

from may_mcp.models.fuel import FuelCreate, FuelUpdate


@pytest.mark.parametrize(
    "extra",
    [
        {"discount_per_unit": 1},
        {"odometer_confirmed": False},
        {"vehicle_id": 2},
        {"consumption": 5},
    ],
)
def test_read_only_or_web_only_fields_are_not_write_inputs(extra):
    with pytest.raises(ValidationError):
        FuelCreate.model_validate({"date": "2026-01-01", "odometer": 100, **extra})
    with pytest.raises(ValidationError):
        FuelUpdate.model_validate(extra)


@pytest.mark.parametrize(
    "changes",
    [
        {"volume": float("nan")},
        {"sales_tax": float("inf")},
        {"odometer": -1},
        {"date": "2026-2-01"},
        {"is_missed": "false"},
        {"odometer": "0"},
    ],
)
def test_invalid_fuel_values_are_rejected(changes):
    with pytest.raises(ValidationError):
        FuelUpdate.model_validate(changes)


@pytest.mark.parametrize(
    "changes",
    [{"odometer": None}, {"odometer": 0}, {"notes": None}, {"is_full_tank": False, "volume": 0}],
)
def test_distinct_patch_states_remain_distinct(changes):
    assert FuelUpdate.model_validate(changes).model_dump(exclude_unset=True) == changes
