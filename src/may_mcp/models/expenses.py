"""Explicit expense inputs for May 0.44.2's REST API."""

import datetime as dt
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DateText = Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}$")]
Category = Annotated[str, Field(min_length=1, max_length=50)]
Description = Annotated[str, Field(min_length=1, max_length=200)]
Amount = Annotated[float, Field(ge=0, allow_inf_nan=False)]


class ExpenseFields(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    odometer: Amount | None = None
    vendor: Annotated[str, Field(max_length=100)] | None = None
    notes: str | None = None

    @field_validator("date", "category", "description", "cost", mode="before", check_fields=False)
    @classmethod
    def reject_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("This field cannot be null.")
        return value

    @field_validator("date", check_fields=False)
    @classmethod
    def validate_date(cls, value: str) -> str:
        dt.date.fromisoformat(value)
        return value


class ExpenseCreate(ExpenseFields):
    date: DateText
    category: Category
    description: Description
    cost: Annotated[float, Field(gt=0, allow_inf_nan=False)]


class ExpenseUpdate(ExpenseFields):
    date: DateText | None = None
    category: Category | None = None
    description: Description | None = None
    cost: Amount | None = None

    @model_validator(mode="after")
    def require_changes(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one change is required.")
        return self
