"""Supported fuel REST inputs, preserving May 0.44.2's odometer distinction."""

import datetime as dt
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Number = Annotated[float, Field(ge=0, allow_inf_nan=False)]
Reading = Annotated[float, Field(ge=0, le=9999999, allow_inf_nan=False)]
DateText = Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}$")]


class FuelFields(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    volume: Number | None = None
    price_per_unit: Number | None = None
    total_cost: Number | None = None
    sales_tax: Number | None = None
    fuel_distance: Number | None = None
    fuel_type: Annotated[str, Field(max_length=20)] | None = None
    station: Annotated[str, Field(max_length=100)] | None = None
    notes: str | None = None
    is_full_tank: bool = True
    is_missed: bool = False

    @field_validator("date", check_fields=False)
    @classmethod
    def validate_date(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("Date cannot be null.")
        dt.date.fromisoformat(value)
        return value


class FuelCreate(FuelFields):
    """May's POST requires a nonzero reading; PATCH can set confirmed zero."""

    date: DateText
    odometer: Annotated[float, Field(gt=0, le=9999999, allow_inf_nan=False)]


class FuelUpdate(FuelFields):
    """Omit fields to keep them. Null odometer means unknown, zero is confirmed."""

    date: DateText | None = None
    odometer: Reading | None = None

    @model_validator(mode="after")
    def require_changes(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one change is required.")
        return self
