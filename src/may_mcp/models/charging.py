"""Explicit charging REST inputs; energy is in kWh and SoC in percent."""

import datetime as dt
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DateText = Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}$")]
TimeText = Annotated[str, Field(pattern=r"^\d{2}:\d{2}(:\d{2})?$")]
Number = Annotated[float, Field(ge=0, allow_inf_nan=False)]
Percentage = Annotated[int, Field(ge=0, le=100)]


class ChargingFields(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    start_time: TimeText | None = None
    end_time: TimeText | None = None
    odometer: Number | None = None
    kwh_added: Number | None = None
    start_soc: Percentage | None = None
    end_soc: Percentage | None = None
    cost_per_kwh: Number | None = None
    total_cost: Number | None = None
    charger_type: Annotated[str, Field(max_length=20)] | None = None
    location: Annotated[str, Field(max_length=200)] | None = None
    network: Annotated[str, Field(max_length=100)] | None = None
    notes: str | None = None

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_time(cls, value: str | None) -> str | None:
        if value is not None:
            dt.time.fromisoformat(value)
        return value

    @field_validator("date", check_fields=False)
    @classmethod
    def validate_date(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("Date cannot be null.")
        dt.date.fromisoformat(value)
        return value


class ChargingCreate(ChargingFields):
    date: DateText


class ChargingUpdate(ChargingFields):
    date: DateText | None = None

    @model_validator(mode="after")
    def require_changes(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one change is required.")
        return self
