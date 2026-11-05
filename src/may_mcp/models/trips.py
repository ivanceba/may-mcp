"""Trip fields exposed by May 0.44.2's public REST API."""

import datetime as dt
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DateText = Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}$")]
Reading = Annotated[float, Field(ge=0, allow_inf_nan=False)]
FuelLevel = Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)]
Purpose = Annotated[str, Field(min_length=1, max_length=20)]
ShortText = Annotated[str, Field(max_length=200)]


class TripFields(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    end_odometer: Reading | None = None
    start_fuel_level: FuelLevel | None = None
    end_fuel_level: FuelLevel | None = None
    description: ShortText | None = None
    start_location: ShortText | None = None
    end_location: ShortText | None = None
    notes: str | None = None

    @field_validator("date", "purpose", "start_odometer", mode="before", check_fields=False)
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


class TripCreate(TripFields):
    date: DateText
    start_odometer: Reading
    purpose: Purpose


class TripUpdate(TripFields):
    date: DateText | None = None
    start_odometer: Reading | None = None
    purpose: Purpose | None = None

    @model_validator(mode="after")
    def require_changes(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one change is required.")
        return self
