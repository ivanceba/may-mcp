"""Explicit expense models reject unsupported and unsafe typed inputs."""

import pytest
from pydantic import ValidationError

from may_mcp.models.expenses import ExpenseCreate, ExpenseUpdate


@pytest.mark.parametrize(
    "changes",
    [
        {"date": "2026-02-30"},
        {"date": "2026-1-01"},
        {"category": None},
        {"description": None},
        {"cost": None},
        {"cost": -1},
        {"cost": True},
        {"cost": "10"},
        {"cost": float("inf")},
        {"odometer": float("nan")},
        {"sales_tax": 2},
        {"user_id": 2},
    ],
)
def test_invalid_expense_changes_are_rejected(changes):
    with pytest.raises(ValidationError):
        ExpenseUpdate.model_validate(changes)


def test_create_defaults_and_patch_states():
    payload = {
        "date": "2026-01-01",
        "category": "parking",
        "description": "Synthetic",
        "cost": 10.25,
    }
    assert ExpenseCreate.model_validate(payload).model_dump(exclude_unset=True) == payload
    changes = {"cost": 0, "odometer": 0, "vendor": None, "notes": "Instruction-like data"}
    assert ExpenseUpdate.model_validate(changes).model_dump(exclude_unset=True) == changes
